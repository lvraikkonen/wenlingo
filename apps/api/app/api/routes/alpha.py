from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import logging
import re
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    optional_parent_context,
    require_allowed_origin,
    require_json_state_change,
    require_linked_parent,
    require_student_for_parent,
)
from app.api.deps import get_db_session
from app.api.feedback_state import parent_summary_usefulness
from app.core.config import Settings, get_settings
from app.domain.enums import StudentPersona
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    AlphaInviteCode,
    Assessment,
    Essay,
    EssayVersion,
    ParentAccount,
    ParentFeedback,
    ParentUser,
    ProductEvent,
    SentenceTraining,
    StudentProfile,
)
from app.services.auth_security import mask_email, mask_phone
from app.services.writing_castle_state import (
    LEGACY_SCHEMA_VERSION,
    SCHEMA_VERSION,
    resolve_essay_scaffold,
)

router = APIRouter(prefix="/api/alpha", tags=["alpha"])
LOGGER = logging.getLogger(__name__)

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
    "sentence_challenge_generated",
    "sentence_challenge_completed",
    "sentence_challenge_feedback_failed",
    "ai_daily_limit_reached",
    "writing_castle_started",
    "ai_topic_ideas_requested",
    "ai_topic_ideas_generated",
    "ai_topic_idea_selected",
    "scaffold_selected",
    "topic_analysis_completed",
    "topic_focus_confirmed",
    "topic_focus_skipped",
    "material_question_answered",
    "material_questions_completed",
    "material_questions_skipped",
    "material_cards_generated",
    "material_cards_edited",
    "material_cards_confirmed",
    "outline_generated",
    "outline_edited",
    "outline_confirmed",
    "outline_skipped",
    "prewriting_first_draft_submitted",
}

