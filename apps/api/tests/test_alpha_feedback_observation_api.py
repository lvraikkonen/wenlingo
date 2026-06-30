from datetime import datetime
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import select

from app.api.deps import get_ai_task_runner, get_db_session
from app.api.routes import alpha as alpha_routes
from app.api.routes import assessment as assessment_routes
from app.api.routes import essays as essay_routes
from app.api.routes import sentences as sentence_routes
from app.core.config import get_settings
from app.domain.models import (
    AlphaInviteCode,
    Assessment,
    Essay,
    EssayVersion,
    FeedbackReaction,
    ParentFeedback,
    ParentAccount,
    ParentUser,
    ProductEvent,
    SentenceTraining,
    StudentProfile,
    utcnow,
)
from app.main import create_app
from app.services.ai_runner import run_ai_task


def hash_code(code: str) -> str:
    return sha256(code.strip().upper().encode("utf-8")).hexdigest()


def create_invite(session, code: str = "ALPHA-001", status: str = "issued"):
    invite = AlphaInviteCode(
        code_hash=hash_code(code),
        label="家庭 01",
        status=status,
        issued_to_note="manual test",
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def create_parent(client, session, code: str = "ALPHA-001") -> dict:
    create_invite(session, code=code)
    response = client.post(
        "/api/alpha/parents",
        json={
            "display_name": "测试家长",
            "invite_code": code,
            "alpha_session_id": "session-test",
        },
    )
    assert response.status_code == 201
    return response.json()["parent"]


def create_child(client, parent_id: str, nickname: str = "小文") -> dict:
    response = client.post(
        f"/api/alpha/parents/{parent_id}/children",
        json={"nickname": nickname, "grade": 4},
    )
    assert response.status_code == 201
    return response.json()["child"]


def create_parent_and_child(client, session, code: str = "ALPHA-001"):
    parent = create_parent(client, session, code=code)
    child = create_child(client, parent["id"])
    return parent, child


def contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(contains_key(child, key) for child in value.values())
    if isinstance(value, list):
        return any(contains_key(child, key) for child in value)
    return False


def test_scaffold_selected_product_event_contract_preserves_scaffold_payload(session):
    payload = {
        "essay_id": "essay-1",
        "step": "scaffold_selection",
        "topic_type": "person_portrait",
        "topic_variant": "default",
        "scaffold_template_version": "person_portrait.default.v0.6b.1",
        "selection_source": "ai_suggested",
        "override_reason": "suggestion_accepted",
        "accepted_suggestion_id": "suggestion-1",
        "unsupported_future_type": "reading_response_recommendation",
        "unsupported_override": True,
        "unsafe_key": "drop me",
    }

    event = alpha_routes.record_product_event(
        session,
        "scaffold_selected",
        payload=payload,
    )
    session.commit()
    session.refresh(event)

    assert event.payload == {
        "essay_id": "essay-1",
        "step": "scaffold_selection",
        "topic_type": "person_portrait",
        "topic_variant": "default",
        "scaffold_template_version": "person_portrait.default.v0.6b.1",
        "selection_source": "ai_suggested",
        "override_reason": "suggestion_accepted",
        "accepted_suggestion_id": "suggestion-1",
        "unsupported_future_type": "reading_response_recommendation",
        "unsupported_override": True,
    }


class ProviderFailureFallbackRunner:
    provider_name = "fake"
    model_name = "provider-failure-fallback"

    async def run(self, **kwargs):
        return await run_ai_task(
            settings=get_settings(),
            primary_provider=self,
            fallback_provider=self,
            **kwargs,
        )

    async def complete_json(self, task_name, payload):
        raise RuntimeError(f"{task_name} provider failed")


def test_invite_validation_accepts_issued_code_and_records_event(session, client):
    invite = create_invite(session, "ALPHA-001")

    response = client.post(
        "/api/alpha/invites/validate",
        json={"code": " alpha-001 ", "alpha_session_id": "session-1"},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["invite_id"] == invite.id
    assert response.json()["label"] == "家庭 01"
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "invite_code_validated")
    ).one()
    assert event.invite_code_id == invite.id
    assert event.alpha_session_id == "session-1"
    assert event.payload == {"status": "validated"}


