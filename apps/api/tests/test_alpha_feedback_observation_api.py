from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import select

from app.api.deps import get_db_session
from app.api.routes import alpha as alpha_routes
from app.api.routes import assessment as assessment_routes
from app.api.routes import essays as essay_routes
from app.api.routes import sentences as sentence_routes
from app.domain.models import (
    AlphaInviteCode,
    Assessment,
    Essay,
    EssayVersion,
    FeedbackReaction,
    ParentFeedback,
    ParentUser,
    ProductEvent,
    SentenceTraining,
)
from app.main import create_app


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
            "content": "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松手后，我摇摇晃晃骑过了花坛。",
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

    reactions = session.exec(select(FeedbackReaction)).all()
    assert len(reactions) == 1
    assert reactions[0].reaction == "negative"
    assert reactions[0].parent_id == parent["id"]
    events = session.exec(
        select(ProductEvent).where(
            ProductEvent.event_type == "child_feedback_reaction_submitted"
        )
    ).all()
    assert len(events) == 2
    assert [event.parent_id for event in events] == [parent["id"], parent["id"]]


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

    feedback_rows = session.exec(select(ParentFeedback)).all()
    assert len(feedback_rows) == 1
    assert feedback_rows[0].parent_id == parent["id"]
    assert feedback_rows[0].student_id == child["id"]
    assert feedback_rows[0].target_type == "alpha_summary"
    assert feedback_rows[0].target_id == child["id"]
    assert feedback_rows[0].usefulness == "not_helpful"


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
