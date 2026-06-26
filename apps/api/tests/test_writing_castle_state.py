import pytest

from app.services.writing_castle_scaffold import resolve_scaffold_snapshot
from app.services.writing_castle_state import (
    LEGACY_SCHEMA_VERSION,
    MATERIALS_READY_STATUS,
    OUTLINE_READY_STATUS,
    PREWRITING_STARTED_STATUS,
    REVISION_REQUESTED_STATUS,
    SCHEMA_VERSION,
    attach_scaffold_snapshot,
    TOPIC_READY_STATUS,
    assert_prewriting_editable,
    confirm_material_cards,
    has_resolved_scaffold,
    init_material_card_state,
    init_outline_state,
    merge_material_answers,
    merge_material_cards,
    merge_topic_focus,
    next_status_after_materials,
    next_status_after_outline,
    next_status_after_topic,
    normalize_material_state,
    normalize_outline_state,
    resolve_essay_scaffold,
    validate_card_sources,
    validate_outline_sources,
)


class FakeEssay:
    def __init__(self, material_card, outline):
        self.material_card = material_card
        self.outline = outline


def test_init_states_include_schema_version_and_empty_slots():
    material = init_material_card_state()
    outline = init_outline_state()

    assert material["schema_version"] == SCHEMA_VERSION
    assert outline["schema_version"] == SCHEMA_VERSION
    assert material["cards"] == []
    assert outline["sections"] == []


def test_v06b_init_states_use_current_schema_without_scaffold():
    material = init_material_card_state()
    outline = init_outline_state()

    assert material["schema_version"] == "v0.6b.1"
    assert outline["schema_version"] == "v0.6b.1"
    assert material["scaffold_ref"] is None
    assert outline["scaffold"] is None
    assert has_resolved_scaffold(material, outline) is False


def test_attach_scaffold_snapshot_stores_full_snapshot_and_ref():
    material = init_material_card_state()
    outline = init_outline_state()
    snapshot = resolve_scaffold_snapshot("person_portrait", None, "manual")

    updated_material, updated_outline = attach_scaffold_snapshot(material, outline, snapshot)

    assert updated_outline["scaffold"] == snapshot
    assert updated_material["scaffold_ref"] == {
        "topic_type": "person_portrait",
        "topic_variant": "default",
        "scaffold_template_version": "person_portrait.default.v0.6b.1",
    }
    assert has_resolved_scaffold(updated_material, updated_outline) is True


def test_resolve_essay_scaffold_fails_closed_on_ref_mismatch():
    snapshot = resolve_scaffold_snapshot("person_portrait", None, "manual")
    material, outline = attach_scaffold_snapshot(init_material_card_state(), init_outline_state(), snapshot)
    material["scaffold_ref"]["topic_type"] = "generic_narrative"

    with pytest.raises(ValueError, match="scaffold_ref mismatch"):
        resolve_essay_scaffold(FakeEssay(material, outline))


def test_resolve_essay_scaffold_returns_saved_snapshot_not_registry_rebuild():
    snapshot = resolve_scaffold_snapshot("person_portrait", None, "manual")
    snapshot["display_name_child"] = "保存时的写人标签"
    material, outline = attach_scaffold_snapshot(init_material_card_state(), init_outline_state(), snapshot)

    resolved = resolve_essay_scaffold(FakeEssay(material, outline))

    assert resolved["display_name_child"] == "保存时的写人标签"


def test_legacy_v06a_state_normalizes_without_v06b_scaffold():
    material = {"schema_version": LEGACY_SCHEMA_VERSION, "questions": [], "answers": [], "cards": []}
    outline = {
        "schema_version": LEGACY_SCHEMA_VERSION,
        "topic_analysis": {"cards": [], "status": "not_started"},
        "sections": [],
    }

    normalized_material = normalize_material_state(material)
    normalized_outline = normalize_outline_state(outline)

    assert normalized_material["schema_version"] == LEGACY_SCHEMA_VERSION
    assert normalized_outline["schema_version"] == LEGACY_SCHEMA_VERSION
    assert "scaffold_ref" not in normalized_material
    assert "scaffold" not in normalized_outline