def test_invite_validation_rejects_consumed_disabled_and_missing_codes(session, client):
    create_invite(session, "ALPHA-CONSUMED", status="consumed")
    create_invite(session, "ALPHA-DISABLED", status="disabled")

    for code in ["ALPHA-CONSUMED", "ALPHA-DISABLED", "ALPHA-MISSING"]:
        response = client.post("/api/alpha/invites/validate", json={"code": code})

        assert response.status_code == 400
        assert response.json()["detail"] == "invite code is not available"

    events = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "invite_code_rejected")
    ).all()
    assert [event.payload for event in events] == [
        {"status": "rejected", "error_category": "not_available"},
        {"status": "rejected", "error_category": "not_available"},
        {"status": "rejected", "error_category": "not_available"},
    ]


def test_parent_creation_requires_valid_invite_code_and_consumes_once(session, client):
    invite = create_invite(session, "ALPHA-001")

    response = client.post(
        "/api/alpha/parents",
        json={
            "display_name": "测试家长",
            "invite_code": "ALPHA-001",
            "alpha_session_id": "session-parent",
        },
    )

    assert response.status_code == 201
    parent = response.json()["parent"]
    session.refresh(invite)
    assert invite.status == "consumed"
    assert invite.consumed_by_parent_id == parent["id"]
    assert invite.consumed_at is not None
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "alpha_parent_created")
    ).one()
    assert event.payload == {"status": "created"}

    response = client.post(
        "/api/alpha/parents",
        json={"display_name": "另一位家长", "invite_code": "ALPHA-001"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invite code is not available"


def test_parent_creation_rejects_invite_consumed_after_lookup(
    session, client, monkeypatch
):
    create_invite(session, "ALPHA-RACE")
    original_lookup = alpha_routes._get_available_invite

    def consume_after_lookup(db_session, code):
        invite = original_lookup(db_session, code)
        if invite:
            db_session.execute(
                update(AlphaInviteCode)
                .where(AlphaInviteCode.id == invite.id)
                .values(status="consumed")
            )
            db_session.flush()
        return invite

    monkeypatch.setattr(alpha_routes, "_get_available_invite", consume_after_lookup)

    response = client.post(
        "/api/alpha/parents",
        json={"display_name": "竞态家长", "invite_code": "ALPHA-RACE"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invite code is not available"
    assert session.exec(select(ParentUser)).all() == []
    assert session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "alpha_parent_created")
    ).all() == []


def test_product_event_endpoint_allows_only_safe_p0_events(client):
    response = client.post(
        "/api/alpha/events",
        json={"event_type": "parent_children_viewed", "alpha_session_id": "session-1"},
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True}

    response = client.post("/api/alpha/events", json={"event_type": "unknown_event"})

    assert response.status_code in {400, 422}


def test_product_event_payload_is_sanitized(session, client):
    response = client.post(
        "/api/alpha/events",
        json={
            "event_type": "parent_children_viewed",
            "payload": {
                "path": "/parent/children",
                "status": "ok",
                "essay_text": "private draft",
                "ai_feedback": {"secret": True},
                "phone": "13800000000",
            },
        },
    )

    assert response.status_code == 201
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "parent_children_viewed")
    ).one()
    assert event.payload == {"path": "/parent/children", "status": "ok"}


def test_product_event_payload_drops_scalar_invite_code_values(session, client):
    response = client.post(
        "/api/alpha/events",
        json={
            "event_type": "alpha_start_viewed",
            "payload": {
                "path": "/alpha/start?code=ALPHA-001",
                "status": "ALPHA-001",
                "error_category": "bad code ALPHA-SECRET-123",
                "target_type": "viewed",
                "target_id": 123,
                "summary_viewed": True,
            },
        },
    )

    assert response.status_code == 201
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "alpha_start_viewed")
    ).one()
    assert event.payload == {
        "target_type": "viewed",
        "target_id": 123,
        "summary_viewed": True,
    }
    persisted_payload = str(event.payload)
    assert "ALPHA-001" not in persisted_payload
    assert "ALPHA-SECRET-123" not in persisted_payload
    assert "code=" not in persisted_payload


