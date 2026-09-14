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


# `False` 是好响应；其余都是坏响应。载荷形状随 Task「reflection 切 tool calling」
# 从 `response_format=json_object` 的 content 通道改为 tool call arguments，
# 但本用例的立意未变：不可信输出一律被拒、传输参数独立、密钥不入日志。
# `"content_channel"` 是切换后**新出现**的失败模式：模型完全不调工具。
@pytest.mark.parametrize("bad", [False, "not JSON", {"insight": "missing evidence"},
    "```json\n{}\n```", "content_channel"])
def test_adapter_strict_json_safe_errors_and_transport(bad, caplog):
    def respond(req):
        body = json.loads(req.content)
        assert body["temperature"] == 0 and "response_format" not in body
        assert body["tool_choice"] == "required"
        assert [t["function"]["name"] for t in body["tools"]] == ["submit_reflection"]
        assert body["model"] == "independent-model"
        assert req.headers["Authorization"] == "Bearer independent-key"
        assert req.extensions["timeout"]["read"] <= 3
        if bad == "content_channel":
            return httpx.Response(200, json={"choices": [{"message": {
                "content": json.dumps(payload())}}]})
        good = {"insight": "A tentative observation", "confidence": .7, "evidence_indices": [1]}
        arguments = json.dumps(good) if bad is False else (
            json.dumps(bad) if isinstance(bad, dict) else bad)
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [
            {"function": {"name": "submit_reflection", "arguments": arguments}}]}}]})
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


def multi_request(**changes):
    """三条候选、两条现有信念：序号映射错一位就能被下面的断言抓到。"""
    return api().ReflectionRequest(
        candidates=tuple(
            api().ReflectionCandidate(memory_id=UUID(int=n), content=f"记忆 {n}", source_label="observed_event")
            for n in (11, 22, 33)
        ),
        current_beliefs=tuple(
            api().CurrentBelief(belief_id=UUID(int=n), statement=f"信念 {n}", confidence=.5, lifecycle_state="active")
            for n in (77, 88)
        ),
        **changes,
    )


def tool_call_provider(arguments, *, timeout_seconds=3):
    """把一次 tool call 的 arguments 喂给 provider，其余走真实请求构造与解析。"""
    captured = {}

    def respond(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [
            {"function": {"name": "submit_reflection",
                          "arguments": json.dumps(arguments, ensure_ascii=False)}}]}}]})

    provider = api().OpenAICompatibleReflectionProvider(
        base_url="https://fixture.test/v1", api_key="independent-key",
        model="independent-model", auth_mode="bearer", timeout_seconds=timeout_seconds,
        transport=httpx.MockTransport(respond))
    return provider, captured


def test_evidence_indices_map_to_the_exact_candidate_ids():
    """序号到 UUID 的映射错位是**静默**的：引擎的 `evidence ⊆ candidates` 守卫
    仍然通过，只是引用了别的记忆。所以必须逐个断言到具体 UUID，
    不能只断言「都在候选集里」。"""
    provider, captured = tool_call_provider(
        {"insight": "结论", "confidence": .7, "evidence_indices": [1, 3]})
    draft = provider.reflect(multi_request())

    assert draft.evidence_memory_ids == (UUID(int=11), UUID(int=33))
    assert draft.insight == "结论"
    # 非空前提：候选里确实有第 2 条，它没被选中才说明映射按序号走而不是照单全收。
    assert UUID(int=22) not in draft.evidence_memory_ids

    body = captured["body"]
    assert body["tool_choice"] == "required"
    assert [t["function"]["name"] for t in body["tools"]] == ["submit_reflection"]
    assert "response_format" not in body


def test_provenance_is_injected_by_the_provider_not_taken_from_the_model():
    """`provider` / `model` 是传输层事实，不是模型判断。让模型自报等于允许它伪造
    来源 —— 本用例故意让响应里带上伪造值，断言它们被忽略。"""
    provider, _ = tool_call_provider({
        "insight": "结论", "confidence": .7, "evidence_indices": [2],
        "provider": "forged-provider", "model": "forged-model",
        "prompt_version": "reflection-v9",
    })
    draft = provider.reflect(multi_request())

    assert (draft.provider, draft.model) == ("openai_compatible", "independent-model")
    assert draft.prompt_version == "reflection-v1"


@pytest.mark.parametrize("indices", [[0], [4], [-1], [], ["1"], [1.5], "1"])
def test_out_of_range_or_malformed_indices_fail_instead_of_being_dropped(indices):
    """静默丢弃越界序号会让 draft 携带一个**模型没打算给出**的证据集合，
    或者干脆变成空集合再被下游拒绝，两者都比直接失败更难排查。"""
    provider, _ = tool_call_provider(
        {"insight": "结论", "confidence": .7, "evidence_indices": indices})
    with pytest.raises(api().ReflectionProviderError, match="^reflection unavailable$"):
        provider.reflect(multi_request())


def test_belief_indices_map_and_omitted_belief_stays_none():
    provider, _ = tool_call_provider({
        "insight": "结论", "confidence": .7, "evidence_indices": [1, 2],
        "belief": {"statement": "信念", "safe_summary": "简述", "confidence": .6,
                   "supporting_indices": [2], "contradicting_indices": [3],
                   "supersedes_belief_index": 2, "prior_belief_disposition": "superseded"},
    })
    draft = provider.reflect(multi_request())

    assert draft.belief is not None
    assert draft.belief.supporting_memory_ids == (UUID(int=22),)
    assert draft.belief.contradicting_memory_ids == (UUID(int=33),)
    assert draft.belief.supersedes_belief_id == UUID(int=88)
    assert draft.belief.prior_belief_disposition == "superseded"

    bare, _ = tool_call_provider(
        {"insight": "结论", "confidence": .7, "evidence_indices": [1]})
    assert bare.reflect(multi_request()).belief is None
