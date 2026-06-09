import pytest

from app.prompts.registry import get_prompt, registered_prompts


EXPECTED_KEYS = {
    "sentence_upgrade_feedback",
    "essay_feedback",
    "essay_revision_comparison",
    "sentence_challenge_generation",
    "sentence_challenge_feedback",
}


def test_registered_prompt_keys_load_successfully():
    prompts = registered_prompts()

    assert EXPECTED_KEYS.issubset(set(prompts))
    for key in EXPECTED_KEYS:
        prompt = get_prompt(key)
        assert prompt.prompt_key == key
        assert prompt.version == "v0.5b-2026-06-08"
        assert prompt.response_contract
        assert prompt.system_prompt_key in {
            "wenlingo_primary_coach",
            "wenlingo_sentence_challenge",
        }


def test_unknown_prompt_key_raises_key_error():
    with pytest.raises(KeyError):
        get_prompt("writing_castle_outline")
