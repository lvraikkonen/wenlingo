import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    AuthMagicCode,
    Essay,
    EssayVersion,
    GameEvent,
    LLMCallLog,
    ParentAccount,
    ParentSession,
    ParentUser,
    ReadingSession,
    Report,
    SentenceTraining,
    StudentProfile,
)


TIMESTAMP_FIELDS = [
    (ParentUser, "created_at"),
    (ParentAccount, "created_at"),
    (ParentAccount, "updated_at"),
    (AuthMagicCode, "expires_at"),
    (AuthMagicCode, "created_at"),
    (ParentSession, "created_at"),
    (ParentSession, "expires_at"),
    (ParentSession, "last_seen_at"),
    (StudentProfile, "created_at"),
    (AbilityProfile, "updated_at"),
    (Assessment, "created_at"),
    (SentenceTraining, "created_at"),
    (Essay, "created_at"),
    (EssayVersion, "created_at"),
    (ReadingSession, "created_at"),
    (GameEvent, "created_at"),
    (Report, "created_at"),
    (LLMCallLog, "created_at"),
]


NULLABLE_TIMESTAMP_FIELDS = [
    (ParentUser, "account_linked_at"),
    (ParentAccount, "email_verified_at"),
    (ParentAccount, "phone_bound_at"),
    (ParentAccount, "phone_verified_at"),
    (ParentAccount, "last_login_at"),
    (AuthMagicCode, "consumed_at"),
    (AuthMagicCode, "last_attempt_at"),
    (ParentSession, "revoked_at"),
]


JSON_FIELDS = [
    (AbilityProfile, "evidence"),
    (SentenceTraining, "ai_feedback"),
    (Essay, "material_card"),
    (Essay, "outline"),
    (EssayVersion, "ai_feedback"),
    (ReadingSession, "answers"),
    (ReadingSession, "ai_feedback"),
    (GameEvent, "problem_monsters"),
    (GameEvent, "evidence"),
    (Report, "content"),
    (LLMCallLog, "output_json"),
]


def test_timestamp_columns_are_timezone_aware_and_not_nullable():
    for model, field_name in TIMESTAMP_FIELDS:
        column = model.__table__.c[field_name]

        assert column.type.timezone is True, f"{model.__name__}.{field_name}"
        assert column.nullable is False, f"{model.__name__}.{field_name}"


def test_nullable_timestamp_columns_are_timezone_aware():
    for model, field_name in NULLABLE_TIMESTAMP_FIELDS:
        column = model.__table__.c[field_name]

        assert column.type.timezone is True, f"{model.__name__}.{field_name}"
        assert column.nullable is True, f"{model.__name__}.{field_name}"


def test_json_columns_are_not_nullable():
    for model, field_name in JSON_FIELDS:
        column = model.__table__.c[field_name]

        assert column.nullable is False, f"{model.__name__}.{field_name}"


def test_game_event_problem_monsters_are_string_list():
    assert GameEvent.__annotations__["problem_monsters"] == list[str]


def test_ability_history_source_fields_are_indexed():
    index_columns = {
        column.name
        for index in AbilityHistory.__table__.indexes
        for column in index.columns
    }

    assert "ability_name" in index_columns
    assert "source_id" in index_columns


def test_essay_version_labels_are_unique_per_essay(session):
    essay_title = "我学会了骑车"
    first_revision = "我学会了骑车。第一次修改加了动作。"
    duplicate_revision = "我学会了骑车。第二次修改不能重复保存。"

    essay = Essay(student_id="student-1", title=essay_title)
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            content=first_revision,
        )
    )
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            content=duplicate_revision,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_llm_call_log_tracks_provider_prompt_raw_response_and_retry_count():
    log = LLMCallLog(
        task_type=TaskType.essay,
        provider="http",
        model="test-model",
        prompt_version="v0.2-quality-spine-2026-05-14",
        input_summary="作文题目：我学会了骑车",
        raw_response='{"strengths":["清楚","有心情"]}',
        output_json={"strengths": ["清楚", "有心情"]},
        validation_ok=True,
        error_message="",
        retry_count=1,
    )

    assert log.task_type == TaskType.essay
    assert log.provider == "http"
    assert log.model == "test-model"
    assert log.prompt_version == "v0.2-quality-spine-2026-05-14"
    assert log.input_summary == "作文题目：我学会了骑车"
    assert log.raw_response == '{"strengths":["清楚","有心情"]}'
    assert log.output_json == {"strengths": ["清楚", "有心情"]}
    assert log.validation_ok is True
    assert log.error_message == ""
    assert log.retry_count == 1


