from sqlmodel import Session, select

from app.domain.enums import StudentPersona
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    Essay,
    GameEvent,
    ParentUser,
    ReadingSession,
    Report,
    SentenceTraining,
    StudentProfile,
)


DEMO_PARENT_ID = "p1"
DEMO_PARENT_EMAIL = "demo@wenlingo.local"

DEMO_PROFILES = [
    (
        "s1",
        "小宇",
        StudentPersona.real_child,
        True,
        dict(expression=44, observation=38, structure=42, revision=36),
    ),
    (
        "s2",
        "小晴",
        StudentPersona.vague_expression,
        False,
        dict(expression=28, observation=26, structure=45, revision=34),
    ),
    (
        "s3",
        "小川",
        StudentPersona.weak_structure,
        False,
        dict(expression=48, observation=46, structure=24, revision=32),
    ),
    (
        "s4",
        "小禾",
        StudentPersona.weak_reading_summary,
        False,
        dict(comprehension=30, summarization=24, expression=42),
    ),
]

STUDENT_ID_REFERENCES = [
    AbilityHistory,
    Assessment,
    Essay,
    GameEvent,
    ReadingSession,
    Report,
    SentenceTraining,
]


def _legacy_email_for(parent_id: str) -> str:
    return f"{DEMO_PARENT_EMAIL}.legacy.{parent_id}"


def _ensure_demo_parent(session: Session) -> tuple[ParentUser, list[str]]:
    legacy_parent_ids: list[str] = []
    parent = session.get(ParentUser, DEMO_PARENT_ID)
    existing_by_email = session.exec(
        select(ParentUser).where(ParentUser.email == DEMO_PARENT_EMAIL)
    ).first()

    if existing_by_email and existing_by_email.id != DEMO_PARENT_ID:
        legacy_parent_ids.append(existing_by_email.id)
        existing_by_email.email = _legacy_email_for(existing_by_email.id)
        session.add(existing_by_email)
        session.flush()

    if not parent:
        parent = ParentUser(
            id=DEMO_PARENT_ID,
            email=DEMO_PARENT_EMAIL,
            display_name="内测家长",
        )
        session.add(parent)
        session.flush()

    parent.email = DEMO_PARENT_EMAIL
    parent.display_name = "内测家长"
    session.add(parent)
    return parent, legacy_parent_ids


def _move_ability_profile(session: Session, old_student_id: str, new_student_id: str) -> None:
    legacy_ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == old_student_id)
    ).first()
    if not legacy_ability:
        return

    target_ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == new_student_id)
    ).first()
    if target_ability:
        session.delete(legacy_ability)
    else:
        legacy_ability.student_id = new_student_id
        session.add(legacy_ability)


def _move_student_references(
    session: Session, old_student_id: str, new_student_id: str
) -> None:
    _move_ability_profile(session, old_student_id, new_student_id)
    for model in STUDENT_ID_REFERENCES:
        rows = session.exec(
            select(model).where(model.student_id == old_student_id)
        ).all()
        for row in rows:
            row.student_id = new_student_id
            session.add(row)
    session.flush()


def _find_legacy_demo_students(
    session: Session,
    parent_ids: list[str],
    student_id: str,
    name: str,
    persona: StudentPersona,
    is_real_child: bool,
) -> list[StudentProfile]:
    if not parent_ids:
        return []

    return session.exec(
        select(StudentProfile).where(
            StudentProfile.parent_id.in_(parent_ids),
            StudentProfile.name == name,
            StudentProfile.persona == persona,
            StudentProfile.is_real_child == is_real_child,
            StudentProfile.id != student_id,
        )
    ).all()


def _ensure_demo_student(
    session: Session,
    parent: ParentUser,
    legacy_parent_ids: list[str],
    student_id: str,
    name: str,
    persona: StudentPersona,
    is_real_child: bool,
    ability_values: dict[str, int],
) -> None:
    target = session.get(StudentProfile, student_id)
    if not target:
        target = StudentProfile(
            id=student_id,
            parent_id=parent.id,
            name=name,
            persona=persona,
            is_real_child=is_real_child,
        )
        session.add(target)
        session.flush()

    legacy_students = _find_legacy_demo_students(
        session, legacy_parent_ids, student_id, name, persona, is_real_child
    )
    for legacy_student in legacy_students:
        _move_student_references(session, legacy_student.id, student_id)
        session.delete(legacy_student)

    target.name = name
    target.parent_id = parent.id
    target.persona = persona
    target.is_real_child = is_real_child
    session.add(target)

    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student_id)
    ).first()
    if not ability:
        session.add(AbilityProfile(student_id=student_id, **ability_values))


def seed_demo_data(session: Session) -> ParentUser:
    parent, legacy_parent_ids = _ensure_demo_parent(session)
    for student_id, name, persona, is_real_child, ability_values in DEMO_PROFILES:
        _ensure_demo_student(
            session,
            parent,
            legacy_parent_ids,
            student_id,
            name,
            persona,
            is_real_child,
            ability_values,
        )

    for legacy_parent_id in legacy_parent_ids:
        legacy_parent = session.get(ParentUser, legacy_parent_id)
        remaining_children = session.exec(
            select(StudentProfile).where(StudentProfile.parent_id == legacy_parent_id)
        ).first()
        if legacy_parent and not remaining_children:
            session.delete(legacy_parent)

    session.commit()
    session.refresh(parent)
    return parent
