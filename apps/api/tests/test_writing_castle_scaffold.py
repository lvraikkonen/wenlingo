import pytest

from app.services.writing_castle_scaffold import (
    P0_TOPIC_TYPES,
    detect_unsupported_future_type,
    resolve_scaffold_snapshot,
    supported_topic_type_choices,
)


def test_supported_topic_choices_are_four_p0_families():
    choices = supported_topic_type_choices()

    assert [choice["topic_type"] for choice in choices] == [
        "generic_narrative",
        "person_portrait",
        "imaginative_story",
        "expository_introduction",
    ]
    assert {choice["display_name_child"] for choice in choices} == {
        "写一件事",
        "写一个人",
        "编一个想象故事",
        "介绍一种事物",
    }


@pytest.mark.parametrize(
    ("topic_text", "future_type"),
    [
        ("给老师写信", "practical_writing"),
        ("我想对您说", "practical_writing"),
        ("倡议书：节约用水", "practical_writing"),
        ("推荐一本书", "reading_response_recommendation"),
        ("写读后感", "reading_response_recommendation"),
        ("漫画的启示", "central_idea_reflection"),
        ("围绕中心意思写", "central_idea_reflection"),
        ("让生活更美好", "central_idea_reflection"),
        ("写作品梗概", "story_summary"),
        ("故事新编", "story_adaptation"),
    ],
)
def test_detect_unsupported_future_type(topic_text, future_type):
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


def test_unknown_supported_family_is_rejected():
    with pytest.raises(ValueError, match="unsupported topic_type"):
        resolve_scaffold_snapshot(
            topic_type="practical_writing",
            topic_variant=None,
            selection_source="manual",
        )


def test_p0_topic_type_constant_matches_choices():
    assert P0_TOPIC_TYPES == tuple(choice["topic_type"] for choice in supported_topic_type_choices())
