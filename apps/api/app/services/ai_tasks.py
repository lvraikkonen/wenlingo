import html
import re
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.prompts.registry import get_prompt
from app.services.llm_contracts import (
    EssayFeedback,
    EssayRevisionComparison,
    GhostwritingCheck,
    MaterialCardsResult,
    MaterialQuestionsResult,
    SentenceChallenge,
    SentenceChallengeFeedback,
    SentenceFeedback,
    WritingOutlineResult,
    WritingTopicIdeasResult,
    WritingTopicAnalysis,
)
from app.services.ai_routing import TaskFinalStatus
from app.services.llm_provider import LLMProvider
from app.services.llm_usage import llm_daily_limit_reached
from app.services.sentence_challenges import (
    fallback_challenge,
    fallback_challenge_feedback,
    validate_sentence_challenge_grade_label,
)
from app.services.writing_castle_ai import (
    fallback_material_cards,
    fallback_material_questions,
    fallback_outline,
    fallback_topic_analysis,
)
from app.services.writing_castle_sources import validate_slot_level_source_policy
from app.services.writing_topic_ideas import validate_writing_topic_ideas


T = TypeVar("T", bound=BaseModel)
MAX_LLM_ATTEMPTS = 2


@dataclass(frozen=True)
class LLMTaskResult(Generic[T]):
    output: T
    log: LLMCallLog | None
    status: str = "ok"


class LLMTaskValidationError(ValueError):
    pass


GHOSTWRITING_TRIGGERS = [
    "帮我写",
    "直接写",
    "生成一篇",
    "写完整作文",
    "范文",
]

GHOSTWRITING_INTENT_PATTERNS = [
    "替我写作文",
    "替我写一篇作文",
    "给我写作文",
    "给我写一篇作文",
    "帮我写作文",
    "帮我写一篇作文",
    "帮我生成作文",
    "生成作文",
    "生成一篇作文",
    "写一篇作文",
    "写一篇关于",
    "写作文",
]

GHOSTWRITING_INTENT_REGEXES = [
    re.compile(r"(替我|给我|帮我)?写一篇.+作文"),
]


