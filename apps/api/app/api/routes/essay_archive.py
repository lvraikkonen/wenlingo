from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    require_auth_mode_state_change,
    require_essay_for_auth_mode,
    require_student_for_auth_mode,
)
from app.api.deps import get_db_session
from app.api.routes.alpha import record_product_event
from app.core.config import Settings, get_settings
from app.domain.models import Essay, StudentProfile, utcnow
from app.services.essay_archive import build_archive_detail, build_archive_item

router = APIRouter(tags=["essay_archive"])


class VisibilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hidden: bool = Field(strict=True)


def _clamped_limit(limit: int, max_limit: int) -> int:
    return min(max(limit, 1), max_limit)


def _submitted_filter():
    return Essay.last_version_submitted_at.is_not(None)


def _archive_items(
    session: Session,
    essays: list[Essay],
    *,
    parent_visible: bool,
    child_surface: bool,
) -> list[dict]:
    return [
        build_archive_item(
            session,
            essay,
            parent_visible=parent_visible,
            child_surface=child_surface,
        )
        for essay in essays
    ]


def _require_submitted_essay(essay: Essay) -> None:
    if essay.last_version_submitted_at is None:
        raise HTTPException(status_code=404, detail="essay not found")


def _student_parent_id(student: StudentProfile) -> str | None:
    return student.parent_id


def parent_archive_order_by():
    return (
        Essay.visibility_changed_at.desc().nulls_last(),
        Essay.last_version_submitted_at.desc(),
        Essay.id.desc(),
    )


@router.get("/api/students/{student_id}/essay-archive")
def child_essay_archive(
    student_id: str,
    limit: int = 3,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    archive_limit = _clamped_limit(limit, 3)
    essays = session.exec(
        select(Essay)
        .where(
            Essay.student_id == student.id,
            Essay.hidden_by == "",
            _submitted_filter(),
        )
        .order_by(Essay.last_version_submitted_at.desc(), Essay.id.desc())
        .limit(archive_limit)
    ).all()
    return {
        "items": _archive_items(
            session,
            list(essays),
            parent_visible=False,
            child_surface=True,
        )
    }


@router.get("/api/parents/students/{student_id}/essay-archive")
def parent_essay_archive(
    student_id: str,
    include_hidden: bool = False,
    limit: int = 20,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    archive_limit = _clamped_limit(limit, 100)
    statement = select(Essay).where(Essay.student_id == student.id, _submitted_filter())
    if not include_hidden:
        statement = statement.where(Essay.hidden_by == "")
    if include_hidden:
        statement = statement.order_by(*parent_archive_order_by())
    else:
        statement = statement.order_by(Essay.last_version_submitted_at.desc(), Essay.id.desc())
    essays = session.exec(statement.limit(archive_limit)).all()
    return {
        "items": _archive_items(
            session,
            list(essays),
            parent_visible=True,
            child_surface=False,
        )
    }


@router.get("/api/essays/{essay_id}/archive-detail")
def child_essay_archive_detail(
    essay_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _require_submitted_essay(essay)
    if essay.hidden_by:
        raise HTTPException(status_code=404, detail="essay not found")
    return build_archive_detail(
        session,
        essay,
        parent_visible=False,
        child_surface=True,
    )


@router.get("/api/parents/essays/{essay_id}/archive-detail")
def parent_essay_archive_detail(
    essay_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _require_submitted_essay(essay)
    return build_archive_detail(
        session,
        essay,
        parent_visible=True,
        child_surface=False,
    )


@router.patch("/api/essays/{essay_id}/visibility")
def hide_child_essay(
    essay_id: str,
    request: VisibilityUpdate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    if request.hidden is not True:
        raise HTTPException(status_code=400, detail="child visibility only supports hide")
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _require_submitted_essay(essay)
    if essay.hidden_by:
        raise HTTPException(status_code=404, detail="essay not found")

    hidden_at = utcnow()
    essay.hidden_by = "child"
    essay.hidden_at = hidden_at
    essay.visibility_changed_at = hidden_at
    session.add(essay)
    session.flush()
    student = session.get(StudentProfile, essay.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="student not found")
    try:
        record_product_event(
            session,
            "essay_hidden_by_child",
            parent_id=_student_parent_id(student),
            student_id=student.id,
            payload={
                "essay_id": essay.id,
                "hidden": True,
                "actor_type": "child_surface",
            },
        )
    except Exception:
        pass
    item = build_archive_item(
        session,
        essay,
        parent_visible=False,
        child_surface=True,
    )
    session.commit()
    return item


@router.patch("/api/parents/essays/{essay_id}/visibility")
def restore_parent_essay(
    essay_id: str,
    request: VisibilityUpdate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    if request.hidden is not False:
        raise HTTPException(status_code=400, detail="parent visibility only supports restore")
    essay = require_essay_for_auth_mode(session, settings, context, essay_id)
    _require_submitted_essay(essay)
    if not essay.hidden_by:
        return build_archive_item(
            session,
            essay,
            parent_visible=True,
            child_surface=False,
        )

    changed_at = utcnow()
    essay.hidden_by = ""
    essay.hidden_at = None
    essay.visibility_changed_at = changed_at
    session.add(essay)
    session.flush()
    student = session.get(StudentProfile, essay.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="student not found")
    parent_account_id = context.parent.account_id if context and context.parent else ""
    try:
        record_product_event(
            session,
            "essay_restored_by_parent",
            parent_id=_student_parent_id(student),
            student_id=student.id,
            payload={
                "essay_id": essay.id,
                "hidden": False,
                "actor_type": "parent",
                "parent_account_id": parent_account_id,
            },
        )
    except Exception:
        pass
    item = build_archive_item(
        session,
        essay,
        parent_visible=True,
        child_surface=False,
    )
    session.commit()
    return item
