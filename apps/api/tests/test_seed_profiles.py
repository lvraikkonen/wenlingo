from sqlmodel import select

from app.domain.enums import StudentPersona
from app.domain.models import AbilityProfile, ParentUser, StudentProfile
from app.domain.seed import seed_demo_data


def test_seed_demo_data_creates_parent_and_four_children(session):
    seed_demo_data(session)

    parent = session.exec(
        select(ParentUser).where(ParentUser.email == "demo@wenlingo.local")
    ).one()
    students = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent.id)
    ).all()
    abilities = session.exec(select(AbilityProfile)).all()

    assert parent.display_name == "内测家长"
    assert {student.persona for student in students} == {
        StudentPersona.real_child,
        StudentPersona.vague_expression,
        StudentPersona.weak_structure,
        StudentPersona.weak_reading_summary,
    }
    assert len(abilities) == 4
    assert all(20 <= ability.expression <= 70 for ability in abilities)


def test_seed_demo_data_is_idempotent(session):
    seed_demo_data(session)
    seed_demo_data(session)

    parents = session.exec(select(ParentUser)).all()
    students = session.exec(select(StudentProfile)).all()
    abilities = session.exec(select(AbilityProfile)).all()

    assert len(parents) == 1
    assert len(students) == 4
    assert len(abilities) == 4