def test_product_event_payload_sanitizes_nested_sensitive_keys(session, client):
    response = client.post(
        "/api/alpha/events",
        json={
            "event_type": "alpha_start_viewed",
            "payload": {
                "status": {
                    "value": "viewed",
                    "essay_text": "must not persist",
                    "phone": "must not persist",
                    "invite_code": "ALPHA-001",
                    "code": "ALPHA-001",
                    "raw_code": "ALPHA-001",
                    "short_writing": "must not persist",
                    "school": "must not persist",
                    "address": "must not persist",
                    "photo": "must not persist",
                },
                "path": "/alpha/start",
                "ai_feedback": "must not persist",
            },
        },
    )

    assert response.status_code == 201
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "alpha_start_viewed")
    ).one()
    assert event.payload["path"] == "/alpha/start"
    assert not contains_key(event.payload, "essay_text")
    assert not contains_key(event.payload, "ai_feedback")
    assert not contains_key(event.payload, "phone")
    assert not contains_key(event.payload, "invite_code")
    assert not contains_key(event.payload, "code")
    assert not contains_key(event.payload, "raw_code")
    assert not contains_key(event.payload, "short_writing")
    assert not contains_key(event.payload, "school")
    assert not contains_key(event.payload, "address")
    assert not contains_key(event.payload, "photo")


def test_assessment_completion_records_product_event(session, client):
    _, child = create_parent_and_child(client, session)

    response = client.post(
        f"/api/students/{child['id']}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
            "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
        },
    )

    assert response.status_code == 201
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "assessment_completed")
    ).one()
    assert event.student_id == child["id"]
    assert event.payload == {
        "target_type": "assessment",
        "target_id": response.json()["assessment"]["id"],
        "task_type": "assessment",
        "status": "completed",
    }
    assert not contains_key(event.payload, "short_writing")
    assert not contains_key(event.payload, "sentence_after")
    assert not contains_key(event.payload, "ai_feedback")
    assert not contains_key(event.payload, "feedback")


def test_sentence_completion_records_product_event(session, client):
    _, child = create_parent_and_child(client, session)

    response = client.post(
        f"/api/students/{child['id']}/sentences",
        json={
            "source_sentence": "公园很美。",
            "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
            "focus": "加细节",
        },
    )

    assert response.status_code == 201
    event = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "sentence_training_completed"
        )
    ).one()
    assert event.student_id == child["id"]
    assert event.payload == {
        "target_type": "sentence_training",
        "target_id": response.json()["training"]["id"],
        "task_type": "sentence",
        "status": "completed",
    }
    assert not contains_key(event.payload, "source_sentence")
    assert not contains_key(event.payload, "upgraded_sentence")
    assert not contains_key(event.payload, "ai_feedback")
    assert not contains_key(event.payload, "feedback")


def test_essay_draft_and_revision_record_product_events(session, client):
    _, child = create_parent_and_child(client, session)

    draft_response = client.post(
        f"/api/students/{child['id']}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来爸爸扶着我练，我终于能骑一小段了。",
            "entry": "existing_draft",
        },
    )
    assert draft_response.status_code == 201
    essay_id = draft_response.json()["essay"]["id"]

    revision_response = client.post(
        f"/api/essays/{essay_id}/revision",
        json={
            "base_version_id": draft_response.json()["first_draft"]["id"],
            "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。",
            "idempotency_key": "product-events-revision",
            "completed_tasks": ["给第二段加一个动作描写"],
        },
    )

    assert revision_response.status_code == 201
    draft_event = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "essay_draft_feedback_completed"
        )
    ).one()
    revision_event = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "essay_revision_feedback_completed"
        )
    ).one()
    assert draft_event.payload == {
        "target_type": "essay_draft",
        "target_id": draft_response.json()["first_draft"]["id"],
        "task_type": "essay",
        "status": "completed",
    }
    assert revision_event.payload == {
        "target_type": "essay_revision",
        "target_id": revision_response.json()["revision"]["id"],
        "task_type": "essay",
        "status": "completed",
    }
    assert not contains_key(draft_event.payload, "content")
    assert not contains_key(draft_event.payload, "ai_feedback")
    assert not contains_key(revision_event.payload, "content")
    assert not contains_key(revision_event.payload, "ai_feedback")


