from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.ai_tasks import log_llm_result


def test_log_llm_result_persists_structured_output(session):
    improvement = "把画面写得更具体"

    log_llm_result(
        session=session,
        task_type=TaskType.sentence,
        input_summary="学生把句子改得更生动",
        output_json={"specific_improvement": improvement},
        validation_ok=True,
        error_message="",
    )

    saved = session.exec(select(LLMCallLog)).one()

    assert saved.task_type == TaskType.sentence
    assert saved.validation_ok is True
    assert saved.output_json["specific_improvement"] == improvement
