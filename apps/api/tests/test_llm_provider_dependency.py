from sqlmodel import select

from app.api.deps import get_ai_task_runner
from app.domain.models import LLMCallLog
from app.services.ai_runner import AITaskResult
from app.services.ai_tasks import log_llm_result
from app.services.llm_contracts import (
    EssayFeedback,
    EssayRevisionComparison,
    RevisionTask,
    SentenceFeedback,
)
from tests.conftest import create_authenticated_family


class RecordingEssayRunner:
    provider_name = "fake-route-provider"
    model_name = "fake-route-model"

    def __init__(self):
        self.calls: list[str] = []

    async def run(self, **kwargs):
        task_name = kwargs["task_name"]
        self.calls.append(task_name)
        if task_name == "essay_feedback":
            output = EssayFeedback(
                strengths=["能写清楚发生了什么", "有一处心情表达"],
                improvements=["第二段缺少动作细节"],
                problem_monsters=["细节缺口"],
                sentence_notes=["把开心换成看到、听到、做到的细节。"],
                revision_tasks=[
                    RevisionTask(instruction="给第二段加一个动作描写", target="第二段")
                ],
            )
        elif task_name == "essay_revision_comparison":
            output = EssayRevisionComparison(
                encouragement="你把最重要的画面写清楚了。",
                improved_dimensions=["细节更多"],
                evidence=["手心都出汗了"],
                next_step="下一次把结尾感受写清楚。",
            )
        else:
            raise AssertionError(f"unexpected task: {task_name}")
        log = log_llm_result(
            session=kwargs["session"],
            student_id=kwargs["student_id"],
            task_type=kwargs["task_type"],
            task_name=task_name,
            prompt_key=kwargs["prompt_key"],
            provider=self.provider_name,
            model=self.model_name,
            prompt_version=kwargs["prompt_version"],
            input_summary=kwargs["input_summary"],
            raw_response="{}",
            output_json=output.model_dump(),
            validation_ok=True,
            error_message="",
            retry_count=0,
        )
        return AITaskResult(output=output, log=log, status="ok")


class RecordingSentenceRunner:
    provider_name = "fake-sentence-provider"
    model_name = "fake-sentence-model"

    def __init__(self):
        self.calls: list[str] = []

    async def run(self, **kwargs):
        task_name = kwargs["task_name"]
        self.calls.append(task_name)
        output = SentenceFeedback(
            encouragement="你把画面写得更清楚了。",
            specific_improvement="加入了可看见的细节",
            next_step="再加一个动作，会更生动。",
            ability_delta={"expression": 4, "observation": 4},
            problem_monsters=["空泛表达"],
        )
        log = log_llm_result(
            session=kwargs["session"],
            student_id=kwargs["student_id"],
            task_type=kwargs["task_type"],
            task_name=task_name,
            prompt_key=kwargs["prompt_key"],
            provider=self.provider_name,
            model=self.model_name,
            prompt_version=kwargs["prompt_version"],
            input_summary=kwargs["input_summary"],
            raw_response="{}",
            output_json=output.model_dump(),
            validation_ok=True,
            error_message="",
            retry_count=0,
        )
        return AITaskResult(output=output, log=log, status="ok")


def test_essay_routes_use_runner_dependency_override(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    runner = RecordingEssayRunner()
    client.app.dependency_overrides[get_ai_task_runner] = lambda: runner

    start = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
            "client_submission_id": "provider-dependency-essay",
        },
    )
    assert start.status_code == 201

    revision = client.post(
        f"/api/essays/{start.json()['essay']['id']}/revision",
        json={
            "base_version_id": start.json()["first_draft"]["id"],
            "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我骑过了花坛。",
            "idempotency_key": "runner-override-revision",
            "completed_tasks": ["给第二段加一个动作描写"],
            "skipped_tasks": [],
            "duration_seconds": 360,
        },
    )
    assert revision.status_code == 201
    assert runner.calls == ["essay_feedback", "essay_revision_comparison"]


def test_sentence_route_uses_runner_dependency_override_and_logs_student_context(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    runner = RecordingSentenceRunner()
    client.app.dependency_overrides[get_ai_task_runner] = lambda: runner

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
    assert runner.calls == ["sentence_upgrade_feedback"]
    assert logs[0].task_name == "sentence_upgrade_feedback"
    assert logs[0].provider == "fake-sentence-provider"
