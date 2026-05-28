from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.enums import StudentPersona
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    AlphaInviteCode,
    Assessment,
    Essay,
    ParentFeedback,
    ParentUser,
    ProductEvent,
    SentenceTraining,
    StudentProfile,
)

router = APIRouter(prefix="/api/alpha", tags=["alpha"])

GRADE_LABELS = {
    3: "三年级",
    4: "四年级",
    5: "五年级",
    6: "六年级",
}

ABILITY_LABELS = {
    "expression": "表达力",
    "observation": "观察力",
    "structure": "结构力",
    "revision": "修改力",
    "comprehension": "阅读理解力",
    "summarization": "概括力",
}
ABILITY_ORDER = tuple(ABILITY_LABELS)

EMPTY_SUMMARY = "还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。"
EMPTY_NEXT_SUGGESTION = "先完成入门小试炼，生成第一张能力草图。"
POPULATED_NEXT_SUGGESTION = "继续练习把句子写具体。"

P0_EVENT_TYPES = {
    "alpha_start_viewed",
    "invite_code_validated",
    "invite_code_rejected",
    "alpha_parent_created",
    "alpha_child_created",
    "parent_children_viewed",
    "child_handoff_clicked",
    "child_dashboard_viewed",
    "assessment_completed",
    "sentence_training_completed",
    "essay_draft_feedback_completed",
    "essay_revision_feedback_completed",
    "summary_viewed",
    "child_feedback_reaction_submitted",
    "parent_summary_feedback_submitted",
    "ai_feedback_failed",
}

P1_EVENT_TYPES = {
    "invite_code_submitted",
    "assessment_submitted",
    "sentence_training_submitted",
    "essay_draft_submitted",
    "essay_revision_submitted",
    "legacy_parent_invite_bound",
}

ALLOWED_EVENT_TYPES = P0_EVENT_TYPES | P1_EVENT_TYPES

SAFE_PAYLOAD_KEYS = {
    "path",
    "status",
    "target_type",
    "target_id",
    "task_type",
    "error_category",
    "summary_viewed",
    "reaction",
    "usefulness",
    "child_count",
}
JSON_SAFE_SCALARS = (str, int, float, bool, type(None))
INVITE_CODE_VALUE_PATTERN = re.compile(
    r"(?i)(?:^|[^a-z0-9])alpha-[a-z0-9]+(?:-[a-z0-9]+)*"
)


class AlphaParentCreate(BaseModel):
    display_name: str = Field(default="Alpha 家长", max_length=40)
    invite_code: str = Field(min_length=1, max_length=80)
    alpha_session_id: str = Field(default="", max_length=120)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str:
        if value is None:
            return "Alpha 家长"
        normalized = str(value).strip()
        return normalized or "Alpha 家长"

    @field_validator("invite_code")
    @classmethod
    def normalize_invite_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("invite_code is required")
        return normalized


class AlphaInviteValidate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    alpha_session_id: str = Field(default="", max_length=120)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("code is required")
        return normalized


class ProductEventCreate(BaseModel):
    event_type: str
    parent_id: str | None = None
    student_id: str | None = None
    invite_code_id: str | None = None
    alpha_session_id: str = ""
    payload: dict[str, object] = Field(default_factory=dict)


class AlphaChildCreate(BaseModel):
    nickname: str
    grade: int = Field(ge=3, le=6)

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("nickname is required")
        if len(normalized) > 24:
            raise ValueError("nickname must be 24 characters or fewer")
        return normalized


class ParentSummaryFeedbackCreate(BaseModel):
    usefulness: Literal["helpful", "not_helpful"]
    alpha_session_id: str = Field(default="", max_length=120)


def hash_invite_code(code: str) -> str:
    return sha256(code.strip().upper().encode("utf-8")).hexdigest()


def sanitize_event_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    sanitized = {}
    for key, value in payload.items():
        if key not in SAFE_PAYLOAD_KEYS:
            continue
        sanitized_value = _sanitize_payload_value(value)
        if sanitized_value is not _DROP_PAYLOAD_VALUE:
            sanitized[key] = sanitized_value
    return sanitized


_DROP_PAYLOAD_VALUE = object()


def _sanitize_payload_value(value: Any) -> Any:
    if isinstance(value, str):
        if "code=" in value.lower() or INVITE_CODE_VALUE_PATTERN.search(value):
            return _DROP_PAYLOAD_VALUE
        return value
    if isinstance(value, JSON_SAFE_SCALARS):
        return value
    return _DROP_PAYLOAD_VALUE


