from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
from time import perf_counter
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.core.config import Settings
from app.domain.enums import TaskType
from app.domain.models import LLMCallLog, utcnow
from app.services.ai_routing import (
    ModelPricing,
    PricingStatus,
    TaskFallbackReason,
    TaskFinalStatus,
    resolve_task_route,
)
from app.services.llm_provider import LLMProvider, LLMProviderResponse
from app.services.llm_usage_accounting import normalize_usage_and_cost
from app.services.llm_usage import (
    consume_daily_task_reservation,
    fail_daily_task_reservation,
    reserve_daily_task_limit_slot,
)


T = TypeVar("T", bound=BaseModel)
ERROR_MESSAGE_MAX_CHARS = 300


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
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    estimated_cost: float | None
    pricing_status: str
    provider_response_received: bool
    usage_available: bool
    usage_source: str
    usage_is_estimated: bool
    usage_details_json: dict[str, Any]
    cost_source: str
    cost_error_code: str
    pricing_snapshot_id: str | None
    pricing_snapshot_version: str
    provider_reported_cost_usd: float | None
    cost_calculation_version: str
    request_started_at: datetime | None = None
    response_received_at: datetime | None = None
    error_message: str = ""
    validation_errors: tuple[dict[str, str], ...] = ()

    def to_summary(self) -> dict[str, Any]:
        summary = {
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
            "provider_response_received": self.provider_response_received,
            "usage_available": self.usage_available,
            "usage_source": self.usage_source,
            "usage_is_estimated": self.usage_is_estimated,
            "usage_details_json": self.usage_details_json,
            "cost_source": self.cost_source,
            "cost_error_code": self.cost_error_code,
            "pricing_snapshot_id": self.pricing_snapshot_id,
            "pricing_snapshot_version": self.pricing_snapshot_version,
            "provider_reported_cost_usd": self.provider_reported_cost_usd,
            "cost_calculation_version": self.cost_calculation_version,
        }
        if self.error_message:
            summary["error_message"] = self.error_message
        if self.validation_errors:
            summary["validation_errors"] = list(self.validation_errors)
        return summary


def _provider_name(provider: LLMProvider) -> str:
    return getattr(provider, "provider_name", provider.__class__.__name__)


def _model_name(provider: LLMProvider) -> str:
    return getattr(provider, "model_name", "unknown")


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


