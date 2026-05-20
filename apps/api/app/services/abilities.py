from sqlmodel import Session

from app.domain.enums import TaskType
from app.domain.models import AbilityHistory, AbilityProfile, utcnow


VALID_ABILITY_NAMES = {
    "expression",
    "observation",
    "structure",
    "revision",
    "comprehension",
    "summarization",
}


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
    session: Session,
    ability: AbilityProfile,
    ability_deltas: dict[str, int],
    source_type: TaskType,
    source_id: str,
) -> list[AbilityHistory]:
    history_rows: list[AbilityHistory] = []
    if not ability_deltas:
        return history_rows

    for ability_name, raw_delta in ability_deltas.items():
        if ability_name not in VALID_ABILITY_NAMES or raw_delta <= 0:
            continue

        old_value = getattr(ability, ability_name)
        new_value = clamp(old_value + raw_delta)
        actual_delta = new_value - old_value
        if actual_delta == 0:
            continue

        setattr(ability, ability_name, new_value)
        history_row = AbilityHistory(
            student_id=ability.student_id,
            ability_name=ability_name,
            old_value=old_value,
            new_value=new_value,
            delta=actual_delta,
            source_type=source_type,
            source_id=source_id,
        )
        session.add(history_row)
        history_rows.append(history_row)

    if history_rows:
        ability.updated_at = utcnow()

    return history_rows
