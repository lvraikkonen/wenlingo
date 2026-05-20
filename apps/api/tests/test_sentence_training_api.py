from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import AbilityHistory, AbilityProfile, GameEvent, SentenceTraining, StudentProfile
from app.domain.seed import seed_demo_data


def parent_students(session, parent_id: str):
    return session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent_id)).all()


def test_sentence_training_persists_feedback_ability_and_game_event(session, client):
    parent = seed_demo_data(session)
    student = parent_students(session, parent.id)[0]

    response = client.post(
        f"/api/students/{student.id}/sentences",
        json={
            "source_sentence": "鍏洯寰堢編銆?",
            "upgraded_sentence": "娓呮櫒鐨勫叕鍥噷锛岃嵎鍙朵笂鐨勬按鐝犱竴闂竴闂紝鍍忓皬鐏场銆?",
            "focus": "鍔犵粏鑺?",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["feedback"]["specific_improvement"] == "加入了可看见的细节"
    assert payload["settlement"]["xp_delta"] == 25
    assert payload["next_task"]["kind"] in {"essay", "sentence"}
    training = session.exec(select(SentenceTraining)).one()
    assert training.focus == "鍔犵粏鑺?"
    assert session.exec(select(GameEvent)).one().problem_monsters == ["空泛表达"]
    assert session.exec(
        select(AbilityProfile).where(AbilityProfile.student_id == student.id)
    ).one().expression > 40
    history = session.exec(select(AbilityHistory).where(AbilityHistory.student_id == student.id)).all()
    assert {(row.ability_name, row.delta, row.source_type, row.source_id) for row in history} == {
        ("expression", 4, TaskType.sentence, training.id),
        ("observation", 4, TaskType.sentence, training.id),
    }
