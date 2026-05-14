import json

import pytest
from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.ai_tasks import essay_feedback, essay_revision_comparison
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
