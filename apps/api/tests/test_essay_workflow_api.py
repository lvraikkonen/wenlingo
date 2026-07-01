from datetime import timedelta
from hashlib import sha256

import pytest
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.deps import AITaskRunner, get_ai_task_runner
from app.api.routes.essays import EssayRevisionCreate, submit_revision
from app.core.config import get_settings
from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    Essay,
    EssayRevisionAttempt,
    EssayVersion,
    GameEvent,
    LLMCallLog,
    utcnow,
)
from app.services.ai_runner import AITaskResult
from app.services.ai_tasks import log_llm_result
from app.services.essay_archive import REVISION_ATTEMPT_TIMEOUT_SECONDS
from app.services.essay_workflow import draft_ability_deltas
from app.services.llm_contracts import EssayFeedback, EssayRevisionComparison, RevisionTask
from tests.conftest import create_authenticated_family


class RecordingEssayRunner:
    provider_name = "workflow-test-provider"
    model_name = "workflow-test-model"

    def __init__(
        self,
        *,
        fail_comparison: bool = False,
        comparison_validation_ok: bool = True,
        comparison_error_message: str = "",
    ):
        self.fail_comparison = fail_comparison
        self.comparison_validation_ok = comparison_validation_ok
        self.comparison_error_message = comparison_error_message
        self.calls: list[str] = []
        self.sessions_by_task: dict[str, list[object | None]] = {}
        self.in_transaction_by_task: dict[str, list[bool | None]] = {}

    async def run(self, **kwargs):
        task_name = kwargs["task_name"]
        self.calls.append(task_name)
        task_session = kwargs["session"]
        self.sessions_by_task.setdefault(task_name, []).append(task_session)
        self.in_transaction_by_task.setdefault(task_name, []).append(
            task_session.in_transaction() if task_session is not None else None
        )
        if task_name == "essay_feedback":
            output = EssayFeedback(
                strengths=["能写清楚发生了什么", "有一处心情表达"],
                improvements=["第二段缺少动作细节"],
                problem_monsters=["细节缺口"],
                sentence_notes=["把开心换成看到、听到、做到的细节。"],
                revision_tasks=[RevisionTask(instruction="给第二段加一个动作描写", target="第二段")],
            )
        elif task_name == "essay_revision_comparison":
            if self.fail_comparison:
                raise RuntimeError("forced comparison failure")
            output = EssayRevisionComparison(
                encouragement="你把最重要的画面写清楚了。",
                improved_dimensions=["细节更多", "动作更具体"],
                evidence=["手心都出汗了", "摇摇晃晃骑过花坛"],
                next_step="下一次把结尾感受写清楚。",
            )
            validation_ok = self.comparison_validation_ok
            error_message = self.comparison_error_message
        else:
            raise AssertionError(f"unexpected task: {task_name}")
        if task_name != "essay_revision_comparison":
            validation_ok = True
            error_message = ""
        log = None
        if task_session is not None:
            log = log_llm_result(
                session=task_session,
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
                validation_ok=validation_ok,
                error_message=error_message,
                retry_count=0,
            )
        return AITaskResult(output=output, log=log, status="ok")


ROUND_2_CONTENT = (
    "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。"
    "爸爸松手后，我摇摇晃晃骑过了花坛。我开心得跳了起来。"
)
ROUND_3_CONTENT = "孩子自己写的第三稿，加入了动作、心情和更清楚的顺序。"
DIFFERENT_ROUND_3_CONTENT = "孩子这次写了完全不同的第三稿，加入了新的地点、对话和心情。"


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _start_essay(session, client, runner: RecordingEssayRunner | None = None):
    if runner is not None:
        client.app.dependency_overrides[get_ai_task_runner] = lambda: runner
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
        },
    )
    assert start.status_code == 201
    first_draft = session.exec(
        select(EssayVersion).where(EssayVersion.version_label == "first_draft")
    ).one()
    return family, start.json()["essay"]["id"], first_draft


def _revision_payload(
    base_version: EssayVersion,
    *,
    content: str = ROUND_2_CONTENT,
    key: str = "client-key-round-2",
) -> dict:
    return {
        "base_version_id": base_version.id,
        "content": content,
        "idempotency_key": key,
        "completed_tasks": ["把动作写清楚"],
        "skipped_tasks": [],
        "duration_seconds": 180,
    }


