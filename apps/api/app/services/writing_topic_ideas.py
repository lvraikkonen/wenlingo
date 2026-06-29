from typing import Any

from app.services.llm_contracts import WritingTopicIdeasResult
from app.services.writing_castle_scaffold import resolve_scaffold_snapshot


def allowed_topic_variants() -> dict[str, tuple[str, ...]]:
    return {
        "generic_narrative": ("default", "learned_skill"),
        "person_portrait": ("default", "self"),
        "imaginative_story": ("default", "invention_design"),
        "expository_introduction": ("default", "experiment_process"),
        "place_scenery": (
            "default",
            "my_paradise",
            "travel_writing",
            "scene_description",
            "place_recommendation",
        ),
        "animal_object_observation": (
            "default",
            "observation_diary",
            "plant_friend",
            "animal_friend",
            "beloved_object",
        ),
        "practical_writing": (
            "default",
            "diary",
            "letter",
            "proposal",
            "heartfelt_letter",
        ),
        "story_adaptation": ("default", "story_continuation", "story_rewrite"),
    }


def _supported_topic_types(supported_choices: list[dict[str, Any]]) -> set[str]:
    return {
        str(choice.get("topic_type") or "").strip()
        for choice in supported_choices
        if isinstance(choice, dict)
    }


def validate_writing_topic_ideas(
    output: WritingTopicIdeasResult,
    *,
    supported_choices: list[dict[str, Any]],
    allowed_variants: dict[str, tuple[str, ...]],
) -> None:
    supported_topic_types = _supported_topic_types(supported_choices)
    for idea in output.ideas:
        if idea.topic_type not in supported_topic_types:
            raise ValueError(f"unsupported topic_type: {idea.topic_type}")
        variants = allowed_variants.get(idea.topic_type, ())
        if idea.topic_variant not in variants:
            raise ValueError(
                f"unsupported topic_variant: {idea.topic_type}.{idea.topic_variant}"
            )
        resolve_scaffold_snapshot(
            idea.topic_type,
            idea.topic_variant,
            "ai_suggested",
        )