def test_normalize_material_state_does_not_alias_input_nested_fields():
    material = init_material_card_state()
    material["step_state"]["questions_status"] = "generated"
    material["scaffold_ref"] = {
        "topic_type": "person_portrait",
        "topic_variant": "default",
        "scaffold_template_version": "person_portrait.default.v0.6b.1",
    }

    normalized = normalize_material_state(material)
    normalized["step_state"]["questions_status"] = "mutated"
    normalized["scaffold_ref"]["topic_type"] = "generic_narrative"

    assert material["step_state"]["questions_status"] == "generated"
    assert material["scaffold_ref"]["topic_type"] == "person_portrait"


def test_normalize_outline_state_does_not_alias_input_nested_fields():
    snapshot = resolve_scaffold_snapshot("person_portrait", None, "manual")
    outline = init_outline_state()
    outline["topic_analysis"] = {
        "cards": [{"id": "topic-card-1", "text": "原始卡片"}],
        "status": "generated",
    }
    outline["child_topic_focus"]["text"] = "原始重点"
    outline["step_state"]["outline_status"] = "generated"
    outline["scaffold"] = snapshot

    normalized = normalize_outline_state(outline)
    normalized["topic_analysis"]["cards"][0]["text"] = "变更卡片"
    normalized["child_topic_focus"]["text"] = "变更重点"
    normalized["step_state"]["outline_status"] = "mutated"
    normalized["scaffold"]["display_name_child"] = "变更标签"

    assert outline["topic_analysis"]["cards"][0]["text"] == "原始卡片"
    assert outline["child_topic_focus"]["text"] == "原始重点"
    assert outline["step_state"]["outline_status"] == "generated"
    assert outline["scaffold"]["display_name_child"] == "写一个人"


def test_resolve_essay_scaffold_fails_closed_for_unsupported_json_state():
    with pytest.raises(ValueError, match="resolved scaffold is required"):
        resolve_essay_scaffold(FakeEssay({}, {}))


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


def test_status_transitions_do_not_regress_advanced_prewriting_statuses():
    assert next_status_after_topic(MATERIALS_READY_STATUS) == MATERIALS_READY_STATUS
    assert next_status_after_topic(OUTLINE_READY_STATUS) == OUTLINE_READY_STATUS
    assert next_status_after_materials(OUTLINE_READY_STATUS) == OUTLINE_READY_STATUS


def test_empty_material_answers_do_not_mark_questions_skipped():
    updated = merge_material_answers(init_material_card_state(), answers=[])

    assert updated["answers"] == []
    assert updated["step_state"]["questions_status"] == "not_started"


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


def test_source_reference_validation_rejects_skipped_and_blank_answer_ids():
    material = merge_material_answers(
        init_material_card_state(),
        answers=[
            {"id": "answer-skipped", "question_id": "q1", "text": "真实回答", "skipped": True},
            {"id": "answer-blank", "question_id": "q2", "text": "   ", "skipped": False},
            {"id": "answer-valid", "question_id": "q3", "text": "真实回答", "skipped": False},
        ],
    )

    validate_card_sources(
        material,
        [{"id": "card-valid", "source_answer_ids": ["answer-valid"], "placeholder": False}],
    )
    with pytest.raises(ValueError, match="unknown source_answer_ids"):
        validate_card_sources(
            material,
            [
                {
                    "id": "card-event",
                    "text": "不能引用空白或跳过回答。",
                    "source_answer_ids": ["answer-skipped", "answer-blank"],
                    "placeholder": False,
                }
            ],
        )


def test_source_reference_validation_rejects_source_ids_when_no_answers_saved():
    with pytest.raises(ValueError, match="unknown source_answer_ids"):
        validate_card_sources(
            init_material_card_state(),
            [{"id": "card-event", "source_answer_ids": ["answer-1"], "placeholder": False}],
        )


def test_source_reference_validation_requires_sources_for_non_placeholder_story_cards():
    material = merge_material_answers(
        init_material_card_state(),
        answers=[{"id": "answer-1", "question_id": "q1", "text": "真实回答", "skipped": False}],
    )

    with pytest.raises(ValueError, match="non-placeholder material cards require source refs"):
        validate_card_sources(
            material,
            [
                {
                    "id": "card-event",
                    "text": "我学会了骑车。",
                    "source_answer_ids": [],
                    "placeholder": False,
                }
            ],
        )


