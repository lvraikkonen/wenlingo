import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.models import (
    AbilityProfile,
    Assessment,
    Essay,
    EssayVersion,
    GameEvent,
    LLMCallLog,
    ParentUser,
    ReadingSession,
    Report,
    SentenceTraining,
    StudentProfile,
)


TIMESTAMP_FIELDS = [
    (ParentUser, "created_at"),
    (StudentProfile, "created_at"),
    (AbilityProfile, "updated_at"),
    (Assessment, "created_at"),
    (SentenceTraining, "created_at"),
    (Essay, "created_at"),
    (EssayVersion, "created_at"),
    (ReadingSession, "created_at"),
    (GameEvent, "created_at"),
    (Report, "created_at"),
    (LLMCallLog, "created_at"),
]


JSON_FIELDS = [
    (AbilityProfile, "evidence"),
    (SentenceTraining, "ai_feedback"),
    (Essay, "material_card"),
    (Essay, "outline"),
    (EssayVersion, "ai_feedback"),
    (ReadingSession, "answers"),
    (ReadingSession, "ai_feedback"),
    (GameEvent, "problem_monsters"),
    (GameEvent, "evidence"),
    (Report, "content"),
    (LLMCallLog, "output_json"),
]


def test_timestamp_columns_are_timezone_aware_and_not_nullable():
    for model, field_name in TIMESTAMP_FIELDS:
        column = model.__table__.c[field_name]

        assert column.type.timezone is True, f"{model.__name__}.{field_name}"
        assert column.nullable is False, f"{model.__name__}.{field_name}"


def test_json_columns_are_not_nullable():
    for model, field_name in JSON_FIELDS:
        column = model.__table__.c[field_name]

        assert column.nullable is False, f"{model.__name__}.{field_name}"


def test_game_event_problem_monsters_are_string_list():
    assert GameEvent.__annotations__["problem_monsters"] == list[str]


def test_essay_version_labels_are_unique_per_essay(session):
    essay_title = "我学会了骑车"
    first_revision = "我学会了骑车。第一次修改加了动作。"
    duplicate_revision = "我学会了骑车。第二次修改不能重复保存。"

    essay = Essay(student_id="student-1", title=essay_title)
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            content=first_revision,
        )
    )
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            content=duplicate_revision,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()
