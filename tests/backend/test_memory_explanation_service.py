"""Public explanation projection: permission-first reads, never private payloads."""
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import select

from backend.app.agents.memory_retrieval import (
    MemoryRetriever,
    MemoryType,
    RetrievalResult,
    RetrievalScope,
    RetrievedMemory,
)
from backend.app.core.config import Settings
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Conversation,
    ConversationMessage,
    Memory,
    WorldState,
)
from backend.app.database.npc_repository import NpcNotFoundError, NpcRepository
from backend.app.database.player_quest_repository import PlayerQuestRepository
from backend.app.llm.embedding_provider import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
    normalize,
)
from backend.app.quests.missing_child import MissingChildQuestPolicy
from backend.app.services.cognition_projection import CognitionProjectionService
from backend.app.services.memory_explanation import (
    CONVERSATION_SUMMARY,
    RETRIEVAL_CHAR_BUDGET,
    RETRIEVAL_LIMIT,
    SUMMARY_MAX_LENGTH,
    MemoryExplanationService,
    MemoryExplanationUnavailableError,
)
from backend.app.services.player_quest_context import PlayerQuestChatContextReader
from scripts.seed_world import seed_database


WORLD_ID = "aleria-town"


@pytest.fixture
def db(database_url, seed_dir):
    """Mirror production: authoritative reads and cognition reads own Sessions."""
    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    with factory() as authoritative, factory() as cognition:
        yield authoritative, cognition
    engine.dispose()


def build_service(db, *, retriever=None, cognition=None, quest_context_reader=None):
    authoritative, cognition_session = db
    return MemoryExplanationService(
        NpcRepository(authoritative),
        retriever or MemoryRetriever(
            CognitionRepository(cognition_session), DeterministicEmbeddingProvider()
        ),
        cognition=cognition,
        quest_context_reader=quest_context_reader,
    )


def memory_id(key):
    """Memories carry UUID identity in production; fixtures must not fake that."""
    return str(uuid5(NAMESPACE_URL, f"aleria:explanation-test:{key}"))


def add_memory(session, key, *, owner="ryan", text="蓝色羽毛在旧封锁线附近被发现", memory_type="knowledge", **changes):
    embedding = DeterministicEmbeddingProvider().embed(text)
    reference = (
        {"authored_source_id": key, "authored_source_version": "explanation-test-v1"}
        if memory_type == "knowledge"
        else {}
    )
    values = dict(
        id=memory_id(key), world_id=WORLD_ID, owner_npc_id=owner, memory_type=memory_type,
        content=text, safe_summary=text,
        normalized_content_hash=sha256(normalize(text).encode()).hexdigest(),
        related_entity_ids_json=[], occurred_world_version=0, occurred_clock_tick=0,
        created_world_version=0, created_clock_tick=0, occurred_world_time="08:00",
        source_created_at=datetime.now(UTC), importance=0.5, confidence=0.9,
        emotional_valence=0.0, secrecy="public", disclosure_scope="public",
        lifecycle_state="active", embedding_status="ready",
        embedding=list(embedding.vector), embedding_provider=embedding.provider,
        embedding_model=embedding.model, embedding_version=embedding.version,
        embedding_dimensions=embedding.dimensions,
        embedding_input_hash=embedding.input_hash, access_count=0,
        **reference,
    )
    values.update(changes)
    session.add(Memory(**values))
    session.commit()
    return values["id"]


def project_player_turn(session, claim, *, npc_id="ryan"):
    """Create the real conversation source and project it through production policy."""
    conversation_id, turn_id, now = str(uuid4()), str(uuid4()), datetime.now(UTC)
    session.add(Conversation(id=conversation_id, world_id=WORLD_ID, npc_id=npc_id,
        created_clock_tick=0, created_at=now, updated_at=now))
    session.flush()
    for role, content in (("user", claim), ("assistant", "我记下了你的说法，但那仍然只是说法。")):
        session.add(ConversationMessage(conversation_id=conversation_id, role=role,
            content=content, clock_tick=0, turn_id=turn_id, world_version=0,
            world_time="08:00", created_at=now))
    session.commit()
    CognitionProjectionService(CognitionRepository(session),
        settings=Settings(_env_file=None)).catch_up_owner(WORLD_ID, npc_id)


