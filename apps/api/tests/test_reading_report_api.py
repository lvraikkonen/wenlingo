from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db_session
from app.domain.enums import BadgeCode, TaskType
from app.domain.models import (
    AbilityHistory,
    AbilityProfile,
    Essay,
    EssayVersion,
    GameEvent,
    ReadingSession,
    Report,
    StudentProfile,
)
from app.domain.seed import seed_demo_data
from app.main import create_app


TASK9_TEXT_FILES = [
    "app/api/routes/readings.py",
    "app/api/routes/reports.py",
    "app/services/reports.py",
    "tests/test_reading_report_api.py",
]

MOJIBAKE_MARKER_CODEPOINTS = [
    0x93C4,
    0x9350,
    0x6D63,
    0x7F01,
    0x95C3,
    0x704F,
    0x59D2,
    0x95BA,
    0x951B,
    0x9286,
    0xFFFD,
]
MOJIBAKE_MARKERS = [chr(codepoint) for codepoint in MOJIBAKE_MARKER_CODEPOINTS] + [
    "\N{EURO SIGN}?"
]


def parent_students(session, parent_id: str):
    return session.exec(
        select(StudentProfile).where(StudentProfile.parent_id == parent_id).order_by(StudentProfile.id)
    ).all()


@contextmanager
def client_without_server_exceptions(session):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_task9_user_facing_chinese_does_not_contain_mojibake():
    api_root = Path(__file__).resolve().parents[1]

    for relative_path in TASK9_TEXT_FILES:
        content = (api_root / relative_path).read_text(encoding="utf-8")
        for marker in MOJIBAKE_MARKERS:
            assert marker not in content, f"{relative_path} contains mojibake marker {marker!r}"


def test_reading_session_updates_transfer_tip_and_report(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    ability_before = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    comprehension_before = ability_before.comprehension
    summarization_before = ability_before.summarization

    reading = client.post(
        f"/api/students/{student.id}/readings",
        json={
            "article_id": "spring-sounds",
            "answers": {
                "main_idea": "春天来了，小河和鸟儿都很热闹。",
                "detail": "小河发出哗啦啦的声音。",
                "transfer": "写景可以写声音。",
            },
        },
    )

    assert reading.status_code == 201
    assert reading.json()["transfer_tip"] == "写景时可以加入声音。"
    saved_reading = session.exec(select(ReadingSession)).one()
    assert saved_reading.article_title == "春天的声音"

    ability_after = session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one()
    assert ability_after.comprehension > comprehension_before
    assert ability_after.summarization > summarization_before
    history = session.exec(select(AbilityHistory).where(AbilityHistory.source_id == saved_reading.id)).all()
    assert {(row.ability_name, row.source_type) for row in history} == {
        ("comprehension", TaskType.reading),
        ("summarization", TaskType.reading),
    }
    event = session.exec(select(GameEvent).where(GameEvent.task_type == TaskType.reading)).one()
    assert event.xp_delta == 30
    assert event.badge_code == BadgeCode.reading_transfer

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 201
    payload = report.json()["content"]
    assert "本阶段" in payload["practice_summary"]
    assert len(payload["weak_points"]) <= 2
    assert session.exec(select(Report)).one().report_type == "stage"


def test_report_uses_only_requested_students_revision(session, client):
    parent = seed_demo_data(session)
    requested_student, other_student = parent_students(session, parent.id)[:2]

    requested_essay = Essay(student_id=requested_student.id, title="Requested", status="settled")
    other_essay = Essay(student_id=other_student.id, title="Other", status="settled")
    session.add(requested_essay)
    session.add(other_essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=requested_essay.id,
            version_label="revision",
            content="REQUESTED_STUDENT_REVISION",
        )
    )
    session.add(
        EssayVersion(
            essay_id=other_essay.id,
            version_label="revision",
            content="OTHER_STUDENT_REVISION",
        )
    )
    session.commit()

    report = client.post(
        f"/api/students/{requested_student.id}/reports",
        json={"report_type": "stage"},
    )

    assert report.status_code == 201
    assert report.json()["content"]["best_revision"] == "REQUESTED_STUDENT_REVISION"


