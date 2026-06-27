from dataclasses import dataclass, field
import os
from typing import Any

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
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
    ParentFeedback,
    ProductEvent,
    ReadingSession,
    Report,
    SentenceTraining,
    StudentProfile,
)

DELETE_QA_CHILD_PROFILES_CONFIRMATION = "DELETE QA CHILD PROFILES"
MAX_QA_CHILD_PROFILE_DELETE = 30
QA_CHILD_EXACT_NAMES = {"QA v0.6b"}
QA_CHILD_PREFIXES = ("QA06b-",)
DEV_TEST_ENVIRONMENTS = {"development", "dev", "test"}


class QAChildProfileCleanupError(RuntimeError):
    pass


@dataclass(frozen=True)
class CleanupEnvironment:
    environment: str
    railway_environment_name: str
    execute_allowed: bool


@dataclass
class QAChildProfileCleanupChild:
    student_id: str
    child_name: str
    parent_id: str
    essay_ids: list[str] = field(default_factory=list)
    record_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class QAChildProfileCleanupResult:
    mode: str
    detected_environment: CleanupEnvironment
    children: list[QAChildProfileCleanupChild]

    @property
    def matched_count(self) -> int:
        return len(self.children)

    @property
    def deleted_count(self) -> int:
        if self.mode != "execute":
            return 0
        return len(self.children)


def is_v06b_qa_child_name(name: Any) -> bool:
    normalized = " ".join(str(name or "").split())
    return normalized in QA_CHILD_EXACT_NAMES or normalized.startswith(QA_CHILD_PREFIXES)


def detect_cleanup_environment(
    settings: Settings | None = None,
    railway_environment_name: str | None = None,
) -> CleanupEnvironment:
    resolved_settings = settings or get_settings()
    environment = str(resolved_settings.environment or "").lower()
    railway_name = (
        railway_environment_name
        if railway_environment_name is not None
        else os.getenv("RAILWAY_ENVIRONMENT_NAME", "")
    )
    execute_allowed = environment in DEV_TEST_ENVIRONMENTS or "dev" in railway_name.lower()
    return CleanupEnvironment(
        environment=environment,
        railway_environment_name=railway_name,
        execute_allowed=execute_allowed,
    )


def preview_qa_child_profile_cleanup(
    session: Session,
    settings: Settings | None = None,
    railway_environment_name: str | None = None,
) -> QAChildProfileCleanupResult:
    detected_environment = detect_cleanup_environment(
        settings,
        railway_environment_name=railway_environment_name,
    )
    children = [
        _build_child_preview(session, child) for child in _matched_child_rows(session)
    ]
    return QAChildProfileCleanupResult(
        mode="preview",
        detected_environment=detected_environment,
        children=children,
    )


def cleanup_qa_child_profiles(
    session: Session,
    *,
    confirm: str,
    settings: Settings | None = None,
    railway_environment_name: str | None = None,
    max_children: int = MAX_QA_CHILD_PROFILE_DELETE,
) -> QAChildProfileCleanupResult:
    detected_environment = detect_cleanup_environment(
        settings,
        railway_environment_name=railway_environment_name,
    )
    if not detected_environment.execute_allowed:
        raise QAChildProfileCleanupError("refusing to execute outside a dev/test environment")
    if confirm != DELETE_QA_CHILD_PROFILES_CONFIRMATION:
        raise QAChildProfileCleanupError("confirmation text is required")

    result = preview_qa_child_profile_cleanup(
        session,
        settings=settings,
        railway_environment_name=railway_environment_name,
    )
    if result.matched_count > max_children:
        raise QAChildProfileCleanupError(
            f"matched child count exceeds limit of {max_children}"
        )

    try:
        for row in result.children:
            _delete_child_rows(session, row)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return QAChildProfileCleanupResult(
        mode="execute",
        detected_environment=detected_environment,
        children=result.children,
    )


def _matched_child_rows(session: Session) -> list[StudentProfile]:
    children = session.exec(
        select(StudentProfile).order_by(StudentProfile.created_at, StudentProfile.id)
    ).all()
    return [child for child in children if is_v06b_qa_child_name(child.name)]


def _build_child_preview(
    session: Session,
    child: StudentProfile,
) -> QAChildProfileCleanupChild:
    essay_ids = [
        essay.id
        for essay in session.exec(
            select(Essay).where(Essay.student_id == child.id).order_by(Essay.created_at, Essay.id)
        ).all()
    ]
    return QAChildProfileCleanupChild(
        student_id=child.id,
        child_name=child.name,
        parent_id=child.parent_id,
        essay_ids=essay_ids,
        record_counts=_child_record_counts(session, child.id, essay_ids),
    )


