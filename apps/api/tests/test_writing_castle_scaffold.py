import pytest

from app.services import writing_castle_scaffold as scaffold_registry
from app.services.writing_castle_scaffold import (
    DEFAULT_VARIANTS,
    P0_TOPIC_TYPES,
    TEMPLATE_VERSION_SUFFIXES,
    TEMPLATES,
    VARIANT_ALIASES,
    detect_unsupported_future_type,
    resolve_scaffold_snapshot,
    supported_topic_type_choices,
)

V06C_CONCRETE_TEMPLATES = (
    ("place_scenery", None, "place_scenery.default.v0.6c"),
    ("animal_object_observation", None, "animal_object_observation.default.v0.6c"),
    (
        "animal_object_observation",
        "observation_diary",
        "animal_object_observation.observation_diary.v0.6c",
    ),
    ("practical_writing", None, "practical_writing.default.v0.6c"),
    ("practical_writing", "diary", "practical_writing.diary.v0.6c"),
    ("practical_writing", "letter", "practical_writing.letter.v0.6c"),
    ("practical_writing", "proposal", "practical_writing.proposal.v0.6c"),
    ("story_adaptation", None, "story_adaptation.default.v0.6c"),
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


@pytest.mark.parametrize(("topic_type", "variant", "template_version"), V06C_CONCRETE_TEMPLATES)
def test_v06c_concrete_template_versions_are_exact(topic_type, variant, template_version):
    snapshot = resolve_scaffold_snapshot(topic_type, variant, "manual")

    assert snapshot["scaffold_template_version"] == template_version


@pytest.mark.parametrize(
    ("variant", "slot_ids", "outline_ids"),
    [
        (
            "diary",
            ["date_weather", "day_event", "key_detail", "feeling_or_discovery"],
            ["date_weather", "event_process", "key_detail", "feeling_discovery"],
        ),
        (
            "letter",
            [
                "recipient",
                "main_message",
                "reason_or_background",
                "specific_details",
                "blessing",
                "signature_date",
            ],
            ["salutation", "main_message", "details_or_reasons", "blessing", "signature_date"],
        ),
        (
            "proposal",
            [
                "proposal_topic",
                "problem_observed",
                "reason_or_background",
                "specific_suggestions",
                "closing_or_call",
                "signature_or_date",
            ],
            ["problem", "reason", "suggestions", "call", "signature_date"],
        ),
    ],
)
def test_practical_writing_true_variant_ids_match_spec(variant, slot_ids, outline_ids):
    snapshot = resolve_scaffold_snapshot("practical_writing", variant, "manual")

    assert [slot["id"] for slot in snapshot["material_slots"]] == slot_ids
    assert [section["id"] for section in snapshot["outline_sections"]] == outline_ids


@pytest.mark.parametrize(("topic_type", "variant", "_template_version"), V06C_CONCRETE_TEMPLATES)
def test_v06c_snapshots_include_non_empty_source_policy(topic_type, variant, _template_version):
    snapshot = resolve_scaffold_snapshot(topic_type, variant, "manual")

    assert snapshot["source_policy"]["allowed"]
    assert snapshot["source_policy"]["required_for_content"]


def test_registry_defaults_exist_for_every_p0_family():
    assert set(DEFAULT_VARIANTS) == set(P0_TOPIC_TYPES)


def test_registry_default_keys_point_at_concrete_templates():
    assert all((topic_type, variant) in TEMPLATES for topic_type, variant in DEFAULT_VARIANTS.items())


def test_registry_template_suffix_keys_point_at_concrete_templates():
    assert all(key in TEMPLATES for key in TEMPLATE_VERSION_SUFFIXES)


def test_registry_alias_targets_resolve():
    for topic_type, variant in VARIANT_ALIASES:
        snapshot = resolve_scaffold_snapshot(topic_type, variant, "manual")

        assert (snapshot["topic_type"], snapshot["topic_variant"]) == VARIANT_ALIASES[(topic_type, variant)]


def test_supported_topic_type_choices_resolves_each_snapshot_once(monkeypatch):
    calls = []

    def fake_resolve_scaffold_snapshot(topic_type, topic_variant, selection_source):
        calls.append((topic_type, topic_variant, selection_source))
        return {
            "display_name_child": f"{topic_type}-child",
            "display_name_parent": f"{topic_type}-parent",
        }

    monkeypatch.setattr(scaffold_registry, "resolve_scaffold_snapshot", fake_resolve_scaffold_snapshot)

    choices = supported_topic_type_choices()

    assert len(choices) == len(P0_TOPIC_TYPES)
    assert calls == [(topic_type, None, "manual") for topic_type in P0_TOPIC_TYPES]