def _normalize_request(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


def _wrap_student_payload(tag: str, value: str) -> str:
    return f"<{tag}>{html.escape(value, quote=False)}</{tag}>"


def convert_ghostwriting_request(text: str) -> GhostwritingCheck:
    normalized_text = _normalize_request(text)
    blocked = any(_normalize_request(trigger) in normalized_text for trigger in GHOSTWRITING_TRIGGERS)
    blocked = blocked or any(pattern in normalized_text for pattern in GHOSTWRITING_INTENT_PATTERNS)
    blocked = blocked or any(pattern.search(normalized_text) for pattern in GHOSTWRITING_INTENT_REGEXES)
    if not blocked:
        return GhostwritingCheck(blocked=False, message="", next_question="")
    return GhostwritingCheck(
        blocked=True,
        message="我不能替你写完整作文，但可以帮你想一想这件事里最值得写的画面。",
        next_question="这件事里最值得写的一个画面是什么？",
    )


def log_llm_result(
    session: Session,
    student_id: str | None,
    task_type: TaskType,
    task_name: str,
    provider: str,
    model: str,
    prompt_version: str,
    input_summary: str,
    raw_response: str,
    output_json: dict,
    validation_ok: bool,
    error_message: str,
    retry_count: int,
    final_status: str = "",
    prompt_key: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    estimated_cost: float = 0.0,
    latency_ms: int = 0,
    topic_type: str = "",
    topic_variant: str = "",
    scaffold_template_version: str = "",
    source_policy_summary: str = "",
    duration_ms: int | None = None,
    request_started_at: datetime | None = None,
    response_received_at: datetime | None = None,
) -> LLMCallLog:
    log = LLMCallLog(
        student_id=student_id,
        task_type=task_type,
        task_name=task_name,
        prompt_key=prompt_key or task_name,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        input_summary=input_summary,
        raw_response=raw_response,
        output_json=output_json,
        validation_ok=validation_ok,
        final_status=final_status,
        error_message=error_message,
        retry_count=retry_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        topic_type=topic_type,
        topic_variant=topic_variant,
        scaffold_template_version=scaffold_template_version,
        source_policy_summary=source_policy_summary,
        duration_ms=duration_ms or 0,
        request_started_at=request_started_at,
        response_received_at=response_received_at,
    )
    session.add(log)
    session.flush()
    return log


def fallback_essay_feedback() -> EssayFeedback:
    return EssayFeedback(
        strengths=["你已经完成了一版初稿", "你愿意继续修改，这很重要"],
        improvements=["先选择一段，把看到的画面或动作补清楚"],
        problem_monsters=["细节缺口"],
        sentence_notes=["把“很开心”“很害怕”换成看得见的动作、声音或表情。"],
        revision_tasks=[
            {
                "instruction": "先给最重要的一段加一个动作或看到的细节",
                "target": "你觉得最想改好的那一段",
            }
        ],
    )


def fallback_revision_comparison() -> EssayRevisionComparison:
    return EssayRevisionComparison(
        encouragement="你完成了二稿，这一步本身就很值得肯定。",
        improved_dimensions=["完成了一次修改"],
        evidence=["你提交了新的二稿内容"],
        next_step="下一次可以继续挑一段，把动作、声音或心情写得更具体。",
    )


def fallback_sentence_feedback() -> SentenceFeedback:
    return SentenceFeedback(
        encouragement="你已经完成了一次句子升级。",
        specific_improvement="先把一个看得见的细节写清楚",
        next_step="再读一遍你的句子，圈出一个动作、声音或颜色细节。",
        ability_delta={"expression": 2, "observation": 2},
        problem_monsters=["空泛表达"],
    )


def _token_count(usage: dict[str, int] | None, key: str) -> int:
    if not usage:
        return 0
    return int(usage.get(key) or 0)


def _validate_sentence_challenge_grade_label(grade_label: str) -> None:
    validate_sentence_challenge_grade_label(grade_label)


def _validate_sentence_challenge_response_context(
    challenge: SentenceChallenge,
    requested_target_skill: str,
    requested_grade_label: str,
) -> None:
    if challenge.target_skill != requested_target_skill:
        raise LLMTaskValidationError(
            "sentence challenge target_skill mismatch: "
            f"requested {requested_target_skill}, got {challenge.target_skill}"
        )
    if challenge.grade_label != requested_grade_label:
        raise LLMTaskValidationError(
            "sentence challenge grade_label mismatch: "
            f"requested {requested_grade_label}, got {challenge.grade_label}"
        )
    if not challenge.difficulty_label.startswith(requested_grade_label):
        raise LLMTaskValidationError(
            "sentence challenge difficulty_label grade mismatch: "
            f"requested {requested_grade_label}, got {challenge.difficulty_label}"
        )


def _payload_source_id(value) -> str | None:
    if value is None:
        return None
    source_id = str(value)
    if not source_id.strip():
        return None
    return source_id


def _valid_answer_source_ids(answers: list[dict]) -> set[str]:
    source_ids = set()
    for answer in answers:
        if answer.get("skipped"):
            continue
        if not str(answer.get("text") or "").strip():
            continue
        source_id = _payload_source_id(answer.get("id"))
        if source_id is not None:
            source_ids.add(source_id)
    return source_ids


def _known_reading_material_refs(answers: list[dict]) -> set[str]:
    refs = set()
    for answer in answers:
        if answer.get("skipped"):
            continue
        if not str(answer.get("text") or "").strip():
            continue
        source_refs = answer.get("source_refs")
        if not isinstance(source_refs, list):
            continue
        for source_ref in source_refs:
            if not isinstance(source_ref, dict):
                continue
            source_type = str(source_ref.get("source_type") or "").strip()
            reading_material_ref = _payload_source_id(source_ref.get("reading_material_ref"))
            if source_type == "reading_material" and reading_material_ref is not None:
                refs.add(reading_material_ref)
    return refs


def _valid_card_source_ids(cards: list[dict]) -> set[str]:
    source_ids = set()
    for card in cards:
        if card.get("deleted") or card.get("placeholder"):
            continue
        source_id = _payload_source_id(card.get("id"))
        if source_id is not None:
            source_ids.add(source_id)
    return source_ids


def _validate_material_card_source_ids(
    output: MaterialCardsResult,
    valid_source_ids: set[str],
) -> None:
    unknown_source_ids = sorted(
        {
            source_id
            for card in output.cards
            for source_id in card.source_answer_ids
            if source_id not in valid_source_ids
        }
    )
    if unknown_source_ids:
        raise LLMTaskValidationError(
            "unknown source_answer_ids: " + ", ".join(unknown_source_ids)
        )


def _validate_material_card_source_refs(
    output: MaterialCardsResult,
    valid_source_ids: set[str],
    known_reading_material_refs: set[str],
) -> None:
    for card in output.cards:
        for source_ref in card.source_refs:
            source_type = str(source_ref.get("source_type") or "").strip()
            if source_type == "child_confirmed":
                raise LLMTaskValidationError(
                    "model output cannot create child_confirmed source_refs"
                )

            if "answer_id" in source_ref:
                answer_id = _payload_source_id(source_ref.get("answer_id"))
                if answer_id is None or answer_id not in valid_source_ids:
                    raise LLMTaskValidationError(
                        "unknown source_ref answer_id: "
                        + (answer_id if answer_id is not None else "<blank>")
                    )

            if source_type == "reading_material":
                reading_material_ref = _payload_source_id(
                    source_ref.get("reading_material_ref")
                )
                if (
                    reading_material_ref is None
                    or reading_material_ref not in known_reading_material_refs
                ):
                    raise LLMTaskValidationError(
                        "unknown reading_material source_ref"
                    )


def _validate_v06b_material_card_source_refs(
    output: MaterialCardsResult,
    scaffold: dict | None,
) -> None:
    if not scaffold or scaffold.get("schema_version") != "v0.6b.1":
        return
    for card in output.cards:
        if not card.placeholder and not card.source_refs:
            raise LLMTaskValidationError("v0.6b material cards require source_refs")


def _validate_material_card_slot_level_source_policy(
    output: MaterialCardsResult,
    scaffold: dict | None,
) -> None:
    if not scaffold:
        return
    topic_type = str(scaffold.get("topic_type") or "")
    for card in output.cards:
        if card.placeholder:
            continue
        try:
            validate_slot_level_source_policy(
                topic_type=topic_type,
                slot_id=card.category,
                source_refs=card.source_refs,
            )
        except ValueError as exc:
            raise LLMTaskValidationError(str(exc)) from exc


def _validate_outline_source_ids(
    output: WritingOutlineResult,
    valid_source_ids: set[str],
) -> None:
    unknown_source_ids = sorted(
        {
            source_id
            for section in output.sections
            for source_id in section.source_card_ids
            if source_id not in valid_source_ids
        }
    )
    if unknown_source_ids:
        raise LLMTaskValidationError(
            "unknown source_card_ids: " + ", ".join(unknown_source_ids)
        )


def _scaffold_slot_ids(scaffold: dict, key: str) -> set[str]:
    entries = scaffold.get(key, [])
    if not isinstance(entries, list):
        raise LLMTaskValidationError(f"malformed scaffold {key}")

    slot_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise LLMTaskValidationError(f"malformed scaffold {key}")
        slot_id = _payload_source_id(entry.get("id"))
        if slot_id is None:
            raise LLMTaskValidationError(f"malformed scaffold {key}")
        slot_ids.add(slot_id)
    return slot_ids


def _validate_material_card_template_slots(
    output: MaterialCardsResult,
    scaffold: dict | None,
) -> None:
    if not scaffold:
        return
    allowed = _scaffold_slot_ids(scaffold, "material_slots")
    unknown = sorted({card.category for card in output.cards if card.category not in allowed})
    if unknown:
        raise LLMTaskValidationError(
            "unknown scaffold material slot ids: " + ", ".join(unknown)
        )


def _validate_outline_template_slots(
    output: WritingOutlineResult,
    scaffold: dict | None,
) -> None:
    if not scaffold:
        return
    allowed = _scaffold_slot_ids(scaffold, "outline_sections")
    unknown = sorted({section.slot for section in output.sections if section.slot not in allowed})
    if unknown:
        raise LLMTaskValidationError(
            "unknown scaffold outline section ids: " + ", ".join(unknown)
        )


def estimate_llm_cost(
    prompt_tokens: int,
    completion_tokens: int,
    input_cost_per_1k: float,
    output_cost_per_1k: float,
) -> float:
    return (prompt_tokens / 1000 * input_cost_per_1k) + (
        completion_tokens / 1000 * output_cost_per_1k
    )


async def run_validated_llm_task(
    *,
    provider: LLMProvider,
    session: Session | None,
    student_id: str | None = None,
    task_type: TaskType,
    task_name: str,
    payload: dict,
    output_model: type[T],
    fallback: T,
    input_summary: str,
    prompt_version: str,
    prompt_key: str | None = None,
    validation_hook: Callable[[T], None] | None = None,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
    daily_limit_timezone: str = "Asia/Shanghai",
) -> LLMTaskResult[T]:
    errors: list[str] = []
    raw_response = ""
    provider_name = getattr(provider, "provider_name", provider.__class__.__name__)
    model_name = getattr(provider, "model_name", "unknown")
    latest_response_provider = provider_name
    latest_response_model = model_name

    if (
        session is not None
        and student_id is not None
        and daily_limit_enabled
        and llm_daily_limit_reached(
            session=session,
            student_id=student_id,
            task_name=task_name,
            limit=daily_limit_per_student_task,
            timezone_name=daily_limit_timezone,
        )
    ):
        log = log_llm_result(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=prompt_key or task_name,
            provider="local_fallback",
            model="local_fallback",
            prompt_version=prompt_version,
            input_summary=input_summary,
            raw_response="",
            output_json=fallback.model_dump(),
            validation_ok=False,
            final_status=TaskFinalStatus.DAILY_LIMIT_REACHED,
            error_message="daily limit reached",
            retry_count=0,
        )
        return LLMTaskResult(output=fallback, log=log, status="daily_limit_reached")

    for attempt_index in range(MAX_LLM_ATTEMPTS):
        try:
            started_at = perf_counter()
            response = await provider.complete_json(task_name, payload)
            latency_ms = int((perf_counter() - started_at) * 1000)
            prompt_tokens = _token_count(response.usage, "prompt_tokens")
            completion_tokens = _token_count(response.usage, "completion_tokens")
            total_tokens = _token_count(response.usage, "total_tokens")
            estimated_cost = estimate_llm_cost(
                prompt_tokens,
                completion_tokens,
                input_cost_per_1k_tokens,
                output_cost_per_1k_tokens,
            )
            raw_response = response.raw_response
            latest_response_provider = response.provider
            latest_response_model = response.model
            output = output_model.model_validate(response.parsed_json)
            if validation_hook is not None:
                validation_hook(output)
            log = None
            if session is not None:
                log = log_llm_result(
                    session=session,
                    student_id=student_id,
                    task_type=task_type,
                    task_name=task_name,
                    prompt_key=prompt_key or task_name,
                    provider=response.provider,
                    model=response.model,
                    prompt_version=prompt_version,
                    input_summary=input_summary,
                    raw_response=response.raw_response,
                    output_json=output.model_dump(),
                    validation_ok=True,
                    final_status=TaskFinalStatus.PRIMARY_SUCCESS,
                    error_message="",
                    retry_count=attempt_index,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=estimated_cost,
                    latency_ms=latency_ms,
                )
            return LLMTaskResult(output=output, log=log)
        except ValidationError as exc:
            errors.append(f"validation error: {exc}")
        except LLMTaskValidationError as exc:
            errors.append(f"validation error: {exc}")
        except Exception as exc:
            errors.append(str(exc))

    log = None
    if session is not None:
        log = log_llm_result(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=prompt_key or task_name,
            provider=latest_response_provider,
            model=latest_response_model,
            prompt_version=prompt_version,
            input_summary=input_summary,
            raw_response=raw_response,
            output_json=fallback.model_dump(),
            validation_ok=False,
            final_status=TaskFinalStatus.DETERMINISTIC_FALLBACK_USED,
            error_message="; ".join(errors),
            retry_count=MAX_LLM_ATTEMPTS - 1,
        )
    return LLMTaskResult(output=fallback, log=log, status="fallback")


async def sentence_upgrade_feedback(
    runner,
    source_sentence: str,
    upgraded_sentence: str,
    focus: str,
    session: Session | None = None,
    prompt_version: str = "",
    student_id: str | None = None,
) -> LLMTaskResult[SentenceFeedback]:
    prompt = get_prompt("sentence_upgrade_feedback")
    effective_prompt_version = prompt_version or prompt.version
    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.sentence,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "source_sentence": _wrap_student_payload("student_sentence", source_sentence),
            "upgraded_sentence": _wrap_student_payload("student_sentence", upgraded_sentence),
            "focus": focus,
        },
        output_schema=SentenceFeedback,
        deterministic_fallback_factory=lambda _context: fallback_sentence_feedback(),
        input_summary=(
            f"句子快练；原句长度：{len(source_sentence)}；"
            f"升级句长度：{len(upgraded_sentence)}；目标：{focus}"
        ),
        prompt_version=effective_prompt_version,
    )


