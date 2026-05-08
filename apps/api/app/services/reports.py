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
        .order_by(EssayVersion.created_at.desc())
    ).first()
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student_id)).first()
    if not ability:
        raise LookupError("report context not found")
    weak_points = []
    if ability.structure < 45:
        weak_points.append("浣滄枃缁撴瀯杩橀渶瑕佹洿娓呮")
    if ability.summarization < 45:
        weak_points.append("闃呰姒傛嫭鍙互缁х画缁?")
    if not weak_points:
        weak_points.append("缁х画淇濇寔缁嗚妭鍜屼慨鏀圭粌涔?")
    return ReportContent(
        practice_summary=f"鏈樁娈?畬鎴愪簡 {sentence_count} 娆″彞瀛愯缁冨拰 {reading_count} 娆￠槄璇荤粌涔犮€?",
        ability_changes=["鍐欏叿浣撳姏鏈夋柊鐨勮瘉鎹?", "浼氫慨鏀瑰姏闅忕潃浜岀鏇存柊"],
        best_revision=revision.content
        if revision
        else "杩樻病鏈変簩绋匡紝涓嬩竴娆￠噸鐐瑰畬鎴愪竴娆′慨鏀归棴鐜€?",
        weak_points=weak_points[:2],
        next_suggestions=["缁х画鍋?1 娆″彞瀛愬姞缁嗚妭", "瀹屾垚 1 娆′綔鏂囦簩绋夸慨鏀?"],
    )