def record_product_event(
    session: Session,
    event_type: str,
    parent_id: str | None = None,
    student_id: str | None = None,
    invite_code_id: str | None = None,
    alpha_session_id: str = "",
    payload: dict[str, Any] | None = None,
) -> ProductEvent:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError("unsupported product event type")
    event = ProductEvent(
        event_type=event_type,
        parent_id=parent_id,
        student_id=student_id,
        invite_code_id=invite_code_id,
        alpha_session_id=alpha_session_id,
        payload=sanitize_event_payload(payload),
    )
    session.add(event)
    return event


def _parent_payload(parent: ParentUser) -> dict[str, str]:
    return {
        "id": parent.id,
        "email": parent.email,
        "display_name": parent.display_name,
    }


def _dashboard_url(student_id: str) -> str:
    return f"/children/{student_id}"


def _summary_url(student_id: str) -> str:
    return f"/parent/children/{student_id}/summary"


def _assessment_completed(session: Session, student_id: str) -> bool:
    return (
        session.exec(select(Assessment).where(Assessment.student_id == student_id)).first()
        is not None
    )


def _student_payload(
    student: StudentProfile,
    session: Session | None = None,
) -> dict[str, str | bool]:
    payload = {
        "id": student.id,
        "nickname": student.name,
        "name": student.name,
        "grade_label": student.grade_label,
        "persona": student.persona.value,
        "is_real_child": student.is_real_child,
        "dashboard_url": _dashboard_url(student.id),
        "summary_url": _summary_url(student.id),
    }
    if session is not None:
        payload["assessment_completed"] = _assessment_completed(session, student.id)
    return payload


def _get_alpha_parent(session: Session, parent_id: str) -> ParentUser:
    parent = session.get(ParentUser, parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="alpha parent not found")
    return parent


def _get_parent_child(session: Session, parent_id: str, student_id: str) -> StudentProfile:
    _get_alpha_parent(session, parent_id)
    student = session.get(StudentProfile, student_id)
    if not student or student.parent_id != parent_id:
        raise HTTPException(status_code=404, detail="student not found")
    return student


def _count_rows(session: Session, model, student_id: str) -> int:
    return len(session.exec(select(model).where(model.student_id == student_id)).all())


def _get_invite_by_code(session: Session, code: str) -> AlphaInviteCode | None:
    return session.exec(
        select(AlphaInviteCode).where(AlphaInviteCode.code_hash == hash_invite_code(code))
    ).first()


def _get_available_invite(session: Session, code: str) -> AlphaInviteCode | None:
    invite = _get_invite_by_code(session, code)
    if not invite or invite.status != "issued":
        return None
    return invite


@router.post("/invites/validate")
def validate_alpha_invite(
    request: AlphaInviteValidate,
    session: Session = Depends(get_db_session),
):
    invite = _get_available_invite(session, request.code)
    if not invite:
        existing_invite = _get_invite_by_code(session, request.code)
        record_product_event(
            session,
            "invite_code_rejected",
            invite_code_id=existing_invite.id if existing_invite else None,
            alpha_session_id=request.alpha_session_id,
        )
        session.commit()
        raise HTTPException(status_code=400, detail="invite code is not available")
    record_product_event(
        session,
        "invite_code_validated",
        invite_code_id=invite.id,
        alpha_session_id=request.alpha_session_id,
    )
    session.commit()
    return {"valid": True, "invite_id": invite.id, "label": invite.label}


@router.post("/events", status_code=201)
def create_product_event(
    request: ProductEventCreate,
    session: Session = Depends(get_db_session),
):
    try:
        record_product_event(
            session,
            request.event_type,
            parent_id=request.parent_id,
            student_id=request.student_id,
            invite_code_id=request.invite_code_id,
            alpha_session_id=request.alpha_session_id,
            payload=request.payload,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/parents", status_code=201)
def create_alpha_parent(
    request: AlphaParentCreate,
    session: Session = Depends(get_db_session),
):
    invite = _get_available_invite(session, request.invite_code)
    if not invite:
        raise HTTPException(status_code=400, detail="invite code is not available")
    parent = ParentUser(
        email=f"alpha-{uuid4()}@wenlingo.local",
        display_name=request.display_name,
    )
    session.add(parent)
    session.flush()
    consumed_at = datetime.now(timezone.utc)
    consume_result = session.execute(
        update(AlphaInviteCode)
        .where(AlphaInviteCode.id == invite.id, AlphaInviteCode.status == "issued")
        .values(
            status="consumed",
            consumed_by_parent_id=parent.id,
            consumed_at=consumed_at,
        )
        .execution_options(synchronize_session=False)
    )
    if consume_result.rowcount != 1:
        session.rollback()
        raise HTTPException(status_code=400, detail="invite code is not available")
    record_product_event(
        session,
        "alpha_parent_created",
        parent_id=parent.id,
        invite_code_id=invite.id,
        alpha_session_id=request.alpha_session_id,
    )
    session.commit()
    session.refresh(parent)
    return {
        "parent": _parent_payload(parent),
        "children_url": "/parent/children",
    }


@router.get("/parents/{parent_id}/children")
def list_alpha_children(
    parent_id: str,
    session: Session = Depends(get_db_session),
):
    parent = _get_alpha_parent(session, parent_id)
    children = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent.id)
    ).all()
    children = sorted(children, key=lambda child: (child.created_at, child.id))
    return {
        "parent": _parent_payload(parent),
        "children": [_student_payload(child, session=session) for child in children],
    }


