import pytest

from app.services.writing_castle_state import (
    MATERIALS_READY_STATUS,
    OUTLINE_READY_STATUS,
    PREWRITING_STARTED_STATUS,
    REVISION_REQUESTED_STATUS,
    SCHEMA_VERSION,
    TOPIC_READY_STATUS,
    assert_prewriting_editable,
    confirm_material_cards,
    init_material_card_state,
    init_outline_state,
    merge_material_answers,
    merge_topic_focus,
    next_status_after_materials,
    next_status_after_outline,
    next_status_after_topic,
    validate_card_sources,
    validate_outline_sources,
)


def test_init_states_include_schema_version_and_empty_slots():
    material = init_material_card_state()
    outline = init_outline_state()

    assert material["schema_version"] == SCHEMA_VERSION
    assert outline["schema_version"] == SCHEMA_VERSION
    assert material["cards"] == []
    assert outline["sections"] == []


def test_patch_helpers_preserve_unrelated_fields():
    material = init_material_card_state()
    material["cards"] = [{"id": "card-event", "text": "保留", "deleted": False}]

    updated = merge_material_answers(
        material,
        answers=[{"id": "answer-1", "question_id": "q1", "text": "我学会了骑车。", "skipped": False}],
    )

    assert updated["cards"] == [{"id": "card-event", "text": "保留", "deleted": False}]
    assert updated["answers"][0]["id"] == "answer-1"


def test_status_transitions_allow_skip_forward_but_not_regress_from_revision():
    assert next_status_after_topic(PREWRITING_STARTED_STATUS) == TOPIC_READY_STATUS
    assert next_status_after_materials(TOPIC_READY_STATUS) == MATERIALS_READY_STATUS
    assert next_status_after_outline(MATERIALS_READY_STATUS) == OUTLINE_READY_STATUS

    with pytest.raises(ValueError, match="prewriting is closed"):
        assert_prewriting_editable(REVISION_REQUESTED_STATUS)


def test_source_reference_validation_rejects_unknown_answer_ids():
    material = merge_material_answers(
        init_material_card_state(),
        answers=[{"id": "answer-1", "question_id": "q1", "text": "真实回答", "skipped": False}],
    )

    with pytest.raises(ValueError, match="unknown source_answer_ids"):
        validate_card_sources(
            material,
            [{"id": "card-event", "source_answer_ids": ["missing"], "placeholder": False}],
        )


def test_source_reference_validation_rejects_source_ids_when_no_answers_saved():
    with pytest.raises(ValueError, match="unknown source_answer_ids"):
        validate_card_sources(
            init_material_card_state(),
            [{"id": "card-event", "source_answer_ids": ["answer-1"], "placeholder": False}],
        )


def test_outline_source_validation_rejects_unknown_card_ids():
    material_with_answer = merge_material_answers(
        init_material_card_state(),
        answers=[{"id": "answer-1", "question_id": "q1", "text": "真实回答", "skipped": False}],
    )
    material = confirm_material_cards(
        material_with_answer,
        cards=[
            {
                "id": "card-event",
                "category": "event",
                "text": "我学会了骑车。",
                "source_answer_ids": ["answer-1"],
                "order": 1,
                "deleted": False,
                "child_edited": False,
                "placeholder": False,
            }
        ],
    )

    with pytest.raises(ValueError, match="unknown source_card_ids"):
        validate_outline_sources(
            material,
            [{"id": "outline-cause", "source_card_ids": ["missing"], "placeholder": False}],
        )


def test_topic_focus_merge_preserves_topic_analysis():
    outline = init_outline_state()
    outline["topic_analysis"]["cards"] = [{"id": "topic-ask", "title": "题目在问什么"}]

    updated = merge_topic_focus(
        outline,
        text="我想写自己学会骑车的过程。",
        adopted_from_ai=False,
        skipped=False,
    )

    assert updated["topic_analysis"]["cards"] == [{"id": "topic-ask", "title": "题目在问什么"}]
    assert updated["child_topic_focus"]["text"] == "我想写自己学会骑车的过程。"
