from typing import Any

import httpx
import pytest
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api import deps
from app.core.config import Settings
from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.ai_routing import (
    COST_REGISTRY,
    ModelPricing,
    PricingStatus,
    TaskFallbackReason,
    TaskFinalStatus,
)
from app.services.ai_runner import FailureContext, run_ai_task
from app.services.llm_provider import HttpJsonLLMProvider, LLMProviderResponse


class TinyOutput(BaseModel):
    message: str = Field(min_length=3)


class FakeProvider:
    def __init__(
        self,
        *,
        provider_name: str,
        model_name: str,
        actions: list[LLMProviderResponse | BaseException],
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.actions = actions
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def complete_json(self, task_name: str, payload: dict[str, Any]) -> LLMProviderResponse:
        self.calls.append((task_name, payload))
        action = self.actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return action


def response(
    *,
    message: str,
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int | None = None,
) -> LLMProviderResponse:
    total_tokens = prompt_tokens + completion_tokens if total_tokens is None else total_tokens
    parsed_json = {"message": message}
    return LLMProviderResponse(
        parsed_json=parsed_json,
        raw_response=f'{{"message":"{message}"}}',
        provider=provider,
        model=model,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    )


def local_fallback(context: FailureContext) -> TinyOutput:
    return TinyOutput(message="local fallback")


class RecordingFallback:
    def __init__(self, message: str = "local fallback"):
        self.message = message
        self.contexts: list[FailureContext] = []

    def __call__(self, context: FailureContext) -> TinyOutput:
        self.contexts.append(context)
        return TinyOutput(message=self.message)


@pytest.mark.asyncio
async def test_run_ai_task_records_primary_success(session, monkeypatch):
    monkeypatch.setitem(
        COST_REGISTRY,
        "mock:cheap-fast",
        ModelPricing("mock:cheap-fast", "mock_primary", "cheap-fast", 0.002, 0.004, "test"),
    )
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[
            response(
                message="hello child",
                provider="primary",
                model="cheap-fast",
                prompt_tokens=100,
                completion_tokens=25,
            )
        ],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[],
    )

    result = await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
        primary_provider=primary,
        fallback_provider=fallback,
        prompt_version="test-v1",
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output == TinyOutput(message="hello child")
    assert result.log.id == saved.id
    assert primary.calls == [("sentence_upgrade_feedback", {"draft": "tiny draft"})]
    assert fallback.calls == []
    assert saved.final_status == TaskFinalStatus.PRIMARY_SUCCESS
    assert saved.validation_ok is True
    assert saved.provider == "primary"
    assert saved.model == "cheap-fast"
    assert saved.resolved_provider == "primary"
    assert saved.resolved_model == "cheap-fast"
    assert saved.primary_provider == "primary"
    assert saved.primary_model == "cheap-fast"
    assert saved.fallback_provider == ""
    assert saved.attempt_count == 1
    assert saved.retry_count == 0
    assert saved.prompt_tokens == 100
    assert saved.completion_tokens == 25
    assert saved.total_tokens == 125
    assert saved.estimated_cost == pytest.approx(0.0003)
    assert saved.attempt_summaries == [
        {
            "attempt_index": 1,
            "role": "primary",
            "provider": "primary",
            "model": "cheap-fast",
            "status": "success",
            "error_class": "",
            "latency_ms": saved.attempt_summaries[0]["latency_ms"],
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
            "estimated_cost": pytest.approx(0.0003),
            "pricing_status": "configured",
        }
    ]


@pytest.mark.asyncio
async def test_run_ai_task_defaults_prompt_version_to_prompt_key(session):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[
            response(
                message="hello child",
                provider="primary",
                model="cheap-fast",
            )
        ],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[],
    )

    await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
        primary_provider=primary,
        fallback_provider=fallback,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert saved.prompt_version == "sentence_upgrade_feedback"


