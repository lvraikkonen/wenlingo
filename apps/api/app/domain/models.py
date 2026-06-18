from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, JSON, UniqueConstraint
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


class EssayVersion(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("essay_id", "version_label", name="uq_essay_version_label_per_essay"),
    )

    id: str = Field(default_factory=new_uuid, primary_key=True)
    essay_id: str = Field(foreign_key="essay.id", index=True)
    version_label: str
    content: str
    ai_feedback: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    duration_seconds: int | None = None
    completed_tasks: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    skipped_tasks: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    llm_call_log_id: str | None = Field(default=None, foreign_key="llmcalllog.id", index=True)
    created_at: datetime = timestamp_field()


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
    prompt_version: str = "v0.2-quality-spine-2026-05-14"
    input_summary: str
    raw_response: str = ""
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    validation_ok: bool = False
    error_message: str = ""
    retry_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: int = 0
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
    reservation_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    updated_at: datetime = timestamp_field()
