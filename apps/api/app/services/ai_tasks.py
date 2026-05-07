from app.services.llm_contracts import GhostwritingCheck, SentenceFeedback
from app.services.llm_provider import LLMProvider


GHOSTWRITING_TRIGGERS = [
    "帮我写",
    "直接写",
    "生成一篇",
    "写完整作文",
    "范文",
]


def convert_ghostwriting_request(text: str) -> GhostwritingCheck:
    blocked = any(trigger in text for trigger in GHOSTWRITING_TRIGGERS)
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