@router.post("/parents/{parent_id}/children", status_code=201)
def create_alpha_child(
    parent_id: str,
    request: AlphaChildCreate,
    session: Session = Depends(get_db_session),
):
    parent = _get_alpha_parent(session, parent_id)
    student = StudentProfile(
        parent_id=parent.id,
        name=request.nickname,
        grade_label=GRADE_LABELS[request.grade],
        persona=StudentPersona.real_child,
        is_real_child=True,
    )
    session.add(student)
    session.flush()
    session.add(AbilityProfile(student_id=student.id))
    try:
        record_product_event(
            session,
            "alpha_child_created",
            parent_id=parent.id,
            student_id=student.id,
            payload={"child_count": 1},
        )
    except Exception:
        pass
    session.commit()
    session.refresh(student)
    return {
        "child": _student_payload(student),
        "dashboard_url": _dashboard_url(student.id),
        "summary_url": _summary_url(student.id),
    }


@router.get("/parents/{parent_id}/children/{student_id}/summary")
def alpha_child_summary(
    parent_id: str,
    student_id: str,
    session: Session = Depends(get_db_session),
):
    student = _get_parent_child(session, parent_id, student_id)
    assessment_count = _count_rows(session, Assessment, student.id)
    sentence_count = _count_rows(session, SentenceTraining, student.id)
    essay_count = _count_rows(session, Essay, student.id)
    history_rows = session.exec(
        select(AbilityHistory).where(AbilityHistory.student_id == student.id)
    ).all()

    deltas = {ability: 0 for ability in ABILITY_ORDER}
    for row in history_rows:
        if row.ability_name in deltas:
            deltas[row.ability_name] += row.delta

    ability_changes = [
        {
            "ability": ability,
            "label": ABILITY_LABELS[ability],
            "delta": deltas[ability],
        }
        for ability in ABILITY_ORDER
        if deltas[ability] != 0
    ]
    assessment_completed = assessment_count > 0
    has_progress = assessment_count + sentence_count + essay_count > 0 or bool(history_rows)

    return {
        "parent_id": parent_id,
        "child": _student_payload(student),
        "assessment_completed": assessment_completed,
        "practice_counts": {
            "assessments": assessment_count,
            "sentence_trainings": sentence_count,
            "essays": essay_count,
        },
        "ability_changes": ability_changes,
        "recent_highlight": "孩子完成了第一次能力草图。"
        if assessment_completed
        else None,
        "empty_state": None if has_progress else EMPTY_SUMMARY,
        "next_suggestion": POPULATED_NEXT_SUGGESTION
        if has_progress
        else EMPTY_NEXT_SUGGESTION,
    }


@router.post(
    "/parents/{parent_id}/children/{student_id}/summary-feedback",
    status_code=201,
)
def create_parent_summary_feedback(
    parent_id: str,
    student_id: str,
    request: ParentSummaryFeedbackCreate,
    session: Session = Depends(get_db_session),
):
    student = _get_parent_child(session, parent_id, student_id)
    feedback = session.exec(
        select(ParentFeedback).where(
            ParentFeedback.parent_id == parent_id,
            ParentFeedback.student_id == student.id,
            ParentFeedback.target_type == "alpha_summary",
        )
    ).first()
    if feedback:
        feedback.usefulness = request.usefulness
        feedback.target_id = student.id
        feedback.alpha_session_id = request.alpha_session_id
        feedback.updated_at = datetime.now(timezone.utc)
    else:
        feedback = ParentFeedback(
            parent_id=parent_id,
            student_id=student.id,
            target_type="alpha_summary",
            target_id=student.id,
            usefulness=request.usefulness,
            alpha_session_id=request.alpha_session_id,
        )
    session.add(feedback)
    try:
        record_product_event(
            session,
            "parent_summary_feedback_submitted",
            parent_id=parent_id,
            student_id=student.id,
            alpha_session_id=request.alpha_session_id,
            payload={"usefulness": request.usefulness, "target_type": "alpha_summary"},
        )
    except Exception:
        pass
    session.commit()
    session.refresh(feedback)
    return {
        "feedback": {
            "id": feedback.id,
            "parent_id": feedback.parent_id,
            "student_id": feedback.student_id,
            "target_type": feedback.target_type,
            "target_id": feedback.target_id,
            "usefulness": feedback.usefulness,
        }
    }