def test_provider_fallback_records_failure_and_completion_events(session, client):
    _, child = create_parent_and_child(client, session)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_ai_task_runner] = lambda: ProviderFailureFallbackRunner()

    with TestClient(app) as test_client:
        sentence_response = test_client.post(
            f"/api/students/{child['id']}/sentences",
            json={
                "source_sentence": "公园很美。",
                "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
                "focus": "加细节",
            },
        )
        draft_response = test_client.post(
            f"/api/students/{child['id']}/essays",
            json={
                "title": "我学会了骑车",
                "draft": "我学会了骑车。刚开始我很害怕。后来爸爸扶着我练，我终于能骑一小段了。",
                "entry": "existing_draft",
            },
        )
        revision_response = test_client.post(
            f"/api/essays/{draft_response.json()['essay']['id']}/revision",
            json={
                "base_version_id": draft_response.json()["first_draft"]["id"],
                "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。",
                "idempotency_key": "fallback-events-revision",
                "completed_tasks": ["给第二段加一个动作描写"],
            },
        )
    app.dependency_overrides.clear()

    assert sentence_response.status_code == 201
    assert draft_response.status_code == 201
    assert revision_response.status_code == 502
    assert revision_response.json()["detail"] == "这次 AI 对比没有完成，请稍后重试。"
    failure_events = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "ai_feedback_failed")
    ).all()
    assert [event.payload for event in failure_events] == [
        {"task_type": "sentence", "error_category": "exception"},
        {"task_type": "essay", "error_category": "exception"},
        {"task_type": "essay", "error_category": "exception"},
    ]
    completion_types = {
        event.event_type
        for event in session.exec(
            select(ProductEvent).where(
                ProductEvent.event_type.in_(
                    [
                        "sentence_training_completed",
                        "essay_draft_feedback_completed",
                        "essay_revision_feedback_completed",
                    ]
                )
            )
        ).all()
    }
    assert completion_types == {
        "sentence_training_completed",
        "essay_draft_feedback_completed",
    }


def test_essay_ghostwriting_policy_block_does_not_record_ai_failure(session, client):
    _, child = create_parent_and_child(client, session)

    response = client.post(
        f"/api/students/{child['id']}/essays",
        json={
            "title": "我的一天",
            "draft": "请帮我写作文。我想直接生成一篇完整作文，不想自己写。",
            "entry": "existing_draft",
        },
    )

    assert response.status_code == 400
    assert "不能替你写完整作文" in response.json()["detail"]
    assert session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "ai_feedback_failed")
    ).all() == []


def test_ai_feedback_failures_record_product_events(session, client, monkeypatch):
    _, child = create_parent_and_child(client, session)

    async def raise_assessment_failure(*args, **kwargs):
        raise RuntimeError("assessment failed")

    async def raise_sentence_failure(*args, **kwargs):
        raise RuntimeError("sentence failed")

    async def raise_essay_failure(*args, **kwargs):
        raise RuntimeError("essay failed")

    monkeypatch.setattr(
        assessment_routes, "complete_entry_assessment", raise_assessment_failure
    )
    monkeypatch.setattr(
        sentence_routes, "sentence_upgrade_feedback", raise_sentence_failure
    )
    monkeypatch.setattr(essay_routes, "essay_feedback", raise_essay_failure)

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session

    with TestClient(app, raise_server_exceptions=False) as test_client:
        assessment_response = test_client.post(
            f"/api/students/{child['id']}/assessment",
            json={
                "sentence_before": "公园很美。",
                "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
                "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
            },
        )
        sentence_response = test_client.post(
            f"/api/students/{child['id']}/sentences",
            json={
                "source_sentence": "公园很美。",
                "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
                "focus": "加细节",
            },
        )
        essay_response = test_client.post(
            f"/api/students/{child['id']}/essays",
            json={
                "title": "我学会了骑车",
                "draft": "我学会了骑车。刚开始我很害怕。后来爸爸扶着我练，我终于能骑一小段了。",
                "entry": "existing_draft",
            },
        )
    app.dependency_overrides.clear()

    assert assessment_response.status_code == 500
    assert sentence_response.status_code == 500
    assert essay_response.status_code == 500
    events = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "ai_feedback_failed")
    ).all()
    assert [event.payload for event in events] == [
        {"task_type": "assessment", "error_category": "exception"},
        {"task_type": "sentence", "error_category": "exception"},
        {"task_type": "essay", "error_category": "exception"},
    ]


def test_feedback_reaction_upserts_assessment_target(session, client):
    parent, child = create_parent_and_child(client, session)
    assessment = Assessment(
        student_id=child["id"],
        sentence_before="公园很美。",
        sentence_after="公园里的花红红的。",
        short_writing="我学会了骑车，刚开始害怕，后来慢慢会了。",
        summary="表达更具体。",
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)

    for reaction in ["positive", "negative"]:
        response = client.post(
            f"/api/students/{child['id']}/feedback-reactions",
            json={
                "target_type": "assessment",
                "target_id": assessment.id,
                "reaction": reaction,
            },
        )
        assert response.status_code == 201
        assert response.json()["reaction"]["reaction"] == reaction

    reactions = session.exec(select(FeedbackReaction)).all()
    assert len(reactions) == 1
    assert reactions[0].reaction == "negative"
    assert reactions[0].parent_id == parent["id"]
    events = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "child_feedback_reaction_submitted"
        )
    ).all()
    assert len(events) == 1
    assert events[0].parent_id == parent["id"]


