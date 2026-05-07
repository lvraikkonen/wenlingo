import pytest
from pydantic import ValidationError

from app.services.ai_tasks import convert_ghostwriting_request, sentence_upgrade_feedback
from app.services.llm_contracts import EssayFeedback, RevisionTask
from app.services.llm_provider import MockLLMProvider


def test_essay_feedback_rejects_more_than_three_revision_tasks():
    with pytest.raises(ValidationError):
        EssayFeedback(
            strengths=["动作写得清楚", "心情能看见"],
            improvements=["结尾可以更有力"],
            problem_monsters=["结尾没力"],
            sentence_notes=["第一句可以加动作"],
            revision_tasks=[
                RevisionTask(instruction="加一个动作描写", target="第二段"),
                RevisionTask(instruction="加一句心理活动", target="第二段"),
                RevisionTask(instruction="加一个过渡句", target="第三段"),
                RevisionTask(instruction="让结尾感受更清楚", target="结尾"),
            ],
        )


def test_convert_ghostwriting_request_returns_coaching_message():
    result = convert_ghostwriting_request("帮我写一篇推荐一个好地方的作文")

    assert result.blocked is True
    assert "不能替你写完整作文" in result.message
    assert result.next_question == "这件事里最值得写的一个画面是什么？"


@pytest.mark.asyncio
async def test_sentence_upgrade_feedback_uses_structured_mock_provider():
    provider = MockLLMProvider()

    result = await sentence_upgrade_feedback(
        provider=provider,
        source_sentence="公园很美。",
        upgraded_sentence="清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
        focus="加细节",
    )

    assert result.specific_improvement == "加入了可看见的细节"
    assert result.ability_delta["expression"] == 4
    assert result.problem_monsters == ["空泛表达"]