def test_stage_report_mentions_revision_task_evidence(session, client):
    parent = seed_demo_data(session)
    student = session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent.id)).first()
    essay = Essay(student_id=student.id, title="我学会了骑车", status="settled")
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            content="我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
            completed_tasks=["给第二段加一个动作描写"],
            skipped_tasks=[],
            duration_seconds=420,
            ai_feedback={
                "encouragement": "你把最重要的画面写清楚了。",
                "improved_dimensions": ["细节更多"],
                "evidence": ["手心都出汗了"],
                "next_step": "下一次把结尾感受写清楚。",
            },
        )
    )
    session.commit()

    response = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert response.status_code == 201
    content = response.json()["content"]
    assert "完成了 1 个修改任务" in content["practice_summary"]
    assert "手心都出汗了" in content["best_revision"]
    assert any("给第二段加一个动作描写" in change for change in content["ability_changes"])


def test_stage_report_handles_legacy_revision_null_task_metadata(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    essay = Essay(student_id=student.id, title="旧数据作文", status="settled")
    session.add(essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=essay.id,
            version_label="revision",
            content="这是一篇旧数据二稿。",
            completed_tasks=None,
            skipped_tasks=None,
        )
    )
    session.commit()

    with client_without_server_exceptions(session) as client:
        response = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert response.status_code == 201
    content = response.json()["content"]
    assert "完成了 0 个修改任务" in content["practice_summary"]
    assert content["ability_changes"] == ["会修改力有新的练习证据"]
    assert content["next_suggestions"] == ["继续做 1 次句子加细节", "完成 1 次作文二稿修改"]


def test_report_returns_404_when_student_ability_is_missing(session):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    ability = session.exec(select(AbilityProfile).where(AbilityProfile.student_id == student.id)).one()
    session.delete(ability)
    session.commit()

    with client_without_server_exceptions(session) as client:
        report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 404
    assert report.json()["detail"] == "report context not found"


def test_report_uses_latest_requested_students_revision(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    now = datetime.now(timezone.utc)
    newer_essay = Essay(student_id=student.id, title="Newer", status="settled")
    older_essay = Essay(student_id=student.id, title="Older", status="settled")
    session.add(newer_essay)
    session.add(older_essay)
    session.flush()
    session.add(
        EssayVersion(
            essay_id=newer_essay.id,
            version_label="revision",
            content="NEWER_REVISION",
            created_at=now,
        )
    )
    session.add(
        EssayVersion(
            essay_id=older_essay.id,
            version_label="revision",
            content="OLDER_REVISION",
            created_at=now - timedelta(days=1),
        )
    )
    session.commit()

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 201
    assert report.json()["content"]["best_revision"] == "NEWER_REVISION"


def test_report_breaks_revision_created_at_ties_by_revision_id(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]
    same_created_at = datetime.now(timezone.utc)
    first_essay = Essay(student_id=student.id, title="First", status="settled")
    second_essay = Essay(student_id=student.id, title="Second", status="settled")
    session.add(first_essay)
    session.add(second_essay)
    session.flush()
    session.add(
        EssayVersion(
            id="00000000-0000-0000-0000-000000000001",
            essay_id=first_essay.id,
            version_label="revision",
            content="LOWER_ID_REVISION",
            created_at=same_created_at,
        )
    )
    session.add(
        EssayVersion(
            id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            essay_id=second_essay.id,
            version_label="revision",
            content="HIGHER_ID_REVISION",
            created_at=same_created_at,
        )
    )
    session.commit()

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 201
    assert report.json()["content"]["best_revision"] == "HIGHER_ID_REVISION"


def test_report_rejects_weekly_report_type(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "weekly"})

    assert report.status_code == 400
    assert report.json()["detail"] == "only stage reports are supported"


def test_four_demo_profiles_report_weak_points_match_profile(session, client):
    parent = seed_demo_data(session)
    students = sorted(parent_students(session, parent.id), key=lambda student: student.id)

    reports = {
        student.id: client.post(
            f"/api/students/{student.id}/reports",
            json={"report_type": "stage"},
        ).json()["content"]
        for student in students
    }

    assert "继续保持细节和修改练习" in reports["s1"]["weak_points"]
    assert "表达还可以更具体" in reports["s2"]["weak_points"]
    assert "作文结构还需要更清晰" in reports["s3"]["weak_points"]
    assert "阅读概括可以继续练" in reports["s4"]["weak_points"]
