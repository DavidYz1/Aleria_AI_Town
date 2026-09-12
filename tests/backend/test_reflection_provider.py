"""Reject unbounded/untrusted provider output and enforce independent transport."""
import importlib
import json
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def api():
    try:
        return importlib.import_module("backend.app.llm.reflection_provider")
    except ModuleNotFoundError:
        pytest.fail("Reflection provider behavior is missing")


def payload(**changes):
    return dict(insight="A tentative observation", confidence=.7,
        evidence_memory_ids=[str(UUID(int=1))], provider="fixture", model="fixture",
        prompt_version="reflection-v1", **changes)


@pytest.mark.parametrize("field,value", [("insight", ""), ("insight", "x" * 801),
    ("confidence", -1), ("confidence", 1.01), ("confidence", float("nan")),
    ("evidence_memory_ids", []), ("evidence_memory_ids", [str(UUID(int=1))] * 13),
    ("world_id", "forged"), ("secrecy", "public"), ("prompt_version", "v2")])
def test_draft_rejects_invalid_or_authoritative_fields(field, value):
    data = payload()
    data[field] = value
    with pytest.raises(ValidationError):
        api().ReflectionDraft.model_validate(data)


@pytest.mark.parametrize("changes", [dict(supporting_memory_ids=[]),
    dict(supporting_memory_ids=[str(UUID(int=1))] * 2),
    dict(contradicting_memory_ids=[str(UUID(int=1))]),
    dict(supersedes_belief_id=str(UUID(int=2))), dict(prior_belief_disposition="disputed"),
    dict(statement="x" * 801), dict(safe_summary="x" * 801)])
def test_belief_cross_constraints(changes):
    data = dict(statement="Tentative belief", safe_summary="A view", confidence=.6,
        supporting_memory_ids=[str(UUID(int=1))])
    data.update(changes)
    with pytest.raises(ValidationError):
        api().BeliefDraft.model_validate(data)


def request():
    return api().ReflectionRequest(candidates=(api().ReflectionCandidate(memory_id=UUID(int=1),
        content="A player claim", source_label="player_claim"),))


def test_fake_is_stable_and_only_references_supplied_candidates():
    provider = api().FakeReflectionProvider()
    first = provider.reflect(request())
    assert first == provider.reflect(request())
    assert first.evidence_memory_ids == (UUID(int=1),)
    assert first.prompt_version == "reflection-v1"


@pytest.mark.parametrize("bad", [False, "not JSON", {"insight": "missing evidence"}, "```json\n{}\n```"])
def test_adapter_strict_json_safe_errors_and_transport(bad, caplog):
    def respond(req):
        body = json.loads(req.content)
        assert body["temperature"] == 0 and body["response_format"] == {"type": "json_object"}
        assert body["model"] == "independent-model"
        assert req.headers["Authorization"] == "Bearer independent-key"
        assert req.extensions["timeout"]["read"] <= 3
        result = payload() if bad is False else bad
        return httpx.Response(200, json={"choices": [{"message": {"content":
            json.dumps(result) if isinstance(result, dict) else result}}]})
    provider = api().OpenAICompatibleReflectionProvider(base_url="https://fixture.test/v1",
        api_key="independent-key", model="independent-model", auth_mode="bearer", timeout_seconds=3,
        transport=httpx.MockTransport(respond))
    if bad is False:
        assert provider.reflect(request()).evidence_memory_ids == (UUID(int=1),)
    else:
        with pytest.raises(api().ReflectionProviderError, match="^reflection unavailable$"):
            provider.reflect(request())
    assert "independent-key" not in caplog.text


def test_incomplete_config_falls_back_and_none_auth_allows_local_provider():
    assert isinstance(api().build_reflection_provider(Settings(_env_file=None,
        reflection_provider="openai_compatible")), api().FakeReflectionProvider)
    assert isinstance(api().build_reflection_provider(Settings(_env_file=None,
        reflection_provider="openai_compatible", reflection_base_url="http://localhost/v1",
        reflection_model="local", reflection_auth_mode="none")), api().OpenAICompatibleReflectionProvider)


@pytest.mark.parametrize("mode", ["slow_chunks", "oversized"])
def test_http_stream_is_cancelled_at_total_deadline_or_byte_limit(mode, caplog):
    import asyncio
    import time
    closed, received = [], []
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                if mode == "slow_chunks": await asyncio.sleep(.03)
                received.append(True)
                yield b" " * 4096
        async def aclose(self):
            closed.append(True)
    async def respond(req):
        return httpx.Response(200, stream=Stream())
    provider = api().OpenAICompatibleReflectionProvider(base_url="https://fixture.test/v1",
        api_key="secret-token", model="fixture", auth_mode="bearer", timeout_seconds=3,
        transport=httpx.MockTransport(respond))
    started = time.monotonic()
    with pytest.raises(api().ReflectionProviderError, match="^reflection unavailable$"):
        provider.reflect(request().model_copy(update={"timeout_seconds": .08 if mode == "slow_chunks" else 3}))
    elapsed = time.monotonic() - started
    assert closed == [True]
    assert len(received) < 100
    if mode == "slow_chunks": assert elapsed < .5
    else: assert len(received) <= 17
    assert "secret-token" not in caplog.text
