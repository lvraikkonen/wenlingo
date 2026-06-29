import pytest

from app.services.writing_castle_scaffold import (
    P0_TOPIC_TYPES,
    detect_unsupported_future_type,
    resolve_scaffold_snapshot,
    supported_topic_type_choices,
)


def test_supported_topic_choices_are_eight_p0_families():
    choices = supported_topic_type_choices()

    assert [choice["topic_type"] for choice in choices] == [
        "generic_narrative",
        "person_portrait",
        "imaginative_story",
        "expository_introduction",
        "place_scenery",
        "animal_object_observation",
        "practical_writing",
        "story_adaptation",
    ]
    assert P0_TOPIC_TYPES == tuple(choice["topic_type"] for choice in choices)


@pytest.mark.parametrize(
    "topic_text",
    ["写信", "书信", "我想对您说", "倡议书", "故事新编", "续写故事"],
)
def test_newly_supported_topics_are_not_future_unsupported(topic_text):
    assert detect_unsupported_future_type(topic_text) is None


@pytest.mark.parametrize(
    ("topic_text", "future_type"),
    [
        ("写作品梗概", "story_summary"),
        ("缩写故事", "story_summary"),
        ("推荐一本书", "reading_response_recommendation"),
        ("围绕中心意思写", "central_idea_reflection"),
        ("漫画的启示", "central_idea_reflection"),
    ],
)
def test_remaining_backlog_topics_stay_future_unsupported(topic_text, future_type):
    assert detect_unsupported_future_type(topic_text) == future_type


def test_detect_unsupported_future_type_ignores_supported_topics():
    assert detect_unsupported_future_type("国宝大熊猫") is None
    assert detect_unsupported_future_type("我的自画像") is None


def test_resolve_manual_family_selection_defaults_variant():
    snapshot = resolve_scaffold_snapshot(
        topic_type="person_portrait",
        topic_variant=None,
        selection_source="manual",
    )

    assert snapshot["schema_version"] == "v0.6b.1"
    assert snapshot["topic_type"] == "person_portrait"
    assert snapshot["topic_variant"] == "default"
    assert snapshot["display_name_child"] == "写一个人"
    assert snapshot["material_slots"][0]["id"] == "person_subject"
    assert snapshot["outline_sections"][0]["id"] == "opening_impression"


def test_schema_version_stays_v06b1_and_template_versions_are_decoupled():
    old_snapshot = resolve_scaffold_snapshot("person_portrait", None, "manual")
    new_snapshot = resolve_scaffold_snapshot("place_scenery", None, "manual")

    assert old_snapshot["schema_version"] == "v0.6b.1"
    assert new_snapshot["schema_version"] == "v0.6b.1"
    assert old_snapshot["scaffold_template_version"] == "person_portrait.default.v0.6b.1"
    assert new_snapshot["scaffold_template_version"] == "place_scenery.default.v0.6c"


@pytest.mark.parametrize(
    ("topic_type", "slot_id", "content_kind"),
    [
        ("place_scenery", "place_subject", "subject"),
        ("animal_object_observation", "observation_subject", "subject"),
        ("story_adaptation", "kept_elements", "source"),
    ],
)
def test_new_scaffold_family_slot_content_kinds_match_spec(topic_type, slot_id, content_kind):
    snapshot = resolve_scaffold_snapshot(topic_type, None, "manual")
    slots_by_id = {slot["id"]: slot for slot in snapshot["material_slots"]}

    assert slots_by_id[slot_id]["content_kind"] == content_kind


def test_aliases_map_to_variants():
    learned = resolve_scaffold_snapshot(
        topic_type="learned_skill",
        topic_variant=None,
        selection_source="manual",
    )
    portrait = resolve_scaffold_snapshot(
        topic_type="self_portrait",
        topic_variant=None,
        selection_source="manual",
    )
    invention = resolve_scaffold_snapshot(
        topic_type="invention_idea",
        topic_variant=None,
        selection_source="manual",
    )

    assert learned["topic_type"] == "generic_narrative"
    assert learned["topic_variant"] == "learned_skill"
    assert portrait["topic_type"] == "person_portrait"
    assert portrait["topic_variant"] == "self"
    assert invention["topic_type"] == "imaginative_story"
    assert invention["topic_variant"] == "invention_design"


def test_unsupported_variant_falls_back_within_same_family():
    snapshot = resolve_scaffold_snapshot(
        topic_type="expository_introduction",
        topic_variant="teacher_portrait",
        selection_source="manual",
    )

    assert snapshot["topic_type"] == "expository_introduction"
    assert snapshot["topic_variant"] == "default"
    assert snapshot["fallback_reason"] == "unsupported_variant"


def test_unknown_family_is_rejected():
    with pytest.raises(ValueError, match="unsupported topic_type"):
        resolve_scaffold_snapshot(
            topic_type="picture_prompt_story",
            topic_variant=None,
            selection_source="manual",
        )


def test_p0_topic_type_constant_matches_choices():
    assert P0_TOPIC_TYPES == tuple(choice["topic_type"] for choice in supported_topic_type_choices())
