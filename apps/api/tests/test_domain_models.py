import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import TaskType
from app.domain.models import (
    AbilityHistory,
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


def test_ability_history_source_fields_are_indexed():
    index_columns = {
        column.name
        for index in AbilityHistory.__table__.indexes
        for column in index.columns
    }

    assert "ability_name" in index_columns
    assert "source_id" in index_columns


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


def test_llm_call_log_tracks_provider_prompt_raw_response_and_retry_count():
    log = LLMCallLog(
        task_type=TaskType.essay,
        provider="http",
        model="test-model",
        prompt_version="v0.2-quality-spine-2026-05-14",
        input_summary="作文题目：我学会了骑车",
        raw_response='{"strengths":["清楚","有心情"]}',
        output_json={"strengths": ["清楚", "有心情"]},
        validation_ok=True,
        error_message="",
        retry_count=1,
    )

    assert log.task_type == TaskType.essay
    assert log.provider == "http"
    assert log.model == "test-model"
    assert log.prompt_version == "v0.2-quality-spine-2026-05-14"
    assert log.input_summary == "作文题目：我学会了骑车"
    assert log.raw_response == '{"strengths":["清楚","有心情"]}'
    assert log.output_json == {"strengths": ["清楚", "有心情"]}
    assert log.validation_ok is True
    assert log.error_message == ""
    assert log.retry_count == 1


def test_llm_call_log_tracks_student_and_task_name():
    log = LLMCallLog(
        student_id="s1",
        task_type=TaskType.sentence,
        task_name="sentence_upgrade_feedback",
        provider="http",
        model="test-model",
        prompt_version="v0.2-family-test-2026-05-15",
        input_summary="句子快练；原句长度：5；升级句长度：18",
        raw_response='{"encouragement":"写清楚了"}',
        output_json={"encouragement": "写清楚了"},
        validation_ok=True,
        error_message="",
        retry_count=0,
    )

    assert log.student_id == "s1"
    assert log.task_name == "sentence_upgrade_feedback"


def test_essay_version_tracks_revision_task_metadata_and_llm_log_link():
    version = EssayVersion(
        essay_id="essay-1",
        version_label="revision",
        content="我学会了骑车。二稿加入了手心出汗的细节。",
        duration_seconds=420,
        completed_tasks=["给第二段加一个动作描写"],
        skipped_tasks=["补一个结尾感受"],
        llm_call_log_id="log-1",
    )

    assert version.essay_id == "essay-1"
    assert version.version_label == "revision"
    assert version.content == "我学会了骑车。二稿加入了手心出汗的细节。"
    assert version.duration_seconds == 420
    assert version.completed_tasks == ["给第二段加一个动作描写"]
    assert version.skipped_tasks == ["补一个结尾感受"]
    assert version.llm_call_log_id == "log-1"


def test_assessment_artifact_references_are_nullable_and_indexed():
    sentence_column = Assessment.__table__.c["sentence_training_id"]
    essay_column = Assessment.__table__.c["essay_id"]
    index_columns = {
        column.name
        for index in Assessment.__table__.indexes
        for column in index.columns
    }

    assert sentence_column.nullable is True
    assert essay_column.nullable is True
    assert sentence_column.foreign_keys
    assert essay_column.foreign_keys
    assert "sentence_training_id" in index_columns
    assert "essay_id" in index_columns
