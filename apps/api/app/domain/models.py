from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, JSON, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.domain.enums import BadgeCode, ReportType, StudentPersona, TaskType


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid4())


def timestamp_field():
    return Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ParentUser(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    email: str = Field(index=True, unique=True)
    display_name: str
    account_id: str | None = Field(default=None, foreign_key="parentaccount.id", index=True)
    account_linked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = timestamp_field()


class ParentAccount(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    email_normalized: str = Field(index=True, unique=True)
    email_verified_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    phone_e164: str | None = Field(default=None, index=True)
    phone_bound_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    phone_verified_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    status: str = Field(default="active", index=True)
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field()
    last_login_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class AuthMagicCode(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    email_normalized: str = Field(index=True)
    code_hash: str = Field(index=True)
    purpose: str = Field(default="parent_login", index=True)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    consumed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    attempt_count: int = 0
    created_at: datetime = timestamp_field()
    last_attempt_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    alpha_session_id: str = Field(default="", index=True)
    request_ip_hash: str = Field(default="", index=True)


class ParentSession(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    account_id: str = Field(foreign_key="parentaccount.id", index=True)
    token_hash: str = Field(index=True, unique=True)
    created_at: datetime = timestamp_field()
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    last_seen_at: datetime = timestamp_field()
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )


class AlphaInviteCode(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    code_hash: str = Field(index=True, unique=True)
    label: str
    status: str = Field(default="issued", index=True)
    issued_to_note: str = ""
    consumed_by_parent_id: str | None = Field(
        default=None,
        foreign_key="parentuser.id",
        index=True,
    )
    consumed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = timestamp_field()


class ProductEvent(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    event_type: str = Field(index=True)
    parent_id: str | None = Field(default=None, foreign_key="parentuser.id", index=True)
    student_id: str | None = Field(default=None, foreign_key="studentprofile.id", index=True)
    invite_code_id: str | None = Field(default=None, foreign_key="alphainvitecode.id", index=True)
    alpha_session_id: str = Field(default="", index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = timestamp_field()


class FeedbackReaction(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "target_type",
            "target_id",
            name="uq_feedbackreaction_student_target",
        ),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    parent_id: str | None = Field(default=None, foreign_key="parentuser.id", index=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    target_type: str = Field(index=True)
    target_id: str = Field(index=True)
    reaction: str
    alpha_session_id: str = Field(default="", index=True)
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field()


class ParentFeedback(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "parent_id",
            "student_id",
            "target_type",
            name="uq_parentfeedback_parent_student_target",
        ),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    parent_id: str = Field(foreign_key="parentuser.id", index=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    target_type: str = Field(default="alpha_summary", index=True)
    target_id: str
    usefulness: str
    alpha_session_id: str = Field(default="", index=True)
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field()


class StudentProfile(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    parent_id: str = Field(foreign_key="parentuser.id", index=True)
    name: str
    grade_label: str = "四年级"
    persona: StudentPersona
    is_real_child: bool = False
    level: int = 1
    xp: int = 0
    created_at: datetime = timestamp_field()


class AbilityProfile(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True, unique=True)
    expression: int = 40
    observation: int = 40
    structure: int = 40
    revision: int = 40
    comprehension: int = 40
    summarization: int = 40
    evidence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    updated_at: datetime = timestamp_field()


class AbilityHistory(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    ability_name: str = Field(index=True)
    old_value: int
    new_value: int
    delta: int
    source_type: TaskType
    source_id: str = Field(index=True)
    created_at: datetime = timestamp_field()


class Assessment(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    sentence_before: str
    sentence_after: str
    short_writing: str
    summary: str
    sentence_training_id: str | None = Field(
        default=None,
        foreign_key="sentencetraining.id",
        index=True,
    )
    essay_id: str | None = Field(default=None, foreign_key="essay.id", index=True)
    created_at: datetime = timestamp_field()


class SentenceTraining(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    source_sentence: str
    upgraded_sentence: str = ""
    focus: str
    ai_feedback: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="completed", index=True)
    challenge_prompt: str = ""
    hint: str = ""
    target_skill: str = Field(default="", index=True)
    completed_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = timestamp_field()


class Essay(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    title: str
    status: str = "draft_feedback"
    material_card: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    outline: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field()
    last_version_submitted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    visibility_changed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    hidden_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    hidden_by: str = Field(default="", index=True)


class WritingTopicIdeaBatch(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    grade_label: str = Field(index=True)
    interest_input_present: bool = False
    ideas: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    consumed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    selected_idea_id: str = Field(default="", index=True)
    created_essay_id: str | None = Field(default=None, foreign_key="essay.id", index=True)
    created_at: datetime = timestamp_field()


class EssayVersion(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("essay_id", "version_label", name="uq_essay_version_label_per_essay"),
        UniqueConstraint("essay_id", "round_index", name="uq_essay_version_round_per_essay"),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    essay_id: str = Field(foreign_key="essay.id", index=True)
    version_label: str
    round_index: int | None = Field(default=None, index=True)
    content: str
    ai_feedback: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    duration_seconds: int | None = None
    completed_tasks: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    skipped_tasks: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    llm_call_log_id: str | None = Field(default=None, foreign_key="llmcalllog.id", index=True)
    created_at: datetime = timestamp_field()


class EssayRevisionAttempt(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "essay_id",
            "base_version_id",
            "idempotency_key",
            name="uq_essay_revision_attempt_idempotency",
        ),
        Index(
            "uq_essay_revision_attempt_target_round_active",
            "essay_id",
            "base_version_id",
            "target_round_index",
            unique=True,
            sqlite_where=text("status IN ('pending_comparison', 'completed')"),
            postgresql_where=text("status IN ('pending_comparison', 'completed')"),
        ),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    essay_id: str = Field(foreign_key="essay.id", index=True)
    base_version_id: str = Field(foreign_key="essayversion.id", index=True)
    target_round_index: int = Field(index=True)
    submitted_content: str | None = None
    submitted_content_hash: str = Field(default="", index=True)
    idempotency_key: str = Field(index=True)
    status: str = Field(default="pending_comparison", index=True)
    new_version_id: str | None = Field(default=None, foreign_key="essayversion.id", index=True)
    error_code: str | None = Field(default=None, index=True)
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field()


class ReadingSession(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    article_title: str
    answers: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    ai_feedback: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    transfer_tip: str
    created_at: datetime = timestamp_field()


class GameEvent(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    task_type: TaskType
    xp_delta: int
    level_after: int
    badge_code: BadgeCode | None = None
    problem_monsters: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    evidence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = timestamp_field()


class Report(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    report_type: ReportType
    content: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = timestamp_field()


class LLMCallLog(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str | None = Field(default=None, foreign_key="studentprofile.id", index=True)
    task_type: TaskType
    task_name: str = Field(default="unknown", index=True)
    prompt_key: str = Field(default="unknown", index=True)
    provider: str = "mock"
    model: str = "mock"
    resolved_provider: str = Field(default="", index=True)
    resolved_model: str = Field(default="", index=True)
    primary_provider: str = Field(default="", index=True)
    primary_model: str = ""
    fallback_provider: str = Field(default="", index=True)
    fallback_model: str = ""
    fallback_reason: str = Field(default="", index=True)
    attempt_count: int = 0
    final_status: str = Field(default="", index=True)
    pricing_status: str = Field(default="", index=True)
    attempt_summaries: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    prompt_version: str = ""
    input_summary: str
    raw_response: str = ""
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    validation_ok: bool = False
    error_message: str = ""
    retry_count: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None
    latency_ms: int = 0
    topic_type: str = Field(default="", index=True)
    topic_variant: str = Field(default="", index=True)
    scaffold_template_version: str = Field(default="", index=True)
    source_policy_summary: str = ""
    duration_ms: int = 0
    request_started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    response_received_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    streaming_enabled: bool = Field(default=False, index=True)
    stream_protocol: str = Field(default="none", index=True)
    stream_started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    first_provider_delta_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    first_visible_content_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_content_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    usage_received_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    client_disconnected_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    provider_stream_completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    usage_available: bool = Field(default=False, index=True)
    usage_source: str = Field(default="unavailable", index=True)
    usage_is_estimated: bool = Field(default=False, index=True)
    usage_details_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    stream_final_status: str = Field(default="not_streaming", index=True)
    cost_source: str = Field(default="unavailable", index=True)
    cost_error_code: str = Field(default="", index=True)
    pricing_snapshot_id: str | None = Field(default=None, index=True)
    pricing_snapshot_version: str = Field(default="")
    provider_reported_cost_usd: float | None = None
    cost_calculation_version: str = Field(default="v0.6e.1")
    provider_request_id: str | None = Field(default=None, index=True)
    provider_generation_id: str | None = Field(default=None, index=True)
    created_at: datetime = timestamp_field()


class DailyTaskLimitCounter(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "task_name",
            "product_day",
            name="uq_daily_task_limit_counter_key",
        ),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    task_name: str = Field(index=True)
    product_day: str = Field(index=True)
    limit_value: int
    reserved_count: int = 0
    consumed_count: int = 0
    failed_count: int = 0
    released_count: int = 0
    active_reservations: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    reservation_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    updated_at: datetime = timestamp_field()


class PrewritingAIJob(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "essay_id",
            "task_name",
            "idempotency_key",
            name="uq_prewriting_ai_job_idempotency",
        ),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    essay_id: str = Field(foreign_key="essay.id", index=True)
    task_name: str = Field(index=True)
    idempotency_key: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    stage: str = Field(default="queued", index=True)
    attempt_count: int = 0
    locked_by: str | None = Field(default=None, index=True)
    lease_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True, index=True)
    )
    last_heartbeat_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    progress_event_seq: int = 0
    schema_version: str = Field(default="v0.6e.1")
    result_ref_type: str = Field(default="")
    result_ref_id: str | None = Field(default=None, index=True)
    result_payload_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    error_code: str = Field(default="", index=True)
    error_message: str = ""
    llm_call_log_id: str | None = Field(default=None, foreign_key="llmcalllog.id", index=True)
    started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field()


class EssayFeedbackSubmission(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope",
            "task_name",
            "client_submission_id",
            name="uq_essay_feedback_submission_idempotency",
        ),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    essay_id: str | None = Field(default=None, foreign_key="essay.id", index=True)
    idempotency_scope: str = Field(index=True)
    route_scope: str = Field(index=True)
    payload_schema_version: str = Field(default="v0.6e.1", index=True)
    task_name: str = Field(index=True)
    client_submission_id: str = Field(index=True)
    payload_hash: str = Field(index=True)
    status: str = Field(default="created", index=True)
    llm_call_log_id: str | None = Field(default=None, foreign_key="llmcalllog.id", index=True)
    essay_version_id: str | None = Field(default=None, foreign_key="essayversion.id", index=True)
    daily_limit_counter_id: str | None = Field(default=None, index=True)
    daily_limit_reservation_token: str | None = Field(default=None, index=True)
    result_fetch_url: str = ""
    error_code: str = Field(default="", index=True)
    error_message: str = ""
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field()
    completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
