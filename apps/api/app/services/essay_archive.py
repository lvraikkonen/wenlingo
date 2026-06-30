from typing import Any

from sqlmodel import Session, select

from app.domain.models import Essay, EssayRevisionAttempt, EssayVersion


CANONICAL_TOPIC_ORIGINS = {"teacher_provided", "ai_topic_idea", "direct_draft"}
ASSESSMENT_STATUSES = {"assessment_completed", "assessment_feedback", "assessment_settled"}


def get_version_label_for_round(round_index: int) -> str:
    if round_index < 1:
        raise ValueError("round_index must be positive")
    if round_index == 1:
        return "first_draft"
    if round_index == 2:
        return "revision"
    return f"revision_round_{round_index}"


def get_round_index(version: EssayVersion) -> int:
    if version.round_index is not None:
        if version.round_index < 1:
            raise ValueError("round_index must be positive")
        return version.round_index
    if version.version_label == "first_draft":
        return 1
    if version.version_label == "revision":
        return 2
    if version.version_label.startswith("revision_round_"):
        round_suffix = version.version_label.removeprefix("revision_round_")
        if not round_suffix.isdecimal():
            raise ValueError(f"unknown essay version label: {version.version_label}")
        round_index = int(round_suffix)
        if round_index < 1:
            raise ValueError("round_index must be positive")
        return round_index
    raise ValueError(f"unknown essay version label: {version.version_label}")


def latest_essay_version(session: Session, essay_id: str) -> EssayVersion | None:
    """Return highest round_index version, falling back to legacy labels."""
    versions = ordered_essay_versions(session, essay_id)
    if not versions:
        return None
    return versions[-1]


def ordered_essay_versions(session: Session, essay_id: str) -> list[EssayVersion]:
    """Return versions ordered by derived round index ascending."""
    versions = list(
        session.exec(select(EssayVersion).where(EssayVersion.essay_id == essay_id)).all()
    )
    return sorted(
        versions, key=lambda version: (get_round_index(version), version.created_at, version.id)
    )


def failed_attempt_for_latest(
    session: Session,
    essay: Essay,
    latest: EssayVersion | None,
) -> EssayRevisionAttempt | None:
    """Return the newest comparison_failed attempt whose base_version_id is latest.id."""
    if latest is None:
        return None
    attempts = session.exec(
        select(EssayRevisionAttempt).where(
            EssayRevisionAttempt.essay_id == essay.id,
            EssayRevisionAttempt.base_version_id == latest.id,
            EssayRevisionAttempt.status == "comparison_failed",
        )
    ).all()
    if not attempts:
        return None
    return sorted(
        attempts, key=lambda attempt: (attempt.updated_at, attempt.created_at, attempt.id)
    )[-1]


def derive_archive_status(
    essay: Essay,
    versions: list[EssayVersion],
    failed_attempt: EssayRevisionAttempt | None,
    *,
    parent_visible: bool,
) -> str:
    """Return hidden_by_child, needs_retry, needs_revision, revised_once, multi_round_revision, or not_archived."""
    if parent_visible and essay.hidden_by == "child":
        return "hidden_by_child"
    if not _has_first_draft_round(versions):
        return "not_archived"
    if failed_attempt is not None:
        return "needs_retry"

    latest_round_index = get_round_index(versions[-1])
    if latest_round_index <= 1:
        return "needs_revision"
    if latest_round_index == 2:
        return "revised_once"
    return "multi_round_revision"


def can_continue_revision(
    essay: Essay,
    versions: list[EssayVersion],
    *,
    child_surface: bool,
) -> bool:
    """Return true for visible non-assessment essays with at least round 1."""
    if not child_surface:
        return False
    if essay.hidden_by:
        return False
    if essay.status in ASSESSMENT_STATUSES or essay.status.startswith("assessment_"):
        return False
    return _has_first_draft_round(versions)


def can_retry_revision_attempt(
    failed_attempt: EssayRevisionAttempt | None,
    latest: EssayVersion | None,
) -> bool:
    """Return true when failed_attempt.base_version_id equals latest.id."""
    return (
        failed_attempt is not None
        and latest is not None
        and failed_attempt.base_version_id == latest.id
    )