async def sentence_challenge_generation(
    runner,
    target_skill: str,
    grade_label: str,
    session: Session | None = None,
    student_id: str | None = None,
    daily_limit: int | None = None,
) -> LLMTaskResult[SentenceChallenge]:
    _validate_sentence_challenge_grade_label(grade_label)
    fallback_challenge(target_skill, grade_label)
    prompt = get_prompt("sentence_challenge_generation")
    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.sentence,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={"target_skill": target_skill, "grade_label": grade_label},
        output_schema=SentenceChallenge,
        deterministic_fallback_factory=lambda _context: fallback_challenge(
            target_skill,
            grade_label,
        ),
        input_summary=f"句子挑战生成；年级：{grade_label}；目标：{target_skill}",
        daily_limit=daily_limit,
        prompt_version=prompt.version,
        validate_output=lambda challenge: _validate_sentence_challenge_response_context(
            challenge,
            target_skill,
            grade_label,
        ),
    )


async def sentence_challenge_feedback(
    runner,
    target_skill: str,
    source_sentence: str,
    upgraded_sentence: str,
    session: Session | None = None,
    student_id: str | None = None,
    daily_limit: int | None = None,
) -> LLMTaskResult[SentenceChallengeFeedback]:
    fallback_challenge_feedback(target_skill)
    prompt = get_prompt("sentence_challenge_feedback")
    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.sentence,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "target_skill": target_skill,
            "source_sentence": _wrap_student_payload("student_sentence", source_sentence),
            "upgraded_sentence": _wrap_student_payload("student_sentence", upgraded_sentence),
        },
        output_schema=SentenceChallengeFeedback,
        deterministic_fallback_factory=lambda _context: fallback_challenge_feedback(
            target_skill
        ),
        input_summary=(
            f"句子挑战反馈；目标：{target_skill}；"
            f"原句长度：{len(source_sentence)}；升级句长度：{len(upgraded_sentence)}"
        ),
        daily_limit=daily_limit,
        prompt_version=prompt.version,
    )


