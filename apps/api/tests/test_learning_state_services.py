from datetime import datetime, timezone

import pytest

from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, StudentProfile
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
    student = StudentProfile(
        parent_id="parent-1",
        name="小宇",
        persona="real_child",
        xp=90,
        level=1,
    )
    ability = AbilityProfile(student_id=student.id, expression=40, observation=38, revision=30)

    apply_ability_delta(
        ability,
        task_type=TaskType.sentence,
        evidence_key="specific_detail_added",
        quality_score=0.8,
    )
    event = settle_task(
        student,
        TaskType.sentence,
        problem_monsters=["空泛表达"],
        evidence={"focus": "加细节"},
    )

    assert ability.expression == 44
    assert ability.observation == 42
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


def test_apply_ability_delta_refreshes_updated_at():
    old_updated_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ability = AbilityProfile(
        student_id="student-1",
        expression=40,
        observation=38,
        updated_at=old_updated_at,
    )

    apply_ability_delta(
        ability,
        task_type=TaskType.sentence,
        evidence_key="specific_detail_added",
        quality_score=0.8,
    )

    assert ability.updated_at > old_updated_at


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