@pytest.mark.asyncio
async def test_run_ai_task_uses_fallback_after_primary_api_error(session):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[RuntimeError("provider exploded")],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[
            response(
                message="fallback ok",
                provider="fallback",
                model="strong-default",
                prompt_tokens=20,
                completion_tokens=10,
            )
        ],
    )

    result = await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
        primary_provider=primary,
        fallback_provider=fallback,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output == TinyOutput(message="fallback ok")
    assert saved.final_status == TaskFinalStatus.FALLBACK_SUCCESS
    assert saved.fallback_reason == TaskFallbackReason.API_ERROR
    assert saved.validation_ok is True
    assert saved.provider == "fallback"
    assert saved.resolved_provider == "fallback"
    assert saved.primary_provider == "primary"
    assert saved.fallback_provider == "fallback"
    assert saved.attempt_count == 2
    assert saved.retry_count == 1
    assert [attempt["status"] for attempt in saved.attempt_summaries] == [
        TaskFallbackReason.API_ERROR,
        "success",
    ]
    assert saved.attempt_summaries[0]["error_class"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("primary_error", "expected_reason"),
    [
        (
            httpx.ReadTimeout("primary read timed out"),
            TaskFallbackReason.TIMEOUT,
        ),
        (
            httpx.HTTPStatusError(
                "too many requests",
                request=httpx.Request("POST", "https://primary.example/v1/chat/completions"),
                response=httpx.Response(
                    429,
                    request=httpx.Request(
                        "POST",
                        "https://primary.example/v1/chat/completions",
                    ),
                ),
            ),
            TaskFallbackReason.RATE_LIMIT,
        ),
    ],
)
async def test_httpx_provider_errors_are_classified_for_fallback(
    primary_error,
    expected_reason,
    session,
):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[primary_error],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[
            response(
                message="fallback ok",
                provider="fallback",
                model="strong-default",
            )
        ],
    )

    await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
        primary_provider=primary,
        fallback_provider=fallback,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert saved.final_status == TaskFinalStatus.FALLBACK_SUCCESS
    assert saved.fallback_reason == expected_reason
    assert saved.attempt_summaries[0]["status"] == expected_reason


@pytest.mark.asyncio
async def test_schema_validation_failure_falls_back_and_keeps_primary_usage(session):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[
            response(
                message="no",
                provider="primary",
                model="cheap-fast",
                prompt_tokens=11,
                completion_tokens=7,
            )
        ],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[
            response(
                message="fallback valid",
                provider="fallback",
                model="strong-default",
                prompt_tokens=13,
                completion_tokens=5,
            )
        ],
    )

    result = await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
        primary_provider=primary,
        fallback_provider=fallback,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output == TinyOutput(message="fallback valid")
    assert saved.final_status == TaskFinalStatus.FALLBACK_SUCCESS
    assert saved.fallback_reason == TaskFallbackReason.SCHEMA_VALIDATION_FAILED
    assert saved.validation_ok is True
    assert saved.prompt_tokens == 24
    assert saved.completion_tokens == 12
    assert saved.total_tokens == 36
    assert saved.attempt_summaries[0]["status"] == TaskFallbackReason.SCHEMA_VALIDATION_FAILED
    assert saved.attempt_summaries[0]["prompt_tokens"] == 11
    assert saved.attempt_summaries[0]["completion_tokens"] == 7
    assert saved.attempt_summaries[1]["status"] == "success"


@pytest.mark.asyncio
async def test_double_failure_uses_deterministic_fallback(session):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[TimeoutError("primary timed out")],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[RuntimeError("rate limit exceeded")],
    )

    fallback_factory = RecordingFallback()

    result = await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=fallback_factory,
        primary_provider=primary,
        fallback_provider=fallback,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output == TinyOutput(message="local fallback")
    assert saved.final_status == TaskFinalStatus.DETERMINISTIC_FALLBACK_USED
    assert saved.validation_ok is False
    assert saved.provider == "local_fallback"
    assert saved.model == "local_fallback"
    assert saved.resolved_provider == "local_fallback"
    assert saved.resolved_model == "local_fallback"
    assert saved.fallback_reason == TaskFallbackReason.RATE_LIMIT
    assert saved.attempt_count == 2
    assert saved.retry_count == 1
    assert [attempt["status"] for attempt in saved.attempt_summaries] == [
        TaskFallbackReason.TIMEOUT,
        TaskFallbackReason.RATE_LIMIT,
    ]
    assert fallback_factory.contexts == [
        FailureContext(
            task_name="sentence_upgrade_feedback",
            fallback_reason=TaskFallbackReason.RATE_LIMIT,
            errors=(
                f"primary {TaskFallbackReason.TIMEOUT}",
                f"fallback {TaskFallbackReason.RATE_LIMIT}",
            ),
        )
    ]


