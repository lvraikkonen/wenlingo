from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.admin_alpha_routes.common import _product_day, require_alpha_admin_token
from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.domain.models import LLMCallLog, ProductEvent

router = APIRouter()


def _p50(values: list[int]) -> int:
    if not values:
        return 0
    sorted_values = sorted(values)
    return sorted_values[(len(sorted_values) - 1) // 2]


def _elapsed_ms(start, end) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


def _final_status(log: LLMCallLog) -> str:
    return log.final_status or ("primary_success" if log.validation_ok else "failed")


def _has_provider_attempt(log: LLMCallLog) -> bool:
    return bool(
        log.attempt_count > 0
        or log.attempt_summaries
        or log.primary_provider
        or log.fallback_provider
    )


def _attempt_provider_model(log: LLMCallLog) -> tuple[str, str] | None:
    for provider, model in (
        (log.primary_provider, log.primary_model),
        (log.fallback_provider, log.fallback_model),
    ):
        if provider and model:
            return provider, model

    attempts = [
        attempt
        for attempt in log.attempt_summaries
        if isinstance(attempt, dict)
    ]
    for role in ("primary", "fallback"):
        for attempt in attempts:
            if attempt.get("role") != role:
                continue
            provider = attempt.get("provider")
            model = attempt.get("model")
            if isinstance(provider, str) and provider and isinstance(model, str) and model:
                return provider, model
    return None


def _aggregation_provider_model(log: LLMCallLog) -> tuple[str, str]:
    provider = log.resolved_provider or log.provider
    model = log.resolved_model or log.model
    attempted = _attempt_provider_model(log)
    if attempted is not None and (
        not provider
        or not model
        or (provider == "local_fallback" and model == "local_fallback")
    ):
        return attempted
    return provider, model


def _usage_applicable(log: LLMCallLog, final_status: str) -> bool:
    if final_status == "daily_limit_reached":
        return False
    if _has_provider_attempt(log):
        return True
    if final_status == "deterministic_fallback_used":
        return False
    return bool(log.resolved_provider or log.provider)


def _material_cards(output_json: dict[str, Any]) -> list[dict[str, Any]]:
    cards = output_json.get("cards")
    if not isinstance(cards, list):
        return []
    return [card for card in cards if isinstance(card, dict)]


def _has_material_card_source_references(log: LLMCallLog) -> bool:
    for card in _material_cards(log.output_json):
        source_refs = card.get("source_refs")
        source_answer_ids = card.get("source_answer_ids")
        if isinstance(source_refs, list) and source_refs:
            return True
        if isinstance(source_answer_ids, list) and source_answer_ids:
            return True
    return False


def _material_card_schema_success(log: LLMCallLog, final_status: str) -> bool:
    if log.task_name != "material_card_generation":
        return False
    if log.validation_ok:
        return True
    return final_status == "deterministic_fallback_used" and bool(
        _material_cards(log.output_json)
    )


def _is_timeout_like(log: LLMCallLog, final_status: str) -> bool:
    if final_status == "timeout":
        return True
    if log.fallback_reason == "timeout" or log.cost_error_code == "timeout":
        return True
    return "timeout" in log.error_message.lower()


@router.get("/ai-usage", dependencies=[Depends(require_alpha_admin_token)])
def alpha_admin_ai_usage(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    pricing_configured = (
        settings.llm_input_cost_per_1k_tokens > 0
        or settings.llm_output_cost_per_1k_tokens > 0
        or settings.llm_primary_input_cost_per_1k_tokens > 0
        or settings.llm_primary_output_cost_per_1k_tokens > 0
        or settings.llm_fallback_input_cost_per_1k_tokens > 0
        or settings.llm_fallback_output_cost_per_1k_tokens > 0
    )
    aggregates: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for log in session.exec(select(LLMCallLog)).all():
        usage_date = _product_day(log.created_at, settings.llm_daily_limit_timezone)
        final_status = _final_status(log)
        provider, model = _aggregation_provider_model(log)
        key = (
            usage_date,
            log.task_name,
            provider,
            model,
        )
        row = aggregates.setdefault(
            key,
            {
                "date": usage_date,
                "task_type": log.task_name,
                "provider": provider,
                "model": model,
                "final_status": final_status,
                "call_count": 0,
                "success_count": 0,
                "fallback_success_count": 0,
                "deterministic_fallback_count": 0,
                "failure_count": 0,
                "daily_limit_hit_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0.0,
                "pricing_status": log.pricing_status or "pricing_unconfigured",
                "latency_ms_total": 0,
                "avg_latency_ms": 0,
                "streaming_enabled_count": 0,
                "stream_completed_count": 0,
                "client_disconnect_count": 0,
                "provider_failed_before_visible_content_count": 0,
                "provider_failed_after_visible_content_count": 0,
                "usage_available_count": 0,
                "usage_missing_count": 0,
                "calls_with_usage_applicable": 0,
                "usage_available_rate": 0.0,
                "first_provider_delta_p50_ms": 0,
                "first_visible_content_p50_ms": 0,
                "provider_stream_duration_p50_ms": 0,
                "live_llm_success_count": 0,
                "timeout_count": 0,
                "schema_validation_success_count": 0,
                "source_reference_success_count": 0,
                "_final_status_counts": Counter(),
                "_pricing_status_counts": Counter(),
                "_first_provider_delta_ms": [],
                "_first_visible_content_ms": [],
                "_provider_stream_duration_ms": [],
            },
        )
        row["call_count"] += 1
        row["_final_status_counts"][final_status] += 1
        row["_pricing_status_counts"][log.pricing_status or "pricing_unconfigured"] += 1
        status = final_status
        if status == "primary_success":
            row["success_count"] += 1
        elif status == "fallback_success":
            row["success_count"] += 1
            row["fallback_success_count"] += 1
        elif status == "deterministic_fallback_used":
            row["deterministic_fallback_count"] += 1
        elif status == "failed":
            row["failure_count"] += 1

        usage_applicable = _usage_applicable(log, final_status)
        if usage_applicable:
            row["calls_with_usage_applicable"] += 1
            if log.usage_available:
                row["usage_available_count"] += 1
            else:
                row["usage_missing_count"] += 1

        if log.usage_available:
            if log.prompt_tokens is not None:
                row["prompt_tokens"] += log.prompt_tokens
            if log.completion_tokens is not None:
                row["completion_tokens"] += log.completion_tokens
            if log.total_tokens is not None:
                row["total_tokens"] += log.total_tokens
            if log.estimated_cost is not None:
                row["estimated_cost"] += log.estimated_cost

        row["latency_ms_total"] += log.latency_ms

        if log.streaming_enabled:
            row["streaming_enabled_count"] += 1
        stream_status = log.stream_final_status or ""
        if stream_status in {"completed", "client_disconnected_after_visible_content_completed"}:
            row["stream_completed_count"] += 1
        if stream_status.startswith("client_disconnected") or log.client_disconnected_at is not None:
            row["client_disconnect_count"] += 1
        if stream_status == "provider_failed_before_visible_content":
            row["provider_failed_before_visible_content_count"] += 1
        if stream_status == "provider_failed_after_visible_content":
            row["provider_failed_after_visible_content_count"] += 1

        first_provider_delta_ms = _elapsed_ms(
            log.stream_started_at,
            log.first_provider_delta_at,
        )
        if first_provider_delta_ms is not None:
            row["_first_provider_delta_ms"].append(first_provider_delta_ms)
        first_visible_content_ms = _elapsed_ms(
            log.stream_started_at,
            log.first_visible_content_at,
        )
        if first_visible_content_ms is not None:
            row["_first_visible_content_ms"].append(first_visible_content_ms)
        provider_stream_duration_ms = _elapsed_ms(
            log.stream_started_at,
            log.provider_stream_completed_at,
        )
        if provider_stream_duration_ms is not None:
            row["_provider_stream_duration_ms"].append(provider_stream_duration_ms)

        if _is_timeout_like(log, final_status):
            row["timeout_count"] += 1
        if (
            log.task_name == "material_card_generation"
            and log.validation_ok
            and final_status in {"primary_success", "fallback_success"}
        ):
            row["live_llm_success_count"] += 1
        if _material_card_schema_success(log, final_status):
            row["schema_validation_success_count"] += 1
            if _has_material_card_source_references(log):
                row["source_reference_success_count"] += 1

    limit_hits: Counter[tuple[str, str]] = Counter()
    events = session.exec(
        select(ProductEvent).where(ProductEvent.event_type == "ai_daily_limit_reached")
    ).all()
    for event in events:
        task_type = event.payload.get("task_type")
        if isinstance(task_type, str) and task_type:
            usage_date = _product_day(
                event.created_at,
                settings.llm_daily_limit_timezone,
            )
            limit_hits[(usage_date, task_type)] += 1

    rows = []
    for key in sorted(aggregates):
        row = aggregates[key]
        row["daily_limit_hit_count"] += limit_hits[(row["date"], row["task_type"])]
        row["estimated_cost"] = round(row["estimated_cost"], 6)
        row["avg_latency_ms"] = (
            int(row["latency_ms_total"] / row["call_count"])
            if row["call_count"]
            else 0
        )
        status_counts = row.pop("_final_status_counts")
        row["final_status"] = (
            next(iter(status_counts)) if len(status_counts) == 1 else "mixed"
        )
        pricing_status_counts = row.pop("_pricing_status_counts")
        row["pricing_status"] = (
            next(iter(pricing_status_counts))
            if len(pricing_status_counts) == 1
            else "mixed"
        )
        row["usage_available_rate"] = (
            row["usage_available_count"] / row["calls_with_usage_applicable"]
            if row["calls_with_usage_applicable"]
            else 0.0
        )
        row["first_provider_delta_p50_ms"] = _p50(
            row.pop("_first_provider_delta_ms")
        )
        row["first_visible_content_p50_ms"] = _p50(
            row.pop("_first_visible_content_ms")
        )
        row["provider_stream_duration_p50_ms"] = _p50(
            row.pop("_provider_stream_duration_ms")
        )
        row.pop("latency_ms_total", None)
        rows.append(row)
    return {"pricing_configured": pricing_configured, "usage": rows}