def test_llm_call_log_default_prompt_version_uses_registry_version():
    log = LLMCallLog(
        task_type=TaskType.essay,
        input_summary="manual construction without prompt version",
    )

    assert log.prompt_version == ""


def test_llm_call_log_tracks_student_and_task_name():
    log = LLMCallLog(
        student_id="s1",
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        provider="http",
        model="test-model",
        prompt_version="v0.2-family-test-2026-05-15",
        input_summary="句子快练；原句长度：5；升级句长度：18",
        raw_response='{"encouragement":"写清楚了"}',
        output_json={"encouragement": "写清楚了"},
        validation_ok=True,
        error_message="",
        retry_count=0,
    )

    assert log.student_id == "s1"
    assert log.task_name == "sentence_upgrade_feedback"


def test_sentence_training_can_represent_generated_challenge():
    training = SentenceTraining(
        student_id="student-1",
        source_sentence="小猫跑了。",
        upgraded_sentence="",
        focus="动作描写",
        status="generated",
        challenge_prompt="请把句子写具体，加上动作和样子。",
        hint="可以写小猫怎么跑、跑到哪里、看起来怎么样。",
        target_skill="action_expression",
    )

    assert training.status == "generated"
    assert training.challenge_prompt.startswith("请把句子")
    assert training.hint.startswith("可以写")
    assert training.target_skill == "action_expression"
    assert training.completed_at is None


def test_llm_call_log_records_prompt_usage_latency_and_cost():
    log = LLMCallLog(
        student_id="student-1",
        task_type=TaskType.sentence,
        task_name="sentence_challenge_generation",
        prompt_key="sentence_challenge_generation",
        prompt_version="v0.5b-2026-06-08",
        provider="http",
        model="test-model",
        input_summary="句子挑战生成；年级：四年级",
        raw_response="{}",
        output_json={},
        prompt_tokens=12,
        completion_tokens=8,
        total_tokens=20,
        estimated_cost=0.0004,
        latency_ms=321,
    )

    assert log.prompt_key == "sentence_challenge_generation"
    assert log.prompt_tokens == 12
    assert log.completion_tokens == 8
    assert log.total_tokens == 20
    assert log.estimated_cost == 0.0004
    assert log.latency_ms == 321


def test_llm_call_log_records_v05c_task_observability_fields():
    log = LLMCallLog(
        student_id="student-1",
        task_type=TaskType.sentence,
        task_name="sentence_challenge_generation",
        prompt_key="sentence_challenge_generation",
        provider="openai",
        model="strong-model",
        resolved_provider="openai",
        resolved_model="strong-model",
        primary_provider="openrouter",
        primary_model="cheap-model",
        fallback_provider="openai",
        fallback_model="strong-model",
        fallback_reason="schema_validation_failed",
        attempt_count=2,
        final_status="fallback_success",
        pricing_status="configured",
        attempt_summaries=[
            {
                "attempt_index": 1,
                "role": "primary",
                "provider": "openrouter",
                "model": "cheap-model",
                "status": "schema_validation_failed",
                "error_class": "schema_validation_failed",
                "latency_ms": 8200,
                "prompt_tokens": 300,
                "completion_tokens": 120,
                "estimated_cost": 0.00012,
                "pricing_status": "configured",
            },
            {
                "attempt_index": 2,
                "role": "fallback",
                "provider": "openai",
                "model": "strong-model",
                "status": "success",
                "error_class": "",
                "latency_ms": 5300,
                "prompt_tokens": 300,
                "completion_tokens": 110,
                "estimated_cost": 0.0012,
                "pricing_status": "configured",
            },
        ],
        prompt_version="v0.5c-test",
        input_summary="句子挑战生成；年级：四年级；目标：action_expression",
        raw_response="{}",
        output_json={},
        validation_ok=True,
        prompt_tokens=600,
        completion_tokens=230,
        total_tokens=830,
        estimated_cost=0.00132,
        latency_ms=13500,
    )

    assert log.resolved_provider == "openai"
    assert log.resolved_model == "strong-model"
    assert log.primary_provider == "openrouter"
    assert log.primary_model == "cheap-model"
    assert log.fallback_provider == "openai"
    assert log.fallback_model == "strong-model"
    assert log.fallback_reason == "schema_validation_failed"
    assert log.attempt_count == 2
    assert log.final_status == "fallback_success"
    assert log.pricing_status == "configured"
    assert log.attempt_summaries[0]["role"] == "primary"
    assert log.attempt_summaries[1]["status"] == "success"