def _child_record_counts(
    session: Session,
    student_id: str,
    essay_ids: list[str],
) -> dict[str, int]:
    essay_id_set = set(essay_ids)
    return {
        "Assessment": _count_where(session, Assessment, Assessment.student_id, student_id),
        "EssayVersion": _count_where_in(
            session,
            EssayVersion,
            EssayVersion.essay_id,
            essay_id_set,
        ),
        "Essay": _count_where(session, Essay, Essay.student_id, student_id),
        "SentenceTraining": _count_where(
            session,
            SentenceTraining,
            SentenceTraining.student_id,
            student_id,
        ),
        "ReadingSession": _count_where(
            session,
            ReadingSession,
            ReadingSession.student_id,
            student_id,
        ),
        "GameEvent": _count_where(session, GameEvent, GameEvent.student_id, student_id),
        "Report": _count_where(session, Report, Report.student_id, student_id),
        "AbilityHistory": _count_where(
            session,
            AbilityHistory,
            AbilityHistory.student_id,
            student_id,
        ),
        "AbilityProfile": _count_where(
            session,
            AbilityProfile,
            AbilityProfile.student_id,
            student_id,
        ),
        "DailyTaskLimitCounter": _count_where(
            session,
            DailyTaskLimitCounter,
            DailyTaskLimitCounter.student_id,
            student_id,
        ),
        "LLMCallLog": _count_where(session, LLMCallLog, LLMCallLog.student_id, student_id),
        "FeedbackReaction": _count_where(
            session,
            FeedbackReaction,
            FeedbackReaction.student_id,
            student_id,
        ),
        "ParentFeedback": _count_where(
            session,
            ParentFeedback,
            ParentFeedback.student_id,
            student_id,
        ),
        "ProductEvent": _count_where(
            session,
            ProductEvent,
            ProductEvent.student_id,
            student_id,
        ),
        "StudentProfile": 1,
    }


def _count_where(session: Session, model, field, value: str) -> int:
    return len(session.exec(select(model).where(field == value)).all())


def _count_where_in(session: Session, model, field, values: set[str]) -> int:
    if not values:
        return 0
    return len(session.exec(select(model).where(field.in_(values))).all())


def _delete_child_rows(session: Session, row: QAChildProfileCleanupChild) -> None:
    student_id = row.student_id
    essay_ids = set(row.essay_ids)

    _delete_where(session, Assessment, Assessment.student_id, student_id)
    _delete_where_in(session, EssayVersion, EssayVersion.essay_id, essay_ids)
    _delete_where(session, Essay, Essay.student_id, student_id)
    _delete_where(session, SentenceTraining, SentenceTraining.student_id, student_id)
    _delete_where(session, ReadingSession, ReadingSession.student_id, student_id)
    _delete_where(session, GameEvent, GameEvent.student_id, student_id)
    _delete_where(session, Report, Report.student_id, student_id)
    _delete_where(session, AbilityHistory, AbilityHistory.student_id, student_id)
    _delete_where(session, AbilityProfile, AbilityProfile.student_id, student_id)
    _delete_where(session, DailyTaskLimitCounter, DailyTaskLimitCounter.student_id, student_id)
    _delete_where(session, LLMCallLog, LLMCallLog.student_id, student_id)
    _delete_where(session, FeedbackReaction, FeedbackReaction.student_id, student_id)
    _delete_where(session, ParentFeedback, ParentFeedback.student_id, student_id)
    _delete_product_events_for_parent_children(session, row.parent_id)

    child = session.get(StudentProfile, student_id)
    if child is not None:
        session.delete(child)
    session.flush()


def _delete_where(session: Session, model, field, value: str) -> int:
    rows = session.exec(select(model).where(field == value)).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def _delete_where_in(session: Session, model, field, values: set[str]) -> int:
    if not values:
        return 0
    rows = session.exec(select(model).where(field.in_(values))).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def _delete_product_events_for_parent_children(session: Session, parent_id: str) -> int:
    rows = session.exec(
        select(ProductEvent).where(
            ProductEvent.parent_id == parent_id,
            ProductEvent.student_id.is_not(None),
        )
    ).all()
    for row in rows:
        session.delete(row)
    return len(rows)
