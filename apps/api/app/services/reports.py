from sqlalchemy import and_, func, or_
from sqlmodel import Session, select

from app.domain.models import AbilityProfile, Essay, EssayVersion, ReadingSession, SentenceTraining
from app.services.llm_contracts import ReportContent


def build_stage_report_content(session: Session, student_id: str) -> ReportContent:
    sentence_count = len(
        session.exec(select(SentenceTraining).where(SentenceTraining.student_id == student_id)).all()
    )
    reading_count = len(
        session.exec(select(ReadingSession).where(ReadingSession.student_id == student_id)).all()
    )
    revision = session.exec(
        select(EssayVersion)
        .join(Essay)
        .where(
            Essay.student_id == student_id,
            or_(
                EssayVersion.round_index >= 2,
                and_(
                    EssayVersion.round_index.is_(None),
                    EssayVersion.version_label == "revision",
                ),
            ),
        )
        .order_by(
            EssayVersion.created_at.desc(),
            func.coalesce(EssayVersion.round_index, 2).desc(),
            EssayVersion.id.desc(),
        )
    ).first()
    completed_tasks = revision.completed_tasks if revision and isinstance(revision.completed_tasks, list) else []
    skipped_tasks = revision.skipped_tasks if revision and isinstance(revision.skipped_tasks, list) else []
    comparison_evidence = []
    if revision and isinstance(revision.ai_feedback, dict):
        raw_evidence = revision.ai_feedback.get("evidence", [])
        if isinstance(raw_evidence, list):
            comparison_evidence = [str(item) for item in raw_evidence if item]
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
        raise LookupError("report context not found")
    weak_points = []
    if ability.expression < 35 or ability.observation < 35:
        weak_points.append("表达还可以更具体")
    if ability.structure < 40:
        weak_points.append("作文结构还需要更清晰")
    if ability.summarization < 35 or ability.comprehension < 35:
        weak_points.append("阅读概括可以继续练")
    if not weak_points:
        weak_points.append("继续保持细节和修改练习")
    return ReportContent(
        practice_summary=(
            f"本阶段完成了 {sentence_count} 次句子训练、{reading_count} 次阅读练习，"
            f"并完成了 {len(completed_tasks)} 个修改任务。"
        ),
        ability_changes=[
            f"本次完成的修改任务：{task}" for task in completed_tasks[:2]
        ]
        or ["会修改力有新的练习证据"],
        best_revision=(
            "；".join(comparison_evidence[:2])
            if comparison_evidence
            else revision.content
            if revision
            else "还没有二稿，下一次重点完成一次修改闭环。"
        ),
        weak_points=weak_points[:2],
        next_suggestions=(
            [f"下次继续完成：{task}" for task in skipped_tasks[:2]]
            if skipped_tasks
            else ["继续做 1 次句子加细节", "完成 1 次作文二稿修改"]
        ),
    )