def test_essay_version_tracks_revision_task_metadata_and_llm_log_link():
    version = EssayVersion(
        essay_id="essay-1",
        version_label="revision",
        content="我学会了骑车。二稿加入了手心出汗的细节。",
        duration_seconds=420,
        completed_tasks=["给第二段加一个动作描写"],
        skipped_tasks=["补一个结尾感受"],
        llm_call_log_id="log-1",
    )

    assert version.essay_id == "essay-1"
    assert version.version_label == "revision"
    assert version.content == "我学会了骑车。二稿加入了手心出汗的细节。"
    assert version.duration_seconds == 420
    assert version.completed_tasks == ["给第二段加一个动作描写"]
    assert version.skipped_tasks == ["补一个结尾感受"]
    assert version.llm_call_log_id == "log-1"


def test_assessment_artifact_references_are_nullable_and_indexed():
    sentence_column = Assessment.__table__.c["sentence_training_id"]
    essay_column = Assessment.__table__.c["essay_id"]
    index_columns = {
        column.name
        for index in Assessment.__table__.indexes
        for column in index.columns
    }

    assert sentence_column.nullable is True
    assert essay_column.nullable is True
    assert sentence_column.foreign_keys
    assert essay_column.foreign_keys
    assert "sentence_training_id" in index_columns
    assert "essay_id" in index_columns


def test_v05a_parent_user_account_link_is_nullable_indexed_and_foreign_keyed():
    account_column = ParentUser.__table__.c["account_id"]
    linked_column = ParentUser.__table__.c["account_linked_at"]
    index_columns = {
        column.name
        for index in ParentUser.__table__.indexes
        for column in index.columns
    }

    assert account_column.nullable is True
    assert linked_column.nullable is True
    assert account_column.foreign_keys
    assert "account_id" in index_columns


def test_v05a_auth_tables_have_expected_indexes_and_uniques():
    parent_account_indexes = {
        column.name
        for index in ParentAccount.__table__.indexes
        for column in index.columns
    }
    magic_code_indexes = {
        column.name
        for index in AuthMagicCode.__table__.indexes
        for column in index.columns
    }
    session_indexes = {
        column.name
        for index in ParentSession.__table__.indexes
        for column in index.columns
    }

    assert ParentAccount.__table__.c["email_normalized"].unique is True
    assert ParentSession.__table__.c["token_hash"].unique is True
    assert "email_normalized" in parent_account_indexes
    assert "phone_e164" in parent_account_indexes
    assert "status" in parent_account_indexes
    assert "email_normalized" in magic_code_indexes
    assert "code_hash" in magic_code_indexes
    assert "purpose" in magic_code_indexes
    assert "alpha_session_id" in magic_code_indexes
    assert "request_ip_hash" in magic_code_indexes
    assert "expires_at" in magic_code_indexes
    assert "consumed_at" in magic_code_indexes
    assert "account_id" in session_indexes
    assert "token_hash" in session_indexes
    assert "expires_at" in session_indexes
    assert "revoked_at" in session_indexes
