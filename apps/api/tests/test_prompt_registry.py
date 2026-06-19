from pathlib import Path

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


def test_prompt_key_naming_convention_for_registered_prompts():
    for prompt_key in registered_prompts():
        assert prompt_key == prompt_key.lower()
        assert "-" not in prompt_key
        assert " " not in prompt_key


def test_all_v05c_production_prompt_keys_are_registered():
    assert set(registered_prompts()) >= {
        "sentence_upgrade_feedback",
        "sentence_challenge_generation",
        "sentence_challenge_feedback",
        "essay_feedback",
        "essay_revision_comparison",
    }


def test_ai_tasks_no_longer_defines_legacy_default_prompt_version():
    text = Path("app/services/ai_tasks.py").read_text(encoding="utf-8")

    assert "LEGACY_DEFAULT_PROMPT_VERSION" not in text


def test_llm_provider_does_not_keep_v06_legacy_prompt_content():
    text = Path("app/services/llm_provider.py").read_text(encoding="utf-8")

    assert "LEGACY_RESPONSE_CONTRACTS" not in text
    assert "material_questions" not in text
    assert "outline_generation" not in text


def test_unknown_prompt_key_raises_key_error():
    with pytest.raises(KeyError):
        get_prompt("writing_castle_outline")


def test_sentence_challenge_generation_contract_supports_alpha_grades():
    contract = get_prompt("sentence_challenge_generation").response_contract

    for grade_label in ["三年级", "四年级", "五年级", "六年级"]:
        assert grade_label in contract
        assert f"{grade_label}基础" in contract
        assert f"{grade_label}进阶" in contract
    assert "grade_label: 四年级." not in contract
    assert "must match the request payload grade context" in contract


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
