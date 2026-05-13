from sqlmodel import select

from app.domain.enums import BadgeCode, ReportType, StudentPersona, TaskType
from app.domain.models import (
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

    assert parent.id == "p1"
    assert parent.display_name == "内测家长"
    assert {student.id for student in students} == {"s1", "s2", "s3", "s4"}
    assert {student.name for student in students} == {"小宇", "小晴", "小川", "小禾"}
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


def test_seed_demo_data_normalizes_existing_random_demo_ids(session):
    legacy_parent = ParentUser(
        id="legacy-parent",
        email="demo@wenlingo.local",
        display_name="内测家长",
    )
    session.add(legacy_parent)
    legacy_profiles = [
        ("legacy-s1", "小宇", StudentPersona.real_child, True),
        ("legacy-s2", "小晴", StudentPersona.vague_expression, False),
        ("legacy-s3", "小川", StudentPersona.weak_structure, False),
        ("legacy-s4", "小禾", StudentPersona.weak_reading_summary, False),
    ]
    for student_id, name, persona, is_real_child in legacy_profiles:
        session.add(
            StudentProfile(
                id=student_id,
                parent_id=legacy_parent.id,
                name=name,
                persona=persona,
                is_real_child=is_real_child,
            )
        )
        session.add(AbilityProfile(student_id=student_id))
    session.add_all(
        [
            Assessment(
                student_id="legacy-s1",
                sentence_before="公园很美。",
                sentence_after="公园里的花红红的。",
                short_writing="我学会了骑车。刚开始我很害怕，后来爸爸扶着我练。",
                summary="legacy assessment",
            ),
            Essay(student_id="legacy-s1", title="legacy essay"),
            GameEvent(
                student_id="legacy-s1",
                task_type=TaskType.assessment,
                xp_delta=10,
                level_after=1,
                badge_code=BadgeCode.first_sentence_upgrade,
            ),
            ReadingSession(
                student_id="legacy-s1",
                article_title="legacy reading",
                transfer_tip="legacy tip",
            ),
            Report(student_id="legacy-s1", report_type=ReportType.stage),
            SentenceTraining(
                student_id="legacy-s1",
                source_sentence="公园很美。",
                upgraded_sentence="公园里的花红红的。",
                focus="detail",
            ),
        ]
    )
    session.commit()

    parent = seed_demo_data(session)

    students = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == "p1")
    ).all()
    abilities = session.exec(select(AbilityProfile)).all()

    assert parent.id == "p1"
    assert session.get(ParentUser, "legacy-parent") is None
    assert {student.id for student in students} == {"s1", "s2", "s3", "s4"}
    assert {ability.student_id for ability in abilities} == {"s1", "s2", "s3", "s4"}
    assert session.exec(select(Assessment)).one().student_id == "s1"
    assert session.exec(select(Essay)).one().student_id == "s1"
    assert session.exec(select(GameEvent)).one().student_id == "s1"
    assert session.exec(select(ReadingSession)).one().student_id == "s1"
    assert session.exec(select(Report)).one().student_id == "s1"
    assert session.exec(select(SentenceTraining)).one().student_id == "s1"


def test_seed_demo_data_preserves_extra_canonical_child_with_same_persona(session):
    session.add(
        ParentUser(
            id="p1",
            email="demo@wenlingo.local",
            display_name="内测家长",
        )
    )
    session.add(
        StudentProfile(
            id="extra-child",
            parent_id="p1",
            name="真实孩子",
            persona=StudentPersona.real_child,
            is_real_child=True,
        )
    )
    session.add(AbilityProfile(student_id="extra-child", expression=65))
    session.commit()

    seed_demo_data(session)

    students = session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == "p1")
    ).all()
    extra_child = session.get(StudentProfile, "extra-child")
    extra_ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == "extra-child")
    ).one()

    assert {student.id for student in students} == {
        "s1",
        "s2",
        "s3",
        "s4",
        "extra-child",
    }
    assert extra_child is not None
    assert extra_child.name == "真实孩子"
    assert extra_ability.expression == 65


def test_seed_demo_data_preserves_non_demo_child_under_legacy_parent(session):
    legacy_parent = ParentUser(
        id="legacy-parent",
        email="demo@wenlingo.local",
        display_name="内测家长",
    )
    session.add(legacy_parent)
    session.add(
        StudentProfile(
            id="legacy-s1",
            parent_id=legacy_parent.id,
            name="小宇",
            persona=StudentPersona.real_child,
            is_real_child=True,
        )
    )
    session.add(
        StudentProfile(
            id="legacy-extra",
            parent_id=legacy_parent.id,
            name="真实孩子",
            persona=StudentPersona.real_child,
            is_real_child=True,
        )
    )
    session.commit()

    seed_demo_data(session)

    legacy_extra = session.get(StudentProfile, "legacy-extra")
    legacy_parent_after_seed = session.get(ParentUser, "legacy-parent")

    assert legacy_extra is not None
    assert legacy_extra.parent_id == "legacy-parent"
    assert legacy_parent_after_seed is not None
    assert legacy_parent_after_seed.email == "demo@wenlingo.local.legacy.legacy-parent"
