from datetime import datetime, timezone

import pytest
from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import AbilityHistory, AbilityProfile, ParentUser, StudentProfile
from app.services.abilities import apply_ability_delta, to_child_abilities
from app.services.gamification import settle_task
from app.services.recommendations import choose_today_tasks


def test_child_ability_mapping_uses_three_public_dimensions():
    ability = AbilityProfile(
        student_id="student-1",
        comprehension=40,
        summarization=60,
        expression=50,
        observation=70,
        structure=30,
        revision=20,
    )

    mapped = to_child_abilities(ability)

    assert mapped == {
        "reading_power": 50,
        "specific_writing_power": 54,
        "revision_power": 20,
    }


def test_sentence_training_updates_ability_and_settlement(session):
    parent = ParentUser(email="parent@example.com", display_name="Parent")
    student = StudentProfile(
        parent_id=parent.id,
        name="小宇",
        persona="real_child",
        xp=90,
        level=1,
    )
    ability = AbilityProfile(student_id=student.id, expression=40, observation=38, revision=30)
    session.add(parent)
    session.add(student)
    session.add(ability)
    session.commit()

    history_rows = apply_ability_delta(
        session,
        ability,
        ability_deltas={"expression": 4, "observation": 4},
        source_type=TaskType.sentence,
        source_id="sentence-training-1",
    )
    event = settle_task(
        student,
        TaskType.sentence,
        problem_monsters=["空泛表达"],
        evidence={"focus": "加细节"},
    )

    assert ability.expression == 44
    assert ability.observation == 42
    assert [
        (row.ability_name, row.old_value, row.new_value, row.delta)
        for row in history_rows
    ] == [
        ("expression", 40, 44, 4),
        ("observation", 38, 42, 4),
    ]
    assert all(row.source_type == TaskType.sentence for row in history_rows)
    assert all(row.source_id == "sentence-training-1" for row in history_rows)
    assert student.xp == 115
    assert student.level == 2
    assert event.xp_delta == 25
    assert event.badge_code == "first_sentence_upgrade"
    assert event.problem_monsters == ["空泛表达"]

    session.add(event)
    session.commit()
    session.refresh(event)

    assert event.problem_monsters == ["空泛表达"]
    assert all(
        isinstance(problem_monster, str) for problem_monster in event.problem_monsters
    )
    persisted_history = session.exec(select(AbilityHistory)).all()
    assert len(persisted_history) == 2


def test_apply_ability_delta_refreshes_updated_at(session):
    old_updated_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ability = AbilityProfile(
        student_id="student-1",
        expression=40,
        observation=38,
        updated_at=old_updated_at,
    )

    apply_ability_delta(
        session,
        ability,
        ability_deltas={"expression": 4},
        source_type=TaskType.sentence,
        source_id="sentence-training-1",
    )

    assert ability.updated_at > old_updated_at


def test_apply_ability_delta_persists_history_with_source(session):
    parent = ParentUser(email="parent@example.com", display_name="Parent")
    student = StudentProfile(parent_id=parent.id, name="小宇", persona="real_child")
    ability = AbilityProfile(
        student_id=student.id,
        expression=40,
        observation=38,
    )
    session.add(parent)
    session.add(student)
    session.add(ability)
    session.commit()

    history_rows = apply_ability_delta(
        session,
        ability,
        ability_deltas={"expression": 3},
        source_type=TaskType.essay,
        source_id="essay-version-1",
    )
    session.commit()
    session.refresh(ability)
    persisted_history = session.exec(select(AbilityHistory)).one()

    assert ability.expression == 43
    assert history_rows == [persisted_history]
    assert persisted_history.student_id == student.id
    assert persisted_history.ability_name == "expression"
    assert persisted_history.old_value == 40
    assert persisted_history.new_value == 43
    assert persisted_history.delta == 3
    assert persisted_history.source_type == TaskType.essay
    assert persisted_history.source_id == "essay-version-1"
    assert isinstance(persisted_history.created_at, datetime)


def test_apply_ability_delta_records_actual_delta_after_clamp(session):
    ability = AbilityProfile(student_id="student-1", expression=98)

    history_rows = apply_ability_delta(
        session,
        ability,
        ability_deltas={"expression": 5},
        source_type=TaskType.sentence,
        source_id="sentence-training-1",
    )

    assert ability.expression == 100
    assert [(row.old_value, row.new_value, row.delta) for row in history_rows] == [
        (98, 100, 2)
    ]


def test_apply_ability_delta_ignores_empty_zero_negative_invalid_and_unchanged_deltas(
    session,
):
    ability = AbilityProfile(
        student_id="student-1",
        expression=100,
        observation=40,
        revision=45,
    )

    empty_rows = apply_ability_delta(
        session,
        ability,
        ability_deltas={},
        source_type=TaskType.sentence,
        source_id="sentence-training-1",
    )
    ignored_rows = apply_ability_delta(
        session,
        ability,
        ability_deltas={"expression": 5, "observation": 0, "revision": -3, "vibes": 7},
        source_type=TaskType.sentence,
        source_id="sentence-training-1",
    )

    assert empty_rows == []
    assert ignored_rows == []
    assert ability.expression == 100
    assert ability.observation == 40
    assert ability.revision == 45
    assert session.exec(select(AbilityHistory)).all() == []


def test_settle_task_rejects_unsupported_task_type():
    student = StudentProfile(parent_id="parent-1", name="小宇", persona="real_child")

    with pytest.raises(ValueError, match="Unsupported settlement task type"):
        settle_task(student, TaskType.report, problem_monsters=[], evidence={})


def test_recommendations_prioritize_structure_gap():
    ability = AbilityProfile(
        student_id="student-1",
        expression=52,
        observation=50,
        structure=30,
        revision=28,
    )

    tasks = choose_today_tasks(ability, has_completed_assessment=True)

    assert tasks.main.kind == "essay"
    assert tasks.main.title == "作文城堡"
    assert tasks.main.focus == "把选材和结构说清楚"
    assert tasks.quick.kind == "sentence"
    assert tasks.quick.title == "句子工坊"
    assert tasks.quick.focus == "加动作或神态"
