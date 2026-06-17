from collections.abc import Callable
from dataclasses import dataclass
import json
from time import perf_counter
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.core.config import Settings
from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.ai_routing import (
    ModelPricing,
    PricingStatus,
    TaskFallbackReason,
    TaskFinalStatus,
    resolve_task_route,
)
from app.services.llm_provider import LLMProvider, LLMProviderResponse
from app.services.llm_usage import llm_daily_limit_reached


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class AITaskResult(Generic[T]):
    output: T
    log: LLMCallLog | None
    status: str


@dataclass(frozen=True)
class FailureContext:
    task_name: str
    fallback_reason: str
    errors: tuple[str, ...]


@dataclass(frozen=True)
class AttemptRecord:
    attempt_index: int
    role: str
    provider: str
    model: str
    status: str
    error_class: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    pricing_status: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "attempt_index": self.attempt_index,
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "error_class": self.error_class,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "pricing_status": self.pricing_status,
        }


def _provider_name(provider: LLMProvider) -> str:
    return getattr(provider, "provider_name", provider.__class__.__name__)


def _model_name(provider: LLMProvider) -> str:
    return getattr(provider, "model_name", "unknown")


def _usage_token(response: LLMProviderResponse | None, key: str) -> int:
    if response is None or response.usage is None:
        return 0
    return int(response.usage.get(key) or 0)


def _usage_total_tokens(
    response: LLMProviderResponse | None,
    prompt_tokens: int,
    completion_tokens: int,
) -> int:
    total_tokens = _usage_token(response, "total_tokens")
    return total_tokens or prompt_tokens + completion_tokens


def _estimate_cost(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    pricing: ModelPricing | None,
) -> float:
    if pricing is None:
        return 0.0
    return (prompt_tokens / 1000 * pricing.input_cost_per_1k_tokens) + (
        completion_tokens / 1000 * pricing.output_cost_per_1k_tokens
    )


def _attempt_pricing_status(pricing: ModelPricing | None, route_status: str) -> str:
    if pricing is not None:
        return PricingStatus.CONFIGURED
    return route_status or PricingStatus.UNAVAILABLE


