from sqlmodel import Session, select

from app.domain.enums import StudentPersona
from app.domain.models import AbilityProfile, ParentUser, StudentProfile


def seed_demo_data(session: Session) -> ParentUser:
    existing = session.exec(
        select(ParentUser).where(ParentUser.email == "demo@wenlingo.local")
    ).first()
    if existing:
        return existing

    parent = ParentUser(email="demo@wenlingo.local", display_name="内测家长")
    session.add(parent)
    session.flush()

    profiles = [
        (
            "小宇",
            StudentPersona.real_child,
            True,
            dict(expression=44, observation=38, structure=42, revision=36),
        ),
        (
            "小晴",
            StudentPersona.vague_expression,
            False,
            dict(expression=28, observation=26, structure=45, revision=34),
        ),
        (
            "小川",
            StudentPersona.weak_structure,
            False,
            dict(expression=48, observation=46, structure=24, revision=32),
        ),
        (
            "小禾",
            StudentPersona.weak_reading_summary,
            False,
            dict(comprehension=30, summarization=24, expression=42),
        ),
    ]
    for name, persona, is_real_child, ability_values in profiles:
        student = StudentProfile(
            parent_id=parent.id,
            name=name,
            persona=persona,
            is_real_child=is_real_child,
        )
        session.add(student)
        session.flush()
        session.add(AbilityProfile(student_id=student.id, **ability_values))

    session.commit()
    session.refresh(parent)
    return parent
