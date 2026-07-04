import asyncio
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any
import re
import unicodedata

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.config import Settings
from app.domain.enums import TaskType
from app.domain.models import Essay, EssayFeedbackSubmission, LLMCallLog, new_uuid, utcnow
from app.prompts.registry import get_prompt
from app.services.ai_routing import ModelPricing, PricingStatus, resolve_task_route
from app.services.essay_feedback_persistence import (
    save_direct_draft_feedback_result,
    save_prewriting_first_draft_feedback_result,
)
from app.services.essay_feedback_submission import (
    IdempotencyPayloadMismatch,
    create_or_get_submission,
    finalize_submission_with_reservation,
    mark_submission_status,
)
from app.services.llm_contracts import EssayFeedback
from app.services.llm_provider import LLMProvider, LLMProviderStreamEvent
from app.services.llm_usage import reserve_daily_task_limit_slot
from app.services.llm_usage_accounting import (
    UsageCostRecord,
    normalize_usage_and_cost,
)
from app.services.streaming_events import (
    StreamEventBuilder,
    WenLingoStreamFrame,
    format_sse_event,
)


SECTION_ORDER = [
    "strengths",
    "improvements",
    "problem_monsters",
    "sentence_notes",
    "revision_tasks",
]
SECTION_PATTERN = re.compile(
    r"<(?P<name>strengths|improvements|problem_monsters|sentence_notes|revision_tasks)>"
    r"(?P<body>.*?)"
    r"</(?P=name)>",
    re.DOTALL,
)
OPENING_TAG_PATTERN = re.compile(
    r"^<(?P<name>strengths|improvements|problem_monsters|sentence_notes|revision_tasks)>"
)
SECTION_ITEM_LIMITS: dict[str, tuple[int, int]] = {
    "strengths": (2, 2),
    "improvements": (1, 3),
    "problem_monsters": (1, 3),
    "sentence_notes": (1, 3),
    "revision_tasks": (1, 1),
}
PREVIEW_SECTIONS = {"strengths", "improvements", "sentence_notes", "revision_tasks"}
ANTI_GHOSTWRITING_MARKERS = (
    "范文",
    "可以这样写：",
    "可以这样写:",
    "作文如下",
    "完整作文",
)
ACTIVE_STREAMING_STATUSES = {
    "streaming_started",
    "first_visible_content_sent",
    "backend_continuing_after_disconnect",
}
TERMINAL_FAILURE_STATUSES = {"failed_released", "expired_released"}


@dataclass(frozen=True)
class FeedbackSectionPreview:
    section: str
    items: list[str]


class StreamSectionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class StreamTimeoutError(Exception):
    def __init__(self, code: str, status: str, message: str):
        super().__init__(message)
        self.code = code
        self.status = status


class StreamingAlreadyInProgress(Exception):
    def __init__(self, submission_id: str, fetch_url: str = ""):
        super().__init__("essay feedback submission is already in progress")
        self.submission_id = submission_id
        self.fetch_url = fetch_url


class StreamingSubmissionCompleted(Exception):
    def __init__(self, submission_id: str, fetch_url: str):
        super().__init__("essay feedback submission already completed")
        self.submission_id = submission_id
        self.fetch_url = fetch_url


@dataclass(frozen=True)
class StreamingSaveContext:
    route_scope: str
    student_id: str
    title: str
    draft: str
    essay_id: str | None = None


SessionFactory = Callable[[], Session]


class EssayFeedbackSectionParser:
    def __init__(self, *, max_buffer_bytes: int = 12000, max_item_chars: int = 160):
        self.buffer = ""
        self.next_index = 0
        self.seen: set[str] = set()
        self.sections: dict[str, list[str]] = {}
        self.max_buffer_bytes = max_buffer_bytes
        self.max_item_chars = max_item_chars

    def feed(self, text_delta: str) -> list[FeedbackSectionPreview]:
        self.buffer += text_delta
        if len(self.buffer.encode("utf-8")) > self.max_buffer_bytes:
            raise StreamSectionError("STREAM_SECTION_TOO_LARGE", "section buffer exceeded limit")
        if "```" in self.buffer:
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", "markdown code fence")

        emitted: list[FeedbackSectionPreview] = []
        while True:
            stripped = self.buffer.lstrip()
            if not stripped:
                self.buffer = ""
                return emitted
            if self.next_index >= len(SECTION_ORDER):
                if stripped:
                    raise StreamSectionError("STREAM_SECTION_OUT_OF_ORDER", "content after final section")
                return emitted

            expected = SECTION_ORDER[self.next_index]
            opening_match = OPENING_TAG_PATTERN.match(stripped)
            if opening_match is not None:
                opened_name = opening_match.group("name")
                if opened_name in self.seen:
                    raise StreamSectionError("STREAM_SECTION_DUPLICATE", opened_name)
                if opened_name != expected:
                    raise StreamSectionError("STREAM_SECTION_OUT_OF_ORDER", opened_name)
            else:
                expected_open = f"<{expected}>"
                if expected_open.startswith(stripped):
                    return emitted
                raise StreamSectionError("STREAM_SECTION_OUT_OF_ORDER", stripped[:40])

            match = SECTION_PATTERN.match(stripped)
            if match is None:
                return emitted

            name = match.group("name")
            body = match.group("body")
            if any(f"<{section}>" in body or f"</{section}>" in body for section in SECTION_ORDER):
                raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", "nested section")

            items = _parse_section_items(name, body, self.max_item_chars)
            self.seen.add(name)
            self.sections[name] = list(items)
            self.next_index += 1
            if name in PREVIEW_SECTIONS:
                emitted.append(FeedbackSectionPreview(section=name, items=list(items)))
            self.buffer = stripped[match.end():]

    def build_feedback(self) -> EssayFeedback:
        return build_validated_feedback_from_sections(self.sections)


