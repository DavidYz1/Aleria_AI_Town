"""Restart acceptance: persisted claims leave short history and re-enter as memories."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.database.models import Memory, Observation, AgentCognitionState, ConversationMessage
from backend.app.llm.mock import MockChatProvider
from backend.app.main import create_app
from scripts.seed_world import seed_database


class CapturingProvider(MockChatProvider):
    def __init__(self): self.requests = []
    async def generate_reply(self, request):
        self.requests.append(request)
        return await super().generate_reply(request)


def test_claim_survives_restart_deduplicates_history_and_projects_current_turn(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    settings = Settings(_env_file=None, chat_history_limit=2)
    first_provider = CapturingProvider()
    first = create_app(database_url, settings=settings, chat_provider=first_provider)
    with TestClient(first) as client:
        response = client.post("/api/npcs/grey/chat", json={"message": "我在城堡发现蓝色羽毛"})
        assert response.status_code == 200
        conversation_id = response.json()["data"]["conversation_id"]
        for message in ("今天天气很好", "我准备去吃晚饭", "散步之后想休息"):
            response = client.post("/api/npcs/grey/chat", json={"conversation_id": conversation_id, "message": message})
            assert response.status_code == 200
            assert message not in {item.content for item in first_provider.requests[-1].long_term_memories}
            # Same cognition Session retrieval + post-turn catch-up must persist the newest turn.
            with first.state.session_factory() as session:
                newest = session.scalar(select(ConversationMessage).order_by(ConversationMessage.id.desc()))
                observation = session.scalar(select(Observation).where(Observation.source_turn_id == newest.turn_id))
                assert observation is not None
                memory = session.scalar(select(Memory).where(Memory.source_observation_id == observation.id))
                assert memory.embedding_status == "ready"
                assert session.get(AgentCognitionState, ("aleria-town", "grey")).last_conversation_message_id == newest.id
    second_provider = CapturingProvider()
    second = create_app(database_url, settings=settings, chat_provider=second_provider)
    with TestClient(second) as client:
        response = client.post("/api/npcs/grey/chat", json={"conversation_id": conversation_id, "message": "还记得蓝色羽毛吗？"})
        assert response.status_code == 200
    context = second_provider.requests[-1]
    assert len(context.conversation_history) == 2
    assert context.conversation_history[0].content == "散步之后想休息"
    assert context.long_term_memories[0].source_label == "player_claim"
    assert "蓝色羽毛" in context.long_term_memories[0].content
    assert "蓝色羽毛" in response.json()["data"]["turn"]["assistant"]["content"]
    assert "你之前说过" in response.json()["data"]["turn"]["assistant"]["content"]
    with second.state.session_factory() as session:
        short_history_turn = session.scalar(select(ConversationMessage.turn_id).where(ConversationMessage.content == "散步之后想休息"))
        assert short_history_turn not in {item.source_turn_id for item in context.long_term_memories}
    assert "还记得蓝色羽毛吗？" not in {item.content for item in context.long_term_memories}


def test_pre_reply_enriches_existing_authored_memory_without_new_projection(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    class CheckProvider(CapturingProvider):
        async def generate_reply(self, request):
            with app.state.session_factory() as session:
                rows = list(session.scalars(select(Memory).where(Memory.owner_npc_id == "grey", Memory.memory_type == "knowledge")))
                assert rows and all(row.embedding_status == "ready" for row in rows)
            return await super().generate_reply(request)
    app = create_app(database_url, settings=Settings(_env_file=None), chat_provider=CheckProvider())
    with TestClient(app) as client:
        assert client.post("/api/npcs/grey/chat", json={"message": "你好"}).status_code == 200


def test_telemetry_and_rollback_failure_degrades_chat_without_exposing_payload(database_url, seed_dir, monkeypatch, caplog):
    from backend.app.database.cognition_repository import CognitionRepository
    seed_database(database_url, seed_dir)
    original_access = CognitionRepository.record_access
    def fail_telemetry(repository, ids):
        original_access(repository, ids)
        rollback = repository.session.rollback
        def reported_rollback_failure():
            rollback()
            raise RuntimeError("private claim API-key")
        repository.session.rollback = reported_rollback_failure
        raise RuntimeError("private claim API-key")
    monkeypatch.setattr(CognitionRepository, "record_access", fail_telemetry)
    provider = CapturingProvider()
    app = create_app(database_url, settings=Settings(_env_file=None), chat_provider=provider)
    with TestClient(app) as client:
        response = client.post("/api/npcs/grey/chat", json={"message": "你好"})
        assert response.status_code == 200
    assert provider.requests[-1].long_term_memories == ()
    assert provider.requests[-1].memory_retrieval_mode == "memory_unavailable"
    assert "private claim API-key" not in response.text + caplog.text
