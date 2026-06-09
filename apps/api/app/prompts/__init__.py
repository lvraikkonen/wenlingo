import importlib


_PROMPT_EXPORTS = {
    "ESSAY_FEEDBACK_PROMPT": "app.prompts.essay_feedback",
    "ESSAY_REVISION_COMPARISON_PROMPT": "app.prompts.revision_feedback",
    "SENTENCE_CHALLENGE_FEEDBACK_PROMPT": "app.prompts.sentence_challenge",
    "SENTENCE_CHALLENGE_GENERATION_PROMPT": "app.prompts.sentence_challenge",
    "SENTENCE_UPGRADE_FEEDBACK_PROMPT": "app.prompts.sentence_feedback",
}

__all__ = [
    "ESSAY_FEEDBACK_PROMPT",
    "ESSAY_REVISION_COMPARISON_PROMPT",
    "SENTENCE_CHALLENGE_FEEDBACK_PROMPT",
    "SENTENCE_CHALLENGE_GENERATION_PROMPT",
    "SENTENCE_UPGRADE_FEEDBACK_PROMPT",
]


def __getattr__(name: str):
    if name not in _PROMPT_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(_PROMPT_EXPORTS[name])
    return getattr(module, name)