def _parse_section_items(section: str, body: str, max_item_chars: int) -> list[str]:
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("- "):
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
        item = stripped[2:].strip()
        if not item:
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
        items.append(item)

    min_items, max_items = SECTION_ITEM_LIMITS[section]
    if len(items) < min_items or len(items) > max_items:
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
    if any(_display_length(item) > max_item_chars for item in items):
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
    if any(_looks_copy_ready(item) for item in items):
        raise StreamSectionError("STREAM_ANTI_GHOSTWRITING_BLOCKED", section)

    if section == "revision_tasks":
        for item in items:
            parts = item.split(" | ", 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise StreamSectionError(
                    "STREAM_FINAL_SCHEMA_INVALID",
                    f"revision_task must be 'instruction | target', got: {item[:60]}",
                )
    return items


def _display_length(text: str) -> int:
    total = 0
    for char in text:
        total += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return total


def _looks_copy_ready(item: str) -> bool:
    return any(marker in item for marker in ANTI_GHOSTWRITING_MARKERS)


def build_validated_feedback_from_sections(
    sections: Mapping[str, Sequence[str]] | Sequence[FeedbackSectionPreview],
) -> EssayFeedback:
    if isinstance(sections, Mapping):
        section_map = {name: list(items) for name, items in sections.items()}
    else:
        section_map = {section.section: list(section.items) for section in sections}

    missing = [section for section in SECTION_ORDER if section not in section_map]
    if missing:
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", f"missing sections: {missing}")

    revision_tasks = []
    for item in section_map["revision_tasks"]:
        parts = item.split(" | ", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", "invalid revision task")
        revision_tasks.append({"instruction": parts[0].strip(), "target": parts[1].strip()})

    try:
        return EssayFeedback(
            strengths=section_map["strengths"],
            improvements=section_map["improvements"],
            problem_monsters=section_map["problem_monsters"],
            sentence_notes=section_map["sentence_notes"],
            revision_tasks=revision_tasks,
        )
    except ValidationError as exc:
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", str(exc)) from exc


class StreamingBackendTask:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        payload: dict[str, Any],
        submission_id: str,
        save_context: StreamingSaveContext | None = None,
        session_factory: SessionFactory | None = None,
        pricing: ModelPricing | None = None,
        pricing_status: str = PricingStatus.UNAVAILABLE,
        prompt_version: str = "",
        heartbeat_seconds: int = 12,
        first_provider_event_delay_seconds: float = 0,
        first_event_timeout_seconds: float = 8,
        section_timeout_seconds: float = 20,
        backend_continuation_timeout_seconds: float = 60,
    ):
        self.provider = provider
        self.payload = payload
        self.submission_id = submission_id
        self.save_context = save_context
        self.session_factory = session_factory
        self.pricing = pricing
        self.pricing_status = pricing_status
        self.prompt_version = prompt_version or get_prompt("essay_feedback").version
        self.heartbeat_seconds = heartbeat_seconds
        self.first_provider_event_delay_seconds = first_provider_event_delay_seconds
        self.first_event_timeout_seconds = first_event_timeout_seconds
        self.section_timeout_seconds = section_timeout_seconds
        self.backend_continuation_timeout_seconds = backend_continuation_timeout_seconds
        self.parser = EssayFeedbackSectionParser()
        self.event_builder = StreamEventBuilder(
            stream_id=f"stream_{new_uuid()}",
            submission_id=submission_id,
        )
        self.queue: asyncio.Queue[WenLingoStreamFrame | None] = asyncio.Queue()
        self.started_at = utcnow()
        self.request_started_at = self.started_at
        self.first_provider_delta_at = None
        self.first_visible_content_at = None
        self.last_content_at = None
        self.usage_received_at = None
        self.provider_stream_completed_at = None
        self.client_disconnected_at = None
        self.stream_final_status = ""
        self.error_code = ""
        self.error_message = ""
        self.official_result_saved = False
        self.reservation_final_action = ""
        self.usage_record: UsageCostRecord | None = None
        self.provider_request_id: str | None = None
        self.provider_generation_id: str | None = None
        self.output: EssayFeedback | None = None
        self.llm_log_id: str | None = None
        self.essay_version_id: str | None = None
        self.result_fetch_url = ""
        self._task_handle: asyncio.Task[None] | None = None
        self._terminal = asyncio.Event()
        self._disconnect_event = asyncio.Event()

    @classmethod
    def for_test(
        cls,
        *,
        provider: LLMProvider,
        first_provider_event_delay_seconds: float = 0,
        heartbeat_seconds: int = 12,
        first_event_timeout_seconds: float = 8,
        section_timeout_seconds: float = 20,
        backend_continuation_timeout_seconds: float = 60,
    ) -> "StreamingBackendTask":
        return cls(
            provider=provider,
            payload={"title": "测试", "draft": "测试作文内容。"},
            submission_id=f"test-submission-{new_uuid()}",
            heartbeat_seconds=heartbeat_seconds,
            first_provider_event_delay_seconds=first_provider_event_delay_seconds,
            first_event_timeout_seconds=first_event_timeout_seconds,
            section_timeout_seconds=section_timeout_seconds,
            backend_continuation_timeout_seconds=backend_continuation_timeout_seconds,
        )

    @property
    def usage_available(self) -> bool:
        return bool(self.usage_record and self.usage_record.usage_available)

    @property
    def usage_source(self) -> str:
        if self.usage_record is None:
            return "unavailable"
        return self.usage_record.usage_source

    def ensure_started(self) -> asyncio.Task[None]:
        if self._task_handle is None:
            self._task_handle = asyncio.create_task(self.run_to_terminal())
        return self._task_handle

    async def wait_for_terminal_for_test(self) -> None:
        self.ensure_started()
        await self._terminal.wait()
        if self._task_handle is not None and self._task_handle.done():
            await self._task_handle

    async def run_to_terminal(self) -> None:
        start_perf = perf_counter()
        seen_provider_event = False
        try:
            self._mark_submission_status("streaming_started")
            await self.queue.put(
                self.event_builder.frame(
                    "start",
                    {
                        "phase": "reserved",
                        "task_name": "essay_feedback",
                        "stream_protocol": "sse",
                    },
                )
            )
            provider_iterator = self._provider_events().__aiter__()
            while True:
                try:
                    provider_event = await self._next_provider_event(
                        provider_iterator,
                        seen_provider_event=seen_provider_event,
                    )
                except StopAsyncIteration:
                    break
                seen_provider_event = True
                self._capture_provider_ids(provider_event)
                if provider_event.event_type == "text_delta":
                    await self.handle_text_delta(provider_event.text_delta)
                elif provider_event.event_type == "usage_final":
                    self.usage_received_at = utcnow()
                    self.usage_record = normalize_usage_and_cost(
                        provider=getattr(self.provider, "provider_name", "unknown"),
                        model=getattr(self.provider, "model_name", "unknown"),
                        role="primary",
                        provider_usage=provider_event.usage,
                        usage_source=(
                            "provider_final_chunk" if provider_event.usage else "unavailable"
                        ),
                        tokenizer_estimate=None,
                        provider_reported_cost_usd=provider_event.provider_reported_cost_usd,
                        pricing=self.pricing,
                    )
                elif provider_event.event_type == "provider_error":
                    await self.fail_stream(
                        provider_event.error_code or "PROVIDER_ERROR",
                        provider_event.error_message,
                    )
                    return
                elif provider_event.event_type == "provider_done":
                    break
            self.provider_stream_completed_at = utcnow()
            await self.validate_save_and_emit_done(latency_ms=int((perf_counter() - start_perf) * 1000))
        except asyncio.CancelledError:
            await self._handle_cancelled()
        except StreamSectionError as exc:
            await self._finalize_failure(
                status=(
                    "provider_failed_after_visible_content"
                    if self.first_visible_content_at
                    else "provider_failed_before_visible_content"
                ),
                error_code=exc.code,
                error_message=str(exc),
            )
        except StreamTimeoutError as exc:
            await self._finalize_failure(
                status=exc.status,
                error_code=exc.code,
                error_message=str(exc),
            )
        except Exception as exc:
            await self._finalize_failure(
                status=(
                    "provider_failed_after_visible_content"
                    if self.first_visible_content_at
                    else "provider_failed_before_visible_content"
                ),
                error_code=exc.__class__.__name__,
                error_message=str(exc),
            )
        finally:
            self._terminal.set()
            await self.queue.put(None)

    async def _provider_events(self) -> AsyncIterator[LLMProviderStreamEvent]:
        if self.first_provider_event_delay_seconds > 0:
            await asyncio.sleep(self.first_provider_event_delay_seconds)
        async for provider_event in self.provider.stream_text("essay_feedback", self.payload):
            yield provider_event

    async def _next_provider_event(
        self,
        provider_iterator: AsyncIterator[LLMProviderStreamEvent],
        *,
        seen_provider_event: bool,
    ) -> LLMProviderStreamEvent:
        provider_task = asyncio.create_task(provider_iterator.__anext__())
        while True:
            timeout = self._provider_wait_timeout(seen_provider_event=seen_provider_event)
            wait_tasks: set[asyncio.Task] = {provider_task}
            disconnect_task: asyncio.Task | None = None
            if self.client_disconnected_at is None and self.first_visible_content_at is not None:
                disconnect_task = asyncio.create_task(self._disconnect_event.wait())
                wait_tasks.add(disconnect_task)
            done, _pending = await asyncio.wait(
                wait_tasks,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if provider_task in done:
                if disconnect_task is not None and not disconnect_task.done():
                    disconnect_task.cancel()
                return provider_task.result()
            if disconnect_task is not None and disconnect_task in done:
                continue
            if disconnect_task is not None and not disconnect_task.done():
                disconnect_task.cancel()
            provider_task.cancel()
            raise self._timeout_error(seen_provider_event=seen_provider_event)

    def _provider_wait_timeout(self, *, seen_provider_event: bool) -> float | None:
        timeouts: list[float] = []
        if not seen_provider_event and self.first_event_timeout_seconds > 0:
            timeouts.append(self.first_event_timeout_seconds)
        elif self.first_provider_delta_at is not None and self.section_timeout_seconds > 0:
            timeouts.append(self.section_timeout_seconds)
        continuation_remaining = self._backend_continuation_remaining_seconds()
        if continuation_remaining is not None:
            timeouts.append(continuation_remaining)
        return min(timeouts) if timeouts else None

    def _backend_continuation_remaining_seconds(self) -> float | None:
        if (
            self.client_disconnected_at is None
            or self.first_visible_content_at is None
            or self.backend_continuation_timeout_seconds <= 0
        ):
            return None
        elapsed = (utcnow() - self.client_disconnected_at).total_seconds()
        return max(self.backend_continuation_timeout_seconds - elapsed, 0.001)

    def _timeout_error(self, *, seen_provider_event: bool) -> StreamTimeoutError:
        continuation_remaining = self._backend_continuation_remaining_seconds()
        if (
            self.client_disconnected_at is not None
            and self.first_visible_content_at is not None
            and continuation_remaining is not None
            and continuation_remaining <= 0.01
        ):
            return StreamTimeoutError(
                "STREAM_BACKEND_CONTINUATION_TIMEOUT",
                "client_disconnected_after_visible_content_aborted",
                "backend continuation exceeded timeout after client disconnect",
            )
        if not seen_provider_event:
            return StreamTimeoutError(
                "STREAM_FIRST_EVENT_TIMEOUT",
                "provider_failed_before_visible_content",
                "provider did not emit a first event before timeout",
            )
        return StreamTimeoutError(
            "STREAM_SECTION_TIMEOUT",
            (
                "provider_failed_after_visible_content"
                if self.first_provider_delta_at is not None
                else "provider_failed_before_visible_content"
            ),
            "provider stream stalled before the next section completed",
        )

    async def handle_text_delta(self, text_delta: str) -> None:
        if not text_delta:
            return
        now = utcnow()
        if self.first_provider_delta_at is None:
            self.first_provider_delta_at = now
        self.last_content_at = now
        previews = self.parser.feed(text_delta)
        for preview in previews:
            if self.first_visible_content_at is None:
                self.first_visible_content_at = utcnow()
                self._mark_submission_status("first_visible_content_sent")
            await self.queue.put(
                self.event_builder.frame(
                    "feedback_section_preview",
                    {"section": preview.section, "items": preview.items},
                )
            )

    async def next_event_or_heartbeat(self) -> WenLingoStreamFrame:
        try:
            frame = await asyncio.wait_for(
                self.queue.get(),
                timeout=max(self.heartbeat_seconds, 1),
            )
        except asyncio.TimeoutError:
            return self.event_builder.frame("heartbeat", {"phase": "waiting"})
        if frame is None:
            return self.event_builder.frame(
                "error" if self.error_code else "done",
                {
                    "stream_final_status": self.stream_final_status,
                    "essay_id": self.save_context.essay_id if self.save_context else "",
                    "first_draft_version_id": self.essay_version_id or "",
                    "fetch_url": self.result_fetch_url,
                    "error_code": self.error_code,
                },
            )
        return frame

    async def fail_stream(self, error_code: str, error_message: str = "") -> None:
        await self._finalize_failure(
            status=(
                "provider_failed_after_visible_content"
                if self.first_visible_content_at
                else "provider_failed_before_visible_content"
            ),
            error_code=error_code,
            error_message=error_message,
        )

    async def validate_save_and_emit_done(self, *, latency_ms: int = 0) -> None:
        try:
            feedback = self.parser.build_feedback()
        except StreamSectionError as exc:
            await self._finalize_failure(
                status=(
                    "provider_failed_after_visible_content"
                    if self.first_visible_content_at is not None
                    or self.first_provider_delta_at is not None
                    else "provider_failed_before_visible_content"
                ),
                error_code=exc.code,
                error_message=str(exc),
            )
            return

        self.output = feedback
        stream_status = "completed"
        if self.client_disconnected_at and self.first_visible_content_at:
            stream_status = "client_disconnected_after_visible_content_completed"
        self.stream_final_status = stream_status
        if self.usage_record is None:
            self.usage_record = normalize_usage_and_cost(
                provider=getattr(self.provider, "provider_name", "unknown"),
                model=getattr(self.provider, "model_name", "unknown"),
                role="primary",
                provider_usage=None,
                usage_source="unavailable",
                tokenizer_estimate=None,
                provider_reported_cost_usd=None,
                pricing=self.pricing,
            )

        if self.session_factory and self.save_context:
            with self.session_factory() as session:
                log = self._create_llm_log(session, feedback=feedback, latency_ms=latency_ms)
                save_result = self._save_feedback_result(session, feedback=feedback, llm_log=log)
                first_draft = save_result.get("first_draft", {})
                essay = save_result.get("essay", {})
                self.llm_log_id = log.id
                self.essay_version_id = str(first_draft.get("id") or "")
                essay_id = str(essay.get("id") or self.save_context.essay_id or "")
                self.result_fetch_url = f"/api/essays/{essay_id}"
                finalize_submission_with_reservation(
                    session=session,
                    submission_id=self.submission_id,
                    terminal_status="completed",
                    saved_result=True,
                    essay_version_id=self.essay_version_id,
                    result_fetch_url=self.result_fetch_url,
                    llm_call_log_id=log.id,
                )
                session.commit()
        self.official_result_saved = True
        self.reservation_final_action = "consumed"
        await self.queue.put(
            self.event_builder.frame(
                "done",
                {
                    "stream_final_status": self.stream_final_status,
                    "essay_id": self.save_context.essay_id if self.save_context else "",
                    "first_draft_version_id": self.essay_version_id or "",
                    "fetch_url": self.result_fetch_url,
                },
            )
        )

    def mark_client_disconnected(self) -> None:
        self.client_disconnected_at = utcnow()
        self._disconnect_event.set()
        if self.first_visible_content_at is not None:
            self._mark_submission_status("backend_continuing_after_disconnect")

    async def _handle_cancelled(self) -> None:
        if self.first_visible_content_at is None:
            await self._finalize_failure(
                status="client_disconnected_before_visible_content",
                error_code="CLIENT_DISCONNECTED",
                error_message="client disconnected before visible content",
            )
        else:
            self.stream_final_status = "client_disconnected_after_visible_content_aborted"
            self.reservation_final_action = "released"
            raise

    async def _finalize_failure(
        self,
        *,
        status: str,
        error_code: str,
        error_message: str = "",
    ) -> None:
        self.stream_final_status = status
        self.error_code = error_code
        self.error_message = error_message
        self.official_result_saved = False
        self.reservation_final_action = "released"
        if self.session_factory:
            with self.session_factory() as session:
                log = self._create_llm_log(session, feedback=None, latency_ms=0)
                self.llm_log_id = log.id
                finalize_submission_with_reservation(
                    session=session,
                    submission_id=self.submission_id,
                    terminal_status="failed_released",
                    saved_result=False,
                    essay_version_id=None,
                    result_fetch_url="",
                    llm_call_log_id=log.id,
                    error_code=error_code,
                    error_message=error_message,
                )
                session.commit()
        await self.queue.put(
            self.event_builder.frame(
                "error",
                {
                    "stream_final_status": status,
                    "error_code": error_code,
                    "message": error_message,
                },
            )
        )

    def _mark_submission_status(self, status: str) -> None:
        if not self.session_factory:
            return
        with self.session_factory() as session:
            mark_submission_status(
                session=session,
                submission_id=self.submission_id,
                status=status,
                llm_call_log_id=self.llm_log_id,
            )
            session.commit()

    def _capture_provider_ids(self, event: LLMProviderStreamEvent) -> None:
        if event.provider_request_id:
            self.provider_request_id = event.provider_request_id
        if event.provider_generation_id:
            self.provider_generation_id = event.provider_generation_id

    def _create_llm_log(
        self,
        session: Session,
        *,
        feedback: EssayFeedback | None,
        latency_ms: int,
    ) -> LLMCallLog:
        usage = self.usage_record or normalize_usage_and_cost(
            provider=getattr(self.provider, "provider_name", "unknown"),
            model=getattr(self.provider, "model_name", "unknown"),
            role="primary",
            provider_usage=None,
            usage_source="unavailable",
            tokenizer_estimate=None,
            provider_reported_cost_usd=None,
            pricing=self.pricing,
        )
        final_status = "primary_success" if feedback is not None else "failed"
        log = LLMCallLog(
            student_id=self.save_context.student_id if self.save_context else None,
            task_type=TaskType.essay,
            task_name="essay_feedback",
            prompt_key="essay_feedback",
            provider=getattr(self.provider, "provider_name", "unknown"),
            model=getattr(self.provider, "model_name", "unknown"),
            resolved_provider=getattr(self.provider, "provider_name", "unknown"),
            resolved_model=getattr(self.provider, "model_name", "unknown"),
            primary_provider=getattr(self.provider, "provider_name", "unknown"),
            primary_model=getattr(self.provider, "model_name", "unknown"),
            attempt_count=1,
            final_status=final_status,
            pricing_status=self.pricing_status,
            prompt_version=self.prompt_version,
            input_summary=(
                f"作文题目：{self.save_context.title}；初稿长度：{len(self.save_context.draft)}"
                if self.save_context
                else "streaming test"
            ),
            raw_response=self.parser.buffer,
            output_json=feedback.model_dump() if feedback is not None else {},
            validation_ok=feedback is not None,
            error_message=self.error_message,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost=usage.estimated_cost_usd,
            latency_ms=latency_ms,
            duration_ms=latency_ms,
            request_started_at=self.request_started_at,
            response_received_at=self.provider_stream_completed_at or utcnow(),
            streaming_enabled=True,
            stream_protocol="sse",
            stream_started_at=self.started_at,
            first_provider_delta_at=self.first_provider_delta_at,
            first_visible_content_at=self.first_visible_content_at,
            last_content_at=self.last_content_at,
            usage_received_at=self.usage_received_at,
            client_disconnected_at=self.client_disconnected_at,
            provider_stream_completed_at=self.provider_stream_completed_at,
            usage_available=usage.usage_available,
            usage_source=usage.usage_source,
            usage_is_estimated=usage.usage_is_estimated,
            usage_details_json=usage.usage_details_json,
            stream_final_status=self.stream_final_status,
            cost_source=usage.cost_source,
            cost_error_code=usage.cost_error_code,
            pricing_snapshot_id=usage.pricing_snapshot_id,
            pricing_snapshot_version=usage.pricing_snapshot_version,
            provider_reported_cost_usd=usage.provider_reported_cost_usd,
            cost_calculation_version=usage.cost_calculation_version,
            provider_request_id=self.provider_request_id,
            provider_generation_id=self.provider_generation_id,
        )
        session.add(log)
        session.flush()
        return log

    def _save_feedback_result(
        self,
        session: Session,
        *,
        feedback: EssayFeedback,
        llm_log: LLMCallLog,
    ) -> dict[str, Any]:
        if self.save_context is None:
            return {}
        if self.save_context.route_scope == "prewriting_first_draft":
            essay = session.get(Essay, self.save_context.essay_id)
            if essay is None:
                raise ValueError("essay not found")
            result = save_prewriting_first_draft_feedback_result(
                session=session,
                essay=essay,
                draft=self.save_context.draft,
                feedback=feedback,
                llm_log=llm_log,
            )
            self.save_context = StreamingSaveContext(
                route_scope=self.save_context.route_scope,
                student_id=self.save_context.student_id,
                title=self.save_context.title,
                draft=self.save_context.draft,
                essay_id=essay.id,
            )
            return result
        result = save_direct_draft_feedback_result(
            session=session,
            student_id=self.save_context.student_id,
            title=self.save_context.title,
            draft=self.save_context.draft,
            feedback=feedback,
            llm_log=llm_log,
        )
        essay_payload = result.get("essay", {})
        self.save_context = StreamingSaveContext(
            route_scope=self.save_context.route_scope,
            student_id=self.save_context.student_id,
            title=self.save_context.title,
            draft=self.save_context.draft,
            essay_id=str(essay_payload.get("id") or ""),
        )
        return result


class SseMirror:
    def __init__(self, *, backend_task: StreamingBackendTask):
        self.backend_task = backend_task
        self.backend_task_handle: asyncio.Task[None] | None = None

    async def frames(self) -> AsyncIterator[str]:
        self.backend_task_handle = self.backend_task.ensure_started()
        shielded = asyncio.shield(self.backend_task_handle)
        try:
            while True:
                frame = await self.backend_task.next_event_or_heartbeat()
                yield format_sse_event(frame.event_name, frame.data)
                if frame.event_name in {"done", "error"}:
                    await shielded
                    return
        except asyncio.CancelledError:
            self.backend_task.mark_client_disconnected()
            if self.backend_task.first_visible_content_at is None:
                self.backend_task_handle.cancel()
            raise

    async def next_frame_for_test(self) -> WenLingoStreamFrame:
        self.backend_task_handle = self.backend_task.ensure_started()
        while True:
            frame = await self.backend_task.next_event_or_heartbeat()
            if frame.event_name != "start":
                return frame

    async def disconnect_for_test(self, after_frame: WenLingoStreamFrame | None) -> None:
        self.backend_task.ensure_started()
        self.backend_task.mark_client_disconnected()
        await asyncio.sleep(0)


def session_factory_from_request_session(
    request_session: Session,
    fallback: SessionFactory,
) -> SessionFactory:
    bind = request_session.get_bind()
    if isinstance(bind, Engine):
        return lambda: Session(bind)
    return fallback


def active_submission_json_response(submission) -> dict[str, Any] | None:
    if submission.status in ACTIVE_STREAMING_STATUSES:
        return {
            "status": "IN_PROGRESS",
            "submission_id": submission.id,
            "fetch_url": submission.result_fetch_url,
        }
    if submission.status == "completed":
        return {
            "status": "COMPLETED",
            "submission_id": submission.id,
            "fetch_url": submission.result_fetch_url,
        }
    if submission.status in TERMINAL_FAILURE_STATUSES:
        raise ValueError("previous submission failed; retry with a new client_submission_id")
    return None


async def _single_done_stream(
    *,
    submission_id: str,
    fetch_url: str,
) -> AsyncIterator[str]:
    builder = StreamEventBuilder(stream_id=f"stream_{new_uuid()}", submission_id=submission_id)
    start = builder.frame(
        "start",
        {"phase": "completed", "task_name": "essay_feedback", "stream_protocol": "sse"},
    )
    done = builder.frame(
        "done",
        {
            "stream_final_status": "completed",
            "essay_id": "",
            "first_draft_version_id": "",
            "fetch_url": fetch_url,
        },
    )
    yield format_sse_event(start.event_name, start.data)
    yield format_sse_event(done.event_name, done.data)


async def _single_in_progress_stream(
    *,
    submission_id: str,
    fetch_url: str,
) -> AsyncIterator[str]:
    builder = StreamEventBuilder(stream_id=f"stream_{new_uuid()}", submission_id=submission_id)
    start = builder.frame(
        "start",
        {"phase": "in_progress", "task_name": "essay_feedback", "stream_protocol": "sse"},
    )
    status = builder.frame(
        "error",
        {
            "status": "IN_PROGRESS",
            "stream_final_status": "streaming_in_progress",
            "error_code": "STREAM_ALREADY_IN_PROGRESS",
            "fetch_url": fetch_url,
        },
    )
    yield format_sse_event(start.event_name, start.data)
    yield format_sse_event(status.event_name, status.data)


def _payload_dict(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return dict(payload)


def _require_client_submission_id(client_submission_id: str) -> str:
    stripped = (client_submission_id or "").strip()
    if not stripped:
        raise HTTPException(
            status_code=422,
            detail="client_submission_id is required for streaming feedback",
        )
    return stripped


def _stream_payload(title: str, draft: str) -> dict[str, Any]:
    return {
        "title": {"kind": "student_text", "text": title},
        "draft": {"kind": "student_text", "text": draft},
    }


def _reserve_submission_limit(
    *,
    session: Session,
    settings: Settings,
    student_id: str,
    submission_id: str,
    route_daily_limit: int,
) -> None:
    if not settings.llm_daily_limit_enabled:
        return
    reservation = reserve_daily_task_limit_slot(
        session=session,
        student_id=student_id,
        task_name="essay_feedback",
        limit=route_daily_limit,
        timezone_name=settings.llm_daily_limit_timezone,
    )
    if not reservation.reserved:
        raise ValueError("daily limit reached")
    row = session.get(EssayFeedbackSubmission, submission_id)
    if row is None:
        raise ValueError("essay feedback submission not found")
    row.daily_limit_counter_id = reservation.counter_id
    row.daily_limit_reservation_token = reservation.reservation_token
    session.add(row)
    session.flush()


def _build_backend_task(
    *,
    request_session: Session,
    session_factory: SessionFactory,
    settings: Settings,
    provider: LLMProvider,
    submission_id: str,
    payload: dict[str, Any],
    save_context: StreamingSaveContext,
) -> StreamingBackendTask:
    route = resolve_task_route(settings, "essay_feedback", "essay_feedback")
    return StreamingBackendTask(
        provider=provider,
        payload=payload,
        submission_id=submission_id,
        save_context=save_context,
        session_factory=session_factory_from_request_session(request_session, session_factory),
        pricing=route.primary_pricing,
        pricing_status=route.pricing_status,
        prompt_version=settings.llm_prompt_version,
        heartbeat_seconds=settings.streaming_heartbeat_seconds,
        first_event_timeout_seconds=settings.streaming_first_event_timeout_seconds,
        section_timeout_seconds=settings.streaming_section_timeout_seconds,
        backend_continuation_timeout_seconds=(
            settings.streaming_backend_continuation_timeout_seconds
        ),
    )


def _provider_for_stream(settings: Settings):
    from app.api.deps import provider_for_profile

    route = resolve_task_route(settings, "essay_feedback", "essay_feedback")
    return provider_for_profile(
        settings=settings,
        profile=route.primary_profile,
        logical_model=route.primary_model,
        timeout_seconds=route.task.primary_timeout_seconds,
    )


def _prepare_streaming_submission(
    *,
    session: Session,
    settings: Settings,
    student_id: str,
    essay_id: str | None,
    route_scope: str,
    client_submission_id: str,
    payload: dict[str, Any],
) -> EssayFeedbackSubmission:
    try:
        submission = create_or_get_submission(
            session=session,
            student_id=student_id,
            essay_id=essay_id,
            task_name="essay_feedback",
            route_scope=route_scope,
            client_submission_id=client_submission_id,
            payload=payload,
        )
    except IdempotencyPayloadMismatch as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_PAYLOAD_MISMATCH"},
        ) from exc

    if submission.status == "completed":
        raise StreamingSubmissionCompleted(submission.id, submission.result_fetch_url)
    if submission.status in ACTIVE_STREAMING_STATUSES:
        raise StreamingAlreadyInProgress(submission.id, submission.result_fetch_url)
    if submission.status in TERMINAL_FAILURE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SUBMISSION_RETRY_REQUIRES_NEW_CLIENT_SUBMISSION_ID",
                "submission_id": submission.id,
            },
        )

    route = resolve_task_route(settings, "essay_feedback", "essay_feedback")
    _reserve_submission_limit(
        session=session,
        settings=settings,
        student_id=student_id,
        submission_id=submission.id,
        route_daily_limit=route.task.daily_limit,
    )
    mark_submission_status(
        session=session,
        submission_id=submission.id,
        status="reserved",
    )
    session.commit()
    return submission


