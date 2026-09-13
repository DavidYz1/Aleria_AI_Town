"""Stage 2 acceptance through real HTTP routes and one durable SQLite file."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from backend.app.core.config import Settings
from backend.app.database.models import (
    ActionProposalRecord,
    AgentRun,
    Event,
    Memory,
    WorldAction,
    WorldState,
)
from backend.app.llm.embedding_provider import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
)
from backend.app.llm.mock import MockChatProvider
from backend.app.llm.reflection_provider import (
    FakeReflectionProvider,
    ReflectionProviderError,
)
from backend.app.main import create_app
from scripts.seed_world import seed_database


CLUE = "我在城堡北门发现琥珀钟徽"
FOLLOW_UP = "还记得琥珀钟徽吗？"


class CapturingChatProvider(MockChatProvider):
    def __init__(self) -> None:
        self.requests = []

    async def generate_reply(self, request):
        self.requests.append(request)
        return await super().generate_reply(request)


class FailingEmbeddingProvider(DeterministicEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def embed(self, text, *, timeout_seconds=None):
        self.calls += 1
        raise EmbeddingProviderError("PRIVATE embedding payload")


class FailingReflectionProvider(FakeReflectionProvider):
    def __init__(self) -> None:
        self.calls = 0

    def reflect(self, request):
        self.calls += 1
        raise ReflectionProviderError("PRIVATE reflection payload")


def settings(database_url: str, *, force_reflection: bool = False) -> Settings:
    values = {
        "database_url": database_url,
        "chat_history_limit": 2,
    }
    if force_reflection:
        values.update(
            reflection_importance_threshold=0,
            reflection_min_new_memories=1,
        )
    return Settings(_env_file=None, **values)


def dispose_app(app) -> None:
    app.state.session_factory.kw["bind"].dispose()


def counters(world_data: dict) -> tuple[int, int, int]:
    world = world_data["world"]
    return (
        world["world_version"],
        world["clock_tick"],
        world["event_sequence"],
    )


async def assert_complete_run_graph(client: AsyncClient, run_id: str, event_sequences: list[int]) -> None:
    response = await client.get(f"/api/agent-runs/{run_id}")
    assert response.status_code == 200, response.text
    graph = response.json()["data"]
    assert graph["run"]["status"] == "completed"
    assert [item["ordinal"] for item in graph["proposals"]] == [0, 1, 2]
    assert [item["event_sequence"] for item in graph["events"]] == event_sequences
    assert [item["sequence"] for item in graph["trace"]] == list(range(1, 15))
    assert graph["trace"][0]["stage"] == "run_started"
    assert graph["trace"][-1]["stage"] == "run_completed"


@pytest.mark.anyio
async def test_stage2_http_closure_survives_restart_and_cognition_failures(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)

    first_provider = CapturingChatProvider()
    first_app = create_app(
        database_url,
        settings=settings(database_url),
        chat_provider=first_provider,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=first_app),
            base_url="http://test",
        ) as client:
            reset = await client.post("/api/demo/reset")
            assert reset.status_code == 200, reset.text
            world = await client.get("/api/world")
            assert world.status_code == 200
            assert counters(world.json()["data"]) == (0, 0, 0)

            first_turn = await client.post(
                "/api/npcs/grey/chat",
                json={"message": CLUE},
            )
            assert first_turn.status_code == 200, first_turn.text
            conversation_id = first_turn.json()["data"]["conversation_id"]
            for message in ("今天天气很好", "我准备去吃晚饭", "散步之后想休息"):
                response = await client.post(
                    "/api/npcs/grey/chat",
                    json={"conversation_id": conversation_id, "message": message},
                )
                assert response.status_code == 200, response.text

            unchanged = await client.get("/api/world")
            assert counters(unchanged.json()["data"]) == (0, 0, 0)
    finally:
        dispose_app(first_app)

    second_provider = CapturingChatProvider()
    second_app = create_app(
        database_url,
        settings=settings(database_url),
        chat_provider=second_provider,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=second_app),
            base_url="http://test",
        ) as client:
            recalled = await client.post(
                "/api/npcs/grey/chat",
                json={"conversation_id": conversation_id, "message": FOLLOW_UP},
            )
            assert recalled.status_code == 200, recalled.text
            reply = recalled.json()["data"]["turn"]["assistant"]["content"]
            assert "琥珀钟徽" in reply
            assert "你之前说过" in reply
            assert "你的说法" in reply

            recalled_context = second_provider.requests[-1]
            assert len(recalled_context.conversation_history) == 2
            assert all(CLUE not in item.content for item in recalled_context.conversation_history)
            claims = [
                item
                for item in recalled_context.long_term_memories
                if item.source_label == "player_claim" and "琥珀钟徽" in item.content
            ]
            assert len(claims) == 1

            private_only = await client.get("/api/npcs/grey/memory-explanations")
            assert private_only.status_code == 200, private_only.text
            assert CLUE not in private_only.text

            tick = await client.post(
                "/api/world/tick",
                json={"expected_world_version": 0, "runtime_mode": "deterministic"},
            )
            assert tick.status_code == 200, tick.text
            first_run_id = tick.json()["data"]["run"]["id"]
            assert counters(tick.json()["data"]["world"]) == (1, 1, 3)
            await assert_complete_run_graph(client, first_run_id, [1, 2, 3])

            public_explanation = await client.get("/api/npcs/grey/memory-explanations")
            assert public_explanation.status_code == 200, public_explanation.text
            memories = public_explanation.json()["data"]["memories"]
            assert memories
            assert any(item["type"] == "episodic" for item in memories)
            assert all(item["source"]["kind"] == "world_event" for item in memories)
            assert CLUE not in public_explanation.text
    finally:
        dispose_app(second_app)

    failed_embedding = FailingEmbeddingProvider()
    failed_reflection = FailingReflectionProvider()
    failure_app = create_app(
        database_url,
        settings=settings(database_url, force_reflection=True),
        embedding_provider=failed_embedding,
        reflection_provider=failed_reflection,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=failure_app),
            base_url="http://test",
        ) as client:
            degraded_chat = await client.post(
                "/api/npcs/grey/chat",
                json={"conversation_id": conversation_id, "message": "故障期间仍要继续交谈"},
            )
            assert degraded_chat.status_code == 200, degraded_chat.text
            assert "PRIVATE" not in degraded_chat.text
            after_chat = await client.get("/api/world")
            assert counters(after_chat.json()["data"]) == (1, 1, 3)

            degraded_tick = await client.post(
                "/api/world/tick",
                json={"expected_world_version": 1, "runtime_mode": "deterministic"},
            )
            assert degraded_tick.status_code == 200, degraded_tick.text
            second_run_id = degraded_tick.json()["data"]["run"]["id"]
            assert counters(degraded_tick.json()["data"]["world"]) == (2, 2, 6)
            await assert_complete_run_graph(client, second_run_id, [4, 5, 6])

            degraded_quest = await client.post(
                "/api/quests/missing-child/interact",
                json={
                    "interaction": "accept_quest",
                    "expected_version": 0,
                    "expected_world_version": 2,
                },
            )
            assert degraded_quest.status_code == 200, degraded_quest.text
            assert degraded_quest.json()["data"]["quest"]["status"] == "accepted"
            assert "PRIVATE" not in degraded_quest.text

            # docs/05:105 — the anonymous endpoint owns a LOCAL deterministic
            # query embedding instead of the configured live provider, so a
            # failing configured provider must neither degrade this read nor
            # be reached by it.
            configured_calls_before = failed_embedding.calls
            public_read = await client.get("/api/npcs/grey/memory-explanations")
            assert public_read.status_code == 200, public_read.text
            public_data = public_read.json()["data"]
            assert public_data["retrieval_mode"] == "hybrid"
            assert public_data["fallback_used"] is False
            assert failed_embedding.calls == configured_calls_before
            assert public_data["memories"]
            assert CLUE not in public_read.text

            final_world = await client.get("/api/world")
            assert counters(final_world.json()["data"]) == (3, 2, 7)

        assert failed_embedding.calls > 0
        assert failed_reflection.calls > 0
        with failure_app.state.session_factory() as session:
            persisted_claims = tuple(session.scalars(select(Memory).where(
                Memory.world_id == "aleria-town",
                Memory.owner_npc_id == "grey",
                Memory.memory_type == "conversation",
            )))
            assert any(CLUE in memory.content for memory in persisted_claims)
            assert all(
                (memory.secrecy, memory.disclosure_scope) == ("private", "player_dialogue")
                for memory in persisted_claims
            )
            world = session.get(WorldState, "aleria-town")
            assert (world.world_version, world.clock_tick, world.event_sequence) == (3, 2, 7)
            assert session.scalar(select(func.count()).select_from(AgentRun)) == 2
            assert session.scalar(select(func.count()).select_from(ActionProposalRecord)) == 6
            assert session.scalar(select(func.count()).select_from(WorldAction)) == 6
            assert session.scalar(select(func.count()).select_from(Event).where(Event.run_id.is_not(None))) == 6
    finally:
        dispose_app(failure_app)
