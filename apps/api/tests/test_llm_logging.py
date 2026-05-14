from sqlmodel import select

from app.domain.enums import TaskType
from app.domain.models import LLMCallLog
from app.services.ai_tasks import log_llm_result


def test_log_llm_result_persists_structured_output(session):
    improvement = "把画面写得更具体"

    log_llm_result(
        session=session,
        task_type=TaskType.sentence,
        provider="mock",
        model="mock",
        prompt_version="test-v1",
        input_summary="学生把句子改得更生动",
        raw_response='{"specific_improvement":"把画面写得更具体"}',
        output_json={"specific_improvement": improvement},
        validation_ok=True,
        error_message="",
        retry_count=0,
    )

    saved = session.exec(select(LLMCallLog)).one()

    assert saved.task_type == TaskType.sentence
    assert saved.provider == "mock"
    assert saved.model == "mock"
    assert saved.prompt_version == "test-v1"
    assert saved.raw_response
    assert saved.validation_ok is True
    assert saved.retry_count == 0
    assert saved.output_json["specific_improvement"] == improvement
