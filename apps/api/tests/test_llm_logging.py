from datetime import datetime, timezone

import pytest
from pydantic import BaseModel
from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.ai_tasks import log_llm_result, run_validated_llm_task
from app.services.llm_provider import LLMProviderResponse


class LegacyOutput(BaseModel):
    message: str


class LegacyProvider:
    provider_name = "legacy-http"
    model_name = "legacy-model"

    async def complete_json(self, task_name: str, payload: dict) -> LLMProviderResponse:
        return LLMProviderResponse(
            parsed_json={"message": "ok"},
            raw_response='{"message":"ok"}',
            provider=self.provider_name,
            model=self.model_name,
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        )


def test_log_llm_result_persists_structured_output(session):
    improvement = "把画面写得更具体"

    log_llm_result(
        session=session,
        student_id="s1",
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        provider="mock",
        model="mock",
        prompt_version="test-v1",
        input_summary="学生把句子改得更生动",
        raw_response='{"specific_improvement":"把画面写得更具体"}',
        output_json={"specific_improvement": improvement},
        validation_ok=True,
        error_message="",
        retry_count=0,
    )

    saved = session.exec(select(LLMCallLog)).one()

    assert saved.student_id == "s1"
    assert saved.task_type == TaskType.sentence
    assert saved.task_name == "sentence_upgrade_feedback"
    assert saved.provider == "mock"
    assert saved.model == "mock"
    assert saved.prompt_version == "test-v1"
    assert saved.raw_response
    assert saved.validation_ok is True
    assert saved.retry_count == 0
    assert saved.output_json["specific_improvement"] == improvement
    assert saved.usage_available is False
    assert saved.usage_source == "unavailable"
    assert saved.prompt_tokens is None
    assert saved.completion_tokens is None
    assert saved.total_tokens is None
    assert saved.estimated_cost is None


def test_log_llm_result_persists_usage_latency_and_cost(session):
    log_llm_result(
        session=session,
        student_id="s1",
        task_type=TaskType.sentence,
        task_name="sentence_challenge_generation",
        prompt_key="sentence_challenge_generation",
        provider="http",
        model="test-model",
        prompt_version="v0.5b-2026-06-08",
        input_summary="句子挑战生成；年级：四年级",
        raw_response="{}",
        output_json={},
        validation_ok=True,
        error_message="",
        retry_count=0,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost=0.00025,
        latency_ms=45,
    )

    saved = session.exec(select(LLMCallLog)).one()

    assert saved.prompt_key == "sentence_challenge_generation"
    assert saved.prompt_tokens == 100
    assert saved.completion_tokens == 50
    assert saved.total_tokens == 150
    assert saved.estimated_cost == 0.00025
    assert saved.latency_ms == 45
    assert saved.usage_available is True
    assert saved.usage_source == "legacy_usage_fields"
    assert saved.usage_is_estimated is False
    assert saved.usage_details_json["prompt_tokens"] == 100
    assert saved.cost_source == "legacy_estimated_cost"
    assert saved.cost_error_code == ""
    assert saved.pricing_snapshot_id is None
    assert saved.pricing_snapshot_version == ""


@pytest.mark.asyncio
async def test_run_validated_llm_task_marks_legacy_explicit_cost_inputs(session):
    result = await run_validated_llm_task(
        provider=LegacyProvider(),
        session=session,
        student_id="s1",
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        payload={},
        output_model=LegacyOutput,
        fallback=LegacyOutput(message="fallback"),
        input_summary="legacy path",
        prompt_version="legacy-v1",
        input_cost_per_1k_tokens=0.01,
        output_cost_per_1k_tokens=0.02,
    )

    saved = session.exec(select(LLMCallLog)).one()
    assert result.output == LegacyOutput(message="ok")
    assert saved.estimated_cost == 0.002
    assert saved.cost_source == "legacy_explicit_cost_rates"
    assert saved.usage_details_json["legacy_pricing_source"] == "explicit_cost_parameters"
    assert saved.pricing_snapshot_id is None
    assert saved.pricing_snapshot_version == ""


def test_log_llm_result_persists_v06b_scaffold_metadata(session):
    request_started_at = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone.utc)
    response_received_at = datetime(2026, 6, 25, 10, 0, 1, tzinfo=timezone.utc)

    log_llm_result(
        session=session,
        student_id="s1",
        task_type=TaskType.essay,
        task_name="material_questions",
        prompt_key="material_questions",
        provider="mock",
        model="mock",
        prompt_version="v0.6b-2026-06-25",
        input_summary="写作城堡素材问题",
        raw_response="{}",
        output_json={},
        validation_ok=True,
        error_message="",
        retry_count=0,
        topic_type="person_portrait",
        topic_variant="default",
        scaffold_template_version="person_portrait.default.v0.6b.1",
        source_policy_summary="real_experience,observation,child_confirmed",
        request_started_at=request_started_at,
        response_received_at=response_received_at,
        duration_ms=1000,
    )

    saved = session.exec(select(LLMCallLog)).one()

    assert saved.topic_type == "person_portrait"
    assert saved.topic_variant == "default"
    assert saved.scaffold_template_version == "person_portrait.default.v0.6b.1"
    assert saved.source_policy_summary == "real_experience,observation,child_confirmed"
    assert saved.request_started_at is not None
    assert saved.response_received_at is not None
    assert saved.duration_ms == 1000
