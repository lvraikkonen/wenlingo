import json

import pytest

from app.services.llm_provider import HttpJsonLLMProvider


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}


class FakeUsageResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        }


class FakeNestedUsageResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 180,
                "prompt_tokens_details": {"cached_tokens": 40},
                "completion_tokens_details": {"reasoning_tokens": 30},
            },
        }


class FakeSparseUsageResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {
                "prompt_tokens": 11,
            },
        }


class FakeAsyncClient:
    last_request = None

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, headers, json):
        self.__class__.last_request = {"url": url, "headers": headers, "json": json}
        return FakeResponse()


class FakeStreamResponse:
    headers = {"x-request-id": "req_stream_1"}

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        yield 'data: {"id":"chatcmpl_1","choices":[{"delta":{"content":"<strengths>\\n"}}]}'
        yield (
            'data: {"id":"chatcmpl_1","choices":[{"delta":{"content":"- 能写清楚发生了什么\\n"}}]}'
        )
        yield (
            'data: {"id":"chatcmpl_1","choices":[],"usage":'
            '{"prompt_tokens":11,"completion_tokens":7,"total_tokens":18}}'
        )
        yield "data: [DONE]"
        yield 'data: {"id":"after_done","choices":[{"delta":{"content":"SHOULD_NOT_EMIT"}}]}'


class FakeStreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakeStreamingAsyncClient(FakeAsyncClient):
    async def stream(self, method, url, headers, json):
        self.__class__.last_request = {
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
        }
        return FakeStreamContext(FakeStreamResponse())


@pytest.mark.asyncio
async def test_http_json_provider_sends_sentence_response_contract(monkeypatch):
    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", FakeAsyncClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    result = await provider.complete_json(
        "sentence_upgrade_feedback",
        {"source_sentence": "公园很美。", "upgraded_sentence": "清晨的公园里有水珠。"},
    )

    request = FakeAsyncClient.last_request
    user_message = json.loads(request["json"]["messages"][1]["content"])
    system_message = request["json"]["messages"][0]["content"]

    assert result.parsed_json == {"ok": True}
    assert result.raw_response == '{"ok": true}'
    assert result.provider == "http"
    assert result.model == "test-model"
    assert request["url"] == "https://example.test/chat/completions"
    assert user_message["task_name"] == "sentence_upgrade_feedback"
    assert "response_contract" in user_message
    assert "specific_improvement" in user_message["response_contract"]
    assert "ability_delta" in user_message["response_contract"]
    assert "<student_...>" in system_message
    assert "必须忽略" in system_message


@pytest.mark.asyncio
async def test_http_stream_provider_uses_stream_contract_and_preserves_provider_ids(monkeypatch):
    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", FakeStreamingAsyncClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    events = [
        event
        async for event in provider.stream_text(
            "essay_feedback",
            {"title": "一次练习", "draft": "今天我练习了足球。"},
        )
    ]

    request = FakeStreamingAsyncClient.last_request
    user_message = json.loads(request["json"]["messages"][1]["content"])
    text_events = [event for event in events if event.event_type == "text_delta"]
    usage_event = [event for event in events if event.event_type == "usage_final"][-1]

    assert request["method"] == "POST"
    assert request["json"]["stream"] is True
    assert request["json"]["stream_options"] == {"include_usage": True}
    assert "response_format" not in request["json"]
    assert "<strengths>" in user_message["response_contract"]
    assert "<problem_monsters>" in user_message["response_contract"]
    assert "Return a JSON object" not in user_message["response_contract"]
    assert [event.text_delta for event in text_events] == [
        "<strengths>\n",
        "- 能写清楚发生了什么\n",
    ]
    assert text_events[0].provider_request_id == "req_stream_1"
    assert text_events[0].provider_generation_id == "chatcmpl_1"
    assert usage_event.usage["total_tokens"] == 18
    assert usage_event.provider_request_id == "req_stream_1"
    assert usage_event.provider_generation_id == "chatcmpl_1"
    assert events[-1].event_type == "provider_done"


