from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.enums import StudentPersona
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    Essay,
    ParentUser,
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


class AlphaParentCreate(BaseModel):
    display_name: str = Field(default="Alpha 家长", max_length=40)

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str:
        if value is None:
            return "Alpha 家长"
        normalized = str(value).strip()
        return normalized or "Alpha 家长"


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


@router.post("/parents", status_code=201)
def create_alpha_parent(
    request: AlphaParentCreate,
    session: Session = Depends(get_db_session),
):
    parent = ParentUser(
        email=f"alpha-{uuid4()}@wenlingo.local",
        display_name=request.display_name,
    )
    session.add(parent)
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
        "empty_state": None if assessment_completed else EMPTY_SUMMARY,
        "next_suggestion": POPULATED_NEXT_SUGGESTION
        if assessment_completed
        else EMPTY_NEXT_SUGGESTION,
    }
