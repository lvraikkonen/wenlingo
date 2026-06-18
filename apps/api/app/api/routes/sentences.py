from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.auth_deps import (
    ParentContext,
    require_auth_mode_state_change,
    require_student_for_auth_mode,
)
from app.api.deps import AITaskRunner, get_ai_task_runner, get_db_session
from app.api.feedback_state import feedback_reaction_value
from app.api.routes.alpha import record_product_event
from app.core.config import Settings, get_settings
from app.domain.enums import SentenceFocus, TaskType
from app.domain.models import AbilityProfile, SentenceTraining, utcnow
from app.services.abilities import VALID_ABILITY_NAMES, apply_ability_delta
from app.services.ai_tasks import (
    sentence_challenge_feedback,
    sentence_challenge_generation,
    sentence_upgrade_feedback,
)
from app.services.gamification import settle_task
from app.services.recommendations import choose_today_tasks
from app.services.sentence_challenges import (
    CHALLENGE_TYPE_SPECS,
    deterministic_challenge_ability_delta,
)

router = APIRouter(prefix="/api/students", tags=["sentences"])

SENTENCE_ABILITY_DELTA_FALLBACK = {"expression": 2, "observation": 2}
DAILY_LIMIT_ERROR_MESSAGES = {"daily limit exceeded", "daily limit reached"}
CHALLENGE_TARGET_SKILL_CYCLE = ("expand_sentence", "action_expression", "feeling")
CHALLENGE_LIMIT_MESSAGE = "今天的句子挑战已经完成很多啦，休息一下，明天继续闯关！"


class SentenceTrainingCreate(BaseModel):
    source_sentence: str = Field(min_length=1, max_length=500)
    upgraded_sentence: str = Field(min_length=1, max_length=500)
    focus: SentenceFocus


class SentenceChallengeGenerate(BaseModel):
    pass


class SentenceChallengeComplete(BaseModel):
    upgraded_sentence: str = Field(min_length=5, max_length=120)


class ChallengeLimitExceeded(HTTPException):
    def __init__(self):
        super().__init__(status_code=429, detail=CHALLENGE_LIMIT_MESSAGE)


def _is_ai_feedback_failure(log) -> bool:
    return bool(
        log
        and log.validation_ok is False
        and log.error_message
        and log.error_message not in DAILY_LIMIT_ERROR_MESSAGES
    )


def _challenge_payload(training, challenge) -> dict:
    return {
        "id": training.id,
        "source_sentence": challenge.source_sentence,
        "challenge_prompt": challenge.challenge_prompt,
        "hint": challenge.hint,
        "target_skill": challenge.target_skill,
        "focus": challenge.focus,
        "difficulty_label": challenge.difficulty_label,
        "grade_label": challenge.grade_label,
    }


def choose_challenge_target_skill(session: Session, student_id: str) -> str:
    completed_count = len(
        session.exec(
            select(SentenceTraining).where(
                SentenceTraining.student_id == student_id,
                SentenceTraining.status == "completed",
                SentenceTraining.target_skill != "",
            )
        ).all()
    )
    return CHALLENGE_TARGET_SKILL_CYCLE[
        completed_count % len(CHALLENGE_TARGET_SKILL_CYCLE)
    ]


def _challenge_event_payload(
    training: SentenceTraining | None,
    task_type: str,
    status: str,
    target_skill: str | None = None,
    limit_type: str | None = None,
    error_category: str | None = None,
) -> dict:
    payload = {
        "target_type": "sentence_training" if training else "student",
        "target_id": training.id if training else None,
        "task_type": task_type,
        "status": status,
    }
    if target_skill:
        payload["target_skill"] = target_skill
    if limit_type:
        payload["limit_type"] = limit_type
    if error_category:
        payload["error_category"] = error_category
    return payload


@router.post(
    "/{student_id}/sentence-challenges",
    status_code=201,
)
async def create_sentence_challenge(
    student_id: str,
    _request: SentenceChallengeGenerate,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).first()
    if not ability:
        raise HTTPException(status_code=404, detail="student not found")

    target_skill = choose_challenge_target_skill(session, student.id)
    result = await sentence_challenge_generation(
        runner=runner,
        target_skill=target_skill,
        grade_label=student.grade_label,
        session=session,
        student_id=student.id,
        daily_limit=settings.sentence_challenge_daily_limit_per_student,
    )
    challenge = result.output
    if result.status == "daily_limit_reached":
        record_product_event(
            session,
            "ai_daily_limit_reached",
            parent_id=student.parent_id,
            student_id=student.id,
            payload={
                "target_type": "student",
                "target_id": student.id,
                "task_type": "sentence_challenge_generation",
                "limit_type": "daily_per_student",
                "status": "blocked",
            },
        )
        session.commit()
        raise ChallengeLimitExceeded()

    training = SentenceTraining(
        student_id=student.id,
        source_sentence=challenge.source_sentence,
        upgraded_sentence="",
        focus=challenge.focus,
        ai_feedback={},
        status="generated",
        challenge_prompt=challenge.challenge_prompt,
        hint=challenge.hint,
        target_skill=challenge.target_skill,
    )
    session.add(training)
    session.flush()
    record_product_event(
        session,
        "sentence_challenge_generated",
        parent_id=student.parent_id,
        student_id=student.id,
        payload=_challenge_event_payload(
            training,
            "sentence_challenge_generation",
            "generated",
            challenge.target_skill,
        ),
    )
    payload = _challenge_payload(training, challenge)
    session.commit()
    return {"challenge": payload}


