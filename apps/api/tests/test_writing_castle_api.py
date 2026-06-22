from sqlmodel import select

from app.domain.models import Essay, EssayVersion, LLMCallLog, ProductEvent
from app.services.writing_castle_state import (
    OUTLINE_READY_STATUS,
    PREWRITING_STARTED_STATUS,
    REVISION_REQUESTED_STATUS,
    SCHEMA_VERSION,
)
from tests.conftest import create_authenticated_family


def test_classroom_prewriting_happy_path_reaches_first_draft_feedback(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    assert start.status_code == 201
    essay_id = start.json()["essay"]["id"]
    assert start.json()["essay"]["status"] == PREWRITING_STARTED_STATUS
    assert start.json()["essay"]["material_card"]["schema_version"] == SCHEMA_VERSION
    assert start.json()["essay"]["outline"]["schema_version"] == SCHEMA_VERSION

    topic = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})
    assert topic.status_code == 200
    assert len(topic.json()["topic_analysis"]["cards"]) == 3

    focus = client.patch(
        f"/api/essays/{essay_id}/topic-focus",
        json={"text": "我想写学会骑车的过程。", "adopted_from_ai": False, "skipped": False},
    )
    assert focus.status_code == 200

    questions = client.post(f"/api/essays/{essay_id}/material-questions", json={})
    assert questions.status_code == 200
    answer_payload = {
        "answers": [
            {"id": "answer-1", "question_id": "q-event", "text": "我学会了骑车。", "skipped": False},
            {"id": "answer-2", "question_id": "q-detail", "text": "我紧紧抓着车把。", "skipped": False},
            {"id": "answer-3", "question_id": "q-feeling", "text": "我很开心。", "skipped": False},
        ]
    }
    answers = client.patch(f"/api/essays/{essay_id}/material-answers", json=answer_payload)
    assert answers.status_code == 200

    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})
    assert cards.status_code == 200
    assert cards.json()["material_card"]["cards"][0]["source_answer_ids"]

    outline = client.post(f"/api/essays/{essay_id}/outline", json={})
    assert outline.status_code == 200
    outline_payload = outline.json()["outline"]
    assert len(outline_payload["sections"]) == 4

    confirmed_outline = client.patch(
        f"/api/essays/{essay_id}/outline",
        json={"sections": outline_payload["sections"], "skipped": False},
    )
    assert confirmed_outline.status_code == 200
    assert confirmed_outline.json()["essay"]["status"] == OUTLINE_READY_STATUS

    first_draft = client.post(
        f"/api/essays/{essay_id}/first-draft",
        json={"draft": "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。"},
    )
    assert first_draft.status_code == 201
    assert first_draft.json()["essay"]["status"] == REVISION_REQUESTED_STATUS
    assert first_draft.json()["feedback"]["revision_tasks"][0]["instruction"]

    saved = session.get(Essay, essay_id)
    assert saved.status == REVISION_REQUESTED_STATUS
    assert len(session.exec(select(EssayVersion).where(EssayVersion.essay_id == essay_id)).all()) == 1
    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == student.id)).all()
    assert {log.task_name for log in logs} >= {
        "writing_topic_analysis",
        "material_questions",
        "material_card_generation",
        "outline_generation",
        "essay_feedback",
    }


def test_generation_endpoints_are_idempotent_and_do_not_overwrite_child_edits(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]

    first = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})
    second = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})
    assert first.json()["topic_analysis"] == second.json()["topic_analysis"]

    client.post(f"/api/essays/{essay_id}/material-questions", json={})
    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {"id": "answer-1", "question_id": "q-event", "text": "我学会了骑车。", "skipped": False}
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={}).json()["material_card"]["cards"]
    edited = [{**card, "text": "孩子改过的素材", "child_edited": True} for card in cards]
    patch = client.patch(f"/api/essays/{essay_id}/material-cards", json={"cards": edited})
    assert patch.status_code == 200

    blocked = client.post(f"/api/essays/{essay_id}/material-cards", json={"regenerate": True})
    assert blocked.status_code == 409
    saved = session.get(Essay, essay_id)
    assert saved.material_card["cards"][0]["text"] == "孩子改过的素材"


def test_topic_analysis_is_blocked_after_child_topic_focus(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]

    focus = client.patch(
        f"/api/essays/{essay_id}/topic-focus",
        json={"text": "", "adopted_from_ai": False, "skipped": True},
    )
    blocked = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    assert focus.status_code == 200
    assert blocked.status_code == 409


def test_material_questions_are_blocked_after_child_answers(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]

    answers = client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我学会了骑车。",
                    "skipped": False,
                }
            ]
        },
    )
    blocked = client.post(f"/api/essays/{essay_id}/material-questions", json={})

    assert answers.status_code == 200
    assert blocked.status_code == 409


