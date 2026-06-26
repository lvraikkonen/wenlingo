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
    usage: dict[str, int] | None = None

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
        usage = data.get("usage")
        normalized_usage = None
        if isinstance(usage, dict):
            normalized_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            }
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
