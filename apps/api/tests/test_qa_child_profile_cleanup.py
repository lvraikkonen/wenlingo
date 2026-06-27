from datetime import timedelta

import pytest
from sqlmodel import select

from app.core.config import Settings
from app.domain.enums import ReportType, StudentPersona, TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Assessment,
    DailyTaskLimitCounter,
    Essay,
    EssayVersion,
    FeedbackReaction,
    GameEvent,
    LLMCallLog,
    ParentAccount,
    ParentFeedback,
    ParentSession,
    ParentUser,
    ProductEvent,
    ReadingSession,
    Report,
    SentenceTraining,
    StudentProfile,
    utcnow,
)
from app.services.auth_security import hash_secret
from app.services.qa_child_profile_cleanup import (
    DELETE_QA_CHILD_PROFILES_CONFIRMATION,
    QAChildProfileCleanupError,
    cleanup_qa_child_profiles,
    detect_cleanup_environment,
    is_v06b_qa_child_name,
    preview_qa_child_profile_cleanup,
)


def seed_parent(session, *, account_id="account-1", parent_id="parent-1"):
    account = ParentAccount(
        id=account_id,
        email_normalized=f"{account_id}@example.com",
        email_verified_at=utcnow(),
    )
    session.add(account)
    session.flush()
    parent = ParentUser(
        id=parent_id,
        email=f"{parent_id}@example.com",
        display_name="QA Parent",
        account_id=account.id,
        account_linked_at=utcnow(),
    )
    session.add(parent)
    session.add(
        ParentSession(
            account_id=account.id,
            token_hash=hash_secret("session-token", purpose="session-token", pepper="test-pepper"),
            expires_at=utcnow() + timedelta(days=1),
        )
    )
    session.flush()
    return account, parent


def seed_child_graph(session, parent: ParentUser, *, child_id: str, name: str):
    child = StudentProfile(
        id=child_id,
        parent_id=parent.id,
        name=name,
        grade_label="四年级",
        persona=StudentPersona.real_child,
        is_real_child=True,
    )
    session.add(child)
    session.flush()
    sentence = SentenceTraining(
        student_id=child.id,
        source_sentence="原句",
        upgraded_sentence="升级句",
        focus="加细节",
    )
    essay = Essay(student_id=child.id, title="QA Essay")
    llm_log = LLMCallLog(
        student_id=child.id,
        task_type=TaskType.essay,
        task_name="writing_topic_analysis",
        input_summary="qa",
    )
    session.add(sentence)
    session.add(essay)
    session.add(llm_log)
    session.flush()
    rows = [
        Assessment(
            student_id=child.id,
            sentence_before="a",
            sentence_after="b",
            short_writing="c",
            summary="d",
            sentence_training_id=sentence.id,
            essay_id=essay.id,
        ),
        EssayVersion(
            essay_id=essay.id,
            version_label="first_draft",
            content="draft",
            llm_call_log_id=llm_log.id,
        ),
        ReadingSession(student_id=child.id, article_title="文章", transfer_tip="tip"),
        GameEvent(student_id=child.id, task_type=TaskType.essay, xp_delta=1, level_after=1),
        Report(student_id=child.id, report_type=ReportType.stage),
        AbilityProfile(student_id=child.id),
        AbilityHistory(
            student_id=child.id,
            ability_name="expression",
            old_value=40,
            new_value=41,
            delta=1,
            source_type=TaskType.essay,
            source_id=essay.id,
        ),
        FeedbackReaction(
            parent_id=parent.id,
            student_id=child.id,
            target_type="essay_draft",
            target_id="draft",
            reaction="positive",
        ),
        ParentFeedback(
            parent_id=parent.id,
            student_id=child.id,
            target_type="alpha_summary",
            target_id="summary",
            usefulness="helpful",
        ),
        ProductEvent(event_type="qa_child_event", parent_id=parent.id, student_id=child.id),
        ProductEvent(event_type="parent_level_event", parent_id=parent.id, student_id=None),
        DailyTaskLimitCounter(
            student_id=child.id,
            task_name="material_questions",
            product_day="2026-06-27",
            limit_value=5,
        ),
    ]
    for row in rows:
        session.add(row)
    session.commit()
    session.refresh(child)
    return child, essay, sentence, llm_log


def count_rows(session, model) -> int:
    return len(session.exec(select(model)).all())


def test_v06b_qa_child_name_matcher_is_narrow():
    assert is_v06b_qa_child_name("QA v0.6b") is True
    assert is_v06b_qa_child_name("QA06b-Happy2") is True
    assert is_v06b_qa_child_name("QA06b-N1") is True
    assert is_v06b_qa_child_name("QA v0.6c") is False
    assert is_v06b_qa_child_name("小星") is False
    assert is_v06b_qa_child_name("QA06") is False


def test_preview_matches_only_v06b_qa_children(session):
    _account, parent = seed_parent(session)
    qa_child, _essay, _sentence, _llm_log = seed_child_graph(
        session, parent, child_id="qa-child", name="QA06b-Happy2"
    )
    regular_child, _essay2, _sentence2, _llm_log2 = seed_child_graph(
        session, parent, child_id="real-child", name="小星"
    )

    result = preview_qa_child_profile_cleanup(session)

    assert [row.student_id for row in result.children] == [qa_child.id]
    assert result.matched_count == 1
    assert session.get(StudentProfile, regular_child.id) is not None


