import pytest
from sqlmodel import select

from app.domain.models import Essay, EssayVersion, LLMCallLog, ProductEvent
from app.services.writing_castle_state import (
    LEGACY_SCHEMA_VERSION,
    OUTLINE_READY_STATUS,
    PREWRITING_STARTED_STATUS,
    REVISION_REQUESTED_STATUS,
    SCHEMA_VERSION,
    init_material_card_state,
    init_outline_state,
)
from tests.conftest import create_authenticated_family


def _select_generic_scaffold(client, essay_id):
    response = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "generic_narrative", "topic_variant": "learned_skill"},
    )
    assert response.status_code == 200
    return response


def test_classroom_creation_returns_supported_scaffold_choices(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    response = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["essay"]["outline"]["schema_version"] == "v0.6b.1"
    assert payload["essay"]["outline"]["scaffold"] is None
    assert [choice["topic_type"] for choice in payload["supported_topic_types"]] == [
        "generic_narrative",
        "person_portrait",
        "imaginative_story",
        "expository_introduction",
    ]


def test_generation_requires_selected_scaffold_for_v06b_session(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]

    blocked = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "resolved scaffold is required"


def test_manual_scaffold_selection_defaults_variant_and_allows_topic_analysis(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]

    selection = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "manual_choice"},
    )
    topic = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    assert selection.status_code == 200
    selected = selection.json()["essay"]
    assert selected["outline"]["scaffold"]["topic_type"] == "person_portrait"
    assert selected["outline"]["scaffold"]["topic_variant"] == "default"
    assert selected["material_card"]["scaffold_ref"]["scaffold_template_version"] == "person_portrait.default.v0.6b.1"
    assert topic.status_code == 200


def test_generation_rejects_malformed_persisted_scaffold_with_409(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)

    essay = session.get(Essay, essay_id)
    outline = dict(essay.outline)
    scaffold = dict(outline["scaffold"])
    scaffold["material_slots"] = [
        {"id": "skill_name", "label": "学会了什么"},
        None,
    ]
    outline["scaffold"] = scaffold
    essay.outline = outline
    session.add(essay)
    session.commit()

    response = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "malformed scaffold material_slots"


def test_creation_surfaces_deterministic_unsupported_future_type(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    response = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "推荐一本书"},
    )

    assert response.status_code == 201
    assert response.json()["unsupported_future_type"] == "reading_response_recommendation"


@pytest.mark.parametrize(
    ("topic_text", "topic_type", "topic_variant"),
    [
        ("那次经历真难忘", "generic_narrative", None),
        ("我的自画像", "person_portrait", None),
        ("变形记", "imaginative_story", None),
        ("国宝大熊猫", "expository_introduction", None),
    ],
)
def test_each_p0_family_can_select_and_start_topic_analysis(
    session,
    client,
    topic_text,
    topic_type,
    topic_variant,
):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": topic_text},
    )
    essay_id = start.json()["essay"]["id"]

    selection_payload = {"topic_type": topic_type, "override_reason": "manual_choice"}
    if topic_variant is not None:
        selection_payload["topic_variant"] = topic_variant
    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json=selection_payload,
    )
    topic = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    assert selected.status_code == 200
    assert topic.status_code == 200
    assert selected.json()["essay"]["outline"]["scaffold"]["topic_type"] == topic_type


@pytest.mark.parametrize(
    ("topic_text", "future_type"),
    [
        ("写信", "practical_writing"),
        ("推荐一本书", "reading_response_recommendation"),
        ("围绕中心意思写", "central_idea_reflection"),
    ],
)
def test_creation_surfaces_release_blocking_unsupported_future_types(
    session,
    client,
    topic_text,
    future_type,
):
    family = create_authenticated_family(session)
    student = family["student"]

    response = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": topic_text},
    )

    assert response.status_code == 201
    assert response.json()["unsupported_future_type"] == future_type


def test_unsupported_future_type_can_direct_draft_without_scaffold(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "推荐一本书"},
    )
    essay_id = start.json()["essay"]["id"]
    assert start.json()["unsupported_future_type"] == "reading_response_recommendation"

    draft = client.post(
        f"/api/essays/{essay_id}/first-draft",
        json={
            "draft": "我想推荐《西游记》。这本书里有很多有趣的人物，我最喜欢孙悟空。他一路保护唐僧，还会想办法解决困难。"
        },
    )

    assert draft.status_code == 201


def test_unsupported_future_type_override_is_saved_for_parent_summary(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "推荐一本书"},
    )
    essay_id = start.json()["essay"]["id"]

    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={
            "topic_type": "expository_introduction",
            "override_reason": "fallback_selected",
            "unsupported_future_type": "reading_response_recommendation",
        },
    )

    scaffold = selected.json()["essay"]["outline"]["scaffold"]
    assert scaffold["unsupported_future_type"] == "reading_response_recommendation"
    assert scaffold["unsupported_override"] is True