def test_feedback_reaction_rejects_cross_student_target(session, client):
    parent = create_parent(client, session)
    first_child = create_child(client, parent["id"], "小甲")
    second_child = create_child(client, parent["id"], "小乙")
    assessment = Assessment(
        student_id=second_child["id"],
        sentence_before="公园很美。",
        sentence_after="公园里的花红红的。",
        short_writing="我学会了骑车，刚开始害怕，后来慢慢会了。",
        summary="表达更具体。",
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)

    response = client.post(
        f"/api/students/{first_child['id']}/feedback-reactions",
        json={
            "target_type": "assessment",
            "target_id": assessment.id,
            "reaction": "positive",
        },
    )

    assert response.status_code == 404


def test_feedback_reaction_rejects_parent_id_from_other_parent(session, client):
    parent = create_parent(client, session, code="ALPHA-PARENT-A")
    other_parent = create_parent(client, session, code="ALPHA-PARENT-B")
    child = create_child(client, parent["id"], "小甲")
    assessment = Assessment(
        student_id=child["id"],
        sentence_before="公园很美。",
        sentence_after="公园里的花红红的。",
        short_writing="我学会了骑车，刚开始害怕，后来慢慢会了。",
        summary="表达更具体。",
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)

    response = client.post(
        f"/api/students/{child['id']}/feedback-reactions",
        json={
            "parent_id": other_parent["id"],
            "target_type": "assessment",
            "target_id": assessment.id,
            "reaction": "positive",
        },
    )

    assert response.status_code in {400, 404}
    assert session.exec(select(FeedbackReaction)).all() == []


def test_feedback_reaction_supports_sentence_and_essay_version_targets(session, client):
    _, child = create_parent_and_child(client, session)
    training = SentenceTraining(
        student_id=child["id"],
        source_sentence="公园很美。",
        upgraded_sentence="公园里的花红红的。",
        focus="加细节",
        ai_feedback={},
    )
    essay = Essay(student_id=child["id"], title="我的一天")
    session.add(training)
    session.add(essay)
    session.flush()
    first_draft = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content="今天我去公园玩，看到很多花。",
        ai_feedback={},
    )
    revision = EssayVersion(
        essay_id=essay.id,
        version_label="revision",
        content="今天我去公园玩，看到很多红色的花。",
        ai_feedback={},
    )
    session.add(first_draft)
    session.add(revision)
    session.commit()

    targets = [
        ("sentence_training", training.id),
        ("essay_draft", first_draft.id),
        ("essay_revision", revision.id),
    ]
    for target_type, target_id in targets:
        response = client.post(
            f"/api/students/{child['id']}/feedback-reactions",
            json={
                "target_type": target_type,
                "target_id": target_id,
                "reaction": "neutral",
            },
        )
        assert response.status_code == 201

    assert len(session.exec(select(FeedbackReaction)).all()) == 3


def test_parent_summary_feedback_upserts_with_parent_child_ownership(session, client):
    parent, child = create_parent_and_child(client, session)

    for usefulness in ["helpful", "not_helpful"]:
        response = client.post(
            f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary-feedback",
            json={"usefulness": usefulness, "alpha_session_id": "session-summary"},
        )
        assert response.status_code == 201
        assert response.json()["feedback"]["usefulness"] == usefulness

    feedback_rows = session.exec(select(ParentFeedback)).all()
    assert len(feedback_rows) == 1
    assert feedback_rows[0].parent_id == parent["id"]
    assert feedback_rows[0].student_id == child["id"]
    assert feedback_rows[0].target_type == "alpha_summary"
    assert feedback_rows[0].target_id == child["id"]
    assert feedback_rows[0].usefulness == "not_helpful"
    events = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "parent_summary_feedback_submitted"
        )
    ).all()
    assert len(events) == 1
    assert events[0].parent_id == parent["id"]
    assert events[0].student_id == child["id"]