def test_cleanup_execute_deletes_matched_child_data_and_keeps_parent_scoped_rows(session):
    account, parent = seed_parent(session)
    qa_child, qa_essay, _qa_sentence, qa_llm_log = seed_child_graph(
        session, parent, child_id="qa-child", name="QA v0.6b"
    )
    regular_child, _regular_essay, _regular_sentence, _regular_llm_log = seed_child_graph(
        session, parent, child_id="real-child", name="小星"
    )

    result = cleanup_qa_child_profiles(
        session,
        confirm=DELETE_QA_CHILD_PROFILES_CONFIRMATION,
        settings=Settings(environment="development"),
    )

    assert result.deleted_count == 1
    assert result.children[0].student_id == qa_child.id
    assert result.children[0].record_counts["StudentProfile"] == 1
    assert session.get(StudentProfile, qa_child.id) is None
    assert session.get(Essay, qa_essay.id) is None
    assert session.get(LLMCallLog, qa_llm_log.id) is None
    assert session.get(StudentProfile, regular_child.id) is not None
    assert session.get(ParentAccount, account.id) is not None
    assert session.get(ParentUser, parent.id) is not None
    qa_events = session.exec(
        select(ProductEvent).where(ProductEvent.student_id == qa_child.id)
    ).all()
    regular_child_events = session.exec(
        select(ProductEvent).where(ProductEvent.student_id == regular_child.id)
    ).all()
    parent_level_events = session.exec(
        select(ProductEvent).where(ProductEvent.student_id.is_(None))
    ).all()
    assert qa_events == []
    assert len(regular_child_events) == 1
    assert len(parent_level_events) == 2
    assert count_rows(session, ProductEvent) == 3


def test_cleanup_execute_zero_matches_is_noop(session):
    account, parent = seed_parent(session)
    regular_child, _essay, _sentence, _llm_log = seed_child_graph(
        session, parent, child_id="real-child", name="小星"
    )

    result = cleanup_qa_child_profiles(
        session,
        confirm=DELETE_QA_CHILD_PROFILES_CONFIRMATION,
        settings=Settings(environment="test"),
    )

    assert result.deleted_count == 0
    assert session.get(StudentProfile, regular_child.id) is not None
    assert session.get(ParentAccount, account.id) is not None


def test_cleanup_execute_rejects_wrong_confirmation(session):
    _account, parent = seed_parent(session)
    qa_child, _essay, _sentence, _llm_log = seed_child_graph(
        session, parent, child_id="qa-child", name="QA06b-Retest"
    )

    with pytest.raises(QAChildProfileCleanupError, match="confirmation text is required"):
        cleanup_qa_child_profiles(
            session,
            confirm="delete",
            settings=Settings(environment="development"),
        )

    assert session.get(StudentProfile, qa_child.id) is not None


def test_cleanup_execute_rejects_production_environment(session):
    _account, parent = seed_parent(session)
    qa_child, _essay, _sentence, _llm_log = seed_child_graph(
        session, parent, child_id="qa-child", name="QA06b-Happy1"
    )

    with pytest.raises(QAChildProfileCleanupError, match="refusing to execute"):
        cleanup_qa_child_profiles(
            session,
            confirm=DELETE_QA_CHILD_PROFILES_CONFIRMATION,
            settings=Settings(environment="production"),
        )

    assert session.get(StudentProfile, qa_child.id) is not None


def test_detect_cleanup_environment_allows_railway_dev_name():
    detected = detect_cleanup_environment(
        Settings(environment="production"),
        railway_environment_name="Railway-Dev",
    )

    assert detected.environment == "production"
    assert detected.railway_environment_name == "Railway-Dev"
    assert detected.execute_allowed is True


def test_cleanup_execute_rejects_more_than_limit(session):
    _account, parent = seed_parent(session)
    for index in range(31):
        seed_child_graph(
            session,
            parent,
            child_id=f"qa-child-{index}",
            name=f"QA06b-{index:02d}",
        )

    with pytest.raises(QAChildProfileCleanupError, match="matched child count exceeds"):
        cleanup_qa_child_profiles(
            session,
            confirm=DELETE_QA_CHILD_PROFILES_CONFIRMATION,
            settings=Settings(environment="development"),
        )


def test_cleanup_execute_rolls_back_entire_run_on_unexpected_error(session, monkeypatch):
    _account, parent = seed_parent(session)
    first_child, _essay, _sentence, _llm_log = seed_child_graph(
        session, parent, child_id="qa-child-1", name="QA06b-Happy1"
    )
    second_child, _essay2, _sentence2, _llm_log2 = seed_child_graph(
        session, parent, child_id="qa-child-2", name="QA06b-Happy2"
    )

    import app.services.qa_child_profile_cleanup as cleanup_service

    original_delete = cleanup_service._delete_child_rows
    calls = {"count": 0}

    def fail_after_first_child(session, row):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("synthetic cleanup failure")
        return original_delete(session, row)

    monkeypatch.setattr(cleanup_service, "_delete_child_rows", fail_after_first_child)

    with pytest.raises(RuntimeError, match="synthetic cleanup failure"):
        cleanup_qa_child_profiles(
            session,
            confirm=DELETE_QA_CHILD_PROFILES_CONFIRMATION,
            settings=Settings(environment="development"),
        )

    assert session.get(StudentProfile, first_child.id) is not None
    assert session.get(StudentProfile, second_child.id) is not None