def topic_metadata_from_essay(essay: Essay) -> dict[str, Any]:
    """Extract topic_origin, topic_type, topic_variant, template version, and generated-topic metadata."""
    outline = essay.outline if isinstance(essay.outline, dict) else {}
    material_card = essay.material_card if isinstance(essay.material_card, dict) else {}
    scaffold = outline.get("scaffold")
    if not isinstance(scaffold, dict):
        scaffold = {}
    scaffold_ref = material_card.get("scaffold_ref")
    if not isinstance(scaffold_ref, dict):
        scaffold_ref = {}

    topic_origin = str(outline.get("topic_origin") or "teacher_provided")
    if topic_origin not in CANONICAL_TOPIC_ORIGINS:
        topic_origin = "teacher_provided"

    selected_topic_idea = outline.get("selected_topic_idea")
    if not isinstance(selected_topic_idea, dict):
        selected_topic_idea = None
    generated_topic_metadata = outline.get("generated_topic_metadata")
    if not isinstance(generated_topic_metadata, dict):
        generated_topic_metadata = selected_topic_idea

    return {
        "topic_origin": topic_origin,
        "topic_type": scaffold.get("topic_type") or scaffold_ref.get("topic_type") or "",
        "topic_variant": scaffold.get("topic_variant") or scaffold_ref.get("topic_variant") or "",
        "scaffold_template_version": (
            scaffold.get("scaffold_template_version")
            or scaffold_ref.get("scaffold_template_version")
            or ""
        ),
        "selected_topic_idea": selected_topic_idea,
        "generated_topic_metadata": generated_topic_metadata,
    }


def build_archive_item(
    session: Session,
    essay: Essay,
    *,
    parent_visible: bool,
    child_surface: bool,
) -> dict[str, Any]:
    """Build the list-item payload returned by child and parent archive endpoints."""
    versions = ordered_essay_versions(session, essay.id)
    latest = versions[-1] if versions else None
    failed_attempt = failed_attempt_for_latest(session, essay, latest)
    status = derive_archive_status(
        essay,
        versions,
        failed_attempt,
        parent_visible=parent_visible,
    )
    retry_allowed = can_retry_revision_attempt(failed_attempt, latest)
    continue_allowed = can_continue_revision(essay, versions, child_surface=child_surface)
    if status in {"hidden_by_child", "not_archived"}:
        retry_allowed = False
        continue_allowed = False

    latest_round_index = get_round_index(latest) if latest is not None else None
    item = {
        "essay_id": essay.id,
        "title": essay.title,
        "status": status,
        "hidden": bool(essay.hidden_by),
        "hidden_by": essay.hidden_by,
        "hidden_at": essay.hidden_at,
        "latest_round_index": latest_round_index,
        "latest_version_id": latest.id if latest is not None else None,
        "last_version_submitted_at": essay.last_version_submitted_at,
        "revision_round_count": max((latest_round_index or 0) - 1, 0),
        "needs_revision": status in {"needs_revision", "needs_retry"},
        "can_continue_revision": continue_allowed,
        "can_retry_revision_attempt": retry_allowed,
        "summary_label": _summary_label_for_status(status, latest_round_index),
    }
    item.update(topic_metadata_from_essay(essay))
    return item


def build_archive_detail(
    session: Session,
    essay: Essay,
    *,
    parent_visible: bool,
    child_surface: bool,
) -> dict[str, Any]:
    """Build timeline, continue_revision, retry state, topic metadata, and parent summary payload."""
    versions = ordered_essay_versions(session, essay.id)
    latest = versions[-1] if versions else None
    failed_attempt = failed_attempt_for_latest(session, essay, latest)
    item = build_archive_item(
        session,
        essay,
        parent_visible=parent_visible,
        child_surface=child_surface,
    )
    status = item["status"]

    detail = {
        **item,
        "visibility": {
            "hidden": item["hidden"],
            "hidden_by": item["hidden_by"],
            "hidden_at": item["hidden_at"],
            "visibility_changed_at": essay.visibility_changed_at,
        },
        "versions": [_version_payload(version) for version in versions],
        "revision_attempt": _revision_attempt_payload(failed_attempt, latest),
        "continue_revision": None,
        "parent_summary": _parent_summary_payload(item, versions),
    }
    if latest is not None and item["can_continue_revision"]:
        detail["continue_revision"] = {
            "latest_version_id": latest.id,
            "latest_content": latest.content,
            "previous_ai_guidance": _continue_revision_guidance(
                status, latest, versions, failed_attempt
            ),
            "next_round_index": get_round_index(latest) + 1,
        }
    return detail