def _submit_round_2(session, client, essay_id: str, first_draft: EssayVersion) -> EssayVersion:
    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(first_draft),
    )
    assert response.status_code == 201
    return session.exec(select(EssayVersion).where(EssayVersion.version_label == "revision")).one()


def _manual_version(
    session,
    essay_id: str,
    *,
    round_index: int,
    content: str = ROUND_3_CONTENT,
) -> EssayVersion:
    version = EssayVersion(
        essay_id=essay_id,
        version_label=f"revision_round_{round_index}" if round_index > 2 else "revision",
        round_index=round_index,
        content=content,
        ai_feedback={
            "encouragement": "你继续完成了修改。",
            "improved_dimensions": ["顺序更清楚"],
            "evidence": ["加入了动作"],
            "next_step": "下一次继续补心情。",
        },
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def test_essay_from_existing_draft_feedback_and_revision(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
            "entry": "existing_draft",
        },
    )
    assert start.status_code == 201
    essay_id = start.json()["essay"]["id"]
    assert start.json()["feedback"]["revision_tasks"][0]["instruction"] == "给第二段加一个动作描写"
    first_draft = session.exec(
        select(EssayVersion).where(EssayVersion.version_label == "first_draft")
    ).one()
    assert first_draft.round_index == 1
    saved_essay = session.get(Essay, essay_id)
    assert saved_essay is not None
    assert saved_essay.last_version_submitted_at == first_draft.created_at
    assert saved_essay.updated_at == first_draft.created_at
    draft_history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == first_draft.id)
    ).all()
    assert {(row.ability_name, row.delta, row.source_type) for row in draft_history} == {
        ("expression", 5, TaskType.essay),
        ("structure", 5, TaskType.essay),
    }

    revision = client.post(
        f"/api/essays/{essay_id}/revision",
        json={
            "base_version_id": first_draft.id,
            "content": ROUND_2_CONTENT,
            "idempotency_key": "client-key-existing-workflow",
            "completed_tasks": ["给第二段加一个动作描写"],
            "skipped_tasks": [],
            "duration_seconds": 420,
        },
    )

    assert revision.status_code == 201
    assert revision.json()["comparison"]["improved_dimensions"] == ["细节更多", "动作更具体"]
    assert revision.json()["revision"]["completed_tasks"] == ["给第二段加一个动作描写"]
    assert revision.json()["revision"]["skipped_tasks"] == []
    assert revision.json()["revision"]["duration_seconds"] == 420
    assert revision.json()["revision"]["round_index"] == 2
    assert len(session.exec(select(Essay)).all()) == 1
    assert len(session.exec(select(EssayVersion)).all()) == 2
    event = session.exec(select(GameEvent)).one()
    assert event.xp_delta == 60
    assert event.evidence["completed_task_count"] == 1
    assert event.evidence["completed_tasks"] == ["给第二段加一个动作描写"]
    assert event.evidence["ability_deltas"] == {"revision": 5}
    saved_revision = session.exec(
        select(EssayVersion).where(EssayVersion.version_label == "revision")
    ).one()
    revision_history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == saved_revision.id)
    ).all()
    assert {(row.ability_name, row.delta, row.source_type) for row in revision_history} == {
        ("revision", 5, TaskType.essay),
    }
    assert saved_revision.completed_tasks == ["给第二段加一个动作描写"]
    assert saved_revision.skipped_tasks == []
    assert saved_revision.duration_seconds == 420
    assert saved_revision.llm_call_log_id is not None
    saved_essay = session.get(Essay, essay_id)
    assert saved_essay is not None
    assert saved_essay.last_version_submitted_at == saved_revision.created_at
    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == student.id)).all()
    assert {log.task_name for log in logs} == {"essay_feedback", "essay_revision_comparison"}
    assert {log.task_type for log in logs} == {TaskType.essay}