def _bounded_error_message(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    if len(message) > ERROR_MESSAGE_MAX_CHARS:
        return message[:ERROR_MESSAGE_MAX_CHARS]
    return message


def _validation_error_summary(exc: ValidationError) -> tuple[dict[str, str], ...]:
    summaries = []
    for error in exc.errors()[:8]:
        loc = ".".join(str(part) for part in error.get("loc", ())) or "__root__"
        summaries.append(
            {
                "loc": loc,
                "type": str(error.get("type", "")),
                "msg": str(error.get("msg", "")),
            }
        )
    return tuple(summaries)


def _coerce_fallback_output(
    factory: Callable[[FailureContext], T | dict[str, Any]],
    output_schema: type[T],
    context: FailureContext,
) -> T:
    output = factory(context)
    if isinstance(output, output_schema):
        return output
    return output_schema.model_validate(output)


def _source_policy_summary(scaffold: dict[str, Any]) -> str:
    source_policy = scaffold.get("source_policy")
    if not isinstance(source_policy, dict):
        return ""
    raw_sources = source_policy.get("required_for_content")
    if not isinstance(raw_sources, list):
        raw_sources = source_policy.get("allowed")
    if not isinstance(raw_sources, list):
        return ""
    sources = [source for source in raw_sources if isinstance(source, str) and source.strip()]
    return ",".join(sources)


def _scaffold_observability_metadata(payload: dict[str, Any]) -> dict[str, str]:
    scaffold = payload.get("scaffold")
    if not isinstance(scaffold, dict):
        return {
            "topic_type": "",
            "topic_variant": "",
            "scaffold_template_version": "",
            "source_policy_summary": "",
        }
    return {
        "topic_type": str(scaffold.get("topic_type") or ""),
        "topic_variant": str(scaffold.get("topic_variant") or ""),
        "scaffold_template_version": str(scaffold.get("scaffold_template_version") or ""),
        "source_policy_summary": _source_policy_summary(scaffold),
    }


def _sum_int_or_none(values: list[int | None]) -> int | None:
    known_values = [value for value in values if value is not None]
    if not known_values:
        return None
    return sum(known_values)


def _sum_float_or_none(values: list[float | None]) -> float | None:
    known_values = [value for value in values if value is not None]
    if not known_values:
        return None
    return sum(known_values)


def _usage_attempts(attempts: list[AttemptRecord]) -> list[AttemptRecord]:
    return [attempt for attempt in attempts if attempt.usage_available]


def _costable_attempts(attempts: list[AttemptRecord]) -> list[AttemptRecord]:
    return [attempt for attempt in attempts if attempt.estimated_cost is not None]


def _provider_response_attempts(attempts: list[AttemptRecord]) -> list[AttemptRecord]:
    return [attempt for attempt in attempts if attempt.provider_response_received]


def _has_missing_provider_response_usage(attempts: list[AttemptRecord]) -> bool:
    return any(
        attempt.provider_response_received and not attempt.usage_available
        for attempt in attempts
    )


def _has_provider_response_cost_error(attempts: list[AttemptRecord]) -> bool:
    return any(
        attempt.provider_response_received and bool(attempt.cost_error_code)
        for attempt in attempts
    )


def _aggregate_usage_source(attempts: list[AttemptRecord]) -> str:
    if _has_missing_provider_response_usage(attempts):
        return "unavailable"
    available_attempts = _usage_attempts(attempts)
    if not available_attempts:
        if any(attempt.usage_is_estimated for attempt in attempts):
            return "tokenizer_estimate"
        return "unavailable"
    sources = {attempt.usage_source for attempt in available_attempts}
    if len(sources) == 1:
        return available_attempts[0].usage_source
    return "multiple_attempts"


def _aggregate_usage_details(
    *,
    attempts: list[AttemptRecord],
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    usage_unavailable_reason: str | None,
) -> dict[str, Any]:
    if not attempts:
        return {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "usage_unavailable_reason": "no_provider_attempts",
            "attempts": [],
        }
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        **(
            {"usage_unavailable_reason": usage_unavailable_reason}
            if usage_unavailable_reason
            else {}
        ),
        "attempts": [
            {
                "attempt_index": attempt.attempt_index,
                "role": attempt.role,
                "provider": attempt.provider,
                "model": attempt.model,
                "provider_response_received": attempt.provider_response_received,
                "usage_available": attempt.usage_available,
                "usage_source": attempt.usage_source,
                "usage_is_estimated": attempt.usage_is_estimated,
                "usage_details_json": attempt.usage_details_json,
            }
            for attempt in attempts
        ],
    }


def _aggregate_estimated_cost(attempts: list[AttemptRecord]) -> float | None:
    if _has_provider_response_cost_error(attempts):
        return None
    provider_response_attempts = _provider_response_attempts(attempts)
    if not provider_response_attempts:
        return None
    if any(attempt.estimated_cost is None for attempt in provider_response_attempts):
        return None
    return sum(attempt.estimated_cost or 0.0 for attempt in provider_response_attempts)


def _aggregate_cost_source(
    attempts: list[AttemptRecord],
    estimated_cost: float | None,
) -> str:
    costable_attempts = _costable_attempts(_provider_response_attempts(attempts))
    if estimated_cost is None or not costable_attempts:
        return "unavailable"
    sources = {
        attempt.cost_source
        for attempt in costable_attempts
        if attempt.estimated_cost is not None
    }
    if len(sources) == 1:
        return next(iter(sources))
    return "mixed"


def _aggregate_cost_error_code(attempts: list[AttemptRecord]) -> str:
    for attempt in _provider_response_attempts(attempts):
        if attempt.cost_error_code:
            return attempt.cost_error_code
    return ""


def _aggregate_pricing_snapshot_id(attempts: list[AttemptRecord]) -> str | None:
    snapshot_ids = {
        attempt.pricing_snapshot_id
        for attempt in attempts
        if attempt.pricing_snapshot_id is not None
    }
    if len(snapshot_ids) == 1:
        return next(iter(snapshot_ids))
    return None