def _summary_label_for_status(status: str, latest_round_index: int | None) -> str:
    labels = {
        "hidden_by_child": "孩子已隐藏",
        "needs_retry": "需要重新提交修改",
        "needs_revision": "建议继续修改",
        "revised_once": "已完成一次修改",
        "multi_round_revision": "已完成多轮修改",
        "not_archived": "还没有提交初稿",
    }
    if status == "multi_round_revision" and latest_round_index is not None:
        return f"已完成 {latest_round_index} 稿"
    return labels.get(status, "写作记录")


def _has_first_draft_round(versions: list[EssayVersion]) -> bool:
    return any(get_round_index(version) == 1 for version in versions)


def _version_payload(version: EssayVersion) -> dict[str, Any]:
    return {
        "version_id": version.id,
        "version_label": version.version_label,
        "round_index": get_round_index(version),
        "content": version.content,
        "ai_feedback": version.ai_feedback,
        "duration_seconds": version.duration_seconds,
        "completed_tasks": version.completed_tasks,
        "skipped_tasks": version.skipped_tasks,
        "llm_call_log_id": version.llm_call_log_id,
        "created_at": version.created_at,
    }


def _revision_attempt_payload(
    failed_attempt: EssayRevisionAttempt | None,
    latest: EssayVersion | None,
) -> dict[str, Any] | None:
    if failed_attempt is None:
        return None
    return {
        "attempt_id": failed_attempt.id,
        "status": failed_attempt.status,
        "base_version_id": failed_attempt.base_version_id,
        "target_round_index": failed_attempt.target_round_index,
        "submitted_content": failed_attempt.submitted_content,
        "error_code": failed_attempt.error_code,
        "can_retry": can_retry_revision_attempt(failed_attempt, latest),
        "created_at": failed_attempt.created_at,
        "updated_at": failed_attempt.updated_at,
    }


def _parent_summary_payload(item: dict[str, Any], versions: list[EssayVersion]) -> dict[str, Any]:
    latest = versions[-1] if versions else None
    latest_feedback = (
        latest.ai_feedback if latest is not None and isinstance(latest.ai_feedback, dict) else {}
    )
    return {
        "status": item["status"],
        "summary_label": item["summary_label"],
        "latest_round_index": item["latest_round_index"],
        "revision_round_count": item["revision_round_count"],
        "recent_improvement": latest_feedback.get("improvement")
        or latest_feedback.get("praise")
        or "",
        "next_suggestion": latest_feedback.get("next_step")
        or _revision_tasks_guidance(latest_feedback),
    }


def _continue_revision_guidance(
    status: str,
    latest: EssayVersion,
    versions: list[EssayVersion],
    failed_attempt: EssayRevisionAttempt | None,
) -> str:
    if status == "needs_retry" and failed_attempt is not None:
        if failed_attempt.error_code:
            return f"上次 AI 对比没有完成（{failed_attempt.error_code}）。请重新提交这一稿，我们会继续帮你比较修改。"
        return "上次 AI 对比没有完成。请重新提交这一稿，我们会继续帮你比较修改。"

    latest_feedback = latest.ai_feedback if isinstance(latest.ai_feedback, dict) else {}
    next_step = latest_feedback.get("next_step")
    if isinstance(next_step, str) and next_step.strip():
        return next_step.strip()

    first_draft = next((version for version in versions if get_round_index(version) == 1), None)
    first_feedback = (
        first_draft.ai_feedback
        if first_draft is not None and isinstance(first_draft.ai_feedback, dict)
        else {}
    )
    return _revision_tasks_guidance(first_feedback)


def _revision_tasks_guidance(ai_feedback: dict[str, Any]) -> str:
    revision_tasks = ai_feedback.get("revision_tasks")
    if isinstance(revision_tasks, str):
        return revision_tasks.strip()
    if not isinstance(revision_tasks, list):
        return ""
    instructions = []
    for task in revision_tasks:
        if isinstance(task, str) and task.strip():
            instructions.append(task.strip())
        elif isinstance(task, dict):
            instruction = task.get("instruction") or task.get("text") or task.get("description")
            if isinstance(instruction, str) and instruction.strip():
                instructions.append(instruction.strip())
    return "\n".join(instructions)
