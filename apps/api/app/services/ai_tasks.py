import html
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.prompts.registry import PromptSpec, get_prompt
from app.services.llm_contracts import (
    EssayFeedback,
    EssayRevisionComparison,
    GhostwritingCheck,
    SentenceChallenge,
    SentenceChallengeFeedback,
    SentenceFeedback,
)
from app.services.llm_provider import LLMProvider
from app.services.llm_usage import llm_daily_limit_reached
from app.services.sentence_challenges import fallback_challenge, fallback_challenge_feedback


T = TypeVar("T", bound=BaseModel)
MAX_LLM_ATTEMPTS = 2
LEGACY_DEFAULT_PROMPT_VERSION = "v0.2-quality-spine-2026-05-14"


@dataclass(frozen=True)
class LLMTaskResult(Generic[T]):
    output: T
    log: LLMCallLog | None
    status: str = "ok"


GHOSTWRITING_TRIGGERS = [
    "帮我写",
    "直接写",
    "生成一篇",
    "写完整作文",
    "范文",
]

GHOSTWRITING_INTENT_PATTERNS = [
    "替我写作文",
    "替我写一篇作文",
    "给我写作文",
    "给我写一篇作文",
    "帮我写作文",
    "帮我写一篇作文",
    "帮我生成作文",
    "生成作文",
    "生成一篇作文",
    "写一篇作文",
    "写一篇关于",
    "写作文",
]

GHOSTWRITING_INTENT_REGEXES = [
    re.compile(r"(替我|给我|帮我)?写一篇.+作文"),
]


