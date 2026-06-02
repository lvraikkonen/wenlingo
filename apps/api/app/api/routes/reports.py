from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.api.auth_deps import (
    ParentContext,
    require_auth_mode_state_change,
    require_student_for_auth_mode,
)
from app.api.deps import get_db_session
from app.core.config import Settings, get_settings
from app.domain.enums import ReportType
from app.domain.models import Report
from app.services.reports import build_stage_report_content

router = APIRouter(prefix="/api/students", tags=["reports"])


class ReportCreate(BaseModel):
    report_type: ReportType = ReportType.stage


@router.post(
    "/{student_id}/reports",
    status_code=201,
)
def create_report(
    student_id: str,
    request: ReportCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    if request.report_type != ReportType.stage:
        raise HTTPException(status_code=400, detail="only stage reports are supported")
    try:
        content = build_stage_report_content(session, student_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    report = Report(student_id=student_id, report_type=request.report_type, content=content.model_dump())
    session.add(report)
    report_payload = report.model_dump()
    session.commit()
    return {"report": report_payload, "content": content}
