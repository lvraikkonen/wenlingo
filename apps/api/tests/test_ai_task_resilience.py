import json

import pytest
from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.ai_tasks import essay_feedback, essay_revision_comparison, sentence_upgrade_feedback
from app.services.llm_provider import LLMProviderResponse


class InvalidThenValidProvider:
    provider_name = "fake"
    model_name = "invalid-then-valid"

    def __init__(self):
        self.calls = 0

    async def complete_json(self, task_name, payload):
        self.calls += 1
        if self.calls == 1:
            parsed = {"strengths": ["only one"]}
        else:
            parsed = {
                "strengths": ["能写清楚发生了什么", "有一处心情表达"],
                "improvements": ["第二段缺少动作细节"],
                "problem_monsters": ["细节缺口"],
                "sentence_notes": ["把开心换成具体画面。"],
                "revision_tasks": [
                    {"instruction": "给第二段加一个动作描写", "target": "第二段"}
                ],
            }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class AlwaysInvalidProvider:
    provider_name = "fake"
    model_name = "always-invalid"

    async def complete_json(self, task_name, payload):
        parsed = {"strengths": ["only one"]}
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class InvalidSentenceThenValidProvider:
    provider_name = "fake"
    model_name = "sentence-invalid-then-valid"

    def __init__(self):
        self.calls = 0

    async def complete_json(self, task_name, payload):
        self.calls += 1
        if self.calls == 1:
            parsed = {
                "encouragement": "不错",
                "specific_improvement": "",
                "next_step": "继续练习",
                "ability_delta": {"expression": 4},
                "problem_monsters": ["空泛表达"],
            }
        else:
            parsed = {
                "encouragement": "你把画面写得更清楚了。",
                "specific_improvement": "加入了可看见的细节",
                "next_step": "再加一个动作，会更生动。",
                "ability_delta": {"expression": 4, "observation": 4},
                "problem_monsters": ["空泛表达"],
            }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class RecordingSentenceProvider:
    provider_name = "fake"
    model_name = "recording-sentence"

    def __init__(self):
        self.calls = []

    async def complete_json(self, task_name, payload):
        self.calls.append((task_name, payload))
        parsed = {
            "encouragement": "你把画面写得更清楚了。",
            "specific_improvement": "加入了可看见的细节",
            "next_step": "再加一个动作，会更生动。",
            "ability_delta": {"expression": 4, "observation": 4},
            "problem_monsters": ["空泛表达"],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class AlwaysInvalidSentenceProvider:
    provider_name = "fake"
    model_name = "sentence-always-invalid"

    async def complete_json(self, task_name, payload):
        parsed = {
            "encouragement": "",
            "specific_improvement": "",
            "next_step": "",
            "ability_delta": {},
            "problem_monsters": [],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class RecordingEssayProvider:
    provider_name = "fake"
    model_name = "recording-essay"

    def __init__(self):
        self.calls = []

    async def complete_json(self, task_name, payload):
        self.calls.append((task_name, payload))
        parsed = {
            "strengths": ["能写清楚发生了什么", "有一处心情表达"],
            "improvements": ["第二段缺少动作细节"],
            "problem_monsters": ["细节缺口"],
            "sentence_notes": ["把开心换成具体画面。"],
            "revision_tasks": [
                {"instruction": "给第二段加一个动作描写", "target": "第二段"}
            ],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


class RaisingProvider:
    provider_name = "fake"
    model_name = "raising"

    async def complete_json(self, task_name, payload):
        raise RuntimeError("provider unavailable")


class ResponseMetadataInvalidProvider:
    provider_name = "object-provider"
    model_name = "object-model"

    async def complete_json(self, task_name, payload):
        parsed = {"strengths": ["only one"]}
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider="response-provider",
            model="response-model",
        )


class CountingRealProvider:
    provider_name = "http"
    model_name = "limit-test-model"

    def __init__(self):
        self.calls = 0

    async def complete_json(self, task_name, payload):
        self.calls += 1
        parsed = {
            "strengths": ["能写清楚发生了什么", "有一处心情表达"],
            "improvements": ["第二段缺少动作细节"],
            "problem_monsters": ["细节缺口"],
            "sentence_notes": ["把开心换成具体画面。"],
            "revision_tasks": [
                {"instruction": "给第二段加一个动作描写", "target": "第二段"}
            ],
        }
        return LLMProviderResponse(
            parsed_json=parsed,
            raw_response=json.dumps(parsed, ensure_ascii=False),
            provider=self.provider_name,
            model=self.model_name,
        )


@pytest.mark.asyncio
async def test_invalid_then_valid_retries_and_logs_success(session):
    provider = InvalidThenValidProvider()

    result = await essay_feedback(
        provider=provider,
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert provider.calls == 2
    assert result.output.revision_tasks[0].instruction == "给第二段加一个动作描写"
    assert result.log.id == saved.id
    assert saved.validation_ok is True
    assert saved.retry_count == 1
    assert saved.prompt_version == "test-v1"
    assert saved.raw_response


@pytest.mark.asyncio
async def test_always_invalid_returns_schema_valid_fallback_and_logs_failure(session):
    result = await essay_feedback(
        provider=AlwaysInvalidProvider(),
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output.strengths == ["你已经完成了一版初稿", "你愿意继续修改，这很重要"]
    assert result.output.revision_tasks[0].instruction == "先给最重要的一段加一个动作或看到的细节"
    assert saved.validation_ok is False
    assert saved.retry_count == 1
    assert "validation" in saved.error_message.lower()


@pytest.mark.asyncio
async def test_sentence_invalid_then_valid_retries_and_logs_success(session):
    provider = InvalidSentenceThenValidProvider()

    result = await sentence_upgrade_feedback(
        provider=provider,
        source_sentence="公园很美。",
        upgraded_sentence="清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
        focus="加细节",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert provider.calls == 2
    assert result.output.specific_improvement == "加入了可看见的细节"
    assert saved.student_id == "s1"
    assert saved.task_name == "sentence_upgrade_feedback"
    assert saved.validation_ok is True
    assert saved.retry_count == 1


@pytest.mark.asyncio
async def test_sentence_upgrade_feedback_wraps_student_payload():
    provider = RecordingSentenceProvider()

    await sentence_upgrade_feedback(
        provider=provider,
        source_sentence="公园很美。",
        upgraded_sentence="公园里的花在风里轻轻摇。",
        focus="加细节",
    )

    assert provider.calls == [
        (
            "sentence_upgrade_feedback",
            {
                "source_sentence": "<student_sentence>公园很美。</student_sentence>",
                "upgraded_sentence": "<student_sentence>公园里的花在风里轻轻摇。</student_sentence>",
                "focus": "加细节",
            },
        )
    ]


@pytest.mark.asyncio
async def test_sentence_always_invalid_returns_schema_valid_fallback(session):
    result = await sentence_upgrade_feedback(
        provider=AlwaysInvalidSentenceProvider(),
        source_sentence="公园很美。",
        upgraded_sentence="公园的花在风里轻轻摇。",
        focus="加细节",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output.encouragement == "你已经完成了一次句子升级。"
    assert result.output.specific_improvement == "先把一个看得见的细节写清楚"
    assert result.output.problem_monsters == ["空泛表达"]
    assert saved.validation_ok is False
    assert "validation" in saved.error_message.lower()


@pytest.mark.asyncio
async def test_essay_feedback_wraps_student_payload(session):
    provider = RecordingEssayProvider()

    await essay_feedback(
        provider=provider,
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
    )

    assert provider.calls == [
        (
            "essay_feedback",
            {
                "title": "<student_title>我学会了骑车</student_title>",
                "draft": "<student_draft>我学会了骑车。刚开始我很害怕。后来我会了。我很开心。</student_draft>",
            },
        )
    ]


@pytest.mark.asyncio
async def test_raising_provider_returns_fallback_and_logs_error(session):
    result = await essay_revision_comparison(
        provider=RaisingProvider(),
        first_draft="我学会了骑车。刚开始我很害怕。后来我会了。",
        revision="我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
        session=session,
        prompt_version="test-v1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output.encouragement == "你完成了二稿，这一步本身就很值得肯定。"
    assert saved.task_type == TaskType.essay
    assert saved.validation_ok is False
    assert "provider unavailable" in saved.error_message


@pytest.mark.asyncio
async def test_invalid_response_fallback_log_uses_latest_response_metadata(session):
    await essay_feedback(
        provider=ResponseMetadataInvalidProvider(),
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert saved.validation_ok is False
    assert saved.provider == "response-provider"
    assert saved.model == "response-model"


@pytest.mark.asyncio
async def test_daily_limit_returns_fallback_without_calling_real_provider_again(session):
    provider = CountingRealProvider()

    first = await essay_feedback(
        provider=provider,
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
        daily_limit_enabled=True,
        daily_limit_per_student_task=1,
    )
    second = await essay_feedback(
        provider=provider,
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
        daily_limit_enabled=True,
        daily_limit_per_student_task=1,
    )

    logs = session.exec(select(LLMCallLog).where(LLMCallLog.student_id == "s1")).all()
    assert provider.calls == 1
    assert first.output.revision_tasks[0].instruction == "给第二段加一个动作描写"
    assert second.output.revision_tasks[0].instruction == "先给最重要的一段加一个动作或看到的细节"
    assert len(logs) == 2
    assert logs[-1].validation_ok is False
    assert logs[-1].error_message == "daily limit exceeded"


@pytest.mark.asyncio
async def test_daily_limit_ignores_existing_mock_logs_for_real_provider(session):
    session.add(
        LLMCallLog(
            student_id="s1",
            task_type=TaskType.essay,
            task_name="essay_feedback",
            provider="mock",
            model="mock",
            prompt_version="test-v1",
            input_summary="mock same-day log",
            raw_response='{"strengths":["mock"]}',
            output_json={"strengths": ["mock"]},
            validation_ok=True,
            error_message="",
            retry_count=0,
        )
    )
    session.flush()
    provider = CountingRealProvider()

    result = await essay_feedback(
        provider=provider,
        title="我学会了骑车",
        draft="我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
        session=session,
        prompt_version="test-v1",
        student_id="s1",
        daily_limit_enabled=True,
        daily_limit_per_student_task=1,
    )

    assert provider.calls == 1
    assert result.output.revision_tasks[0].instruction == "给第二段加一个动作描写"
    assert result.log.provider == "http"