def test_material_questions_are_blocked_after_skip_and_do_not_mutate_status(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]

    answers = client.patch(f"/api/essays/{essay_id}/material-answers", json={"answers": []})
    blocked = client.post(f"/api/essays/{essay_id}/material-questions", json={})

    saved = session.get(Essay, essay_id)
    assert answers.status_code == 200
    assert answers.json()["material_card"]["step_state"]["questions_status"] == "skipped"
    assert blocked.status_code == 409
    assert saved.material_card["step_state"]["questions_status"] == "skipped"


def test_outline_generation_is_blocked_after_skip_and_does_not_mutate_status(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的一次进步"},
    )
    essay_id = start.json()["essay"]["id"]

    skipped = client.patch(f"/api/essays/{essay_id}/outline", json={"sections": [], "skipped": True})
    blocked = client.post(f"/api/essays/{essay_id}/outline", json={})

    saved = session.get(Essay, essay_id)
    assert skipped.status_code == 200
    assert skipped.json()["outline"]["step_state"]["outline_status"] == "skipped"
    assert blocked.status_code == 409
    assert saved.outline["step_state"]["outline_status"] == "skipped"


def test_legacy_essay_cannot_enter_writing_castle_prewriting(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    essay = Essay(student_id=student.id, title="legacy", status="draft_feedback")
    session.add(essay)
    session.commit()

    response = client.post(f"/api/essays/{essay.id}/topic-analysis", json={})
    session.refresh(essay)

    assert response.status_code == 404
    assert response.json()["detail"] == "writing castle essay not found"
    assert essay.status == "draft_feedback"
    assert essay.material_card == {}
    assert essay.outline == {}


def test_assessment_essay_cannot_enter_writing_castle_prewriting(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    essay = Essay(student_id=student.id, title="assessment", status="assessment_completed")
    session.add(essay)
    session.commit()

    response = client.patch(
        f"/api/essays/{essay.id}/topic-focus",
        json={"text": "我想写这次测评。", "adopted_from_ai": False, "skipped": False},
    )
    session.refresh(essay)

    assert response.status_code == 404
    assert response.json()["detail"] == "writing castle essay not found"
    assert essay.status == "assessment_completed"
    assert essay.material_card == {}
    assert essay.outline == {}


def test_material_cards_confirmed_event_counts_retained_cards_only(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我学会了骑车。",
                    "skipped": False,
                }
            ]
        },
    )

    response = client.patch(
        f"/api/essays/{essay_id}/material-cards",
        json={
            "cards": [
                {
                    "id": "card-retained",
                    "category": "event",
                    "text": "我学会了骑车。",
                    "source_answer_ids": ["answer-1"],
                    "order": 1,
                    "deleted": False,
                    "child_edited": False,
                    "placeholder": False,
                },
                {
                    "id": "card-placeholder",
                    "category": "detail",
                    "text": "",
                    "source_answer_ids": [],
                    "order": 2,
                    "deleted": False,
                    "child_edited": False,
                    "placeholder": True,
                },
                {
                    "id": "card-deleted",
                    "category": "feeling_takeaway",
                    "text": "删掉的素材",
                    "source_answer_ids": ["answer-1"],
                    "order": 3,
                    "deleted": True,
                    "child_edited": False,
                    "placeholder": False,
                },
            ]
        },
    )
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "material_cards_confirmed")
    ).one()

    assert response.status_code == 200
    assert event.payload["card_count"] == 1


def test_skip_path_can_go_directly_to_first_draft(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的一次进步"},
    )
    essay_id = start.json()["essay"]["id"]

    client.patch(f"/api/essays/{essay_id}/topic-focus", json={"text": "", "adopted_from_ai": False, "skipped": True})
    answers = client.patch(f"/api/essays/{essay_id}/material-answers", json={"answers": []})
    client.patch(f"/api/essays/{essay_id}/outline", json={"sections": [], "skipped": True})
    response = client.post(
        f"/api/essays/{essay_id}/first-draft",
        json={"draft": "这次我想写自己的进步。我先写一个简单初稿，后面再慢慢修改。"},
    )

    assert answers.status_code == 200
    assert answers.json()["material_card"]["step_state"]["questions_status"] == "skipped"
    assert response.status_code == 201
    assert response.json()["essay"]["status"] == REVISION_REQUESTED_STATUS


def test_writing_castle_events_are_recorded(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    event_types = {
        event.event_type
        for event in session.exec(select(ProductEvent).where(ProductEvent.student_id == student.id)).all()
    }
    assert {"writing_castle_started", "topic_analysis_completed"} <= event_types
