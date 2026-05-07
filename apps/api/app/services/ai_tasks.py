import re

from app.services.llm_contracts import (
    EssayFeedback,
    EssayRevisionComparison,
    GhostwritingCheck,
    SentenceFeedback,
)
from app.services.llm_provider import LLMProvider


GHOSTWRITING_TRIGGERS = [
    "帮我写",
    "直接写",
    "生成一篇",
    "写完整作文",
    "范文",
]

GHOSTWRITING_INTENT_PATTERNS = [
    "替我写作文",
    "替我写一篇作文",
    "给我写作文",
    "给我写一篇作文",
    "帮我写作文",
    "帮我写一篇作文",
    "帮我生成作文",
    "生成作文",
    "生成一篇作文",
    "写一篇作文",
    "写一篇关于",
    "写作文",
]

GHOSTWRITING_INTENT_REGEXES = [
    re.compile(r"(替我|给我|帮我)?写一篇.+作文"),
]


def _normalize_request(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


def convert_ghostwriting_request(text: str) -> GhostwritingCheck:
    normalized_text = _normalize_request(text)
    blocked = any(_normalize_request(trigger) in normalized_text for trigger in GHOSTWRITING_TRIGGERS)
    blocked = blocked or any(pattern in normalized_text for pattern in GHOSTWRITING_INTENT_PATTERNS)
    blocked = blocked or any(pattern.search(normalized_text) for pattern in GHOSTWRITING_INTENT_REGEXES)
    if not blocked:
        return GhostwritingCheck(blocked=False, message="", next_question="")
    return GhostwritingCheck(
        blocked=True,
        message="我不能替你写完整作文，但可以帮你想一想这件事里最值得写的画面。",
        next_question="这件事里最值得写的一个画面是什么？",
    )


async def sentence_upgrade_feedback(
    provider: LLMProvider,
    source_sentence: str,
    upgraded_sentence: str,
    focus: str,
) -> SentenceFeedback:
    raw = await provider.complete_json(
        "sentence_upgrade_feedback",
        {
            "source_sentence": source_sentence,
            "upgraded_sentence": upgraded_sentence,
            "focus": focus,
        },
    )
    return SentenceFeedback.model_validate(raw)


async def essay_feedback(provider: LLMProvider, title: str, draft: str) -> EssayFeedback:
    ghostwriting = convert_ghostwriting_request(draft)
    if ghostwriting.blocked:
        raise ValueError(ghostwriting.message)
    raw = await provider.complete_json("essay_feedback", {"title": title, "draft": draft})
    return EssayFeedback.model_validate(raw)


async def essay_revision_comparison(
    provider: LLMProvider,
    first_draft: str,
    revision: str,
) -> EssayRevisionComparison:
    raw = await provider.complete_json(
        "essay_revision_comparison",
        {"first_draft": first_draft, "revision": revision},
    )
    return EssayRevisionComparison.model_validate(raw)