@router.post(
    "/{student_id}/sentences/{training_id}/complete",
)
async def complete_sentence_challenge(
    student_id: str,
    training_id: str,
    request: SentenceChallengeComplete,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    training = session.get(SentenceTraining, training_id)
    if not training or training.student_id != student.id:
        raise HTTPException(status_code=404, detail="sentence training not found")
    if training.status == "completed":
        raise HTTPException(status_code=409, detail="sentence challenge already completed")
    if (
        training.status != "generated"
        or not training.challenge_prompt
        or training.target_skill not in CHALLENGE_TYPE_SPECS
    ):
        raise HTTPException(status_code=404, detail="sentence training not found")

    feedback_result = await sentence_challenge_feedback(
        runner=runner,
        source_sentence=training.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        target_skill=training.target_skill,
        session=session,
        student_id=student.id,
        daily_limit=settings.sentence_feedback_daily_limit_per_student,
    )
    feedback = feedback_result.output
    if feedback_result.status == "daily_limit_reached":
        record_product_event(
            session,
            "ai_daily_limit_reached",
            parent_id=student.parent_id,
            student_id=student.id,
            payload=_challenge_event_payload(
                training,
                "sentence_challenge_feedback",
                "blocked",
                training.target_skill,
                limit_type="daily_per_student",
            ),
        )
    elif _is_ai_feedback_failure(feedback_result.log):
        record_product_event(
            session,
            "sentence_challenge_feedback_failed",
            parent_id=student.parent_id,
            student_id=student.id,
            payload=_challenge_event_payload(
                training,
                "sentence_challenge_feedback",
                "fallback",
                training.target_skill,
                error_category="exception",
            ),
        )

    training.upgraded_sentence = request.upgraded_sentence
    training.ai_feedback = feedback.model_dump()
    training.status = "completed"
    training.completed_at = utcnow()
    session.add(training)

    ability = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).first()
    if not ability:
        raise HTTPException(status_code=404, detail="student not found")
    ability_deltas = deterministic_challenge_ability_delta(training.target_skill)
    apply_ability_delta(session, ability, ability_deltas, TaskType.sentence, training.id)
    event = settle_task(student, TaskType.sentence, [], {"focus": training.focus})
    session.add(ability)
    session.add(student)
    session.add(event)
    record_product_event(
        session,
        "sentence_challenge_completed",
        parent_id=student.parent_id,
        student_id=student.id,
        payload=_challenge_event_payload(
            training,
            "sentence_challenge_feedback",
            "completed",
            training.target_skill,
        ),
    )
    training_payload = training.model_dump()
    training_payload["reaction"] = feedback_reaction_value(
        session,
        student.id,
        "sentence_training",
        training.id,
    )
    settlement_payload = event.model_dump()
    session.commit()
    return {
        "training": training_payload,
        "feedback": feedback,
        "settlement": settlement_payload,
        "next_task": choose_today_tasks(ability).main.model_dump(),
    }


@router.post(
    "/{student_id}/sentences",
    status_code=201,
)
async def create_sentence_training(
    student_id: str,
    request: SentenceTrainingCreate,
    session: Session = Depends(get_db_session),
    runner: AITaskRunner = Depends(get_ai_task_runner),
    settings: Settings = Depends(get_settings),
    context: ParentContext | None = Depends(require_auth_mode_state_change),
):
    student = require_student_for_auth_mode(session, settings, context, student_id)
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
        raise HTTPException(status_code=404, detail="student not found")
    focus = request.focus.value
    try:
        feedback_result = await sentence_upgrade_feedback(
            runner=runner,
            source_sentence=request.source_sentence,
            upgraded_sentence=request.upgraded_sentence,
            focus=focus,
            session=session,
            prompt_version=settings.llm_prompt_version,
            student_id=student_id,
        )
    except Exception:
        session.rollback()
        try:
            record_product_event(
                session,
                "ai_feedback_failed",
                parent_id=student.parent_id,
                student_id=student.id,
                payload={"task_type": "sentence", "error_category": "exception"},
            )
            session.commit()
        except Exception:
            session.rollback()
        raise
    feedback = feedback_result.output
    if _is_ai_feedback_failure(feedback_result.log):
        try:
            record_product_event(
                session,
                "ai_feedback_failed",
                parent_id=student.parent_id,
                student_id=student.id,
                payload={"task_type": "sentence", "error_category": "exception"},
            )
        except Exception:
            pass
    training = SentenceTraining(
        student_id=student_id,
        source_sentence=request.source_sentence,
        upgraded_sentence=request.upgraded_sentence,
        focus=focus,
        ai_feedback=feedback.model_dump(),
        status="completed",
    )
    session.add(training)
    session.flush()
    try:
        record_product_event(
            session,
            "sentence_training_completed",
            parent_id=student.parent_id,
            student_id=student.id,
            payload={
                "target_type": "sentence_training",
                "target_id": training.id,
                "task_type": "sentence",
                "status": "completed",
            },
        )
    except Exception:
        pass
    ability_deltas = feedback.ability_delta
    if not any(
        ability_name in VALID_ABILITY_NAMES and raw_delta > 0
        for ability_name, raw_delta in ability_deltas.items()
    ):
        ability_deltas = SENTENCE_ABILITY_DELTA_FALLBACK
    apply_ability_delta(session, ability, ability_deltas, TaskType.sentence, training.id)
    event = settle_task(student, TaskType.sentence, feedback.problem_monsters, {"focus": focus})
    session.add(ability)
    session.add(student)
    session.add(event)
    training_payload = training.model_dump()
    training_payload["reaction"] = feedback_reaction_value(
        session,
        student.id,
        "sentence_training",
        training.id,
    )
    settlement_payload = event.model_dump()
    session.commit()
    return {
        "training": training_payload,
        "feedback": feedback,
        "settlement": settlement_payload,
        "next_task": choose_today_tasks(ability).main.model_dump(),
    }