async def writing_topic_analysis(
    runner,
    topic_text: str,
    session: Session | None = None,
    student_id: str | None = None,
    scaffold: dict[str, Any] | None = None,
) -> LLMTaskResult[WritingTopicAnalysis]:
    prompt = get_prompt("writing_topic_analysis")
    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "topic_text": _wrap_student_payload("teacher_topic", topic_text),
            "scaffold": scaffold or {},
        },
        output_schema=WritingTopicAnalysis,
        deterministic_fallback_factory=lambda _context: fallback_topic_analysis(topic_text),
        input_summary=f"写作城堡题目分析；题目长度：{len(topic_text)}",
        prompt_version=prompt.version,
    )


async def writing_topic_idea_generation(
    runner,
    grade_label: str,
    interest_text: str,
    supported_choices: list[dict[str, Any]],
    allowed_variants: dict[str, tuple[str, ...]],
    session: Session | None = None,
    student_id: str | None = None,
) -> LLMTaskResult[WritingTopicIdeasResult]:
    prompt = get_prompt("writing_topic_idea_generation")

    def validate_output(output: WritingTopicIdeasResult) -> None:
        validate_writing_topic_ideas(
            output,
            supported_choices=supported_choices,
            allowed_variants=allowed_variants,
        )

    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "grade_label": grade_label,
            "interest_text": _wrap_student_payload("child_interest", interest_text),
            "supported_choices": supported_choices,
            "allowed_variants": allowed_variants,
        },
        output_schema=WritingTopicIdeasResult,
        deterministic_fallback_factory=None,
        input_summary=f"AI 出题灵感；年级：{grade_label}；兴趣长度：{len(interest_text)}",
        prompt_version=prompt.version,
        validate_output=validate_output,
    )