def test_parent_summary_returns_existing_feedback_usefulness(session, client):
    parent, child = create_parent_and_child(client, session)
    session.add(
        ParentFeedback(
            parent_id=parent["id"],
            student_id=child["id"],
            target_type="alpha_summary",
            target_id=child["id"],
            usefulness="helpful",
        )
    )
    session.commit()

    response = client.get(
        f"/api/alpha/parents/{parent['id']}/children/{child['id']}/summary"
    )

    assert response.status_code == 200
    assert response.json()["usefulness"] == "helpful"


def test_learning_responses_return_existing_feedback_reactions(
    session, client, monkeypatch
):
    parent, child = create_parent_and_child(client, session)
    original_assessment = assessment_routes.complete_entry_assessment
    original_sentence_apply = sentence_routes.apply_ability_delta
    original_essay_apply = essay_routes.apply_ability_delta

    async def complete_assessment_with_reaction(**kwargs):
        result = await original_assessment(**kwargs)
        kwargs["session"].add(
            FeedbackReaction(
                parent_id=parent["id"],
                student_id=child["id"],
                target_type="assessment",
                target_id=result.assessment.id,
                reaction="positive",
            )
        )
        kwargs["session"].flush()
        return result

    def add_sentence_reaction(db_session, ability, ability_deltas, source_type, source_id):
        original_sentence_apply(
            db_session,
            ability,
            ability_deltas,
            source_type,
            source_id,
        )
        db_session.add(
            FeedbackReaction(
                parent_id=parent["id"],
                student_id=child["id"],
                target_type="sentence_training",
                target_id=source_id,
                reaction="neutral",
            )
        )
        db_session.flush()

    def add_essay_reaction(db_session, ability, ability_deltas, source_type, source_id):
        original_essay_apply(db_session, ability, ability_deltas, source_type, source_id)
        version = db_session.get(EssayVersion, source_id)
        if not version:
            return
        db_session.add(
            FeedbackReaction(
                parent_id=parent["id"],
                student_id=child["id"],
                target_type="essay_draft"
                if version.version_label == "first_draft"
                else "essay_revision",
                target_id=source_id,
                reaction="negative",
            )
        )
        db_session.flush()

    monkeypatch.setattr(
        assessment_routes,
        "complete_entry_assessment",
        complete_assessment_with_reaction,
    )
    monkeypatch.setattr(sentence_routes, "apply_ability_delta", add_sentence_reaction)
    monkeypatch.setattr(essay_routes, "apply_ability_delta", add_essay_reaction)

    assessment_response = client.post(
        f"/api/students/{child['id']}/assessment",
        json={
            "sentence_before": "公园很美。",
            "sentence_after": "公园里的花红红的，风一吹就轻轻摇。",
            "short_writing": "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
        },
    )
    sentence_response = client.post(
        f"/api/students/{child['id']}/sentences",
        json={
            "source_sentence": "公园很美。",
            "upgraded_sentence": "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
            "focus": "加细节",
        },
    )
    draft_response = client.post(
        f"/api/students/{child['id']}/essays",
        json={
            "title": "我学会了骑车",
            "draft": "我学会了骑车。刚开始我很害怕。后来爸爸扶着我练，我终于能骑一小段了。",
            "entry": "existing_draft",
        },
    )
    revision_response = client.post(
        f"/api/essays/{draft_response.json()['essay']['id']}/revision",
        json={
            "base_version_id": draft_response.json()["first_draft"]["id"],
            "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。",
            "idempotency_key": "feedback-reaction-revision",
            "completed_tasks": ["给第二段加一个动作描写"],
        },
    )

    assert assessment_response.status_code == 201
    assert sentence_response.status_code == 201
    assert draft_response.status_code == 201
    assert revision_response.status_code == 201
    assert assessment_response.json()["assessment"]["reaction"] == "positive"
    assert sentence_response.json()["training"]["reaction"] == "neutral"
    assert draft_response.json()["first_draft"]["reaction"] == "negative"
    assert revision_response.json()["revision"]["reaction"] == "negative"


def test_event_logging_failure_does_not_break_child_creation(
    session, client, monkeypatch
):
    parent = create_parent(client, session)

    def raise_event_failure(*args, **kwargs):
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr(alpha_routes, "record_product_event", raise_event_failure)

    response = client.post(
        f"/api/alpha/parents/{parent['id']}/children",
        json={"nickname": "小文", "grade": 4},
    )

    assert response.status_code == 201
    child = response.json()["child"]
    children_response = client.get(f"/api/alpha/parents/{parent['id']}/children")
    assert children_response.status_code == 200
    assert [row["id"] for row in children_response.json()["children"]] == [child["id"]]