def _normalize_request(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


def _wrap_student_payload(tag: str, value: str) -> str:
    return f"<{tag}>{html.escape(value, quote=False)}</{tag}>"


def convert_ghostwriting_request(text: str) -> GhostwritingCheck:
    normalized_text = _normalize_request(text)
    blocked = any(_normalize_request(trigger) in normalized_text for trigger in GHOSTWRITING_TRIGGERS)
    blocked = blocked or any(pattern in normalized_text for pattern in GHOSTWRITING_INTENT_PATTERNS)
    blocked = blocked or any(pattern.search(normalized_text) for pattern in GHOSTWRITING_INTENT_REGEXES)
    if not blocked:
        return GhostwritingCheck(blocked=False, message="", next_question="")
    return GhostwritingCheck(
        blocked=True,
        message="我不能替你写完整作文，但可以帮你想一想这件事里最值得写的画面。",
        next_question="这件事里最值得写的一个画面是什么？",
    )


def log_llm_result(
    session: Session,
    student_id: str | None,
    task_type: TaskType,
    task_name: str,
    provider: str,
    model: str,
    prompt_version: str,
    input_summary: str,
    raw_response: str,
    output_json: dict,
    validation_ok: bool,
    error_message: str,
    retry_count: int,
    prompt_key: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    estimated_cost: float = 0.0,
    latency_ms: int = 0,
) -> LLMCallLog:
    log = LLMCallLog(
        student_id=student_id,
        task_type=task_type,
        task_name=task_name,
        prompt_key=prompt_key or task_name,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        input_summary=input_summary,
        raw_response=raw_response,
        output_json=output_json,
        validation_ok=validation_ok,
        error_message=error_message,
        retry_count=retry_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
    )
    session.add(log)
    session.flush()
    return log


def fallback_essay_feedback() -> EssayFeedback:
    return EssayFeedback(
        strengths=["你已经完成了一版初稿", "你愿意继续修改，这很重要"],
        improvements=["先选择一段，把看到的画面或动作补清楚"],
        problem_monsters=["细节缺口"],
        sentence_notes=["把“很开心”“很害怕”换成看得见的动作、声音或表情。"],
        revision_tasks=[
            {
                "instruction": "先给最重要的一段加一个动作或看到的细节",
                "target": "你觉得最想改好的那一段",
            }
        ],
    )


def fallback_revision_comparison() -> EssayRevisionComparison:
    return EssayRevisionComparison(
        encouragement="你完成了二稿，这一步本身就很值得肯定。",
        improved_dimensions=["完成了一次修改"],
        evidence=["你提交了新的二稿内容"],
        next_step="下一次可以继续挑一段，把动作、声音或心情写得更具体。",
    )


def fallback_sentence_feedback() -> SentenceFeedback:
    return SentenceFeedback(
        encouragement="你已经完成了一次句子升级。",
        specific_improvement="先把一个看得见的细节写清楚",
        next_step="再读一遍你的句子，圈出一个动作、声音或颜色细节。",
        ability_delta={"expression": 2, "observation": 2},
        problem_monsters=["空泛表达"],
    )


def _effective_prompt_version(prompt: PromptSpec, requested_version: str) -> str:
    if requested_version == LEGACY_DEFAULT_PROMPT_VERSION:
        return prompt.version
    return requested_version


def _token_count(usage: dict[str, int] | None, key: str) -> int:
    if not usage:
        return 0
    return int(usage.get(key) or 0)


def estimate_llm_cost(
    prompt_tokens: int,
    completion_tokens: int,
    input_cost_per_1k: float,
    output_cost_per_1k: float,
) -> float:
    return (prompt_tokens / 1000 * input_cost_per_1k) + (
        completion_tokens / 1000 * output_cost_per_1k
    )


async def run_validated_llm_task(
    *,
    provider: LLMProvider,
    session: Session | None,
    student_id: str | None = None,
    task_type: TaskType,
    task_name: str,
    payload: dict,
    output_model: type[T],
    fallback: T,
    input_summary: str,
    prompt_version: str,
    prompt_key: str | None = None,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
    daily_limit_timezone: str = "Asia/Shanghai",
) -> LLMTaskResult[T]:
    errors: list[str] = []
    raw_response = ""
    provider_name = getattr(provider, "provider_name", provider.__class__.__name__)
    model_name = getattr(provider, "model_name", "unknown")
    latest_response_provider = provider_name
    latest_response_model = model_name

    if (
        session is not None
        and student_id is not None
        and daily_limit_enabled
        and llm_daily_limit_reached(
            session=session,
            student_id=student_id,
            task_name=task_name,
            provider_name=provider_name,
            limit=daily_limit_per_student_task,
            timezone_name=daily_limit_timezone,
        )
    ):
        log = log_llm_result(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=prompt_key or task_name,
            provider="local_fallback",
            model="local_fallback",
            prompt_version=prompt_version,
            input_summary=input_summary,
            raw_response="",
            output_json=fallback.model_dump(),
            validation_ok=False,
            error_message="daily limit reached",
            retry_count=0,
        )
        return LLMTaskResult(output=fallback, log=log, status="daily_limit_reached")

    for attempt_index in range(MAX_LLM_ATTEMPTS):
        try:
            started_at = perf_counter()
            response = await provider.complete_json(task_name, payload)
            latency_ms = int((perf_counter() - started_at) * 1000)
            prompt_tokens = _token_count(response.usage, "prompt_tokens")
            completion_tokens = _token_count(response.usage, "completion_tokens")
            total_tokens = _token_count(response.usage, "total_tokens")
            estimated_cost = estimate_llm_cost(
                prompt_tokens,
                completion_tokens,
                input_cost_per_1k_tokens,
                output_cost_per_1k_tokens,
            )
            raw_response = response.raw_response
            latest_response_provider = response.provider
            latest_response_model = response.model
            output = output_model.model_validate(response.parsed_json)
            log = None
            if session is not None:
                log = log_llm_result(
                    session=session,
                    student_id=student_id,
                    task_type=task_type,
                    task_name=task_name,
                    prompt_key=prompt_key or task_name,
                    provider=response.provider,
                    model=response.model,
                    prompt_version=prompt_version,
                    input_summary=input_summary,
                    raw_response=response.raw_response,
                    output_json=output.model_dump(),
                    validation_ok=True,
                    error_message="",
                    retry_count=attempt_index,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=estimated_cost,
                    latency_ms=latency_ms,
                )
            return LLMTaskResult(output=output, log=log)
        except ValidationError as exc:
            errors.append(f"validation error: {exc}")
        except Exception as exc:
            errors.append(str(exc))

    log = None
    if session is not None:
        log = log_llm_result(
            session=session,
            student_id=student_id,
            task_type=task_type,
            task_name=task_name,
            prompt_key=prompt_key or task_name,
            provider=latest_response_provider,
            model=latest_response_model,
            prompt_version=prompt_version,
            input_summary=input_summary,
            raw_response=raw_response,
            output_json=fallback.model_dump(),
            validation_ok=False,
            error_message="; ".join(errors),
            retry_count=MAX_LLM_ATTEMPTS - 1,
        )
    return LLMTaskResult(output=fallback, log=log, status="fallback")


async def sentence_upgrade_feedback(
    provider: LLMProvider,
    source_sentence: str,
    upgraded_sentence: str,
    focus: str,
    session: Session | None = None,
    prompt_version: str = LEGACY_DEFAULT_PROMPT_VERSION,
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
    daily_limit_timezone: str = "Asia/Shanghai",
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
) -> LLMTaskResult[SentenceFeedback]:
    prompt = get_prompt("sentence_upgrade_feedback")
    return await run_validated_llm_task(
        provider=provider,
        session=session,
        task_type=TaskType.sentence,
        task_name=prompt.prompt_key,
        payload={
            "source_sentence": _wrap_student_payload("student_sentence", source_sentence),
            "upgraded_sentence": _wrap_student_payload("student_sentence", upgraded_sentence),
            "focus": focus,
        },
        output_model=SentenceFeedback,
        fallback=fallback_sentence_feedback(),
        input_summary=(
            f"句子快练；原句长度：{len(source_sentence)}；"
            f"升级句长度：{len(upgraded_sentence)}；目标：{focus}"
        ),
        prompt_version=_effective_prompt_version(prompt, prompt_version),
        prompt_key=prompt.prompt_key,
        student_id=student_id,
        daily_limit_enabled=daily_limit_enabled,
        daily_limit_per_student_task=daily_limit_per_student_task,
        daily_limit_timezone=daily_limit_timezone,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )


async def sentence_challenge_generation(
    provider: LLMProvider,
    target_skill: str,
    grade_label: str,
    session: Session | None = None,
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 10,
    daily_limit_timezone: str = "Asia/Shanghai",
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
) -> LLMTaskResult[SentenceChallenge]:
    prompt = get_prompt("sentence_challenge_generation")
    return await run_validated_llm_task(
        provider=provider,
        session=session,
        student_id=student_id,
        task_type=TaskType.sentence,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={"target_skill": target_skill, "grade_label": grade_label},
        output_model=SentenceChallenge,
        fallback=fallback_challenge(target_skill),
        input_summary=f"句子挑战生成；年级：{grade_label}；目标：{target_skill}",
        prompt_version=prompt.version,
        daily_limit_enabled=daily_limit_enabled,
        daily_limit_per_student_task=daily_limit_per_student_task,
        daily_limit_timezone=daily_limit_timezone,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )


async def sentence_challenge_feedback(
    provider: LLMProvider,
    target_skill: str,
    source_sentence: str,
    upgraded_sentence: str,
    session: Session | None = None,
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 10,
    daily_limit_timezone: str = "Asia/Shanghai",
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
) -> LLMTaskResult[SentenceChallengeFeedback]:
    prompt = get_prompt("sentence_challenge_feedback")
    return await run_validated_llm_task(
        provider=provider,
        session=session,
        student_id=student_id,
        task_type=TaskType.sentence,
        task_name=prompt.prompt_key,
        prompt_key=prompt.prompt_key,
        payload={
            "target_skill": target_skill,
            "source_sentence": _wrap_student_payload("student_sentence", source_sentence),
            "upgraded_sentence": _wrap_student_payload("student_sentence", upgraded_sentence),
        },
        output_model=SentenceChallengeFeedback,
        fallback=fallback_challenge_feedback(target_skill),
        input_summary=(
            f"句子挑战反馈；目标：{target_skill}；"
            f"原句长度：{len(source_sentence)}；升级句长度：{len(upgraded_sentence)}"
        ),
        prompt_version=prompt.version,
        daily_limit_enabled=daily_limit_enabled,
        daily_limit_per_student_task=daily_limit_per_student_task,
        daily_limit_timezone=daily_limit_timezone,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )


async def essay_feedback(
    provider: LLMProvider,
    title: str,
    draft: str,
    session: Session | None = None,
    prompt_version: str = LEGACY_DEFAULT_PROMPT_VERSION,
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
    daily_limit_timezone: str = "Asia/Shanghai",
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
) -> LLMTaskResult[EssayFeedback]:
    ghostwriting = convert_ghostwriting_request(draft)
    if ghostwriting.blocked:
        raise ValueError(ghostwriting.message)
    prompt = get_prompt("essay_feedback")
    return await run_validated_llm_task(
        provider=provider,
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        payload={
            "title": _wrap_student_payload("student_title", title),
            "draft": _wrap_student_payload("student_draft", draft),
        },
        output_model=EssayFeedback,
        fallback=fallback_essay_feedback(),
        input_summary=f"作文题目：{title}；初稿长度：{len(draft)}",
        prompt_version=_effective_prompt_version(prompt, prompt_version),
        prompt_key=prompt.prompt_key,
        daily_limit_enabled=daily_limit_enabled,
        daily_limit_per_student_task=daily_limit_per_student_task,
        daily_limit_timezone=daily_limit_timezone,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )


async def essay_revision_comparison(
    provider: LLMProvider,
    first_draft: str,
    revision: str,
    session: Session | None = None,
    prompt_version: str = LEGACY_DEFAULT_PROMPT_VERSION,
    student_id: str | None = None,
    daily_limit_enabled: bool = False,
    daily_limit_per_student_task: int = 5,
    daily_limit_timezone: str = "Asia/Shanghai",
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
) -> LLMTaskResult[EssayRevisionComparison]:
    prompt = get_prompt("essay_revision_comparison")
    return await run_validated_llm_task(
        provider=provider,
        session=session,
        student_id=student_id,
        task_type=TaskType.essay,
        task_name=prompt.prompt_key,
        payload={
            "first_draft": _wrap_student_payload("student_first_draft", first_draft),
            "revision": _wrap_student_payload("student_revision", revision),
        },
        output_model=EssayRevisionComparison,
        fallback=fallback_revision_comparison(),
        input_summary=f"二稿对比；初稿长度：{len(first_draft)}；二稿长度：{len(revision)}",
        prompt_version=_effective_prompt_version(prompt, prompt_version),
        prompt_key=prompt.prompt_key,
        daily_limit_enabled=daily_limit_enabled,
        daily_limit_per_student_task=daily_limit_per_student_task,
        daily_limit_timezone=daily_limit_timezone,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
    )
