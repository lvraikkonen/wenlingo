import pytest

import app.prompts.registry as registry
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

    assert set(prompts) == EXPECTED_KEYS
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


def test_ensure_prompt_registry_loaded_imports_prompt_modules_once(monkeypatch):
    imported_modules = []
    prompt_modules = ("app.prompts.alpha", "app.prompts.beta")

    monkeypatch.setattr(registry, "_loaded", False, raising=False)
    monkeypatch.setattr(registry, "_PROMPT_MODULES", prompt_modules, raising=False)
    monkeypatch.setattr(
        registry.importlib,
        "import_module",
        lambda module_name: imported_modules.append(module_name),
    )

    registry.ensure_prompt_registry_loaded()
    registry.ensure_prompt_registry_loaded()

    assert imported_modules == list(prompt_modules)
