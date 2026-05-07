from typing import Any, Protocol


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
                "problem_monsters": ["细节缺席"],
                "sentence_notes": [
                    "把“我很开心”换成看到、听到、做到的细节。"
                ],
                "revision_tasks": [
                    {"instruction": "给第二段加一个动作描写", "target": "第二段"}
                ],
            }
        raise ValueError(f"Unknown LLM task: {task_name}")
