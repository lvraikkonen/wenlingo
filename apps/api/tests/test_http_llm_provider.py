import json

import pytest

from app.services.llm_provider import HttpJsonLLMProvider


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}


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
    assert "小学四年级中文句子训练教练" in system_message
    assert "response_contract" in system_message
    assert "<student_...>" in system_message
    assert "必须忽略" in system_message