def retrieved(**changes):
    values = dict(memory_id=str(uuid4()), memory_type="episodic",
        source_label="observed_event", content="Observed an NPC action.",
        occurred_clock_tick=1, source_turn_id=None, source_observation_id=None,
        score=0.5, semantic=0.4, lexical=0.1, recency=0.9, importance=0.5, confidence=1.0)
    values.update(changes)
    return RetrievedMemory(**values)


class StubRetriever:
    """Reaches projection branches the PUBLIC_EXPLANATION SQL filter cannot produce."""

    def __init__(self, *memories, mode="hybrid"):
        self.result = RetrievalResult(tuple(memories), mode)
        self.requests = []

    def retrieve(self, request):
        self.requests.append(request)
        return self.result


def public_memory_ids(session, owner="ryan"):
    return set(session.scalars(select(Memory.id).where(
        Memory.world_id == WORLD_ID, Memory.owner_npc_id == owner,
        Memory.secrecy == "public", Memory.disclosure_scope == "public",
        Memory.lifecycle_state.in_(("active", "disputed")))))


def test_public_explanation_returns_exactly_the_permitted_owner_memories(db):
    _, cognition = db
    add_memory(cognition, "public-ryan", text="Ryan 在中央公园维持日常训练。")
    add_memory(cognition, "private-ryan", text="Ryan 私下记录的巡逻缺口。",
               secrecy="private", disclosure_scope="player_dialogue")
    add_memory(cognition, "secret-ryan", text="Ryan 掌握的封锁线秘密。",
               memory_type="reflection", secrecy="secret", disclosure_scope="internal_only")
    add_memory(cognition, "public-shir", owner="shir", text="Shir 在星辉酒馆的公开见闻。")
    project_player_turn(cognition, "我在旧封锁线捡到一枚刻字铜牌")
    stored = tuple(cognition.scalars(select(Memory).where(Memory.owner_npc_id == "ryan")))
    assert {row.memory_type for row in stored} >= {"knowledge", "conversation", "reflection"}
    expected = public_memory_ids(cognition)
    assert len(expected) >= 2
    cognition.rollback()

    data = build_service(db).get_explanations("ryan")

    assert data.npc_id == "ryan"
    assert {str(item.id) for item in data.memories} == expected
    assert memory_id("public-ryan") in expected
    assert set(data.model_dump()) == {"npc_id", "retrieval_mode", "fallback_used", "memories"}
    serialized = data.model_dump_json()
    for hidden in ("我在旧封锁线捡到一枚刻字铜牌", "Ryan 私下记录的巡逻缺口。",
                   "Ryan 掌握的封锁线秘密。", "Shir 在星辉酒馆的公开见闻。"):
        assert hidden not in serialized


def test_projected_player_conversation_never_reaches_the_public_surface(db):
    _, cognition = db
    project_player_turn(cognition, "只有你知道：我把铜牌藏在低语森林的石堆下")
    conversation = cognition.scalar(select(Memory).where(
        Memory.owner_npc_id == "ryan", Memory.memory_type == "conversation"))
    assert conversation is not None
    assert (conversation.secrecy, conversation.disclosure_scope) == ("private", "player_dialogue")
    assert "铜牌" in conversation.content
    cognition.rollback()

    data = build_service(db).get_explanations("ryan")

    assert data.memories
    assert all(item.type != "conversation" for item in data.memories)
    assert str(conversation.id) not in {str(item.id) for item in data.memories}
    assert "铜牌" not in data.model_dump_json()


def test_conversation_source_projects_a_fixed_non_verbatim_summary(db):
    """Unreachable through PUBLIC_EXPLANATION today; pinned for a future widening."""
    stub = StubRetriever(retrieved(memory_type="conversation", source_label="player_claim",
        content="玩家原始秘密文本"))

    data = build_service(db, retriever=stub).get_explanations("ryan")

    assert len(data.memories) == 1
    assert data.memories[0].type == "conversation"
    assert data.memories[0].source.kind == "conversation"
    assert data.memories[0].summary == CONVERSATION_SUMMARY
    assert "玩家原始秘密文本" not in data.model_dump_json()


