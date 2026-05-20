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
    created_at: datetime = timestamp_field()


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
    ability_name: str
    old_value: int
    new_value: int
    delta: int
    source_type: TaskType
    source_id: str
    created_at: datetime = timestamp_field()


class Assessment(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    sentence_before: str
    sentence_after: str
    short_writing: str
    summary: str
    created_at: datetime = timestamp_field()


class SentenceTraining(SQLModel, table=True):
    id: str = Field(default_factory=new_uuid, primary_key=True)
    student_id: str = Field(foreign_key="studentprofile.id", index=True)
    source_sentence: str
    upgraded_sentence: str
    focus: str
    ai_feedback: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
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
    provider: str = "mock"
    model: str = "mock"
    prompt_version: str = "v0.2-quality-spine-2026-05-14"
    input_summary: str
    raw_response: str = ""
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    validation_ok: bool = False
    error_message: str = ""
    retry_count: int = 0
    created_at: datetime = timestamp_field()