def test_fallback_scaffold_selection_uses_fallback_source_and_event_payload(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "推荐一本书"},
    )
    essay_id = start.json()["essay"]["id"]

    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={
            "topic_type": "expository_introduction",
            "override_reason": "fallback_selected",
            "unsupported_future_type": "reading_response_recommendation",
        },
    )
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "scaffold_selected")
    ).one()

    scaffold = selected.json()["essay"]["outline"]["scaffold"]
    assert selected.status_code == 200
    assert scaffold["selection_source"] == "fallback"
    assert event.payload["selection_source"] == "fallback"
    assert event.payload["override_reason"] == "fallback_selected"
    assert event.payload["accepted_suggestion_id"] == ""


def test_suggestion_accepted_scaffold_selection_is_traceable(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]

    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={
            "topic_type": "person_portrait",
            "override_reason": "suggestion_accepted",
            "accepted_suggestion_id": "suggestion-1",
        },
    )
    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "scaffold_selected")
    ).one()

    scaffold = selected.json()["essay"]["outline"]["scaffold"]
    assert selected.status_code == 200
    assert scaffold["selection_source"] == "ai_suggested"
    assert event.payload["selection_source"] == "ai_suggested"
    assert event.payload["override_reason"] == "suggestion_accepted"
    assert event.payload["accepted_suggestion_id"] == "suggestion-1"


def test_invalid_scaffold_override_reason_returns_422(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]

    response = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "because_i_said_so"},
    )

    assert response.status_code == 422


def test_scaffold_change_after_answers_is_rejected_without_migration(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]
    client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "manual_choice"},
    )
    answers = client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {"id": "answer-1", "question_id": "q1", "text": "我想写我的特点。", "skipped": False}
            ]
        },
    )

    changed = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "generic_narrative", "override_reason": "manual_choice"},
    )

    assert answers.status_code == 200
    assert changed.status_code == 409
    assert changed.json()["detail"] == "scaffold cannot change after prewriting content exists"


def test_scaffold_change_after_topic_analysis_is_rejected_without_migration(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]
    client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "manual_choice"},
    )
    topic = client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    changed = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "generic_narrative", "override_reason": "manual_choice"},
    )

    assert topic.status_code == 200
    assert changed.status_code == 409
    assert changed.json()["detail"] == "scaffold cannot change after prewriting content exists"


def test_scaffold_change_after_material_cards_is_rejected_without_migration(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)
    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {"id": "answer-1", "question_id": "q-event", "text": "我学会了骑车。", "skipped": False}
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})

    changed = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "manual_choice"},
    )

    assert cards.status_code == 200
    assert changed.status_code == 409
    assert changed.json()["detail"] == "scaffold cannot change after prewriting content exists"


def test_scaffold_change_after_outline_sections_is_rejected_without_migration(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)
    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {"id": "answer-1", "question_id": "q-event", "text": "我学会了骑车。", "skipped": False}
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})
    client.patch(
        f"/api/essays/{essay_id}/material-cards",
        json={"cards": cards.json()["material_card"]["cards"]},
    )
    outline = client.post(f"/api/essays/{essay_id}/outline", json={})

    changed = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "manual_choice"},
    )

    assert outline.status_code == 200
    assert changed.status_code == 409
    assert changed.json()["detail"] == "scaffold cannot change after prewriting content exists"


def test_material_answers_before_scaffold_are_rejected_for_v06b_session(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]

    response = client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {"id": "answer-1", "question_id": "q1", "text": "我想写我的特点。", "skipped": False}
            ]
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "resolved scaffold is required"


def test_topic_focus_before_scaffold_is_allowed_and_does_not_block_selection(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我的自画像"},
    )
    essay_id = start.json()["essay"]["id"]

    focus = client.patch(
        f"/api/essays/{essay_id}/topic-focus",
        json={"text": "我想写我的特点。", "adopted_from_ai": False, "skipped": False},
    )
    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "person_portrait", "override_reason": "manual_choice"},
    )

    assert focus.status_code == 200
    assert selected.status_code == 200
    assert selected.json()["essay"]["outline"]["scaffold"]["topic_type"] == "person_portrait"


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

    selected = client.patch(
        f"/api/essays/{essay_id}/scaffold-selection",
        json={"topic_type": "generic_narrative", "topic_variant": "learned_skill"},
    )
    assert selected.status_code == 200

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