def test_merge_material_cards_accepts_source_refs_only_non_placeholder_cards():
    material = merge_material_answers(
        init_material_card_state(),
        answers=[{"id": "answer-1", "question_id": "q1", "text": "我变成了一朵云。", "skipped": False}],
    )

    updated = merge_material_cards(
        material,
        [
            {
                "id": "card-magic-setting",
                "category": "magic_setting",
                "text": "我变成了一朵云。",
                "source_answer_ids": [],
                "source_refs": [{"source_type": "imagined_setting", "answer_id": "answer-1"}],
                "order": 1,
                "deleted": False,
                "child_edited": False,
                "placeholder": False,
            }
        ],
    )

    assert updated["cards"][0]["source_refs"] == [
        {"source_type": "imagined_setting", "answer_id": "answer-1"}
    ]


def test_source_reference_validation_allows_empty_placeholder_cards_without_sources():
    validate_card_sources(
        init_material_card_state(),
        [{"id": "card-placeholder", "text": "", "source_answer_ids": [], "placeholder": True}],
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


def test_outline_source_validation_requires_sources_for_non_placeholder_story_notes():
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

    with pytest.raises(ValueError, match="story-specific outline sections require source_card_ids"):
        validate_outline_sources(
            material,
            [
                {
                    "id": "outline-cause",
                    "note": "我第一次骑车很害怕。",
                    "source_card_ids": [],
                    "placeholder": False,
                }
            ],
        )


def test_outline_source_validation_allows_empty_placeholder_sections_without_sources():
    validate_outline_sources(
        init_material_card_state(),
        [{"id": "outline-placeholder", "note": "", "source_card_ids": [], "placeholder": True}],
    )


def test_outline_source_validation_rejects_malformed_source_card_ids():
    with pytest.raises(ValueError, match="source_card_ids must be a list of strings"):
        validate_outline_sources(
            init_material_card_state(),
            [
                {
                    "id": "outline-placeholder",
                    "note": "",
                    "source_card_ids": None,
                    "placeholder": True,
                }
            ],
        )


@pytest.mark.parametrize(
    "source_card_ids",
    [
        [["nested"]],
        [{"id": "x"}],
        [1],
        ["valid-card", ["nested"]],
        [""],
        ["   "],
    ],
)
def test_outline_source_validation_rejects_malformed_source_card_id_values(source_card_ids):
    with pytest.raises(ValueError, match="source_card_ids must be a list of strings"):
        validate_outline_sources(
            init_material_card_state(),
            [
                {
                    "id": "outline-placeholder",
                    "note": "",
                    "source_card_ids": source_card_ids,
                    "placeholder": True,
                }
            ],
        )


def test_outline_source_validation_treats_none_note_as_empty():
    validate_outline_sources(
        init_material_card_state(),
        [
            {
                "id": "outline-placeholder",
                "note": None,
                "source_card_ids": [],
                "placeholder": False,
            }
        ],
    )


@pytest.mark.parametrize("note", [[], {}, 1])
def test_outline_source_validation_rejects_malformed_note_values(note):
    with pytest.raises(ValueError, match="note must be a string"):
        validate_outline_sources(
            init_material_card_state(),
            [
                {
                    "id": "outline-placeholder",
                    "note": note,
                    "source_card_ids": [],
                    "placeholder": False,
                }
            ],
        )


def test_child_edited_outline_source_relaxation_is_explicit():
    section = {
        "id": "outline-result",
        "slot": "result",
        "heading": "结果",
        "note": "最后我能自己骑过小区空地。",
        "source_card_ids": [],
        "child_edited": True,
        "placeholder": False,
    }

    with pytest.raises(ValueError, match="story-specific outline sections require source_card_ids"):
        validate_outline_sources(init_material_card_state(), [section])

    validate_outline_sources(
        init_material_card_state(),
        [section],
        allow_child_edited_without_sources=True,
    )


def test_child_edited_outline_relaxation_still_rejects_unknown_sources():
    section = {
        "id": "outline-result",
        "slot": "result",
        "heading": "结果",
        "note": "最后我能自己骑过小区空地。",
        "source_card_ids": ["missing-card"],
        "child_edited": True,
        "placeholder": False,
    }

    with pytest.raises(ValueError, match="unknown source_card_ids"):
        validate_outline_sources(
            init_material_card_state(),
            [section],
            allow_child_edited_without_sources=True,
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