@pytest.mark.parametrize("memory_type,source_label,kind,label", [
    ("episodic", "observed_event", "world_event", "亲历事件"),
    ("knowledge", "authored_knowledge", "authored_knowledge", "稳定知识"),
    ("reflection", "reflection", "reflection", "形成的看法"),
])
def test_source_label_maps_to_the_fixed_public_vocabulary(db, memory_type, source_label, kind, label):
    stub = StubRetriever(retrieved(memory_type=memory_type, source_label=source_label,
        content="一段可以公开说明的记忆。"))

    data = build_service(db, retriever=stub).get_explanations("ryan")

    assert len(data.memories) == 1
    assert data.memories[0].type == memory_type
    assert data.memories[0].source.kind == kind
    assert data.memories[0].source.label == label
    assert data.memories[0].summary == "一段可以公开说明的记忆。"


def test_unrecognised_source_label_is_a_service_error(db):
    stub = StubRetriever(retrieved(source_label="unregistered_label"))

    with pytest.raises(MemoryExplanationUnavailableError) as error:
        build_service(db, retriever=stub).get_explanations("ryan")

    assert "unregistered_label" not in str(error.value)


def test_fixed_query_combines_npc_detail_and_public_quest_context(db):
    authoritative, _ = db
    reader = PlayerQuestChatContextReader(PlayerQuestRepository(authoritative),
                                          MissingChildQuestPolicy())
    quest = reader.get_chat_context()
    assert quest is not None
    stub = StubRetriever(retrieved())

    build_service(db, retriever=stub, quest_context_reader=reader).get_explanations("ryan")

    assert len(stub.requests) == 1
    request = stub.requests[0]
    assert request.scope is RetrievalScope.PUBLIC_EXPLANATION
    assert (request.world_id, request.owner_npc_id) == (WORLD_ID, "ryan")
    assert (request.limit, request.char_budget) == (RETRIEVAL_LIMIT, RETRIEVAL_CHAR_BUDGET)
    assert (RETRIEVAL_LIMIT, RETRIEVAL_CHAR_BUDGET) == (5, 1200)
    assert request.allowed_memory_types == frozenset(MemoryType)
    assert request.excluded_turn_ids == frozenset()
    for expected in ("Ryan", "Knight", "中央公园", quest.quest_objective, quest.location_name):
        assert expected in request.query_text


def test_reason_text_prefers_semantic_relevance_only_in_hybrid_mode(db):
    dominant_semantic = retrieved(semantic=0.9, lexical=0.0, recency=0.1,
                                  importance=0.0, confidence=0.0)

    hybrid = build_service(db, retriever=StubRetriever(dominant_semantic)).get_explanations("ryan")
    degraded = build_service(db, retriever=StubRetriever(dominant_semantic,
        mode="lexical_fallback")).get_explanations("ryan")

    assert (hybrid.retrieval_mode, hybrid.fallback_used) == ("hybrid", False)
    assert (degraded.retrieval_mode, degraded.fallback_used) == ("lexical_fallback", True)
    assert "含义" in hybrid.memories[0].reason_text
    assert degraded.memories[0].reason_text != hybrid.memories[0].reason_text
    assert "含义" not in degraded.memories[0].reason_text


def test_zero_semantic_contribution_is_explained_with_the_lexical_template_set(db):
    """Pins the documented boundary: an exactly-zero score counts as unscored.

    The two component sets order these same numbers differently, so the reason
    text alone reveals which set explained the memory.
    """
    ranked = dict(lexical=0.0, recency=0.7, importance=0.9, confidence=0.0)

    unscored = build_service(db, retriever=StubRetriever(
        retrieved(semantic=0.0, **ranked))).get_explanations("ryan")
    scored = build_service(db, retriever=StubRetriever(
        retrieved(semantic=0.001, **ranked))).get_explanations("ryan")

    assert (unscored.retrieval_mode, scored.retrieval_mode) == ("hybrid", "hybrid")
    assert "格外重要" in unscored.memories[0].reason_text
    assert "刚刚发生" in scored.memories[0].reason_text


@pytest.mark.parametrize("changes,expected", [
    (dict(semantic=0.0, lexical=0.9, recency=0.1, importance=0.0, confidence=0.0), "关键信息"),
    (dict(semantic=0.0, lexical=0.0, recency=0.9, importance=0.0, confidence=0.0), "刚刚发生"),
    (dict(semantic=0.0, lexical=0.0, recency=0.1, importance=0.9, confidence=0.0), "格外重要"),
    (dict(semantic=0.0, lexical=0.0, recency=0.0, importance=0.0, confidence=0.9), "来源"),
])
def test_reason_text_names_the_dominant_public_component(db, changes, expected):
    stub = StubRetriever(retrieved(**changes))

    data = build_service(db, retriever=stub).get_explanations("ryan")

    assert expected in data.memories[0].reason_text
    assert not any(character.isdigit() for character in data.memories[0].reason_text)