P1_EVENT_TYPES = {
    "invite_code_submitted",
    "assessment_submitted",
    "sentence_training_submitted",
    "essay_draft_submitted",
    "essay_revision_submitted",
    "legacy_parent_account_bound",
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
    "target_skill",
    "limit_type",
    "essay_id",
    "step",
    "interest_input_present",
    "grade_label",
    "idea_batch_id",
    "idea_count",
    "selected_idea_id",
    "answered_count",
    "card_count",
    "outline_section_count",
    "skipped",
    "topic_type",
    "topic_variant",
    "topic_origin",
    "scaffold_template_version",
    "selection_source",
    "override_reason",
    "accepted_suggestion_id",
    "unsupported_future_type",
    "unsupported_override",
    "scaffold_schema",
    "frontend_clicked_at",
    "request_started_at",
    "server_completed_at",
    "response_received_at",
    "duration_ms",
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


class LegacyParentBindRequest(BaseModel):
    legacy_parent_id: str = Field(min_length=1)


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


def _has_consumed_alpha_invite(session: Session, parent_id: str) -> bool:
    invite = session.exec(
        select(AlphaInviteCode).where(
            AlphaInviteCode.consumed_by_parent_id == parent_id,
            AlphaInviteCode.status == "consumed",
        )
    ).first()
    return invite is not None


def _resolve_parent_for_path(
    *,
    parent_id: str,
    session: Session,
    settings: Settings,
    context: ParentContext | None,
) -> ParentUser:
    if not settings.auth_required_for_alpha:
        return _get_alpha_parent(session, parent_id)
    if context is None:
        raise HTTPException(status_code=401, detail="parent session required")
    if context.parent is None or context.parent.id != parent_id:
        raise HTTPException(status_code=404, detail="alpha parent not found")
    return context.parent


def _optional_parent_context_when_alpha_auth_required(
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ParentContext | None:
    if not settings.auth_required_for_alpha:
        return None
    return optional_parent_context(request=request, db=session, settings=settings)


def _require_legacy_parent_bind_context(
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ParentContext:
    if not settings.auth_required_for_alpha:
        raise HTTPException(status_code=404, detail="alpha parent not found")
    context = optional_parent_context(request=request, db=session, settings=settings)
    if context is None:
        raise HTTPException(status_code=401, detail="parent session required")
    require_allowed_origin(request, settings)
    require_json_state_change(request)
    if context.account.email_verified_at is None:
        raise HTTPException(status_code=401, detail="verified parent session required")
    return context


def _children_payload(parent: ParentUser, session: Session):
    children = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent.id)
    ).all()
    children = sorted(children, key=lambda child: (child.created_at, child.id))
    payload = {
        "parent": _parent_payload(parent),
        "children": [_student_payload(child, session=session) for child in children],
    }
    if parent.account_id:
        account = session.get(ParentAccount, parent.account_id)
        if account:
            account_payload = {
                "email_masked": mask_email(account.email_normalized),
                "phone_bound": bool(account.phone_bound_at),
            }
            if account.phone_e164:
                account_payload["phone_masked"] = mask_phone(account.phone_e164)
            payload["account"] = account_payload
    return payload


def _create_child_payload(parent: ParentUser, request: AlphaChildCreate, session: Session):
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


def _summary_payload(parent: ParentUser, student: StudentProfile, session: Session):
    assessment_count = _count_rows(session, Assessment, student.id)
    sentence_count, sentence_summary = _sentence_training_summary(session, student.id)
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
    has_progress = assessment_count + sentence_count + essay_count > 0 or bool(
        history_rows
    )
    usefulness = parent_summary_usefulness(session, parent.id, student.id)

    return {
        "parent_id": parent.id,
        "child": _student_payload(student),
        "usefulness": usefulness,
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
        "sentence_training_summary": sentence_summary,
        "writing_castle_summary": _writing_castle_summary(session, student.id),
        "empty_state": None if has_progress else EMPTY_SUMMARY,
        "next_suggestion": POPULATED_NEXT_SUGGESTION
        if has_progress
        else EMPTY_NEXT_SUGGESTION,
    }


def _writing_castle_summary(session: Session, student_id: str) -> dict[str, Any] | None:
    supported_schema_versions = {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}
    essays = session.exec(
        select(Essay)
        .where(Essay.student_id == student_id)
        .order_by(Essay.created_at.desc())
    ).all()
    essay = next(
        (
            row
            for row in essays
            if _json_object(row.material_card).get("schema_version") in supported_schema_versions
            or _json_object(row.outline).get("schema_version") in supported_schema_versions
        ),
        None,
    )
    if essay is None:
        return None
    material = _json_object(essay.material_card)
    outline = _json_object(essay.outline)
    topic_analysis = _json_object(outline.get("topic_analysis"))
    focus = _json_object(outline.get("child_topic_focus"))
    material_answers = _json_object_list(material.get("answers"))
    material_cards = [
        card
        for card in _json_object_list(material.get("cards"))
        if not card.get("deleted") and not card.get("placeholder")
    ]
    scaffold = _summary_scaffold(essay, material, outline)
    source_categories = sorted(
        {
            ref.get("source_type")
            for card in material_cards
            for ref in _json_object_list(card.get("source_refs"))
            if ref.get("source_type")
        }
    )
    if not source_categories and material_answers:
        source_categories = ["real_experience"]
    outline_state = _json_object(outline.get("step_state"))
    outline_sections = _json_object_list(outline.get("sections"))
    first_draft = session.exec(
        select(EssayVersion).where(
            EssayVersion.essay_id == essay.id,
            EssayVersion.version_label == "first_draft",
        )
    ).first()
    revision = session.exec(
        select(EssayVersion).where(
            EssayVersion.essay_id == essay.id,
            EssayVersion.version_label == "revision",
        )
    ).first()
    return {
        "topic": essay.title,
        "selected_topic_type": scaffold.get("display_name_child", ""),
        "selected_topic_type_parent": scaffold.get("display_name_parent", ""),
        "selection_source": scaffold.get("selection_source", ""),
        "material_source_categories": source_categories,
        "unsupported_future_type_overridden": bool(scaffold.get("unsupported_future_type")),
        "copy_ready_ai_body_generated": False,
        "topic_analysis_used": topic_analysis.get("status") == "generated",
        "topic_focus_confirmed": bool(focus.get("text")) and not focus.get("skipped"),
        "topic_focus_edited": bool(focus.get("text"))
        and not focus.get("adopted_from_ai"),
        "material_questions_answered": len(
            [
                answer
                for answer in material_answers
                if _nonblank_json_text(answer.get("text"))
                and not answer.get("skipped")
            ]
        ),
        "material_cards_retained": len(material_cards),
        "outline_confirmed": outline_state.get("outline_status") == "confirmed",
        "outline_edited": any(
            section.get("child_edited") for section in outline_sections
        ),
        "first_draft_completed": first_draft is not None,
        "revision_completed": revision is not None,
        "settlement_completed": essay.status == "settled",
    }


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _summary_scaffold(
    essay: Essay,
    material: dict[str, Any],
    outline: dict[str, Any],
) -> dict[str, Any]:
    if (
        material.get("schema_version") == SCHEMA_VERSION
        and outline.get("schema_version") == SCHEMA_VERSION
    ):
        if material.get("scaffold_ref") is None and outline.get("scaffold") is None:
            return {}
        try:
            return resolve_essay_scaffold(essay) or {}
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _json_object(outline.get("scaffold"))


def _json_object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _nonblank_json_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sentence_training_summary(session: Session, student_id: str) -> tuple[int, str | None]:
    rows = session.exec(
        select(SentenceTraining).where(
            SentenceTraining.student_id == student_id,
            SentenceTraining.status == "completed",
        )
    ).all()
    if not rows:
        return 0, None
    focus_counts = Counter(row.focus for row in rows if row.focus)
    top_focuses = [focus for focus, _count in focus_counts.most_common(2)]
    if not top_focuses:
        return len(rows), f"本周完成 {len(rows)} 次句子挑战。"
    if len(top_focuses) == 1:
        focus_text = f"“{top_focuses[0]}”"
    else:
        focus_text = f"“{top_focuses[0]}”和“{top_focuses[1]}”"
    return len(rows), f"本周完成 {len(rows)} 次句子挑战，主要练习了{focus_text}。"


def _summary_feedback_payload(
    parent: ParentUser,
    student: StudentProfile,
    request: ParentSummaryFeedbackCreate,
    session: Session,
):
    feedback = session.exec(
        select(ParentFeedback).where(
            ParentFeedback.parent_id == parent.id,
            ParentFeedback.student_id == student.id,
            ParentFeedback.target_type == "alpha_summary",
        )
    ).first()
    is_create = feedback is None
    if feedback:
        feedback.usefulness = request.usefulness
        feedback.target_id = student.id
        feedback.alpha_session_id = request.alpha_session_id
        feedback.updated_at = datetime.now(timezone.utc)
    else:
        feedback = ParentFeedback(
            parent_id=parent.id,
            student_id=student.id,
            target_type="alpha_summary",
            target_id=student.id,
            usefulness=request.usefulness,
            alpha_session_id=request.alpha_session_id,
        )
    session.add(feedback)
    if is_create:
        try:
            record_product_event(
                session,
                "parent_summary_feedback_submitted",
                parent_id=parent.id,
                student_id=student.id,
                alpha_session_id=request.alpha_session_id,
                payload={
                    "usefulness": request.usefulness,
                    "target_type": "alpha_summary",
                },
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


def _lock_parent_account(session: Session, account_id: str) -> ParentAccount:
    account = session.exec(
        select(ParentAccount)
        .where(ParentAccount.id == account_id)
        .with_for_update()
    ).first()
    if account is None:
        raise HTTPException(status_code=401, detail="parent session required")
    return account


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
            payload={"status": "rejected", "error_category": "not_available"},
        )
        session.commit()
        raise HTTPException(status_code=400, detail="invite code is not available")
    record_product_event(
        session,
        "invite_code_validated",
        invite_code_id=invite.id,
        alpha_session_id=request.alpha_session_id,
        payload={"status": "validated"},
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
    http_request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    context: ParentContext | None = None
    if settings.auth_required_for_alpha:
        context = optional_parent_context(
            request=http_request,
            db=session,
            settings=settings,
        )
        if context is None:
            raise HTTPException(status_code=401, detail="parent session required")
        require_allowed_origin(http_request, settings)
        require_json_state_change(http_request)
        if context.account.email_verified_at is None:
            raise HTTPException(
                status_code=401, detail="verified parent session required"
            )
        _lock_parent_account(session, context.account.id)
        linked_parent = session.exec(
            select(ParentUser).where(ParentUser.account_id == context.account.id)
        ).first()
        if linked_parent is not None:
            raise HTTPException(status_code=409, detail="alpha parent already linked")

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
    if context is not None:
        existing_parent_for_account = aliased(ParentUser)
        linked_at = datetime.now(timezone.utc)
        link_result = session.execute(
            update(ParentUser)
            .where(
                ParentUser.id == parent.id,
                ParentUser.account_id.is_(None),
                ~select(existing_parent_for_account.id)
                .where(existing_parent_for_account.account_id == context.account.id)
                .exists(),
            )
            .values(account_id=context.account.id, account_linked_at=linked_at)
            .execution_options(synchronize_session=False)
        )
        if link_result.rowcount != 1:
            session.rollback()
            raise HTTPException(status_code=409, detail="alpha parent already linked")
    record_product_event(
        session,
        "alpha_parent_created",
        parent_id=parent.id,
        invite_code_id=invite.id,
        alpha_session_id=request.alpha_session_id,
        payload={"status": "created"},
    )
    session.commit()
    session.refresh(parent)
    return {
        "parent": _parent_payload(parent),
        "children_url": "/parent/children",
    }


@router.post("/legacy-parent-bind")
def bind_legacy_alpha_parent(
    request: LegacyParentBindRequest,
    context: ParentContext = Depends(_require_legacy_parent_bind_context),
    session: Session = Depends(get_db_session),
):
    parent = session.get(ParentUser, request.legacy_parent_id)
    if not parent or not _has_consumed_alpha_invite(session, parent.id):
        raise HTTPException(status_code=404, detail="alpha parent not found")

    _lock_parent_account(session, context.account.id)
    existing_parent_for_account = aliased(ParentUser)
    linked_at = datetime.now(timezone.utc)
    bind_result = session.execute(
        update(ParentUser)
        .where(
            ParentUser.id == parent.id,
            ParentUser.account_id.is_(None),
            ~select(existing_parent_for_account.id)
            .where(existing_parent_for_account.account_id == context.account.id)
            .exists(),
        )
        .values(account_id=context.account.id, account_linked_at=linked_at)
        .execution_options(synchronize_session=False)
    )
    if bind_result.rowcount != 1:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="这个家庭已经绑定过账号，请联系邀请人处理。",
        )

    record_product_event(
        session,
        "legacy_parent_account_bound",
        parent_id=parent.id,
    )
    LOGGER.info(
        "legacy_parent_account_bound",
        extra={"parent_id": parent.id, "account_id": context.account.id},
    )
    session.commit()
    session.refresh(parent)
    return {"parent": _parent_payload(parent)}


@router.get("/parents/me/children")
def list_session_parent_children(
    parent: ParentUser = Depends(require_linked_parent),
    session: Session = Depends(get_db_session),
):
    return _children_payload(parent, session)


@router.post("/parents/me/children", status_code=201)
def create_session_parent_child(
    request: AlphaChildCreate,
    parent: ParentUser = Depends(require_linked_parent),
    session: Session = Depends(get_db_session),
):
    return _create_child_payload(parent, request, session)


@router.get("/parents/me/children/{student_id}/summary")
def session_parent_child_summary(
    student_id: str,
    parent: ParentUser = Depends(require_linked_parent),
    session: Session = Depends(get_db_session),
):
    student = require_student_for_parent(session, parent, student_id)
    return _summary_payload(parent, student, session)


@router.post(
    "/parents/me/children/{student_id}/summary-feedback",
    status_code=201,
)
def create_session_parent_summary_feedback(
    student_id: str,
    request: ParentSummaryFeedbackCreate,
    parent: ParentUser = Depends(require_linked_parent),
    session: Session = Depends(get_db_session),
):
    student = require_student_for_parent(session, parent, student_id)
    return _summary_feedback_payload(parent, student, request, session)


@router.get("/parents/{parent_id}/children")
def list_alpha_children(
    parent_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(
        _optional_parent_context_when_alpha_auth_required
    ),
):
    parent = _resolve_parent_for_path(
        parent_id=parent_id,
        session=session,
        settings=settings,
        context=context,
    )
    return _children_payload(parent, session)


@router.post("/parents/{parent_id}/children", status_code=201)
def create_alpha_child(
    parent_id: str,
    request: AlphaChildCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(
        _optional_parent_context_when_alpha_auth_required
    ),
):
    parent = _resolve_parent_for_path(
        parent_id=parent_id,
        session=session,
        settings=settings,
        context=context,
    )
    return _create_child_payload(parent, request, session)


@router.get("/parents/{parent_id}/children/{student_id}/summary")
def alpha_child_summary(
    parent_id: str,
    student_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(
        _optional_parent_context_when_alpha_auth_required
    ),
):
    parent = _resolve_parent_for_path(
        parent_id=parent_id,
        session=session,
        settings=settings,
        context=context,
    )
    student = require_student_for_parent(session, parent, student_id)
    return _summary_payload(parent, student, session)


@router.post(
    "/parents/{parent_id}/children/{student_id}/summary-feedback",
    status_code=201,
)
def create_parent_summary_feedback(
    parent_id: str,
    student_id: str,
    request: ParentSummaryFeedbackCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(
        _optional_parent_context_when_alpha_auth_required
    ),
):
    parent = _resolve_parent_for_path(
        parent_id=parent_id,
        session=session,
        settings=settings,
        context=context,
    )
    student = require_student_for_parent(session, parent, student_id)
    return _summary_feedback_payload(parent, student, request, session)
