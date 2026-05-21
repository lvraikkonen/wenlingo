from dataclasses import dataclass

from sqlmodel import Session

from app.core.config import Settings
from app.domain.enums import SentenceFocus, TaskType
from app.domain.models import (
    AbilityProfile,
    Assessment,
    Essay,
    EssayVersion,
    GameEvent,
    LLMCallLog,
    SentenceTraining,
    StudentProfile,
)
from app.services.abilities import VALID_ABILITY_NAMES, apply_ability_delta, to_child_abilities
from app.services.ai_tasks import essay_feedback, sentence_upgrade_feedback
from app.services.essay_workflow import ASSESSMENT_ESSAY_STATUS, draft_ability_deltas
from app.services.gamification import settle_task
from app.services.llm_provider import LLMProvider

ASSESSMENT_SUMMARY = "完成入门小试炼，生成第一张能力草图。"
ASSESSMENT_ESSAY_TITLE = "入门小写作"
SENTENCE_ABILITY_DELTA_FALLBACK = {"expression": 2, "observation": 2}


def _raise_for_provider_failure(log: LLMCallLog | None) -> None:
    if not log or log.validation_ok or not log.error_message:
        return
    errors = [error.strip() for error in log.error_message.split(";") if error.strip()]
    if all(error.startswith("validation error:") for error in errors):
        return
    if log.error_message == "daily limit exceeded":
        return
    raise RuntimeError(log.error_message)


@dataclass(frozen=True)
class EntryAssessmentResult:
    assessment: Assessment
    sentence_training: SentenceTraining
    essay: Essay
    first_draft: EssayVersion
    ability_sketch: dict[str, int]
    settlement: GameEvent


def sentence_assessment_deltas(raw_deltas: dict[str, int]) -> dict[str, int]:
    if any(
        ability_name in VALID_ABILITY_NAMES and raw_delta > 0
        for ability_name, raw_delta in raw_deltas.items()
    ):
        return raw_deltas
    return SENTENCE_ABILITY_DELTA_FALLBACK


async def complete_entry_assessment(
    *,
    session: Session,
    student: StudentProfile,
    ability: AbilityProfile,
    provider: LLMProvider,
    settings: Settings,
    sentence_before: str,
    sentence_after: str,
    short_writing: str,
) -> EntryAssessmentResult:
    focus = SentenceFocus.detail.value
    sentence_result = await sentence_upgrade_feedback(
        provider=provider,
        source_sentence=sentence_before,
        upgraded_sentence=sentence_after,
        focus=focus,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=student.id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
    sentence_feedback = sentence_result.output
    _raise_for_provider_failure(sentence_result.log)
    training = SentenceTraining(
        student_id=student.id,
        source_sentence=sentence_before,
        upgraded_sentence=sentence_after,
        focus=focus,
        ai_feedback=sentence_feedback.model_dump(),
    )
    session.add(training)
    session.flush()

    apply_ability_delta(
        session,
        ability,
        sentence_assessment_deltas(sentence_feedback.ability_delta),
        TaskType.sentence,
        training.id,
    )

    essay_result = await essay_feedback(
        provider=provider,
        title=ASSESSMENT_ESSAY_TITLE,
        draft=short_writing,
        session=session,
        prompt_version=settings.llm_prompt_version,
        student_id=student.id,
        daily_limit_enabled=settings.llm_daily_limit_enabled,
        daily_limit_per_student_task=settings.llm_daily_limit_per_student_task,
    )
    essay_output = essay_result.output
    _raise_for_provider_failure(essay_result.log)
    essay = Essay(
        student_id=student.id,
        title=ASSESSMENT_ESSAY_TITLE,
        status=ASSESSMENT_ESSAY_STATUS,
    )
    session.add(essay)
    session.flush()

    first_draft = EssayVersion(
        essay_id=essay.id,
        version_label="first_draft",
        content=short_writing,
        ai_feedback=essay_output.model_dump(),
        llm_call_log_id=essay_result.log.id if essay_result.log else None,
    )
    session.add(first_draft)
    session.flush()

    apply_ability_delta(
        session,
        ability,
        draft_ability_deltas(len(essay_output.improvements)),
        TaskType.essay,
        first_draft.id,
    )

    assessment = Assessment(
        student_id=student.id,
        sentence_before=sentence_before,
        sentence_after=sentence_after,
        short_writing=short_writing,
        summary=ASSESSMENT_SUMMARY,
        sentence_training_id=training.id,
        essay_id=essay.id,
    )
    session.add(assessment)
    session.flush()

    settlement = settle_task(
        student,
        TaskType.assessment,
        [],
        {
            "summary": ASSESSMENT_SUMMARY,
            "sentence_training_id": training.id,
            "essay_id": essay.id,
        },
    )
    session.add(student)
    session.add(ability)
    session.add(settlement)

    return EntryAssessmentResult(
        assessment=assessment,
        sentence_training=training,
        essay=essay,
        first_draft=first_draft,
        ability_sketch=to_child_abilities(ability),
        settlement=settlement,
    )