def _classify_provider_exception(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return TaskFallbackReason.TIMEOUT
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return TaskFallbackReason.RATE_LIMIT
    if isinstance(exc, json.JSONDecodeError):
        return TaskFallbackReason.MALFORMED_JSON
    message = str(exc).lower()
    if "rate" in message and "limit" in message:
        return TaskFallbackReason.RATE_LIMIT
    return TaskFallbackReason.API_ERROR


def _coerce_fallback_output(
    factory: Callable[[FailureContext], T | dict[str, Any]],
    output_schema: type[T],
    context: FailureContext,
) -> T:
    output = factory(context)
    if isinstance(output, output_schema):
        return output
    return output_schema.model_validate(output)


def _record_log(
    *,
    session: Session | None,
    student_id: str | None,
    task_type: TaskType,
    task_name: str,
    prompt_key: str,
    prompt_version: str,
    input_summary: str,
    attempts: list[AttemptRecord],
    final_status: str,
    output: BaseModel | None,
    raw_response: str,
    fallback_reason: str,
    error_message: str,
    resolved_provider: str,
    resolved_model: str,
    pricing_status: str | None = None,
) -> LLMCallLog | None:
    if session is None:
        return None

    prompt_tokens = sum(attempt.prompt_tokens for attempt in attempts)
    completion_tokens = sum(attempt.completion_tokens for attempt in attempts)
    total_tokens = sum(attempt.total_tokens for attempt in attempts)
    estimated_cost = sum(attempt.estimated_cost for attempt in attempts)
    latency_ms = sum(attempt.latency_ms for attempt in attempts)
    primary_attempt = next(
        (attempt for attempt in attempts if attempt.role == "primary"),
        None,
    )
    fallback_attempt = next(
        (attempt for attempt in attempts if attempt.role == "fallback"),
        None,
    )
    validation_ok = final_status in {
        TaskFinalStatus.PRIMARY_SUCCESS,
        TaskFinalStatus.FALLBACK_SUCCESS,
    }
    log = LLMCallLog(
        student_id=student_id,
        task_type=task_type,
        task_name=task_name,
        prompt_key=prompt_key,
        provider=resolved_provider,
        model=resolved_model,
        resolved_provider=resolved_provider,
        resolved_model=resolved_model,
        primary_provider=primary_attempt.provider if primary_attempt else "",
        primary_model=primary_attempt.model if primary_attempt else "",
        fallback_provider=fallback_attempt.provider if fallback_attempt else "",
        fallback_model=fallback_attempt.model if fallback_attempt else "",
        fallback_reason=fallback_reason,
        attempt_count=len(attempts),
        final_status=final_status,
        pricing_status=pricing_status or _overall_pricing_status(attempts),
        attempt_summaries=[attempt.to_summary() for attempt in attempts],
        prompt_version=prompt_version,
        input_summary=input_summary,
        raw_response=raw_response,
        output_json=output.model_dump() if output is not None else {},
        validation_ok=validation_ok,
        error_message=error_message,
        retry_count=max(len(attempts) - 1, 0),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
    )
    session.add(log)
    session.flush()
    return log


def _overall_pricing_status(attempts: list[AttemptRecord]) -> str:
    if not attempts:
        return PricingStatus.UNAVAILABLE
    if all(attempt.pricing_status == PricingStatus.CONFIGURED for attempt in attempts):
        return PricingStatus.CONFIGURED
    if any(attempt.pricing_status == PricingStatus.UNCONFIGURED for attempt in attempts):
        return PricingStatus.UNCONFIGURED
    return PricingStatus.UNAVAILABLE


async def _attempt_provider(
    *,
    attempt_index: int,
    role: str,
    provider: LLMProvider,
    task_name: str,
    payload: dict[str, Any],
    output_schema: type[T],
    validate_output: Callable[[T], Any] | None,
    pricing: ModelPricing | None,
    route_pricing_status: str,
) -> tuple[T | None, LLMProviderResponse | None, AttemptRecord, str]:
    response: LLMProviderResponse | None = None
    provider_name = _provider_name(provider)
    model_name = _model_name(provider)
    output: T | None = None
    started_at = perf_counter()
    try:
        response = await provider.complete_json(task_name, payload)
        provider_name = response.provider
        model_name = response.model
    except Exception as exc:
        reason = _classify_provider_exception(exc)
        error_class = exc.__class__.__name__
    else:
        try:
            output = output_schema.model_validate(response.parsed_json)
        except ValidationError as exc:
            reason = TaskFallbackReason.SCHEMA_VALIDATION_FAILED
            error_class = exc.__class__.__name__
            output = None
        else:
            try:
                validation_result = None
                if validate_output is not None:
                    validation_result = validate_output(output)
                if validation_result is False:
                    raise ValueError("task validation returned False")
            except Exception as exc:
                reason = TaskFallbackReason.TASK_VALIDATION_FAILED
                error_class = exc.__class__.__name__
                output = None
            else:
                reason = "success"
                error_class = ""
    latency_ms = int((perf_counter() - started_at) * 1000)
    prompt_tokens = _usage_token(response, "prompt_tokens")
    completion_tokens = _usage_token(response, "completion_tokens")
    total_tokens = _usage_total_tokens(response, prompt_tokens, completion_tokens)
    attempt = AttemptRecord(
        attempt_index=attempt_index,
        role=role,
        provider=provider_name,
        model=model_name,
        status=reason,
        error_class=error_class,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=_estimate_cost(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            pricing=pricing,
        ),
        pricing_status=_attempt_pricing_status(pricing, route_pricing_status),
    )
    return output, response, attempt, reason


async def run_ai_task(
    *,
    settings: Settings,
    session: Session | None,
    task_type: TaskType,
    task_name: str,
    student_id: str | None,
    payload: dict[str, Any],
    output_schema: type[T],
    prompt_key: str,
    input_summary: str,
    deterministic_fallback_factory: Callable[[FailureContext], T | dict[str, Any]] | None,
    validate_output: Callable[[T], Any] | None = None,
    primary_provider: LLMProvider,
    fallback_provider: LLMProvider,
    daily_limit: int | None = None,
    prompt_version: str = "",
) -> AITaskResult[T]:
    route = resolve_task_route(settings, task_name, prompt_key)
    effective_limit = daily_limit if daily_limit is not None else route.task.daily_limit
    effective_prompt_version = prompt_version or route.prompt_key

    if (
        session is not None
        and student_id is not None
        and settings.llm_daily_limit_enabled
        and llm_daily_limit_reached(
            session=session,
            student_id=student_id,
            task_name=task_name,
            limit=effective_limit,
            timezone_name=settings.llm_daily_limit_timezone,
        )
    ):
        if deterministic_fallback_factory is None:
            raise RuntimeError("LLM daily limit reached and no deterministic fallback is configured")
        fallback_context = FailureContext(
            task_name=task_name,
            fallback_reason=TaskFinalStatus.DAILY_LIMIT_REACHED,
            errors=("daily limit reached",),
        )
        output = _coerce_fallback_output(
            deterministic_fallback_factory,
            output_schema,
            fallback_context,
        )
        log = _record_log(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=route.prompt_key,
            prompt_version=effective_prompt_version,
            input_summary=input_summary,
            attempts=[],
            final_status=TaskFinalStatus.DAILY_LIMIT_REACHED,
            output=output,
            raw_response="",
            fallback_reason="",
            error_message="daily limit reached",
            resolved_provider="local_fallback",
            resolved_model="local_fallback",
            pricing_status=route.pricing_status,
        )
        return AITaskResult(output=output, log=log, status=TaskFinalStatus.DAILY_LIMIT_REACHED)

    attempts: list[AttemptRecord] = []
    errors: list[str] = []

    primary_output, primary_response, primary_attempt, primary_reason = await _attempt_provider(
        attempt_index=1,
        role="primary",
        provider=primary_provider,
        task_name=task_name,
        payload=payload,
        output_schema=output_schema,
        validate_output=validate_output,
        pricing=route.primary_pricing,
        route_pricing_status=route.pricing_status,
    )
    attempts.append(primary_attempt)
    if primary_output is not None and primary_response is not None:
        log = _record_log(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=route.prompt_key,
            prompt_version=effective_prompt_version,
            input_summary=input_summary,
            attempts=attempts,
            final_status=TaskFinalStatus.PRIMARY_SUCCESS,
            output=primary_output,
            raw_response=primary_response.raw_response,
            fallback_reason="",
            error_message="",
            resolved_provider=primary_response.provider,
            resolved_model=primary_response.model,
        )
        return AITaskResult(output=primary_output, log=log, status=TaskFinalStatus.PRIMARY_SUCCESS)
    errors.append(f"primary {primary_reason}")

    fallback_output, fallback_response, fallback_attempt, fallback_reason = await _attempt_provider(
        attempt_index=2,
        role="fallback",
        provider=fallback_provider,
        task_name=task_name,
        payload=payload,
        output_schema=output_schema,
        validate_output=validate_output,
        pricing=route.fallback_pricing,
        route_pricing_status=route.pricing_status,
    )
    attempts.append(fallback_attempt)
    if fallback_output is not None and fallback_response is not None:
        log = _record_log(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=route.prompt_key,
            prompt_version=effective_prompt_version,
            input_summary=input_summary,
            attempts=attempts,
            final_status=TaskFinalStatus.FALLBACK_SUCCESS,
            output=fallback_output,
            raw_response=fallback_response.raw_response,
            fallback_reason=primary_reason,
            error_message="",
            resolved_provider=fallback_response.provider,
            resolved_model=fallback_response.model,
        )
        return AITaskResult(output=fallback_output, log=log, status=TaskFinalStatus.FALLBACK_SUCCESS)
    errors.append(f"fallback {fallback_reason}")

    if deterministic_fallback_factory is not None:
        deterministic_reason = fallback_reason or primary_reason or TaskFallbackReason.UNKNOWN_ERROR
        fallback_context = FailureContext(
            task_name=task_name,
            fallback_reason=deterministic_reason,
            errors=tuple(errors),
        )
        output = _coerce_fallback_output(
            deterministic_fallback_factory,
            output_schema,
            fallback_context,
        )
        log = _record_log(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=route.prompt_key,
            prompt_version=effective_prompt_version,
            input_summary=input_summary,
            attempts=attempts,
            final_status=TaskFinalStatus.DETERMINISTIC_FALLBACK_USED,
            output=output,
            raw_response="",
            fallback_reason=deterministic_reason,
            error_message="; ".join(errors),
            resolved_provider="local_fallback",
            resolved_model="local_fallback",
        )
        return AITaskResult(
            output=output,
            log=log,
            status=TaskFinalStatus.DETERMINISTIC_FALLBACK_USED,
        )

    raise RuntimeError(f"AI task failed: {'; '.join(errors)}") from None
