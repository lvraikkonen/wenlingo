from sqlmodel import select

from app.domain.models import Essay, EssayVersion, ReadingSession, Report, StudentProfile
from app.domain.seed import seed_demo_data


def parent_students(session, parent_id: str):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


def test_reading_session_updates_transfer_tip_and_report(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    reading = client.post(
        f"/api/students/{student.id}/readings",
        json={
            "article_id": "spring-sounds",
            "answers": {
                "main_idea": "鏄ュぉ鏉ヤ簡锛屽皬娌冲拰楦熷効閮藉緢鐑椆銆?",
                "detail": "灏忔渤鍙戝嚭鍝楀暒鍟︾殑澹伴煶銆?",
                "transfer": "鍐欐櫙鍙互鍐欏０闊炽€?",
            },
        },
    )

    assert reading.status_code == 201
    assert reading.json()["transfer_tip"] == "鍐欐櫙鏃跺彲浠ュ姞鍏ュ０闊炽€?"
    assert session.exec(select(ReadingSession)).one().article_title == "鏄ュぉ鐨勫０闊?"

    report = client.post(f"/api/students/{student.id}/reports", json={"report_type": "stage"})

    assert report.status_code == 201
    payload = report.json()["content"]
    assert "鏈樁娈?" in payload["practice_summary"]
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