def test_active_classroom_writing_castle_essay_returns_latest_open_outline(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    edited_outline = {
        **start.json()["essay"]["outline"],
        "sections": [
            {
                "id": "outline-result",
                "slot": "result",
                "heading": "结果",
                "note": "最后我能自己骑过小区空地。",
                "source_card_ids": [],
                "child_edited": True,
                "placeholder": False,
            }
        ],
        "step_state": {"outline_status": "confirmed"},
    }
    saved = session.get(Essay, essay_id)
    saved.status = OUTLINE_READY_STATUS
    saved.outline = edited_outline
    session.add(saved)
    session.commit()

    response = client.get(
        f"/api/students/{student.id}/writing-castle/classroom/active",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["essay"]["id"] == essay_id
    assert payload["essay"]["outline"]["sections"][0]["note"] == "最后我能自己骑过小区空地。"


def test_generation_endpoints_are_idempotent_and_do_not_overwrite_child_edits(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)

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
    _select_generic_scaffold(client, essay_id)

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
    _select_generic_scaffold(client, essay_id)

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
    _select_generic_scaffold(client, essay_id)

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
    _select_generic_scaffold(client, essay_id)

    skipped = client.patch(f"/api/essays/{essay_id}/outline", json={"sections": [], "skipped": True})
    blocked = client.post(f"/api/essays/{essay_id}/outline", json={})

    saved = session.get(Essay, essay_id)
    assert skipped.status_code == 200
    assert skipped.json()["outline"]["step_state"]["outline_status"] == "skipped"
    assert blocked.status_code == 409
    assert saved.outline["step_state"]["outline_status"] == "skipped"


def test_child_edited_placeholder_outline_section_can_be_confirmed(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)

    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我在小区空地学会了骑车。",
                    "skipped": False,
                }
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})
    assert cards.status_code == 200
    confirmed_cards = client.patch(
        f"/api/essays/{essay_id}/material-cards",
        json={"cards": cards.json()["material_card"]["cards"]},
    )
    assert confirmed_cards.status_code == 200

    outline = client.post(f"/api/essays/{essay_id}/outline", json={})
    assert outline.status_code == 200
    sections = outline.json()["outline"]["sections"]
    placeholder_slot = next(
        section["slot"]
        for section in sections
        if section["placeholder"] is True and section["source_card_ids"] == []
    )

    edited_sections = [
        {
            **section,
            "note": "最后我能自己骑过小区空地。",
            "child_edited": True,
            "placeholder": False,
            "source_card_ids": [],
        }
        if section["slot"] == placeholder_slot
        else section
        for section in sections
    ]

    response = client.patch(
        f"/api/essays/{essay_id}/outline",
        json={"sections": edited_sections, "skipped": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["essay"]["status"] == OUTLINE_READY_STATUS
    assert payload["outline"]["step_state"]["outline_status"] == "confirmed"
    edited_result = next(
        section for section in payload["outline"]["sections"] if section["slot"] == placeholder_slot
    )
    assert edited_result["note"] == "最后我能自己骑过小区空地。"
    assert edited_result["child_edited"] is True
    assert edited_result["source_card_ids"] == []

    saved = session.get(Essay, essay_id)
    saved_result = next(
        section for section in saved.outline["sections"] if section["slot"] == placeholder_slot
    )
    assert saved_result["note"] == "最后我能自己骑过小区空地。"

    event = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "outline_confirmed")
    ).one()
    assert event.payload["outline_section_count"] == 4


