import pytest
from pydantic import ValidationError

from app.services.ai_tasks import (
    convert_ghostwriting_request,
    essay_revision_comparison,
    sentence_upgrade_feedback,
)
from app.services.llm_contracts import (
    EssayFeedback,
    GhostwritingCheck,
    ReportContent,
    RevisionTask,
    SentenceFeedback,
)
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


@pytest.mark.parametrize(
    "request_text",
    [
        "替我写一篇作文",
        "给我写作文",
        "写一篇关于春天的作文",
        "帮我生成作文",
        "替我写一篇推荐一个好地方的作文",
        "给我写一篇我的乐园作文",
        "写一篇难忘的一天作文",
    ],
)
def test_convert_ghostwriting_request_blocks_common_variants(request_text):
    result = convert_ghostwriting_request(request_text)

    assert result.blocked is True
    assert "不能替你写完整作文" in result.message
    assert result.next_question


def test_convert_ghostwriting_request_allows_revision_coaching():
    result = convert_ghostwriting_request("帮我修改这篇作文的开头，让它更生动")

    assert result == GhostwritingCheck(blocked=False, message="", next_question="")


@pytest.mark.parametrize(
    ("contract", "payload"),
    [
        (RevisionTask, {"instruction": "   ", "target": "第一段"}),
        (
            EssayFeedback,
            {
                "strengths": ["动作清楚", " "],
                "improvements": ["结尾可以更有力"],
                "problem_monsters": ["结尾没力"],
                "sentence_notes": ["第一句可加动作"],
                "revision_tasks": [{"instruction": "加动作", "target": "第二段"}],
            },
        ),
        (
            SentenceFeedback,
            {
                "encouragement": "",
                "specific_improvement": "加入了细节",
                "next_step": "再加动作",
                "ability_delta": {"expression": 4},
                "problem_monsters": ["空泛表达"],
            },
        ),
        (GhostwritingCheck, {"blocked": True, "message": "", "next_question": "想写哪个画面？"}),
        (
            ReportContent,
            {
                "practice_summary": "本周完成了句子升级练习",
                "ability_changes": ["表达提升", "   "],
                "best_revision": "句子更具体了",
                "weak_points": ["细节不足"],
                "next_suggestions": ["继续练习动作描写"],
            },
        ),
    ],
)
def test_contracts_reject_blank_user_facing_text(contract, payload):
    with pytest.raises(ValidationError):
        contract(**payload)


def test_ghostwriting_check_allows_blank_text_when_unblocked():
    result = GhostwritingCheck(blocked=False, message="", next_question="")

    assert result.blocked is False


class MalformedSentenceProvider:
    async def complete_json(self, task_name, payload):
        return {
            "encouragement": "不错",
            "specific_improvement": "",
            "next_step": "继续练习",
            "ability_delta": {"expression": 4},
            "problem_monsters": ["空泛表达"],
        }


class RecordingComparisonProvider:
    def __init__(self):
        self.calls = []

    async def complete_json(self, task_name, payload):
        self.calls.append((task_name, payload))
        return {
            "encouragement": "你把修改重点抓住了。",
            "improved_dimensions": ["情节更完整"],
            "evidence": ["爸爸松手后"],
            "next_step": "再补一个结尾感受。",
        }


class MalformedComparisonProvider:
    async def complete_json(self, task_name, payload):
        return {
            "encouragement": "继续加油",
            "improved_dimensions": [],
            "evidence": ["爸爸松手后"],
            "next_step": "再补一个结尾感受。",
        }


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


@pytest.mark.asyncio
async def test_sentence_upgrade_feedback_rejects_malformed_provider_response():
    with pytest.raises(ValidationError):
        await sentence_upgrade_feedback(
            provider=MalformedSentenceProvider(),
            source_sentence="公园很美。",
            upgraded_sentence="清晨的公园里，荷叶上的水珠一闪一闪。",
            focus="加细节",
        )


@pytest.mark.asyncio
async def test_essay_revision_comparison_uses_provider_output():
    provider = RecordingComparisonProvider()

    result = await essay_revision_comparison(
        provider=provider,
        first_draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        revision="我学会了骑车。爸爸松手后，我摇摇晃晃骑过了花坛。我开心得跳了起来。",
    )

    assert provider.calls == [
        (
            "essay_revision_comparison",
            {
                "first_draft": "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
                "revision": "我学会了骑车。爸爸松手后，我摇摇晃晃骑过了花坛。我开心得跳了起来。",
            },
        )
    ]
    assert result.encouragement == "你把修改重点抓住了。"
    assert result.improved_dimensions == ["情节更完整"]


@pytest.mark.asyncio
async def test_essay_revision_comparison_rejects_malformed_provider_response():
    with pytest.raises(ValidationError):
        await essay_revision_comparison(
            provider=MalformedComparisonProvider(),
            first_draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
            revision="我学会了骑车。爸爸松手后，我摇摇晃晃骑过了花坛。我开心得跳了起来。",
        )


@pytest.mark.asyncio
async def test_mock_llm_provider_rejects_unknown_task_name():
    provider = MockLLMProvider()

    with pytest.raises(ValueError, match="Unknown LLM task"):
        await provider.complete_json("sentence_upgarde_feedback", {})