async def material_questions(
    runner,
    topic_text: str,
    confirmed_focus: str,
    session: Session | None = None,
    student_id: str | None = None,
    scaffold: dict[str, Any] | None = None,
) -> LLMTaskResult[MaterialQuestionsResult]:
    prompt = get_prompt("material_questions")
    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "topic_text": _wrap_student_payload("teacher_topic", topic_text),
            "confirmed_focus": _wrap_student_payload("confirmed_focus", confirmed_focus),
            "scaffold": scaffold or {},
        },
        output_schema=MaterialQuestionsResult,
        deterministic_fallback_factory=lambda _context: fallback_material_questions(scaffold),
        input_summary=(
            f"写作城堡素材问题；题目长度：{len(topic_text)}；"
            f"焦点长度：{len(confirmed_focus)}"
        ),
        prompt_version=prompt.version,
    )


async def material_card_generation(
    runner,
    answers: list[dict],
    session: Session | None = None,
    student_id: str | None = None,
    scaffold: dict[str, Any] | None = None,
) -> LLMTaskResult[MaterialCardsResult]:
    prompt = get_prompt("material_card_generation")
    valid_source_ids = _valid_answer_source_ids(answers)
    known_reading_material_refs = _known_reading_material_refs(answers)

    def validate_output(output: MaterialCardsResult) -> None:
        _validate_v06b_material_card_source_refs(output, scaffold)
        _validate_material_card_source_ids(output, valid_source_ids)
        _validate_material_card_source_refs(
            output,
            valid_source_ids,
            known_reading_material_refs,
        )
        _validate_material_card_slot_level_source_policy(output, scaffold)
        _validate_material_card_template_slots(output, scaffold)

    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={"answers": answers, "scaffold": scaffold or {}},
        output_schema=MaterialCardsResult,
        deterministic_fallback_factory=lambda _context: fallback_material_cards(
            answers,
            scaffold=scaffold,
        ),
        input_summary=f"写作城堡素材卡片；回答数：{len(answers)}",
        prompt_version=prompt.version,
        validate_output=validate_output,
    )