def build_direct_draft_feedback_stream(
    *,
    request_session: Session,
    session_factory: SessionFactory,
    runner: Any,
    settings: Settings,
    student_id: str,
    payload: Any,
) -> AsyncIterator[str]:
    del runner
    if not settings.essay_feedback_streaming_enabled:
        raise HTTPException(status_code=404, detail="essay feedback streaming is disabled")
    payload_data = _payload_dict(payload)
    client_submission_id = _require_client_submission_id(
        str(payload_data.get("client_submission_id") or "")
    )
    try:
        submission = _prepare_streaming_submission(
            session=request_session,
            settings=settings,
            student_id=student_id,
            essay_id=None,
            route_scope="direct_draft",
            client_submission_id=client_submission_id,
            payload=payload_data,
        )
    except StreamingSubmissionCompleted as completed:
        return _single_done_stream(
            submission_id=completed.submission_id,
            fetch_url=completed.fetch_url,
        )
    except StreamingAlreadyInProgress as active:
        return _single_in_progress_stream(
            submission_id=active.submission_id,
            fetch_url=active.fetch_url,
        )

    provider = _provider_for_stream(settings)
    backend_task = _build_backend_task(
        request_session=request_session,
        session_factory=session_factory,
        settings=settings,
        provider=provider,
        submission_id=submission.id,
        payload=_stream_payload(str(payload.title), str(payload.draft)),
        save_context=StreamingSaveContext(
            route_scope="direct_draft",
            student_id=student_id,
            title=str(payload.title),
            draft=str(payload.draft),
        ),
    )
    return SseMirror(backend_task=backend_task).frames()