@pytest.mark.asyncio
async def test_daily_limit_uses_deterministic_fallback_without_provider_call(session):
    settings = Settings(
        llm_provider="mock",
        llm_daily_limit_enabled=True,
        llm_daily_limit_per_student_task=1,
        llm_daily_limit_timezone="Asia/Shanghai",
    )
    session.add(
        LLMCallLog(
            student_id="s1",
            task_type=TaskType.sentence,
            task_name="sentence_upgrade_feedback",
            prompt_key="sentence_upgrade_feedback",
            provider="primary",
            model="cheap-fast",
            final_status=TaskFinalStatus.PRIMARY_SUCCESS,
            prompt_version="test-v1",
            input_summary="existing use",
            raw_response="{}",
            output_json={},
            validation_ok=True,
            error_message="",
            retry_count=0,
        )
    )
    session.flush()
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[
            response(
                message="should not call",
                provider="primary",
                model="cheap-fast",
            )
        ],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[
            response(
                message="should not call",
                provider="fallback",
                model="strong-default",
            )
        ],
    )

    fallback_factory = RecordingFallback()

    result = await run_ai_task(
        settings=settings,
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=fallback_factory,
        primary_provider=primary,
        fallback_provider=fallback,
        daily_limit=1,
    )

    saved_logs = session.exec(
        select(LLMCallLog).order_by(LLMCallLog.created_at)
    ).all()
    saved = saved_logs[-1]
    assert result.output == TinyOutput(message="local fallback")
    assert primary.calls == []
    assert fallback.calls == []
    assert saved.final_status == TaskFinalStatus.DAILY_LIMIT_REACHED
    assert saved.validation_ok is False
    assert saved.provider == "local_fallback"
    assert saved.model == "local_fallback"
    assert saved.attempt_count == 0
    assert saved.retry_count == 0
    assert saved.attempt_summaries == []
    assert saved.pricing_status == PricingStatus.CONFIGURED
    assert saved.prompt_version == "sentence_upgrade_feedback"
    assert fallback_factory.contexts == [
        FailureContext(
            task_name="sentence_upgrade_feedback",
            fallback_reason=TaskFinalStatus.DAILY_LIMIT_REACHED,
            errors=("daily limit reached",),
        )
    ]


@pytest.mark.asyncio
async def test_usage_total_tokens_falls_back_to_prompt_plus_completion(session):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[
            response(
                message="hello child",
                provider="primary",
                model="cheap-fast",
                prompt_tokens=9,
                completion_tokens=4,
                total_tokens=0,
            )
        ],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[],
    )

    await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
        primary_provider=primary,
        fallback_provider=fallback,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert saved.total_tokens == 13
    assert saved.attempt_summaries[0]["total_tokens"] == 13


