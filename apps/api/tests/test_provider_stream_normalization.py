from app.services.llm_provider import normalize_provider_stream_events


def test_openai_final_usage_chunk_with_empty_choices_is_captured():
    events = normalize_provider_stream_events(
        provider="openai",
        chunks=[
            {"choices": [{"delta": {"content": "hi"}}], "usage": None},
            {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        ],
    )

    assert events[-2].event_type == "usage_final"
    assert events[-2].usage["total_tokens"] == 15
    assert events[-1].event_type == "provider_done"


def test_anthropic_cumulative_usage_is_not_summed():
    events = normalize_provider_stream_events(
        provider="anthropic",
        chunks=[
            {"type": "message_delta", "usage": {"output_tokens": 3}},
            {"type": "message_delta", "usage": {"output_tokens": 7}},
        ],
    )

    usage_events = [event for event in events if event.event_type == "usage_final"]
    assert usage_events[-1].usage["completion_tokens"] == 7


def test_anthropic_start_input_usage_merges_with_cumulative_output_usage():
    events = normalize_provider_stream_events(
        provider="anthropic",
        chunks=[
            {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
            {"type": "message_delta", "usage": {"output_tokens": 3}},
            {"type": "message_delta", "usage": {"output_tokens": 7}},
        ],
    )

    usage = [event for event in events if event.event_type == "usage_final"][-1].usage
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 7
    assert usage["total_tokens"] == 17


def test_gemini_final_usage_metadata_and_thoughts_tokens_are_captured():
    events = normalize_provider_stream_events(
        provider="gemini",
        chunks=[
            {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]},
            {
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 18,
                    "thoughtsTokenCount": 3,
                }
            },
        ],
    )

    usage = [event for event in events if event.event_type == "usage_final"][-1].usage
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 5
    assert usage["thoughts_tokens"] == 3


def test_completed_stream_without_final_usage_sets_usage_unavailable():
    events = normalize_provider_stream_events(
        provider="openai",
        chunks=[{"choices": [{"delta": {"content": "hi"}}], "usage": None}],
    )

    assert events[-2].event_type == "usage_final"
    assert events[-2].usage is None
    assert events[-1].event_type == "provider_done"
