from app.domain.enums import BadgeCode, TaskType
from app.domain.models import GameEvent, StudentProfile


XP_BY_TASK = {
    TaskType.assessment: 20,
    TaskType.sentence: 25,
    TaskType.essay: 60,
    TaskType.reading: 30,
}


def level_for_xp(xp: int) -> int:
    return max(1, xp // 100 + 1)


def settle_task(
    student: StudentProfile,
    task_type: TaskType,
    problem_monsters: list[str],
    evidence: dict,
) -> GameEvent:
    if task_type not in XP_BY_TASK:
        raise ValueError(f"Unsupported settlement task type: {task_type.value}")
    xp_delta = XP_BY_TASK[task_type]
    student.xp += xp_delta
    student.level = level_for_xp(student.xp)
    badge = None
    if task_type == TaskType.sentence:
        badge = BadgeCode.first_sentence_upgrade
    if task_type == TaskType.essay:
        badge = BadgeCode.first_revision
    if task_type == TaskType.reading:
        badge = BadgeCode.reading_transfer
    return GameEvent(
        student_id=student.id,
        task_type=task_type,
        xp_delta=xp_delta,
        level_after=student.level,
        badge_code=badge,
        problem_monsters=problem_monsters,
        evidence=evidence,
    )