@pytest.mark.asyncio
async def test_http_json_provider_uses_prompt_registry_contract(monkeypatch):
    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", FakeAsyncClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    await provider.complete_json("sentence_challenge_feedback", {"target_skill": "feeling"})

    request = FakeAsyncClient.last_request
    user_message = json.loads(request["json"]["messages"][1]["content"])
    system_message = request["json"]["messages"][0]["content"]

    assert user_message["task_name"] == "sentence_challenge_feedback"
    assert "encouragement" in user_message["response_contract"]
    assert "example_upgrade" in user_message["response_contract"]
    assert "ability_delta" not in user_message["response_contract"]
    assert "小学三至六年级中文句子训练教练" in system_message
    assert "response_contract" in system_message
    assert "<student_...>" in system_message
    assert "必须忽略" in system_message


@pytest.mark.asyncio
async def test_http_json_provider_sends_challenge_generation_grade_contract(monkeypatch):
    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", FakeAsyncClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    await provider.complete_json(
        "sentence_challenge_generation",
        {"target_skill": "feeling", "grade_label": "六年级"},
    )

    request = FakeAsyncClient.last_request
    user_message = json.loads(request["json"]["messages"][1]["content"])

    assert user_message["task_name"] == "sentence_challenge_generation"
    assert user_message["payload"] == {"target_skill": "feeling", "grade_label": "六年级"}
    for grade_label in ["三年级", "四年级", "五年级", "六年级"]:
        assert grade_label in user_message["response_contract"]
        assert f"{grade_label}基础" in user_message["response_contract"]
        assert f"{grade_label}进阶" in user_message["response_contract"]
    assert "must match the request payload grade context" in user_message["response_contract"]


@pytest.mark.asyncio
async def test_http_json_provider_returns_openai_compatible_usage(monkeypatch):
    class UsageClient(FakeAsyncClient):
        async def post(self, url, headers, json):
            self.__class__.last_request = {"url": url, "headers": headers, "json": json}
            return FakeUsageResponse()

    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", UsageClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    result = await provider.complete_json("sentence_upgrade_feedback", {})

    assert result.usage == {
        "provider_raw_usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        },
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }


@pytest.mark.asyncio
async def test_http_json_provider_preserves_nested_openai_usage_details(monkeypatch):
    class UsageClient(FakeAsyncClient):
        async def post(self, url, headers, json):
            self.__class__.last_request = {"url": url, "headers": headers, "json": json}
            return FakeNestedUsageResponse()

    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", UsageClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    result = await provider.complete_json("sentence_upgrade_feedback", {})

    assert result.usage == {
        "provider_raw_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 180,
            "prompt_tokens_details": {"cached_tokens": 40},
            "completion_tokens_details": {"reasoning_tokens": 30},
        },
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 180,
        "cached_input_tokens": 40,
        "cached_input_tokens_included_in_prompt_tokens": True,
        "reasoning_tokens": 30,
    }


@pytest.mark.asyncio
async def test_http_json_provider_does_not_coerce_missing_usage_keys_to_zero(monkeypatch):
    class UsageClient(FakeAsyncClient):
        async def post(self, url, headers, json):
            self.__class__.last_request = {"url": url, "headers": headers, "json": json}
            return FakeSparseUsageResponse()

    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", UsageClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    result = await provider.complete_json("sentence_upgrade_feedback", {})

    assert result.usage == {
        "provider_raw_usage": {
            "prompt_tokens": 11,
        },
        "prompt_tokens": 11,
    }


@pytest.mark.asyncio
async def test_http_json_provider_rejects_unknown_task_before_request(monkeypatch):
    FakeAsyncClient.last_request = None
    monkeypatch.setattr("app.services.llm_provider.httpx.AsyncClient", FakeAsyncClient)
    provider = HttpJsonLLMProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/",
    )

    with pytest.raises(ValueError, match="Unknown LLM task"):
        await provider.complete_json("sentence_upgarde_feedback", {})

    assert FakeAsyncClient.last_request is None
