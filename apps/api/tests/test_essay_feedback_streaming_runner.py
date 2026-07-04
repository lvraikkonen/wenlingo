import asyncio

from app.services.essay_feedback_streaming import SseMirror, StreamingBackendTask
from app.services.llm_provider import LLMProviderStreamEvent


VALID_STREAM_EVENTS = [
    LLMProviderStreamEvent(
        event_type="text_delta",
        text_delta=(
            "<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>"
            "<improvements>\n- 第二段缺少动作细节\n</improvements>"
            "<problem_monsters>\n- 细节缺口\n</problem_monsters>"
            "<sentence_notes>\n- 把开心换成看到和做到的细节。\n</sentence_notes>"
            "<revision_tasks>\n- 给第二段加一个动作描写 | 第二段\n</revision_tasks>"
        ),
    ),
    LLMProviderStreamEvent(
        event_type="usage_final",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    ),
    LLMProviderStreamEvent(event_type="provider_done"),
]


class FakeStreamingProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, events):
        self.events = events
        self.cancelled = False

    async def stream_text(self, task_name, payload):
        try:
            for event in self.events:
                await asyncio.sleep(0)
                yield event
        except asyncio.CancelledError:
            self.cancelled = True
            raise


async def run_task(events):
    task = StreamingBackendTask.for_test(provider=FakeStreamingProvider(events))
    await task.run_to_terminal()
    return task


async def test_stream_missing_final_usage_completes_but_usage_available_false():
    events = [event for event in VALID_STREAM_EVENTS if event.event_type != "usage_final"]
    events.append(LLMProviderStreamEvent(event_type="usage_final", usage=None))
    events.append(LLMProviderStreamEvent(event_type="provider_done"))

    task = await run_task(events)

    assert task.stream_final_status == "completed"
    assert task.usage_available is False
    assert task.usage_source == "unavailable"


async def test_provider_fails_before_visible_content_releases_daily_limit():
    task = await run_task(
        [
            LLMProviderStreamEvent(
                event_type="provider_error",
                error_code="PROVIDER_TIMEOUT",
                error_message="provider timed out",
            )
        ]
    )

    assert task.stream_final_status == "provider_failed_before_visible_content"
    assert task.official_result_saved is False
    assert task.reservation_final_action == "released"


async def test_provider_fails_after_visible_content_does_not_save_partial_feedback():
    task = await run_task(
        [
            LLMProviderStreamEvent(
                event_type="text_delta",
                text_delta="<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>",
            ),
            LLMProviderStreamEvent(
                event_type="provider_error",
                error_code="PROVIDER_TIMEOUT",
                error_message="provider timed out",
            ),
        ]
    )

    assert task.first_visible_content_at is not None
    assert task.stream_final_status == "provider_failed_after_visible_content"
    assert task.official_result_saved is False


async def test_final_schema_invalid_after_previews_does_not_save_official_result():
    task = await run_task(
        [
            LLMProviderStreamEvent(
                event_type="text_delta",
                text_delta="<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>",
            ),
            LLMProviderStreamEvent(event_type="provider_done"),
        ]
    )

    assert task.error_code == "STREAM_FINAL_SCHEMA_INVALID"
    assert task.official_result_saved is False
    assert task.reservation_final_action == "released"


async def test_sse_mirror_disconnect_after_preview_does_not_cancel_backend_task():
    backend_task = StreamingBackendTask.for_test(provider=FakeStreamingProvider(VALID_STREAM_EVENTS))
    mirror = SseMirror(backend_task=backend_task)

    first_frame = await mirror.next_frame_for_test()
    await mirror.disconnect_for_test(after_frame=first_frame)
    await backend_task.wait_for_terminal_for_test()

    assert backend_task.first_visible_content_at is not None
    assert (
        backend_task.stream_final_status
        == "client_disconnected_after_visible_content_completed"
    )
    assert backend_task.official_result_saved is True


async def test_sse_mirror_disconnect_before_preview_cancels_or_releases():
    backend_task = StreamingBackendTask.for_test(
        provider=FakeStreamingProvider([LLMProviderStreamEvent(event_type="provider_done")])
    )
    mirror = SseMirror(backend_task=backend_task)

    await mirror.disconnect_for_test(after_frame=None)
    await backend_task.wait_for_terminal_for_test()

    assert backend_task.first_visible_content_at is None
    assert backend_task.reservation_final_action in {"released", "expired"}


async def test_stream_emits_heartbeat_before_provider_first_section_when_slow():
    backend_task = StreamingBackendTask.for_test(
        provider=FakeStreamingProvider(VALID_STREAM_EVENTS),
        first_provider_event_delay_seconds=30,
        heartbeat_seconds=1,
    )
    mirror = SseMirror(backend_task=backend_task)

    frame = await mirror.next_frame_for_test()

    assert frame.event_name in {"heartbeat", "ping"}
