import json

from sqlmodel import select

from app.api.deps import get_llm_provider
from app.domain.models import LLMCallLog, StudentProfile
from app.domain.seed import seed_demo_data
from app.services.llm_provider import LLMProviderResponse


class RecordingEssayProvider:
    provider_name = "fake-route-provider"
    model_name = "fake-route-model"

    def __init__(self):
        self.calls: list[str] = []

    async def complete_json(self, task_name, payload):
        self.calls.append(task_name)
        if task_name == "essay_feedback":
            parsed = {
                "strengths": ["能写清楚发生了什么", "有一处心情表达"],
                "improvements": ["第二段缺少动作细节"],
                "problem_monsters": ["细节缺口"],
                "sentence_notes": ["把开心换成看到、听到、做到的细节。"],
                "revision_tasks": [
                    {"instruction": "给第二段加一个动作描写", "target": "第二段"}
                ],
            }
        elif task_name == "essay_revision_comparison":
            parsed = {
                "encouragement": "你把最重要的画面写清楚了。",
                "improved_dimensions": ["细节更多"],
                "evidence": ["手心都出汗了"],
                "next_step": "下一次把结尾感受写清楚。",
            }
        else:
            raise AssertionError(f"unexpected task: {task_name}")
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class RecordingSentenceProvider:
    provider_name = "fake-sentence-provider"
    model_name = "fake-sentence-model"

    def __init__(self):
        self.calls: list[str] = []

    async def complete_json(self, task_name, payload):
        self.calls.append(task_name)
        parsed = {
            "encouragement": "你把画面写得更清楚了。",
            "specific_improvement": "加入了可看见的细节",
            "next_step": "再加一个动作，会更生动。",
            "ability_delta": {"expression": 4, "observation": 4},
            "problem_monsters": ["空泛表达"],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


def test_essay_routes_use_provider_dependency_override(session, client):
    parent = seed_demo_data(session)
    student = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent.id)
    ).first()
    provider = RecordingEssayProvider()
    client.app.dependency_overrides[get_llm_provider] = lambda: provider

    start = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
        },
    )
    assert start.status_code == 201

    revision = client.post(
        f"/api/essays/{start.json()['essay']['id']}/revision",
        json={
            "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我骑过了花坛。",
            "completed_tasks": ["给第二段加一个动作描写"],
            "skipped_tasks": [],
            "duration_seconds": 360,
        },
    )
    assert revision.status_code == 201
    assert provider.calls == ["essay_feedback", "essay_revision_comparison"]


def test_sentence_route_uses_provider_dependency_override_and_logs_student_context(session, client):
    parent = seed_demo_data(session)
    student = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent.id)
    ).first()
    provider = RecordingSentenceProvider()
    client.app.dependency_overrides[get_llm_provider] = lambda: provider

    response = client.post(
        f"/api/students/{student.id}/sentences",
        json={
            "source_sentence": "公园很美。",
            "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
            "focus": "加细节",
        },
    )

    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == student.id)).all()
    assert response.status_code == 201
    assert provider.calls == ["sentence_upgrade_feedback"]
    assert logs[0].task_name == "sentence_upgrade_feedback"
    assert logs[0].provider == "fake-sentence-provider"
