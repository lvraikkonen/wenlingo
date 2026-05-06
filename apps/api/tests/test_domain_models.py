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