def test_child_edited_outline_with_malformed_source_card_ids_returns_400(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)

    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我在小区空地学会了骑车。",
                    "skipped": False,
                }
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})
    assert cards.status_code == 200
    confirmed_cards = client.patch(
        f"/api/essays/{essay_id}/material-cards",
        json={"cards": cards.json()["material_card"]["cards"]},
    )
    assert confirmed_cards.status_code == 200

    outline = client.post(f"/api/essays/{essay_id}/outline", json={})
    assert outline.status_code == 200
    sections = outline.json()["outline"]["sections"]
    placeholder_slot = next(
        section["slot"]
        for section in sections
        if section["placeholder"] is True and section["source_card_ids"] == []
    )

    edited_sections = [
        {
            **section,
            "note": "最后我能自己骑过小区空地。",
            "child_edited": True,
            "placeholder": False,
            "source_card_ids": None,
        }
        if section["slot"] == placeholder_slot
        else section
        for section in sections
    ]

    response = client.patch(
        f"/api/essays/{essay_id}/outline",
        json={"sections": edited_sections, "skipped": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_card_ids must be a list of strings"


def test_untouched_outline_with_malformed_source_card_ids_returns_400(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)

    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我在小区空地学会了骑车。",
                    "skipped": False,
                }
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})
    assert cards.status_code == 200
    confirmed_cards = client.patch(
        f"/api/essays/{essay_id}/material-cards",
        json={"cards": cards.json()["material_card"]["cards"]},
    )
    assert confirmed_cards.status_code == 200

    outline = client.post(f"/api/essays/{essay_id}/outline", json={})
    assert outline.status_code == 200
    sections = outline.json()["outline"]["sections"]
    placeholder_slot = next(
        section["slot"]
        for section in sections
        if section["placeholder"] is True
    )

    edited_sections = [
        {**section, "source_card_ids": None}
        if section["slot"] == placeholder_slot
        else section
        for section in sections
    ]

    response = client.patch(
        f"/api/essays/{essay_id}/outline",
        json={"sections": edited_sections, "skipped": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_card_ids must be a list of strings"


def test_outline_with_malformed_source_card_id_value_returns_400(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)

    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我在小区空地学会了骑车。",
                    "skipped": False,
                }
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})
    assert cards.status_code == 200
    confirmed_cards = client.patch(
        f"/api/essays/{essay_id}/material-cards",
        json={"cards": cards.json()["material_card"]["cards"]},
    )
    assert confirmed_cards.status_code == 200

    outline = client.post(f"/api/essays/{essay_id}/outline", json={})
    assert outline.status_code == 200
    sections = outline.json()["outline"]["sections"]
    placeholder_slot = next(
        section["slot"]
        for section in sections
        if section["placeholder"] is True
    )

    edited_sections = [
        {**section, "source_card_ids": [["nested"]]}
        if section["slot"] == placeholder_slot
        else section
        for section in sections
    ]

    response = client.patch(
        f"/api/essays/{essay_id}/outline",
        json={"sections": edited_sections, "skipped": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_card_ids must be a list of strings"


def test_outline_with_malformed_note_returns_400(session, client):
    family = create_authenticated_family(session)
    student = family["student"]

    start = client.post(
        f"/api/students/{student.id}/writing-castle/classroom",
        json={"topic_text": "我学会了骑车"},
    )
    essay_id = start.json()["essay"]["id"]
    _select_generic_scaffold(client, essay_id)

    client.patch(
        f"/api/essays/{essay_id}/material-answers",
        json={
            "answers": [
                {
                    "id": "answer-1",
                    "question_id": "q-event",
                    "text": "我在小区空地学会了骑车。",
                    "skipped": False,
                }
            ]
        },
    )
    cards = client.post(f"/api/essays/{essay_id}/material-cards", json={})
    assert cards.status_code == 200
    confirmed_cards = client.patch(
        f"/api/essays/{essay_id}/material-cards",
        json={"cards": cards.json()["material_card"]["cards"]},
    )
    assert confirmed_cards.status_code == 200

    outline = client.post(f"/api/essays/{essay_id}/outline", json={})
    assert outline.status_code == 200
    sections = outline.json()["outline"]["sections"]
    placeholder_slot = next(
        section["slot"]
        for section in sections
        if section["placeholder"] is True
    )

    edited_sections = [
        {**section, "note": ["bad"], "placeholder": False}
        if section["slot"] == placeholder_slot
        else section
        for section in sections
    ]

    response = client.patch(
        f"/api/essays/{essay_id}/outline",
        json={"sections": edited_sections, "skipped": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "note must be a string"


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


def test_legacy_prewriting_session_can_generate_without_scaffold(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    essay = Essay(
        student_id=student.id,
        title="我学会了骑车",
        status=PREWRITING_STARTED_STATUS,
        material_card=init_material_card_state(schema_version=LEGACY_SCHEMA_VERSION),
        outline=init_outline_state(schema_version=LEGACY_SCHEMA_VERSION),
    )
    session.add(essay)
    session.commit()

    response = client.post(f"/api/essays/{essay.id}/topic-analysis", json={})

    assert response.status_code == 200


def test_mixed_legacy_current_schema_pair_cannot_enter_prewriting(session, client):
    family = create_authenticated_family(session)
    student = family["student"]
    legacy_material = init_material_card_state(schema_version=LEGACY_SCHEMA_VERSION)
    current_outline = init_outline_state(schema_version=SCHEMA_VERSION)
    essay = Essay(
        student_id=student.id,
        title="我学会了骑车",
        status=PREWRITING_STARTED_STATUS,
        material_card=legacy_material,
        outline=current_outline,
    )
    session.add(essay)
    session.commit()

    response = client.post(f"/api/essays/{essay.id}/topic-analysis", json={})
    session.refresh(essay)

    assert response.status_code == 404
    assert response.json()["detail"] == "writing castle essay not found"
    assert essay.material_card == legacy_material
    assert essay.outline == current_outline


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
    _select_generic_scaffold(client, essay_id)
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
    _select_generic_scaffold(client, essay_id)

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
    _select_generic_scaffold(client, essay_id)
    client.post(f"/api/essays/{essay_id}/topic-analysis", json={})

    event_types = {
        event.event_type
        for event in session.exec(select(ProductEvent).where(ProductEvent.student_id == student.id)).all()
    }
    assert {"writing_castle_started", "topic_analysis_completed"} <= event_types