@pytest.mark.asyncio
async def test_task_validation_failure_triggers_fallback_and_records_reason(session):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[
            response(
                message="primary valid schema",
                provider="primary",
                model="cheap-fast",
                prompt_tokens=5,
                completion_tokens=6,
            )
        ],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[
            response(
                message="fallback valid",
                provider="fallback",
                model="strong-default",
                prompt_tokens=7,
                completion_tokens=8,
            )
        ],
    )

    def validate_output(output: TinyOutput) -> bool:
        return output.message.startswith("fallback")

    result = await run_ai_task(
        settings=Settings(llm_provider="mock"),
        session=session,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
        validate_output=validate_output,
        primary_provider=primary,
        fallback_provider=fallback,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output == TinyOutput(message="fallback valid")
    assert saved.final_status == TaskFinalStatus.FALLBACK_SUCCESS
    assert saved.fallback_reason == TaskFallbackReason.TASK_VALIDATION_FAILED
    assert saved.attempt_summaries[0]["status"] == TaskFallbackReason.TASK_VALIDATION_FAILED
    assert saved.attempt_summaries[1]["status"] == "success"
    assert saved.prompt_tokens == 12
    assert saved.completion_tokens == 14


@pytest.mark.asyncio
async def test_double_failure_without_deterministic_fallback_raises_without_failed_log(session):
    primary = FakeProvider(
        provider_name="primary",
        model_name="cheap-fast",
        actions=[RuntimeError("provider exploded")],
    )
    fallback = FakeProvider(
        provider_name="fallback",
        model_name="strong-default",
        actions=[RuntimeError("fallback exploded")],
    )

    with pytest.raises(RuntimeError, match="AI task failed"):
        await run_ai_task(
            settings=Settings(llm_provider="mock"),
            session=session,
            task_type=TaskType.sentence,
            task_name="sentence_upgrade_feedback",
            student_id="s1",
            payload={"draft": "tiny draft"},
            output_schema=TinyOutput,
            prompt_key="sentence_upgrade_feedback",
            input_summary="tiny test",
            deterministic_fallback_factory=None,
            primary_provider=primary,
            fallback_provider=fallback,
        )

    assert session.exec(select(LLMCallLog)).all() == []


@pytest.mark.asyncio
async def test_ai_task_runner_resolves_route_providers_and_delegates(monkeypatch):
    provider_calls = []

    def fake_provider_for_profile(*, settings, profile, logical_model, timeout_seconds):
        provider_calls.append(
            {
                "settings": settings,
                "profile": profile.profile_name,
                "model": logical_model.model,
                "timeout_seconds": timeout_seconds,
            }
        )
        return FakeProvider(
            provider_name=profile.profile_name,
            model_name=logical_model.model,
            actions=[],
        )

    async def fake_run_ai_task(**kwargs):
        return kwargs

    monkeypatch.setattr(deps, "provider_for_profile", fake_provider_for_profile)
    monkeypatch.setattr(deps, "run_ai_task", fake_run_ai_task, raising=False)
    settings = Settings(llm_provider="mock")

    result = await deps.AITaskRunner(settings=settings).run(
        session=None,
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_upgrade_feedback",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
    )

    assert provider_calls == [
        {
            "settings": settings,
            "profile": "mock_primary",
            "model": "cheap-fast",
            "timeout_seconds": 10,
        },
        {
            "settings": settings,
            "profile": "mock_fallback",
            "model": "strong-default",
            "timeout_seconds": 8,
        },
    ]
    assert result["settings"] is settings
    assert result["primary_provider"].provider_name == "mock_primary"
    assert result["fallback_provider"].provider_name == "mock_fallback"


@pytest.mark.asyncio
async def test_ai_task_runner_http_settings_create_http_profile_providers(monkeypatch):
    async def fake_run_ai_task(**kwargs):
        return kwargs

    monkeypatch.setattr(deps, "run_ai_task", fake_run_ai_task)
    settings = Settings(
        llm_provider="http",
        llm_primary_http_base_url="https://primary.example/v1",
        llm_primary_http_api_key="primary-key",
        llm_primary_http_model="cheap-prod-model",
        llm_fallback_http_base_url="https://fallback.example/v1",
        llm_fallback_http_api_key="fallback-key",
        llm_fallback_http_model="strong-prod-model",
    )

    result = await deps.AITaskRunner(settings=settings).run(
        session=None,
        task_type=TaskType.sentence,
        task_name="sentence_challenge_generation",
        student_id="s1",
        payload={"draft": "tiny draft"},
        output_schema=TinyOutput,
        prompt_key="sentence_challenge_generation",
        input_summary="tiny test",
        deterministic_fallback_factory=local_fallback,
    )

    primary_provider = result["primary_provider"]
    fallback_provider = result["fallback_provider"]
    assert isinstance(primary_provider, HttpJsonLLMProvider)
    assert isinstance(fallback_provider, HttpJsonLLMProvider)
    assert primary_provider.base_url == "https://primary.example/v1"
    assert primary_provider.model_name == "cheap-prod-model"
    assert primary_provider.timeout_seconds == 8
    assert fallback_provider.base_url == "https://fallback.example/v1"
    assert fallback_provider.model_name == "strong-prod-model"
    assert fallback_provider.timeout_seconds == 7