def create_admin_client(session, monkeypatch, token: str = "secret"):
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", token)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    return app


def seed_admin_family(session):
    invite = AlphaInviteCode(
        code_hash=hash_code("ALPHA-ADMIN"),
        label="家庭 Admin",
        status="consumed",
        issued_to_note="private note",
    )
    parent = ParentUser(
        email="private-parent@example.com",
        display_name="观察家长",
    )
    session.add(invite)
    session.add(parent)
    session.flush()
    invite.consumed_by_parent_id = parent.id
    child = StudentProfile(
        parent_id=parent.id,
        name="小观察",
        grade_label="四年级",
        persona="real_child",
        is_real_child=True,
    )
    session.add(child)
    session.flush()
    session.add(
        Assessment(
            student_id=child.id,
            sentence_before="公园很美。",
            sentence_after="公园里的花红红的。",
            short_writing="孩子写作正文不能出现在管理端",
            summary="summary",
        )
    )
    session.add(
        SentenceTraining(
            student_id=child.id,
            source_sentence="原句不能出现",
            upgraded_sentence="升级句不能出现",
            focus="加细节",
            ai_feedback={"body": "AI feedback body should stay private"},
        )
    )
    essay = Essay(student_id=child.id, title="题目")
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="first_draft",
            content="作文正文不能出现在管理端",
            ai_feedback={"body": "Essay AI feedback body should stay private"},
        )
    )
    session.add(
        ProductEvent(
            event_type="invite_code_validated",
            invite_code_id=invite.id,
            payload={
                "path": "/alpha/start",
                "status": "validated",
                "target_type": "invite",
                "target_id": "invite-validated",
                "task_type": "onboarding",
                "error_category": "none",
                "summary_viewed": True,
                "reaction": "positive",
                "usefulness": "helpful",
                "child_count": 1,
                "essay_text": "unsafe stored writing text",
                "ai_feedback": "unsafe stored AI feedback body",
                "invite_code": "ALPHA-SECRET-999",
                "phone": "13800000000",
                "school": "Unsafe School",
                "address": "Unsafe Address",
                "photo": "unsafe-photo.jpg",
            },
        )
    )
    session.add(
        ProductEvent(
            event_type="alpha_parent_created",
            parent_id=parent.id,
            invite_code_id=invite.id,
            payload={"status": "created"},
        )
    )
    session.add(
        ProductEvent(
            event_type="assessment_completed",
            parent_id=parent.id,
            student_id=child.id,
            payload={
                "target_type": "assessment",
                "target_id": "assessment-1",
                "status": "completed",
            },
        )
    )
    session.add(
        ProductEvent(
            event_type="summary_viewed",
            parent_id=parent.id,
            student_id=child.id,
            payload={"summary_viewed": True, "status": "viewed"},
        )
    )
    session.add(
        FeedbackReaction(
            parent_id=parent.id,
            student_id=child.id,
            target_type="assessment",
            target_id="assessment-1",
            reaction="positive",
        )
    )
    session.add(
        FeedbackReaction(
            parent_id=parent.id,
            student_id=child.id,
            target_type="sentence_training",
            target_id="sentence-1",
            reaction="negative",
        )
    )
    session.add(
        ParentFeedback(
            parent_id=parent.id,
            student_id=child.id,
            target_type="alpha_summary",
            target_id=child.id,
            usefulness="helpful",
        )
    )
    session.commit()
    return invite, parent, child


