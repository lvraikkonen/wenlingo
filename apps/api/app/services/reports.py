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
        .where(Essay.student_id == student_id, EssayVersion.version_label == "revision")
        .order_by(EssayVersion.created_at.desc(), EssayVersion.id.desc())
    ).first()
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
        raise LookupError("report context not found")
    weak_points = []
    if ability.structure < 45:
        weak_points.append("作文结构还需要更清晰")
    if ability.summarization < 45:
        weak_points.append("阅读概括可以继续练")
    if not weak_points:
        weak_points.append("继续保持细节和修改练习")
    return ReportContent(
        practice_summary=f"本阶段完成了 {sentence_count} 次句子训练和 {reading_count} 次阅读练习。",
        ability_changes=["写具体力有新的证据", "会修改力随着二稿更新"],
        best_revision=revision.content if revision else "还没有二稿，下一次重点完成一次修改闭环。",
        weak_points=weak_points[:2],
        next_suggestions=["继续做 1 次句子加细节", "完成 1 次作文二稿修改"],
    )