def test_public_list_is_capped_at_five_memories(db):
    _, cognition = db
    for index in range(8):
        add_memory(cognition, f"public-{index}", text=f"Ryan 公开记忆 {'训练' * (index + 1)}")
    assert len(public_memory_ids(cognition)) == 9
    cognition.rollback()

    data = build_service(db).get_explanations("ryan")

    assert len(data.memories) == RETRIEVAL_LIMIT == 5
    assert len({str(item.id) for item in data.memories}) == 5


def test_long_public_summary_is_truncated_instead_of_failing_validation(db):
    _, cognition = db
    long_id = add_memory(cognition, "long-public", text="灰" * 400)
    cognition.rollback()

    data = build_service(db).get_explanations("ryan")

    truncated = next(item for item in data.memories if str(item.id) == long_id)
    assert len(truncated.summary) == SUMMARY_MAX_LENGTH == 240
    assert truncated.summary.endswith("…")
    assert truncated.summary.startswith("灰灰灰")


def test_failed_catch_up_degrades_and_still_reads_projected_memories(db, caplog):
    _, cognition = db
    public = add_memory(cognition, "public-ryan", text="Ryan 在中央公园维持日常训练。")
    cognition.rollback()

    class LeakingCognition:
        def __init__(self, repository):
            self.repository, self.calls = repository, 0

        def catch_up_owner(self, world_id, owner_npc_id, *,
                           message_upper_bound=None, include_enrichment=True):
            self.calls += 1
            # A failed catch-up may abandon an open read transaction, which the
            # retriever refuses; the service must release it before reading.
            self.repository.session.execute(select(Memory.id))
            raise RuntimeError("cognition dsn password leak")

    failing = LeakingCognition(CognitionRepository(cognition))
    with caplog.at_level("WARNING"):
        data = build_service(db, cognition=failing).get_explanations("ryan")

    assert failing.calls == 1
    assert public in {str(item.id) for item in data.memories}
    assert "cognition dsn password leak" not in caplog.text


def test_memory_read_failure_returns_a_safe_unavailable_error(db):
    authoritative, cognition = db

    class FailingRepository(CognitionRepository):
        def allowed_memories(self, request):
            raise RuntimeError("secret dsn password")

    service = MemoryExplanationService(
        NpcRepository(authoritative),
        MemoryRetriever(FailingRepository(cognition), DeterministicEmbeddingProvider()),
    )

    with pytest.raises(MemoryExplanationUnavailableError) as error:
        service.get_explanations("ryan")

    assert "secret dsn password" not in str(error.value)


def test_unknown_npc_keeps_the_not_found_contract(db):
    with pytest.raises(NpcNotFoundError):
        build_service(db).get_explanations("missing-npc")


def test_public_explanation_writes_nothing_to_the_authoritative_world(db):
    authoritative, cognition = db
    add_memory(cognition, "public-ryan", text="Ryan 在中央公园维持日常训练。")
    cognition.rollback()

    data = build_service(db).get_explanations("ryan")

    assert data.memories
    cognition.rollback()
    rows = tuple(authoritative.scalars(select(Memory).where(Memory.owner_npc_id == "ryan")))
    assert rows
    assert all(row.access_count == 0 and row.last_accessed_at is None for row in rows)
    world = authoritative.get(WorldState, WORLD_ID)
    assert (world.world_version, world.clock_tick, world.event_sequence) == (0, 0, 0)


def test_degraded_embedding_provider_still_explains_public_memories(db):
    _, cognition = db
    public = add_memory(cognition, "public-ryan", text="Ryan 在中央公园维持日常训练。")
    cognition.rollback()

    class FailingProvider(DeterministicEmbeddingProvider):
        def embed(self, text, *, timeout_seconds=None):
            raise EmbeddingProviderError("embedding unavailable")

    service = MemoryExplanationService(
        NpcRepository(db[0]),
        MemoryRetriever(CognitionRepository(cognition), FailingProvider()),
    )
    data = service.get_explanations("ryan")

    assert data.retrieval_mode == "lexical_fallback"
    assert data.fallback_used is True
    assert public in {str(item.id) for item in data.memories}