def test_admin_overview_requires_alpha_admin_token(session, monkeypatch):
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as admin_client:
        missing = admin_client.get("/api/admin/alpha/overview")
        wrong = admin_client.get(
            "/api/admin/alpha/overview",
            headers={"X-Alpha-Admin-Token": "wrong"},
        )
        correct = admin_client.get(
            "/api/admin/alpha/overview",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert missing.status_code in {401, 403}
    assert wrong.status_code in {401, 403}
    assert correct.status_code == 200


def test_admin_overview_returns_family_funnel_without_sensitive_body(
    session, monkeypatch
):
    invite, parent, _ = seed_admin_family(session)
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as admin_client:
        response = admin_client.get(
            "/api/admin/alpha/overview",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    body = response.json()
    row = body["families"][0]
    assert row["invite_id"] == invite.id
    assert row["invite_label"] == "家庭 Admin"
    assert row["invite_status"] == "consumed"
    assert row["parent_id"] == parent.id
    assert row["parent_display_name"] == "观察家长"
    assert row["child_count"] == 1
    assert row["funnel_stage"] == "summary_viewed"
    assert row["assessment_completed_count"] == 1
    assert row["summary_viewed"] is True
    assert row["reaction_counts"] == {"negative": 1, "positive": 1}
    assert row["latest_parent_feedback"] == "helpful"
    assert row["last_event_at"] is not None
    assert row["account_linked"] is False
    assert row["account_email_masked"] is None
    assert row["phone_bound"] is False
    assert row["last_login_at"] is None

    serialized = str(body)
    assert "孩子写作正文不能出现在管理端" not in serialized
    assert "作文正文不能出现在管理端" not in serialized
    assert "AI feedback body should stay private" not in serialized
    assert "Essay AI feedback body should stay private" not in serialized


def test_admin_overview_includes_minimal_account_fields_only(
    session, client, monkeypatch
):
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", "admin-secret")
    parent = create_parent(client, session, code="ALPHA-ADMIN-AUTH")
    last_login_at = datetime(2026, 5, 29, 1, 30)
    account = ParentAccount(
        email_normalized="parent@example.com",
        email_verified_at=utcnow(),
        phone_e164="+8613800001234",
        phone_bound_at=utcnow(),
        last_login_at=last_login_at,
    )
    session.add(account)
    session.flush()
    saved_parent = session.get(ParentUser, parent["id"])
    saved_parent.account_id = account.id
    saved_parent.account_linked_at = utcnow()
    session.add(saved_parent)
    session.commit()

    response = client.get(
        "/api/admin/alpha/overview",
        headers={"X-Alpha-Admin-Token": "admin-secret"},
    )

    assert response.status_code == 200
    row = response.json()["families"][0]
    assert row["account_linked"] is True
    assert row["account_email_masked"] == "pa***@example.com"
    assert row["phone_bound"] is True
    assert row["last_login_at"] == "2026-05-29T01:30:00"
    assert "session_count_active" not in row
    assert "migration_conflict_count" not in row


def test_admin_family_detail_returns_privacy_safe_timeline(session, monkeypatch):
    _, parent, _ = seed_admin_family(session)
    app = create_admin_client(session, monkeypatch)

    with TestClient(app) as admin_client:
        response = admin_client.get(
            f"/api/admin/alpha/families/{parent.id}",
            headers={"X-Alpha-Admin-Token": "secret"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["parent"]["id"] == parent.id
    assert body["parent"]["display_name"] == "观察家长"
    assert len(body["children"]) == 1
    assert body["children"][0] == {"id": body["children"][0]["id"], "grade_label": "四年级"}
    assert "name" not in body["children"][0]
    assert body["reaction_counts"] == {"negative": 1, "positive": 1}
    assert body["parent_feedback"] == [{"student_id": body["children"][0]["id"], "usefulness": "helpful"}]
    assert [event["created_at"] for event in body["events"]] == sorted(
        event["created_at"] for event in body["events"]
    )
    event_types = [event["event_type"] for event in body["events"]]
    assert "invite_code_validated" in event_types
    assert "alpha_parent_created" in event_types
    assert "assessment_completed" in event_types
    assert "summary_viewed" in event_types
    invite_event = next(
        event for event in body["events"] if event["event_type"] == "invite_code_validated"
    )
    assert invite_event["payload"] == {
        "path": "/alpha/start",
        "status": "validated",
        "target_type": "invite",
        "target_id": "invite-validated",
        "task_type": "onboarding",
        "error_category": "none",
        "summary_viewed": True,
        "reaction": "positive",
        "usefulness": "helpful",
        "child_count": 1,
    }
    assessment_event = next(
        event for event in body["events"] if event["event_type"] == "assessment_completed"
    )
    assert assessment_event["payload"] == {
        "target_type": "assessment",
        "target_id": "assessment-1",
        "status": "completed",
    }

    serialized = str(body)
    assert "小观察" not in serialized
    assert "unsafe stored writing text" not in serialized
    assert "unsafe stored AI feedback body" not in serialized
    assert "ALPHA-SECRET-999" not in serialized
    assert "13800000000" not in serialized
    assert "Unsafe School" not in serialized
    assert "Unsafe Address" not in serialized
    assert "unsafe-photo.jpg" not in serialized
    assert "孩子写作正文不能出现在管理端" not in serialized
    assert "作文正文不能出现在管理端" not in serialized
    assert "AI feedback body should stay private" not in serialized