def _aggregate_pricing_snapshot_version(attempts: list[AttemptRecord]) -> str:
    versions = {
        attempt.pricing_snapshot_version
        for attempt in attempts
        if attempt.pricing_snapshot_version
    }
    if len(versions) == 1:
        return next(iter(versions))
    return ""


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
    payload: dict[str, Any],
    pricing_status: str | None = None,
) -> LLMCallLog | None:
    if session is None:
        return None

    has_missing_provider_response_usage = _has_missing_provider_response_usage(attempts)
    available_usage_attempts = (
        [] if has_missing_provider_response_usage else _usage_attempts(attempts)
    )
    prompt_tokens = _sum_int_or_none(
        [attempt.prompt_tokens for attempt in available_usage_attempts]
    )
    completion_tokens = _sum_int_or_none(
        [attempt.completion_tokens for attempt in available_usage_attempts]
    )
    total_tokens = _sum_int_or_none(
        [attempt.total_tokens for attempt in available_usage_attempts]
    )
    estimated_cost = _aggregate_estimated_cost(attempts)
    provider_reported_cost_usd = _sum_float_or_none(
        [attempt.provider_reported_cost_usd for attempt in attempts]
    )
    latency_ms = sum(attempt.latency_ms for attempt in attempts)
    request_started_at = min(
        (
            attempt.request_started_at
            for attempt in attempts
            if attempt.request_started_at is not None
        ),
        default=None,
    )
    response_received_at = max(
        (
            attempt.response_received_at
            for attempt in attempts
            if attempt.response_received_at is not None
        ),
        default=None,
    )
    scaffold_metadata = _scaffold_observability_metadata(payload)
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
        topic_type=scaffold_metadata["topic_type"],
        topic_variant=scaffold_metadata["topic_variant"],
        scaffold_template_version=scaffold_metadata["scaffold_template_version"],
        source_policy_summary=scaffold_metadata["source_policy_summary"],
        duration_ms=latency_ms,
        request_started_at=request_started_at,
        response_received_at=response_received_at,
        usage_available=bool(available_usage_attempts),
        usage_source=_aggregate_usage_source(attempts),
        usage_is_estimated=(
            not available_usage_attempts
            and any(attempt.usage_is_estimated for attempt in attempts)
        ),
        usage_details_json=_aggregate_usage_details(
            attempts=attempts,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            usage_unavailable_reason=(
                "partial_provider_usage_missing"
                if has_missing_provider_response_usage
                else None
            ),
        ),
        cost_source=_aggregate_cost_source(attempts, estimated_cost),
        cost_error_code=_aggregate_cost_error_code(attempts),
        pricing_snapshot_id=(
            _aggregate_pricing_snapshot_id(attempts)
            if estimated_cost is not None
            else None
        ),
        pricing_snapshot_version=(
            _aggregate_pricing_snapshot_version(attempts)
            if estimated_cost is not None
            else ""
        ),
        provider_reported_cost_usd=provider_reported_cost_usd,
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


