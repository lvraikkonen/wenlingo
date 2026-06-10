import pytest

from app.services.sentence_challenges import (
    CHALLENGE_TYPE_SPECS,
    deterministic_challenge_ability_delta,
    fallback_challenge,
    fallback_challenge_feedback,
)


def test_fallback_challenge_returns_valid_supported_type():
    challenge = fallback_challenge("action_expression")

    assert challenge.source_sentence == "小猫跑了。"
    assert challenge.target_skill == "action_expression"
    assert challenge.focus == "动作描写"
    assert challenge.grade_label == "四年级"
    assert challenge.challenge_prompt
    assert challenge.hint


@pytest.mark.parametrize("target_skill", ["expand_sentence", "action_expression", "feeling"])
def test_fallback_challenge_returns_valid_contract_for_all_supported_types(target_skill):
    challenge = fallback_challenge(target_skill)

    assert challenge.target_skill == target_skill
    assert challenge.source_sentence
    assert challenge.challenge_prompt
    assert challenge.hint
    assert challenge.grade_label == "四年级"


def test_fallback_challenge_feedback_has_short_child_contract():
    feedback = fallback_challenge_feedback("feeling")

    assert feedback.encouragement
    assert feedback.highlight
    assert feedback.suggestion
    assert feedback.example_upgrade
    assert not hasattr(feedback, "ability_delta")


def test_deterministic_ability_delta_by_target_skill():
    assert deterministic_challenge_ability_delta("expand_sentence") == {
        "expression": 2,
        "observation": 2,
    }
    assert deterministic_challenge_ability_delta("action_expression") == {
        "expression": 3,
        "observation": 2,
    }
    assert deterministic_challenge_ability_delta("feeling") == {
        "expression": 2,
        "observation": 1,
    }


def test_only_three_challenge_types_are_in_scope():
    assert set(CHALLENGE_TYPE_SPECS) == {
        "expand_sentence",
        "action_expression",
        "feeling",
    }


@pytest.mark.parametrize(
    "helper",
    [
        deterministic_challenge_ability_delta,
        fallback_challenge,
        fallback_challenge_feedback,
    ],
)
def test_unknown_challenge_type_raises_value_error(helper):
    with pytest.raises(ValueError, match="Unsupported sentence challenge target_skill"):
        helper("metaphor")
