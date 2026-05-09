import json
from typing import Any, Protocol

import httpx


class LLMProvider(Protocol):
    async def complete_json(self, task_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class MockLLMProvider:
    async def complete_json(self, task_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task_name == "sentence_upgrade_feedback":
            return {
                "encouragement": "你把画面写得更清楚了。",
                "specific_improvement": "加入了可看见的细节",
                "next_step": "再加一个动作，会更生动。",
                "ability_delta": {"expression": 4, "observation": 4},
                "problem_monsters": ["空泛表达"],
            }
        if task_name == "essay_feedback":
            return {
                "strengths": ["能写清楚发生了什么", "有一处心情表达"],
                "improvements": ["第二段缺少动作细节"],
                "problem_monsters": ["细节缺口"],
                "sentence_notes": ["把“我很开心”换成看到、听到、做到的细节。"],
                "revision_tasks": [
                    {"instruction": "给第二段加一个动作描写", "target": "第二段"}
                ],
            }
        if task_name == "essay_revision_comparison":
            return {
                "encouragement": "你把最重要的画面写清楚了。",
                "improved_dimensions": ["细节更多", "动作更具体"],
                "evidence": ["手心都出汗了", "摇摇晃晃骑过花坛"],
                "next_step": "下一次可以把结尾的感受写得更清楚。",
            }
        raise ValueError(f"Unknown LLM task: {task_name}")


class HttpJsonLLMProvider:
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def complete_json(self, task_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名小学中文表达教练。你必须只输出 JSON，"
                    "不要代写完整作文，只能提供反馈、建议和局部修改方向。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"task_name": task_name, "payload": payload},
                    ensure_ascii=False,
                ),
            },
        ]
        async with httpx.AsyncClient(timeout=30) as client:
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
        if isinstance(content, str):
            return json.loads(content)
        return content
