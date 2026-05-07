from app.domain.enums import TaskType
from app.domain.models import AbilityProfile, utcnow


def clamp(value: int) -> int:
    return max(0, min(100, value))


def to_child_abilities(ability: AbilityProfile) -> dict[str, int]:
    return {
        "reading_power": round((ability.comprehension + ability.summarization) / 2),
        "specific_writing_power": round(
            (ability.expression + ability.observation + ability.structure * 0.5) / 2.5
        ),
        "revision_power": ability.revision,
    }


def apply_ability_delta(
    ability: AbilityProfile,
    task_type: TaskType,
    evidence_key: str,
    quality_score: float,
    completed_revision: bool = False,
) -> AbilityProfile:
    delta = 4 if quality_score >= 0.75 else 2
    if task_type == TaskType.sentence:
        ability.expression = clamp(ability.expression + delta)
        ability.observation = clamp(ability.observation + delta)
    if task_type == TaskType.essay:
        ability.expression = clamp(ability.expression + delta)
        ability.structure = clamp(ability.structure + delta)
        if completed_revision:
            ability.revision = clamp(ability.revision + delta + 1)
    if task_type == TaskType.reading:
        ability.comprehension = clamp(ability.comprehension + delta)
        ability.summarization = clamp(ability.summarization + delta)
    ability.evidence[evidence_key] = {"quality_score": quality_score, "task_type": task_type.value}
    ability.updated_at = utcnow()
    return ability
