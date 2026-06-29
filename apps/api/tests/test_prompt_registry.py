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
    "writing_topic_analysis",
    "material_questions",
    "material_card_generation",
    "outline_generation",
    "writing_topic_idea_generation",
}

EXPECTED_PROMPT_VERSIONS = {
    "sentence_upgrade_feedback": "v0.5b-2026-06-08",
    "essay_feedback": "v0.5b-2026-06-08",
    "essay_revision_comparison": "v0.5b-2026-06-08",
    "sentence_challenge_generation": "v0.5b-2026-06-08",
    "sentence_challenge_feedback": "v0.5b-2026-06-08",
    "writing_topic_analysis": "v0.6a-2026-06-20",
    "material_questions": "v0.6a-2026-06-20",
    "material_card_generation": "v0.6a-2026-06-20",
    "outline_generation": "v0.6a-2026-06-20",
}
EXPECTED_PROMPT_VERSIONS.update(
    {
        "writing_topic_analysis": "v0.6b.1-2026-06-27",
        "material_questions": "v0.6b.1-2026-06-27",
        "material_card_generation": "v0.6b.1-2026-06-27",
        "outline_generation": "v0.6b-2026-06-25",
        "writing_topic_idea_generation": "v0.6c-2026-06-29",
    }
)


def test_registered_prompt_keys_load_successfully():
    prompts = registered_prompts()

    assert set(prompts) == EXPECTED_KEYS
    for key in EXPECTED_KEYS:
        prompt = get_prompt(key)
        assert prompt.prompt_key == key
        assert prompt.version == EXPECTED_PROMPT_VERSIONS[key]
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


def test_writing_castle_prompts_are_registered_with_contracts():
    from app.prompts.registry import get_prompt

    expected = {
        "writing_topic_analysis": "WritingTopicAnalysis",
        "material_questions": "MaterialQuestionsResult",
        "material_card_generation": "MaterialCardsResult",
        "outline_generation": "WritingOutlineResult",
    }

    for prompt_key, contract_name in expected.items():
        prompt = get_prompt(prompt_key)
        assert prompt.prompt_key == prompt_key
        assert prompt.version == EXPECTED_PROMPT_VERSIONS[prompt_key]
        assert contract_name in prompt.response_contract
        assert "Do not write full essay paragraphs" in prompt.response_contract


def test_writing_topic_idea_generation_prompt_is_registered():
    prompt = get_prompt("writing_topic_idea_generation")

    assert prompt.prompt_key == "writing_topic_idea_generation"
    assert prompt.version == "v0.6c-2026-06-29"
    assert "WritingTopicIdeasResult" in prompt.response_contract
    assert "exactly 3" in prompt.response_contract
    assert "Do not write full essay paragraphs" in prompt.response_contract


def test_expository_topic_analysis_contract_sets_fact_boundary():
    contract = get_prompt("writing_topic_analysis").response_contract

    assert "payload.scaffold.topic_type is expository_introduction" in contract
    assert "do not add external facts" in contract
    assert "numbers, habits, labels, or background claims" in contract
    assert "factual phrases already present in payload.topic_text" in contract
    for forbidden_example in ["吃竹子", "活化石", "800万年", "保护动物"]:
        assert forbidden_example in contract


def test_person_portrait_material_questions_contract_sets_child_view():
    contract = get_prompt("material_questions").response_contract

    assert "payload.scaffold.topic_type is person_portrait" in contract
    assert "ask from the child's point of view" in contract
    assert "你" in contract
    assert "自己" in contract
    assert "我的自画像" in contract
    assert "这个人" in contract
    assert "For non-self portraits" in contract


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
