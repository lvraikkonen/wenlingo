from collections.abc import Iterator, Mapping
from dataclasses import dataclass
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