def test_essay_create_rejects_overlong_title_and_draft(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    title_response = client.post(
        f"/api/students/{student.id}/essays",
        json={"title": "题" * 101, "draft": "我学会了骑车。刚开始我很害怕。后来我会了。", "entry": "existing_draft"},
    )
    draft_response = client.post(
        f"/api/students/{student.id}/essays",
        json={"title": "我学会了骑车", "draft": "文" * 3001, "entry": "existing_draft"},
    )

    assert title_response.status_code == 422
    assert draft_response.status_code == 422


def test_draft_ability_deltas_use_five_unless_exactly_three_improvements():
    assert draft_ability_deltas(2) == {"expression": 5, "structure": 5}
    assert draft_ability_deltas(3) == {"expression": 3, "structure": 3}
    assert draft_ability_deltas(4) == {"expression": 5, "structure": 5}


def test_revision_without_first_draft_returns_conflict(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    essay = Essay(student_id=student.id, title="我学会了骑车", status="revision_requested")
    session.add(essay)
    session.commit()

    response = client.post(
        f"/api/essays/{essay.id}/revision",
        json={
            "base_version_id": "missing-first-draft",
            "content": "我学会了骑车。刚开始我很害怕。后来我慢慢练习，终于能稳稳骑过小路。",
            "idempotency_key": "client-key-no-draft",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "first draft not found"
    assert len(session.exec(select(EssayVersion)).all()) == 0
    assert len(session.exec(select(GameEvent)).all()) == 0


def test_revision_missing_student_or_ability_returns_not_found(session, client):
    essay = Essay(student_id="missing-student", title="我学会了骑车", status="revision_requested")
    session.add(essay)
    session.flush()
    first_draft = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
    )
    session.add(first_draft)
    session.commit()

    response = client.post(
        f"/api/essays/{essay.id}/revision",
        json={
            "base_version_id": first_draft.id,
            "content": "我学会了骑车。刚开始我很害怕。后来我慢慢练习，终于能稳稳骑过小路。",
            "idempotency_key": "client-key-missing-student",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "student not found"
    assert len(session.exec(select(GameEvent)).all()) == 0


def test_second_draft_keeps_full_settlement_behavior(session, client):
    runner = RecordingEssayRunner()
    family, essay_id, first_draft = _start_essay(session, client, runner)
    student = family["student"]

    first_revision = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(first_draft),
    )

    assert first_revision.status_code == 201
    assert first_revision.json()["settlement"]["xp_delta"] == 60
    assert len(session.exec(select(EssayVersion)).all()) == 2
    assert len(session.exec(select(GameEvent)).all()) == 1
    assert len(session.exec(select(AbilityHistory)).all()) == 3
    saved_revision = session.exec(
        select(EssayVersion).where(EssayVersion.version_label == "revision")
    ).one()
    assert saved_revision.round_index == 2
    saved_essay = session.get(Essay, essay_id)
    assert saved_essay is not None
    assert saved_essay.last_version_submitted_at == saved_revision.created_at
    assert runner.sessions_by_task["essay_revision_comparison"] == [session]
    assert runner.in_transaction_by_task["essay_revision_comparison"] == [False]
    revision_history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == saved_revision.id)
    ).all()
    assert {(row.ability_name, row.delta) for row in revision_history} == {("revision", 5)}
    session.refresh(student)
    assert student.xp == 60


def test_third_draft_appends_round_three_without_full_settlement(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    comparison_call_count = runner.calls.count("essay_revision_comparison")

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 201
    assert response.json().get("settlement") is None
    assert response.json()["revision"]["version_label"] == "revision_round_3"
    assert response.json()["revision"]["round_index"] == 3
    assert len(session.exec(select(EssayVersion)).all()) == 3
    assert len(session.exec(select(GameEvent)).all()) == 1
    assert runner.calls.count("essay_revision_comparison") == comparison_call_count + 1
    assert runner.sessions_by_task["essay_revision_comparison"][-1] is session
    assert runner.in_transaction_by_task["essay_revision_comparison"][-1] is False
    round_3 = session.exec(
        select(EssayVersion).where(EssayVersion.version_label == "revision_round_3")
    ).one()
    assert round_3.llm_call_log_id is not None
    saved_essay = session.get(Essay, essay_id)
    assert saved_essay is not None
    assert saved_essay.last_version_submitted_at == round_3.created_at
    revision_history = session.exec(
        select(AbilityHistory).where(AbilityHistory.source_id == round_3.id)
    ).all()
    assert all(row.ability_name == "revision" and row.delta <= 2 for row in revision_history)


def test_lost_response_retry_returns_completed_attempt_even_after_latest_advances(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    round_3 = _manual_version(session, essay_id, round_index=3)
    _manual_version(session, essay_id, round_index=4, content="第四稿继续补充了场景和心情。")
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3",
        status="completed",
        new_version_id=round_3.id,
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 201
    assert response.json()["revision"]["id"] == round_3.id
    assert response.json()["revision"]["version_label"] == "revision_round_3"
    assert runner.calls == []
    assert len(session.exec(select(EssayVersion)).all()) == 4


def test_completed_round_two_replay_returns_original_settlement_without_llm(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    first_response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(first_draft),
    )
    assert first_response.status_code == 201
    assert first_response.json()["settlement"]["xp_delta"] == 60
    runner.calls.clear()

    replay_response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(first_draft),
    )

    assert replay_response.status_code == 201
    assert replay_response.json()["revision"]["id"] == first_response.json()["revision"]["id"]
    assert replay_response.json()["settlement"]["xp_delta"] == 60
    assert replay_response.json()["settlement"]["id"] == first_response.json()["settlement"]["id"]
    assert len(session.exec(select(GameEvent)).all()) == 1
    assert runner.calls == []


def test_same_pending_idempotency_key_returns_202_without_second_llm_call(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3",
        status="pending_comparison",
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "pending_comparison"
    assert response.json()["attempt_id"] == attempt.id
    assert runner.calls == []


def test_same_pending_idempotency_key_with_different_content_returns_409(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3",
        status="pending_comparison",
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=DIFFERENT_ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency key content mismatch"
    assert runner.calls == []


def test_same_completed_idempotency_key_with_different_content_returns_409(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    round_3 = _manual_version(session, essay_id, round_index=3)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3",
        status="completed",
        new_version_id=round_3.id,
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=DIFFERENT_ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency key content mismatch"
    assert runner.calls == []


def test_same_failed_idempotency_key_with_different_content_returns_409(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3",
        status="comparison_failed",
        error_code="comparison_failed",
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=DIFFERENT_ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency key content mismatch"
    assert runner.calls == []


def test_different_idempotency_keys_same_target_round_same_content_returns_pending(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3-a",
        status="pending_comparison",
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3-b",
        ),
    )

    assert response.status_code == 202
    assert response.json()["attempt_id"] == attempt.id
    assert runner.calls == []


def test_different_idempotency_keys_same_target_round_different_content_returns_409(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3-a",
        status="pending_comparison",
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=DIFFERENT_ROUND_3_CONTENT,
            key="client-key-round-3-b",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency key content mismatch"
    assert runner.calls == []


def test_stale_pending_attempt_is_marked_failed_and_can_be_retried(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    stale_time = utcnow() - timedelta(seconds=REVISION_ATTEMPT_TIMEOUT_SECONDS + 1)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3",
        status="pending_comparison",
        created_at=stale_time,
        updated_at=stale_time,
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "comparison_failed"
    session.refresh(attempt)
    assert attempt.status == "comparison_failed"
    assert attempt.error_code == "attempt_timeout"
    assert attempt.submitted_content == ROUND_3_CONTENT
    assert runner.calls == []


def test_stale_base_version_returns_409_before_llm_call_after_idempotency_lookup(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    _manual_version(session, essay_id, round_index=3)
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-stale-base",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "base version is stale"
    assert runner.calls == []


def test_ai_comparison_failure_preserves_revision_attempt_content(session, client):
    runner = RecordingEssayRunner(fail_comparison=True)
    _, essay_id, first_draft = _start_essay(session, client, runner)
    runner.fail_comparison = False
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    runner.fail_comparison = True
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 502
    attempt = session.exec(
        select(EssayRevisionAttempt).where(EssayRevisionAttempt.idempotency_key == "client-key-round-3")
    ).one()
    assert attempt.status == "comparison_failed"
    assert attempt.error_code == "comparison_failed"
    assert attempt.submitted_content == ROUND_3_CONTENT


def test_ai_validation_failure_preserves_attempt_without_revision_or_settlement(session, client):
    runner = RecordingEssayRunner(
        comparison_validation_ok=False,
        comparison_error_message="validation failed after fallback",
    )
    family, essay_id, first_draft = _start_essay(session, client, runner)
    student = family["student"]
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(first_draft),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "这次 AI 对比没有完成，请稍后重试。"
    attempt = session.exec(
        select(EssayRevisionAttempt).where(EssayRevisionAttempt.idempotency_key == "client-key-round-2")
    ).one()
    assert attempt.status == "comparison_failed"
    assert attempt.error_code == "comparison_failed"
    assert attempt.submitted_content == ROUND_2_CONTENT
    assert session.exec(select(EssayVersion).where(EssayVersion.version_label == "revision")).all() == []
    assert session.exec(select(GameEvent)).all() == []
    revision_history = session.exec(
        select(AbilityHistory).where(AbilityHistory.ability_name == "revision")
    ).all()
    assert revision_history == []
    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == student.id)).all()
    comparison_logs = [log for log in logs if log.task_name == "essay_revision_comparison"]
    assert len(comparison_logs) == 1
    assert comparison_logs[0].validation_ok is False
    assert comparison_logs[0].error_message == "validation failed after fallback"


def test_retry_failed_revision_attempt_appends_next_version(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-round-3",
        status="comparison_failed",
        error_code="comparison_failed",
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()
    runner.sessions_by_task.clear()
    runner.in_transaction_by_task.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision-attempts/{attempt.id}/retry-comparison",
    )

    assert response.status_code == 201
    assert response.json()["revision"]["version_label"] == "revision_round_3"
    assert response.json()["revision"]["content"] == ROUND_3_CONTENT
    assert runner.calls == ["essay_revision_comparison"]
    assert runner.sessions_by_task["essay_revision_comparison"] == [session]
    assert runner.in_transaction_by_task["essay_revision_comparison"] == [False]
    session.refresh(attempt)
    assert attempt.status == "completed"
    assert attempt.new_version_id == response.json()["revision"]["id"]
    assert attempt.submitted_content is None
    round_3 = session.get(EssayVersion, attempt.new_version_id)
    saved_essay = session.get(Essay, essay_id)
    assert round_3 is not None
    assert round_3.llm_call_log_id is not None
    assert saved_essay is not None
    assert saved_essay.last_version_submitted_at == round_3.created_at


def test_completion_phase_failure_marks_attempt_failed_after_llm(session, client, monkeypatch):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    comparison_log_count = len(
        session.exec(
            select(LLMCallLog).where(LLMCallLog.task_name == "essay_revision_comparison")
        ).all()
    )
    runner.calls.clear()
    from app.api.routes import essays as essay_routes

    monkeypatch.setattr(
        essay_routes,
        "get_version_label_for_round",
        lambda _round_index: "revision",
    )

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert runner.calls == ["essay_revision_comparison"]
    attempt = session.exec(
        select(EssayRevisionAttempt).where(EssayRevisionAttempt.idempotency_key == "client-key-round-3")
    ).one()
    assert attempt.status == "comparison_failed"
    assert attempt.error_code == "completion_failed"
    assert attempt.submitted_content == ROUND_3_CONTENT
    assert attempt.new_version_id is None
    comparison_logs = session.exec(
        select(LLMCallLog).where(LLMCallLog.task_name == "essay_revision_comparison")
    ).all()
    assert len(comparison_logs) == comparison_log_count + 1


def test_slow_completion_after_attempt_timeout_does_not_create_revision(session, client, monkeypatch):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    comparison_log_count = len(
        session.exec(
            select(LLMCallLog).where(LLMCallLog.task_name == "essay_revision_comparison")
        ).all()
    )
    version_count = len(session.exec(select(EssayVersion).where(EssayVersion.essay_id == essay_id)).all())
    runner.calls.clear()
    commit_calls = {"count": 0}
    original_commit = session.commit

    def timeout_after_llm_log_commit():
        commit_calls["count"] += 1
        original_commit()
        if commit_calls["count"] == 4:
            attempt = session.exec(
                select(EssayRevisionAttempt).where(
                    EssayRevisionAttempt.idempotency_key == "client-key-round-3"
                )
            ).one()
            attempt.status = "comparison_failed"
            attempt.error_code = "attempt_timeout"
            attempt.updated_at = utcnow()
            session.add(attempt)
            original_commit()

    monkeypatch.setattr(session, "commit", timeout_after_llm_log_commit)

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "comparison_failed"
    assert runner.calls == ["essay_revision_comparison"]
    attempt = session.exec(
        select(EssayRevisionAttempt).where(EssayRevisionAttempt.idempotency_key == "client-key-round-3")
    ).one()
    assert attempt.status == "comparison_failed"
    assert attempt.error_code == "attempt_timeout"
    assert attempt.submitted_content == ROUND_3_CONTENT
    assert attempt.new_version_id is None
    assert len(session.exec(select(EssayVersion).where(EssayVersion.essay_id == essay_id)).all()) == version_count
    comparison_logs = session.exec(
        select(LLMCallLog).where(LLMCallLog.task_name == "essay_revision_comparison")
    ).all()
    assert len(comparison_logs) == comparison_log_count + 1


def test_completion_race_after_pending_check_does_not_overwrite_failed_attempt(
    session,
    client,
    monkeypatch,
):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    comparison_log_count = len(
        session.exec(
            select(LLMCallLog).where(LLMCallLog.task_name == "essay_revision_comparison")
        ).all()
    )
    version_count = len(session.exec(select(EssayVersion).where(EssayVersion.essay_id == essay_id)).all())
    runner.calls.clear()

    from app.api.routes import essays as essay_routes

    original_conflict_response = essay_routes._completion_attempt_conflict_response

    def timeout_after_pending_check(attempt, **kwargs):
        response = original_conflict_response(attempt, **kwargs)
        if response is None and attempt.idempotency_key == "client-key-round-3":
            session.execute(
                update(EssayRevisionAttempt)
                .where(EssayRevisionAttempt.id == attempt.id)
                .values(
                    status="comparison_failed",
                    error_code="attempt_timeout",
                    updated_at=utcnow(),
                )
                .execution_options(synchronize_session=False)
            )
            session.commit()
        return response

    monkeypatch.setattr(
        essay_routes,
        "_completion_attempt_conflict_response",
        timeout_after_pending_check,
    )

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "comparison_failed"
    assert response.json()["error_code"] == "attempt_timeout"
    assert runner.calls == ["essay_revision_comparison"]
    attempt = session.exec(
        select(EssayRevisionAttempt).where(EssayRevisionAttempt.idempotency_key == "client-key-round-3")
    ).one()
    assert attempt.status == "comparison_failed"
    assert attempt.error_code == "attempt_timeout"
    assert attempt.submitted_content == ROUND_3_CONTENT
    assert attempt.new_version_id is None
    assert len(session.exec(select(EssayVersion).where(EssayVersion.essay_id == essay_id)).all()) == version_count
    comparison_logs = session.exec(
        select(LLMCallLog).where(LLMCallLog.task_name == "essay_revision_comparison")
    ).all()
    assert len(comparison_logs) == comparison_log_count + 1


def test_reservation_integrity_conflict_checks_content_hash_before_pending_response(
    session,
    client,
    monkeypatch,
):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    runner.calls.clear()
    commit_calls = {"count": 0}
    original_commit = session.commit

    def flaky_commit():
        commit_calls["count"] += 1
        if commit_calls["count"] == 3:
            session.rollback()
            session.add(
                EssayRevisionAttempt(
                    essay_id=essay_id,
                    base_version_id=round_2.id,
                    target_round_index=3,
                    submitted_content=ROUND_3_CONTENT,
                    submitted_content_hash=_content_hash(ROUND_3_CONTENT),
                    idempotency_key="client-key-round-3",
                    status="pending_comparison",
                )
            )
            original_commit()
            raise IntegrityError("forced reservation race", None, None)
        original_commit()

    monkeypatch.setattr(session, "commit", flaky_commit)

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=DIFFERENT_ROUND_3_CONTENT,
            key="client-key-round-3",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency key content mismatch"
    assert runner.calls == []


def test_reservation_integrity_conflict_checks_content_hash_before_completed_response(
    session,
    client,
    monkeypatch,
):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    round_3 = EssayVersion(
        essay_id=essay_id,
        version_label="revision_round_3",
        round_index=3,
        content=ROUND_3_CONTENT,
        ai_feedback={
            "encouragement": "你继续完成了修改。",
            "improved_dimensions": ["顺序更清楚"],
            "evidence": ["加入了动作"],
            "next_step": "下一次继续补心情。",
        },
    )
    runner.calls.clear()
    commit_calls = {"count": 0}
    original_commit = session.commit

    def flaky_commit():
        commit_calls["count"] += 1
        if commit_calls["count"] == 3:
            session.rollback()
            session.add(round_3)
            session.flush()
            session.add(
                EssayRevisionAttempt(
                    essay_id=essay_id,
                    base_version_id=round_2.id,
                    target_round_index=3,
                    submitted_content_hash=_content_hash(ROUND_3_CONTENT),
                    idempotency_key="client-key-round-3",
                    status="completed",
                    new_version_id=round_3.id,
                )
            )
            original_commit()
            raise IntegrityError("forced completed reservation race", None, None)
        original_commit()

    monkeypatch.setattr(session, "commit", flaky_commit)

    response = client.post(
        f"/api/essays/{essay_id}/revision",
        json=_revision_payload(
            round_2,
            content=DIFFERENT_ROUND_3_CONTENT,
            key="client-key-round-3-b",
        ),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency key content mismatch"
    assert runner.calls == []


def test_retry_failed_revision_attempt_conflict_returns_pending_before_llm(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    failed_attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash="failed-hash",
        idempotency_key="client-key-failed-round-3",
        status="comparison_failed",
        error_code="comparison_failed",
    )
    pending_attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash="pending-hash",
        idempotency_key="client-key-pending-round-3",
        status="pending_comparison",
    )
    session.add(failed_attempt)
    session.add(pending_attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision-attempts/{failed_attempt.id}/retry-comparison",
    )

    assert response.status_code == 202
    assert response.json()["attempt_id"] == pending_attempt.id
    assert runner.calls == []
    session.refresh(failed_attempt)
    assert failed_attempt.status == "comparison_failed"


def test_retry_endpoint_marks_own_stale_pending_attempt_failed(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    stale_time = utcnow() - timedelta(seconds=REVISION_ATTEMPT_TIMEOUT_SECONDS + 1)
    attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-stale-pending-round-3",
        status="pending_comparison",
        created_at=stale_time,
        updated_at=stale_time,
    )
    session.add(attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision-attempts/{attempt.id}/retry-comparison",
    )

    assert response.status_code == 409
    assert response.json()["status"] == "comparison_failed"
    assert response.json()["attempt_id"] == attempt.id
    assert response.json()["error_code"] == "attempt_timeout"
    assert runner.calls == []
    session.refresh(attempt)
    assert attempt.status == "comparison_failed"
    assert attempt.error_code == "attempt_timeout"
    assert attempt.submitted_content == ROUND_3_CONTENT


def test_retry_failed_revision_attempt_marks_stale_active_pending_failed(session, client):
    runner = RecordingEssayRunner()
    _, essay_id, first_draft = _start_essay(session, client, runner)
    round_2 = _submit_round_2(session, client, essay_id, first_draft)
    stale_time = utcnow() - timedelta(seconds=REVISION_ATTEMPT_TIMEOUT_SECONDS + 1)
    failed_attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-failed-round-3",
        status="comparison_failed",
        error_code="comparison_failed",
    )
    pending_attempt = EssayRevisionAttempt(
        essay_id=essay_id,
        base_version_id=round_2.id,
        target_round_index=3,
        submitted_content=ROUND_3_CONTENT,
        submitted_content_hash=_content_hash(ROUND_3_CONTENT),
        idempotency_key="client-key-stale-active-round-3",
        status="pending_comparison",
        created_at=stale_time,
        updated_at=stale_time,
    )
    session.add(failed_attempt)
    session.add(pending_attempt)
    session.commit()
    runner.calls.clear()

    response = client.post(
        f"/api/essays/{essay_id}/revision-attempts/{failed_attempt.id}/retry-comparison",
    )

    assert response.status_code == 409
    assert response.json()["status"] == "comparison_failed"
    assert response.json()["attempt_id"] == pending_attempt.id
    assert response.json()["error_code"] == "attempt_timeout"
    assert runner.calls == []
    session.refresh(failed_attempt)
    session.refresh(pending_attempt)
    assert failed_attempt.status == "comparison_failed"
    assert pending_attempt.status == "comparison_failed"
    assert pending_attempt.error_code == "attempt_timeout"


@pytest.mark.asyncio
async def test_revision_integrity_conflict_returns_409_before_settlement(session):
    family = create_authenticated_family(session)
    student = family["student"]
    essay = Essay(student_id=student.id, title="我学会了骑车", status="revision_requested")
    session.add(essay)
    session.flush()
    first_draft = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
    )
    session.add(first_draft)
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            round_index=2,
            content="我学会了骑车。第一次修改已经保存。",
        )
    )
    session.commit()
    xp_before = student.xp

    with pytest.raises(HTTPException) as exc_info:
        await submit_revision(
            essay.id,
            EssayRevisionCreate(
                base_version_id=first_draft.id,
                content=ROUND_2_CONTENT,
                idempotency_key="client-key-integrity-conflict",
            ),
            session,
            AITaskRunner(settings=get_settings()),
            get_settings(),
        )

    assert exc_info.value.status_code == 409
    assert len(session.exec(select(GameEvent)).all()) == 0
    assert len(session.exec(select(AbilityHistory)).all()) == 0
    session.refresh(student)
    assert student.xp == xp_before