async def outline_generation(
    runner,
    cards: list[dict],
    session: Session | None = None,
    student_id: str | None = None,
    scaffold: dict[str, Any] | None = None,
) -> LLMTaskResult[WritingOutlineResult]:
    prompt = get_prompt("outline_generation")
    valid_source_ids = _valid_card_source_ids(cards)

    def validate_output(output: WritingOutlineResult) -> None:
        _validate_outline_source_ids(output, valid_source_ids)
        _validate_outline_template_slots(output, scaffold)

    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={"cards": cards, "scaffold": scaffold or {}},
        output_schema=WritingOutlineResult,
        deterministic_fallback_factory=lambda _context: fallback_outline(
            cards,
            scaffold=scaffold,
        ),
        input_summary=f"写作城堡提纲生成；素材卡数：{len(cards)}",
        prompt_version=prompt.version,
        validate_output=validate_output,
    )


async def essay_feedback(
    runner,
    title: str,
    draft: str,
    session: Session | None = None,
    prompt_version: str = "",
    student_id: str | None = None,
) -> LLMTaskResult[EssayFeedback]:
    ghostwriting = convert_ghostwriting_request(draft)
    if ghostwriting.blocked:
        raise ValueError(ghostwriting.message)
    prompt = get_prompt("essay_feedback")
    effective_prompt_version = prompt_version or prompt.version
    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "title": _wrap_student_payload("student_title", title),
            "draft": _wrap_student_payload("student_draft", draft),
        },
        output_schema=EssayFeedback,
        deterministic_fallback_factory=lambda _context: fallback_essay_feedback(),
        input_summary=f"作文题目：{title}；初稿长度：{len(draft)}",
        prompt_version=effective_prompt_version,
    )


async def essay_revision_comparison(
    runner,
    first_draft: str,
    revision: str,
    session: Session | None = None,
    prompt_version: str = "",
    student_id: str | None = None,
) -> LLMTaskResult[EssayRevisionComparison]:
    prompt = get_prompt("essay_revision_comparison")
    effective_prompt_version = prompt_version or prompt.version
    return await runner.run(
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "first_draft": _wrap_student_payload("student_first_draft", first_draft),
            "revision": _wrap_student_payload("student_revision", revision),
        },
        output_schema=EssayRevisionComparison,
        deterministic_fallback_factory=lambda _context: fallback_revision_comparison(),
        input_summary=f"二稿对比；初稿长度：{len(first_draft)}；二稿长度：{len(revision)}",
        prompt_version=effective_prompt_version,
    )