def build_prewriting_first_draft_feedback_stream(
    *,
    request_session: Session,
    session_factory: SessionFactory,
    runner: Any,
    settings: Settings,
    essay: Essay,
    payload: Any,
) -> AsyncIterator[str]:
    del runner
    if not settings.essay_feedback_streaming_enabled:
        raise HTTPException(status_code=404, detail="essay feedback streaming is disabled")
    payload_data = _payload_dict(payload)
    client_submission_id = _require_client_submission_id(
        str(payload_data.get("client_submission_id") or "")
    )
    try:
        submission = _prepare_streaming_submission(
            session=request_session,
            settings=settings,
            student_id=essay.student_id,
            essay_id=essay.id,
            route_scope="prewriting_first_draft",
            client_submission_id=client_submission_id,
            payload=payload_data,
        )
    except StreamingSubmissionCompleted as completed:
        return _single_done_stream(
            submission_id=completed.submission_id,
            fetch_url=completed.fetch_url,
        )
    except StreamingAlreadyInProgress as active:
        return _single_in_progress_stream(
            submission_id=active.submission_id,
            fetch_url=active.fetch_url,
        )

    provider = _provider_for_stream(settings)
    backend_task = _build_backend_task(
        request_session=request_session,
        session_factory=session_factory,
        settings=settings,
        provider=provider,
        submission_id=submission.id,
        payload=_stream_payload(str(essay.title), str(payload.draft)),
        save_context=StreamingSaveContext(
            route_scope="prewriting_first_draft",
            student_id=essay.student_id,
            title=str(essay.title),
            draft=str(payload.draft),
            essay_id=essay.id,
        ),
    )
    return SseMirror(backend_task=backend_task).frames()
