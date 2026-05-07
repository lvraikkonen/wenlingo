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


def test_sentence_training_updates_ability_and_settlement():
    student = StudentProfile(
        parent_id="parent-1",
        name="灏忓畤",
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
        problem_monsters=["绌烘硾琛ㄨ揪"],
        evidence={"focus": "鍔犵粏鑺?"},
    )

    assert ability.expression == 44
    assert ability.observation == 42
    assert student.xp == 115
    assert student.level == 2
    assert event.xp_delta == 25
    assert event.badge_code == "first_sentence_upgrade"


def test_recommendations_prioritize_revision_gap():
    ability = AbilityProfile(
        student_id="student-1",
        expression=52,
        observation=50,
        structure=30,
        revision=28,
    )

    tasks = choose_today_tasks(ability, has_completed_assessment=True)

    assert tasks.main.kind == "essay"
    assert tasks.quick.kind == "sentence"
    assert tasks.quick.focus in {"鍔犵粏鑺?", "鍔犲姩浣滄垨绁炴€?"}
