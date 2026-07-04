from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass
import inspect
import json
from typing import Any, Protocol

import httpx

from app.prompts.registry import get_prompt
from app.services.sentence_challenges import fallback_challenge, fallback_challenge_feedback
from app.services.writing_castle_ai import (
    fallback_material_cards,
    fallback_material_questions,
    fallback_outline,
    fallback_topic_analysis,
)


@dataclass(frozen=True)
class LLMProviderResponse(Mapping[str, Any]):
    parsed_json: dict[str, Any]
    raw_response: str
    provider: str
    model: str
    usage: dict[str, Any] | None = None
    provider_reported_cost_usd: float | None = None

    def __getitem__(self, key: str) -> Any:
        return self.parsed_json[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.parsed_json)

    def __len__(self) -> int:
        return len(self.parsed_json)


@dataclass(frozen=True)
class LLMProviderStreamEvent:
    event_type: str
    text_delta: str = ""
    usage: dict[str, Any] | None = None
    provider_request_id: str | None = None
    provider_generation_id: str | None = None
    provider_reported_cost_usd: float | None = None
    error_code: str = ""
    error_message: str = ""


def response_contract_for_task(task_name: str) -> str:
    try:
        return get_prompt(task_name).response_contract
    except KeyError:
        return "Return a JSON object only. Do not include markdown or explanatory text."


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    async def complete_json(self, task_name: str, payload: dict[str, Any]) -> LLMProviderResponse:
        ...

    async def stream_text(
        self,
        task_name: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[LLMProviderStreamEvent]:
        ...


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _openai_compatible_usage(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None

    normalized_usage: dict[str, Any] = {"provider_raw_usage": dict(usage)}
    for source_key, target_key in (
        ("prompt_tokens", "prompt_tokens"),
        ("completion_tokens", "completion_tokens"),
        ("total_tokens", "total_tokens"),
    ):
        if source_key in usage:
            token_count = _int_or_none(usage.get(source_key))
            if token_count is not None:
                normalized_usage[target_key] = token_count

    prompt_details = usage.get("prompt_tokens_details")
    if isinstance(prompt_details, dict) and "cached_tokens" in prompt_details:
        cached_tokens = _int_or_none(prompt_details.get("cached_tokens"))
        if cached_tokens is not None:
            normalized_usage["cached_input_tokens"] = cached_tokens
            normalized_usage["cached_input_tokens_included_in_prompt_tokens"] = True

    completion_details = usage.get("completion_tokens_details")
    if isinstance(completion_details, dict) and "reasoning_tokens" in completion_details:
        reasoning_tokens = _int_or_none(completion_details.get("reasoning_tokens"))
        if reasoning_tokens is not None:
            normalized_usage["reasoning_tokens"] = reasoning_tokens

    return normalized_usage


def _normalize_anthropic_usage(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None

    normalized_usage: dict[str, Any] = {"provider_raw_usage": dict(usage)}
    for source_key, target_key in (
        ("input_tokens", "prompt_tokens"),
        ("output_tokens", "completion_tokens"),
        ("total_tokens", "total_tokens"),
    ):
        if source_key in usage:
            token_count = _int_or_none(usage.get(source_key))
            if token_count is not None:
                normalized_usage[target_key] = token_count
    if "cache_read_input_tokens" in usage:
        cached_tokens = _int_or_none(usage.get("cache_read_input_tokens"))
        if cached_tokens is not None:
            normalized_usage["cached_input_tokens"] = cached_tokens
            normalized_usage["cached_input_tokens_included_in_prompt_tokens"] = True
    if (
        "prompt_tokens" in normalized_usage
        and "completion_tokens" in normalized_usage
        and "total_tokens" not in normalized_usage
    ):
        normalized_usage["total_tokens"] = (
            normalized_usage["prompt_tokens"] + normalized_usage["completion_tokens"]
        )
    return normalized_usage


def _anthropic_usage_from_chunk(chunk: dict[str, Any]) -> dict[str, Any] | None:
    usage = chunk.get("usage")
    if isinstance(usage, dict):
        return _normalize_anthropic_usage(usage)
    message = chunk.get("message")
    if isinstance(message, dict):
        return _normalize_anthropic_usage(message.get("usage"))
    return None


def _merge_anthropic_usage(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    if previous is None:
        return dict(current)

    merged = dict(previous)
    previous_raw = previous.get("provider_raw_usage")
    current_raw = current.get("provider_raw_usage")
    if isinstance(previous_raw, dict) and isinstance(current_raw, dict):
        merged["provider_raw_usage"] = {**previous_raw, **current_raw}
    elif isinstance(current_raw, dict):
        merged["provider_raw_usage"] = dict(current_raw)

    for key, value in current.items():
        if key != "provider_raw_usage":
            merged[key] = value

    raw = merged.get("provider_raw_usage")
    has_provider_total = isinstance(raw, dict) and "total_tokens" in raw
    if (
        not has_provider_total
        and "prompt_tokens" in merged
        and "completion_tokens" in merged
    ):
        merged["total_tokens"] = merged["prompt_tokens"] + merged["completion_tokens"]
    return merged


def _gemini_usage(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None

    normalized_usage: dict[str, Any] = {"provider_raw_usage": dict(usage)}
    for source_key, target_key in (
        ("promptTokenCount", "prompt_tokens"),
        ("candidatesTokenCount", "completion_tokens"),
        ("totalTokenCount", "total_tokens"),
        ("thoughtsTokenCount", "thoughts_tokens"),
    ):
        if source_key in usage:
            token_count = _int_or_none(usage.get(source_key))
            if token_count is not None:
                normalized_usage[target_key] = token_count
    return normalized_usage


def _openai_text_delta(chunk: dict[str, Any]) -> str:
    pieces: list[str] = []
    choices = chunk.get("choices")
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                pieces.append(content)
    return "".join(pieces)


def _anthropic_text_delta(chunk: dict[str, Any]) -> str:
    if chunk.get("type") != "content_block_delta":
        return ""
    delta = chunk.get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("text"), str):
        return delta["text"]
    return ""


def _gemini_text_delta(chunk: dict[str, Any]) -> str:
    pieces: list[str] = []
    candidates = chunk.get("candidates")
    if not isinstance(candidates, list):
        return ""
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                pieces.append(part["text"])
    return "".join(pieces)


def normalize_provider_stream_events(
    *,
    provider: str,
    chunks: list[dict[str, Any]],
) -> list[LLMProviderStreamEvent]:
    normalized_provider = provider.lower()
    events: list[LLMProviderStreamEvent] = []
    final_usage: dict[str, Any] | None = None

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        error = chunk.get("error")
        if isinstance(error, dict):
            events.append(
                LLMProviderStreamEvent(
                    event_type="provider_error",
                    error_code=str(error.get("code") or "PROVIDER_ERROR"),
                    error_message=str(error.get("message") or "provider stream error"),
                )
            )
            return events
        if chunk.get("type") == "ping":
            continue

        text_delta = ""
        chunk_usage: dict[str, Any] | None = None
        if normalized_provider in {"openai", "http"}:
            text_delta = _openai_text_delta(chunk)
            chunk_usage = _openai_compatible_usage(chunk.get("usage"))
        elif normalized_provider == "anthropic":
            text_delta = _anthropic_text_delta(chunk)
            chunk_usage = _anthropic_usage_from_chunk(chunk)
        elif normalized_provider == "gemini":
            text_delta = _gemini_text_delta(chunk)
            chunk_usage = _gemini_usage(chunk.get("usageMetadata"))
        else:
            text_delta = str(chunk.get("text_delta") or chunk.get("text") or "")
            raw_usage = chunk.get("usage")
            chunk_usage = dict(raw_usage) if isinstance(raw_usage, dict) else None

        if text_delta:
            events.append(LLMProviderStreamEvent(event_type="text_delta", text_delta=text_delta))
        if chunk_usage is not None:
            if normalized_provider == "anthropic":
                final_usage = _merge_anthropic_usage(final_usage, chunk_usage)
            else:
                final_usage = chunk_usage

    events.append(LLMProviderStreamEvent(event_type="usage_final", usage=final_usage))
    events.append(LLMProviderStreamEvent(event_type="provider_done"))
    return events


class MockLLMProvider:
    provider_name = "mock"
    model_name = "mock"

    async def complete_json(self, task_name: str, payload: dict[str, Any]) -> LLMProviderResponse:
        if task_name == "sentence_upgrade_feedback":
            payload = {
                "encouragement": "你把画面写得更清楚了。",
                "specific_improvement": "加入了可看见的细节",
                "next_step": "再加一个动作，会更生动。",
                "ability_delta": {"expression": 4, "observation": 4},
                "problem_monsters": ["空泛表达"],
            }
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "essay_feedback":
            payload = {
                "strengths": ["能写清楚发生了什么", "有一处心情表达"],
                "improvements": ["第二段缺少动作细节"],
                "problem_monsters": ["细节缺口"],
                "sentence_notes": ["把“我很开心”换成看到、听到、做到的细节。"],
                "revision_tasks": [
                    {"instruction": "给第二段加一个动作描写", "target": "第二段"}
                ],
            }
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "essay_revision_comparison":
            payload = {
                "encouragement": "你把最重要的画面写清楚了。",
                "improved_dimensions": ["细节更多", "动作更具体"],
                "evidence": ["手心都出汗了", "摇摇晃晃骑过花坛"],
                "next_step": "下一次可以把结尾的感受写得更清楚。",
            }
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "sentence_challenge_generation":
            payload = fallback_challenge(
                payload["target_skill"],
                payload["grade_label"],
            ).model_dump()
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "sentence_challenge_feedback":
            payload = fallback_challenge_feedback(payload["target_skill"]).model_dump()
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "writing_topic_analysis":
            payload = fallback_topic_analysis(payload.get("topic_text", "")).model_dump()
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "writing_topic_idea_generation":
            payload = {
                "ideas": [
                    {
                        "id": "idea-1",
                        "title": "足球训练小挑战",
                        "topic_type": "generic_narrative",
                        "topic_variant": "default",
                        "why_it_fits_child_interest": "喜欢足球，可以从一次练习中选择真实画面。",
                        "practice_focus": "按顺序写清楚挑战过程",
                        "child_safe_prompt": "你想写哪一次足球练习？先选一个自己记得的画面。",
                    },
                    {
                        "id": "idea-2",
                        "title": "我的运动乐园",
                        "topic_type": "place_scenery",
                        "topic_variant": "my_paradise",
                        "why_it_fits_child_interest": "可以把常去的运动场地写成自己的乐园。",
                        "practice_focus": "观察地点和活动细节",
                        "child_safe_prompt": "你想写哪个运动地点？先确认那里最特别的一处。",
                    },
                    {
                        "id": "idea-3",
                        "title": "给球队的一封信",
                        "topic_type": "practical_writing",
                        "topic_variant": "letter",
                        "why_it_fits_child_interest": "足球兴趣适合练习表达真实想法。",
                        "practice_focus": "写清楚对象和想说的话",
                        "child_safe_prompt": "你想写给谁？先确认自己最想表达的一句话。",
                    },
                ]
            }
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "material_questions":
            payload = fallback_material_questions(payload.get("scaffold")).model_dump()
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "material_card_generation":
            payload = fallback_material_cards(
                payload.get("answers", []),
                scaffold=payload.get("scaffold"),
            ).model_dump()
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        if task_name == "outline_generation":
            payload = fallback_outline(
                payload.get("cards", []),
                scaffold=payload.get("scaffold"),
            ).model_dump()
            return LLMProviderResponse(
                parsed_json=payload,
                raw_response=json.dumps(payload, ensure_ascii=False),
                provider=self.provider_name,
                model=self.model_name,
            )
        raise ValueError(f"Unknown LLM task: {task_name}")

    async def stream_text(
        self,
        task_name: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[LLMProviderStreamEvent]:
        if task_name != "essay_feedback":
            response = await self.complete_json(task_name, payload)
            yield LLMProviderStreamEvent(
                event_type="text_delta",
                text_delta=json.dumps(response.parsed_json, ensure_ascii=False),
            )
            yield LLMProviderStreamEvent(event_type="usage_final", usage=response.usage)
            yield LLMProviderStreamEvent(event_type="provider_done")
            return

        sections = [
            "<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>\n",
            "<improvements>\n- 第二段缺少动作细节\n</improvements>\n",
            "<problem_monsters>\n- 细节缺口\n</problem_monsters>\n",
            "<sentence_notes>\n- 把“我很开心”换成看到、听到、做到的细节。\n</sentence_notes>\n",
            "<revision_tasks>\n- 给第二段加一个动作描写 | 第二段\n</revision_tasks>",
        ]
        for section in sections:
            yield LLMProviderStreamEvent(event_type="text_delta", text_delta=section)
        yield LLMProviderStreamEvent(
            event_type="usage_final",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )
        yield LLMProviderStreamEvent(event_type="provider_done")


class HttpJsonLLMProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.provider_name = "http"
        self.model_name = model

    async def complete_json(self, task_name: str, payload: dict[str, Any]) -> LLMProviderResponse:
        try:
            prompt = get_prompt(task_name)
            system_prompt = prompt.system_prompt
            response_contract = prompt.response_contract
        except KeyError:
            raise ValueError(f"Unknown LLM task: {task_name}") from None

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task_name": task_name,
                        "payload": payload,
                        "response_contract": response_contract,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        normalized_usage = _openai_compatible_usage(data.get("usage"))
        if isinstance(content, str):
            return LLMProviderResponse(
                parsed_json=json.loads(content),
                raw_response=content,
                provider=self.provider_name,
                model=self.model_name,
                usage=normalized_usage,
            )
        return LLMProviderResponse(
            parsed_json=content,
            raw_response=json.dumps(content, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
            usage=normalized_usage,
        )

    async def stream_text(
        self,
        task_name: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[LLMProviderStreamEvent]:
        try:
            prompt = get_prompt(task_name)
            system_prompt = prompt.system_prompt
            response_contract = prompt.response_contract_stream or prompt.response_contract
        except KeyError:
            raise ValueError(f"Unknown LLM task: {task_name}") from None

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task_name": task_name,
                        "payload": payload,
                        "response_contract": response_contract,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        final_usage: dict[str, Any] | None = None
        provider_request_id: str | None = None
        provider_generation_id: str | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            stream_context = client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            )
            if inspect.isawaitable(stream_context):
                stream_context = await stream_context
            async with stream_context as response:
                response.raise_for_status()
                provider_request_id = _header_value(
                    response.headers,
                    ("x-request-id", "openai-request-id"),
                )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError as exc:
                        yield LLMProviderStreamEvent(
                            event_type="provider_error",
                            provider_request_id=provider_request_id,
                            provider_generation_id=provider_generation_id,
                            error_code="PROVIDER_STREAM_INVALID_JSON",
                            error_message=str(exc),
                        )
                        return

                    error = chunk.get("error")
                    if isinstance(error, dict):
                        yield LLMProviderStreamEvent(
                            event_type="provider_error",
                            provider_request_id=provider_request_id,
                            provider_generation_id=provider_generation_id,
                            error_code=str(error.get("code") or "PROVIDER_ERROR"),
                            error_message=str(error.get("message") or "provider stream error"),
                        )
                        return

                    chunk_id = chunk.get("id")
                    if isinstance(chunk_id, str) and chunk_id:
                        provider_generation_id = chunk_id
                    chunk_usage = _openai_compatible_usage(chunk.get("usage"))
                    if chunk_usage is not None:
                        final_usage = chunk_usage
                    text_delta = _openai_text_delta(chunk)
                    if text_delta:
                        yield LLMProviderStreamEvent(
                            event_type="text_delta",
                            text_delta=text_delta,
                            provider_request_id=provider_request_id,
                            provider_generation_id=provider_generation_id,
                        )

        yield LLMProviderStreamEvent(
            event_type="usage_final",
            usage=final_usage,
            provider_request_id=provider_request_id,
            provider_generation_id=provider_generation_id,
        )
        yield LLMProviderStreamEvent(
            event_type="provider_done",
            provider_request_id=provider_request_id,
            provider_generation_id=provider_generation_id,
        )


def _header_value(headers: Any, names: tuple[str, ...]) -> str | None:
    for name in names:
        value = headers.get(name) if hasattr(headers, "get") else None
        if isinstance(value, str) and value:
            return value
    if not isinstance(headers, dict):
        return None
    lower_headers = {str(key).lower(): value for key, value in headers.items()}
    for name in names:
        value = lower_headers.get(name.lower())
        if isinstance(value, str) and value:
            return value
    return None
