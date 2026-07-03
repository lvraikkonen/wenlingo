from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.admin_alpha_routes.common import _product_day, require_alpha_admin_token
from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.domain.models import LLMCallLog, ProductEvent

router = APIRouter()


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
    aggregates: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for log in session.exec(select(LLMCallLog)).all():
        usage_date = _product_day(log.created_at, settings.llm_daily_limit_timezone)
        final_status = log.final_status or (
            "primary_success" if log.validation_ok else "failed"
        )
        key = (
            usage_date,
            log.task_name,
            log.resolved_provider or log.provider,
            log.resolved_model or log.model,
            final_status,
        )
        row = aggregates.setdefault(
            key,
            {
                "date": usage_date,
                "task_type": log.task_name,
                "provider": log.resolved_provider or log.provider,
                "model": log.resolved_model or log.model,
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
            },
        )
        row["call_count"] += 1
        status = row["final_status"]
        if status == "primary_success":
            row["success_count"] += 1
        elif status == "fallback_success":
            row["success_count"] += 1
            row["fallback_success_count"] += 1
        elif status == "deterministic_fallback_used":
            row["deterministic_fallback_count"] += 1
        elif status == "failed":
            row["failure_count"] += 1
        row["prompt_tokens"] += log.prompt_tokens or 0
        row["completion_tokens"] += log.completion_tokens or 0
        row["total_tokens"] += log.total_tokens or 0
        row["estimated_cost"] += log.estimated_cost or 0.0
        row["latency_ms_total"] += log.latency_ms

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
        row.pop("latency_ms_total", None)
        rows.append(row)
    return {"pricing_configured": pricing_configured, "usage": rows}