def _attempt_error_summary(role: str, reason: str, attempt: AttemptRecord) -> str:
    summary = f"{role} {reason}"
    if attempt.error_message:
        summary = f"{summary}: {attempt.error_message}"
    return summary


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
    validation_errors: tuple[dict[str, str], ...] = ()
    error_message = ""
    request_started_at = utcnow()
    started_at = perf_counter()
    try:
        response = await provider.complete_json(task_name, payload)
        provider_name = response.provider
        model_name = response.model
    except Exception as exc:
        reason = _classify_provider_exception(exc)
        error_class = exc.__class__.__name__
        error_message = _bounded_error_message(exc)
    else:
        try:
            output = output_schema.model_validate(response.parsed_json)
        except ValidationError as exc:
            reason = TaskFallbackReason.SCHEMA_VALIDATION_FAILED
            error_class = exc.__class__.__name__
            validation_errors = _validation_error_summary(exc)
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
                error_message = _bounded_error_message(exc)
                output = None
            else:
                reason = "success"
                error_class = ""
    latency_ms = int((perf_counter() - started_at) * 1000)
    response_received_at = utcnow()
    usage_record = normalize_usage_and_cost(
        provider=provider_name,
        model=model_name,
        role=role,
        provider_usage=response.usage if response is not None else None,
        usage_source=(
            "provider_generation_stats"
            if response is not None and response.usage
            else "unavailable"
        ),
        tokenizer_estimate=None,
        provider_reported_cost_usd=(
            response.provider_reported_cost_usd if response is not None else None
        ),
        pricing=pricing,
    )
    attempt = AttemptRecord(
        attempt_index=attempt_index,
        role=role,
        provider=provider_name,
        model=model_name,
        status=reason,
        error_class=error_class,
        latency_ms=latency_ms,
        prompt_tokens=usage_record.prompt_tokens,
        completion_tokens=usage_record.completion_tokens,
        total_tokens=usage_record.total_tokens,
        estimated_cost=usage_record.estimated_cost_usd,
        pricing_status=_attempt_pricing_status(pricing, route_pricing_status),
        provider_response_received=response is not None,
        usage_available=usage_record.usage_available,
        usage_source=usage_record.usage_source,
        usage_is_estimated=usage_record.usage_is_estimated,
        usage_details_json=usage_record.usage_details_json,
        cost_source=usage_record.cost_source,
        cost_error_code=usage_record.cost_error_code,
        pricing_snapshot_id=usage_record.pricing_snapshot_id,
        pricing_snapshot_version=usage_record.pricing_snapshot_version,
        provider_reported_cost_usd=usage_record.provider_reported_cost_usd,
        cost_calculation_version=usage_record.cost_calculation_version,
        request_started_at=request_started_at,
        response_received_at=response_received_at,
        error_message=error_message,
        validation_errors=validation_errors,
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
    reservation_counter_id: str | None = None
    reservation_token: str | None = None

    if (
        session is not None
        and student_id is not None
        and settings.llm_daily_limit_enabled
        and effective_limit is not None
    ):
        reservation = reserve_daily_task_limit_slot(
            session=session,
            student_id=student_id,
            task_name=task_name,
            limit=effective_limit,
            timezone_name=settings.llm_daily_limit_timezone,
        )
        reservation_counter_id = reservation.counter_id
        reservation_token = reservation.reservation_token
        if not reservation.reserved:
            if deterministic_fallback_factory is None:
                raise RuntimeError(
                    "LLM daily limit reached and no deterministic fallback is configured"
                )
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
                payload=payload,
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
            payload=payload,
        )
        if session is not None:
            consume_daily_task_reservation(
                session=session,
                counter_id=reservation_counter_id,
                reservation_token=reservation_token,
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
            payload=payload,
        )
        if session is not None:
            consume_daily_task_reservation(
                session=session,
                counter_id=reservation_counter_id,
                reservation_token=reservation_token,
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
        try:
            output = _coerce_fallback_output(
                deterministic_fallback_factory,
                output_schema,
                fallback_context,
            )
        except Exception:
            if session is not None:
                fail_daily_task_reservation(
                    session=session,
                    counter_id=reservation_counter_id,
                    reservation_token=reservation_token,
                )
            raise
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
            payload=payload,
        )
        if session is not None:
            consume_daily_task_reservation(
                session=session,
                counter_id=reservation_counter_id,
                reservation_token=reservation_token,
            )
        return AITaskResult(
            output=output,
            log=log,
            status=TaskFinalStatus.DETERMINISTIC_FALLBACK_USED,
        )

    if session is not None:
        fail_daily_task_reservation(
            session=session,
            counter_id=reservation_counter_id,
            reservation_token=reservation_token,
        )
        detailed_errors = [
            _attempt_error_summary(attempt.role, attempt.status, attempt)
            for attempt in attempts
        ]
        _record_log(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=route.prompt_key,
            prompt_version=effective_prompt_version,
            input_summary=input_summary,
            attempts=attempts,
            final_status=TaskFinalStatus.FAILED,
            output=None,
            raw_response="",
            fallback_reason=(
                fallback_reason or primary_reason or TaskFallbackReason.UNKNOWN_ERROR
            ),
            error_message="; ".join(detailed_errors),
            resolved_provider="",
            resolved_model="",
            payload=payload,
            pricing_status=route.pricing_status,
        )
    raise RuntimeError(f"AI task failed: {'; '.join(errors)}") from None
