import importlib
from pathlib import Path

import pytest
from sqlalchemy import delete

from backend.app.database.chat_repository import ChatRepository
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import NpcState, QuestProgress
from backend.app.database.npc_repository import NpcNotFoundError, NpcRepository
from backend.app.database.world_tick_repository import WorldTickRepository
from backend.app.services.chat_context import (
    ChatContextAssembler,
    PromptLoader,
    PromptUnavailableError,
)
from backend.app.world.tick_engine import run_tick
from scripts.seed_world import seed_database


CONVERSATION_ID = "5e547c21-a228-4e86-940d-a1bf5d65702f"


def _persist_six_turns(repository: ChatRepository) -> None:
    for turn_number in range(1, 7):
        repository.persist_turn(
            conversation_id=CONVERSATION_ID,
            create_conversation=turn_number == 1,
            npc_id="ryan",
            world_id="aleria-town",
            world_tick=4,
            user_content=f"user-{turn_number}",
            assistant_content=f"assistant-{turn_number}",
            emotion="guarded",
            provider="mock",
            fallback_used=False,
            prompt_version="v1",
        )


def _write_prompt_tree(root: Path, character_content: str = "Ryan") -> None:
    characters = root / "v1" / "characters"
    characters.mkdir(parents=True)
    (root / "v1" / "world_lore.md").write_text(
        "艾莱瑞亚世界背景",
        encoding="utf-8",
    )
    (root / "v1" / "chat_system.md").write_text(
        "只返回安全的角色回复",
        encoding="utf-8",
    )
    (root / "v1" / "player_context.md").write_text(
        "玩家是初次来到小镇的旅行者",
        encoding="utf-8",
    )
    (characters / "ryan.md").write_text(
        character_content,
        encoding="utf-8",
    )


def test_prompt_loader_reads_non_empty_versioned_assets_for_known_npcs():
    loader = PromptLoader()

    for version in ("v1", "v2"):
        for npc_id, npc_name in [
            ("ryan", "Ryan"),
            ("shir", "Shir"),
            ("grey", "Grey"),
        ]:
            bundle = loader.load(version=version, npc_id=npc_id)
            assert bundle.world_lore.strip()
            assert bundle.chat_system_prompt.strip()
            assert bundle.player_context.strip()
            assert npc_name in bundle.character_prompt

    v2_bundle = loader.load(version="v2", npc_id="ryan")
    assert "曦谷" in v2_bundle.world_lore
    assert "旅行者" in v2_bundle.player_context


@pytest.mark.parametrize(
    ("version", "npc_id"),
    [
        ("v3", "ryan"),
        ("../v1", "ryan"),
        ("v1", "../world_lore"),
        ("v1", "unknown"),
    ],
)
def test_prompt_loader_rejects_unknown_or_traversal_paths(version, npc_id):
    with pytest.raises(
        PromptUnavailableError,
        match="^Chat context is unavailable$",
    ):
        PromptLoader().load(version=version, npc_id=npc_id)


@pytest.mark.parametrize("character_content", [None, "", "   "])
def test_prompt_loader_rejects_missing_or_empty_assets(
    tmp_path,
    character_content,
):
    prompt_root = tmp_path / "prompts"
    if character_content is not None:
        _write_prompt_tree(prompt_root, character_content)

    with pytest.raises(PromptUnavailableError):
        PromptLoader(prompt_root).load(version="v1", npc_id="ryan")


def test_prompt_loader_maps_invalid_utf8_asset_to_unavailable(tmp_path):
    prompt_root = tmp_path / "prompts"
    _write_prompt_tree(prompt_root)
    (prompt_root / "v1" / "characters" / "ryan.md").write_bytes(b"\xff")

    with pytest.raises(
        PromptUnavailableError,
        match="^Chat context is unavailable$",
    ):
        PromptLoader(prompt_root).load(version="v1", npc_id="ryan")


def test_context_assembler_uses_authoritative_state_actions_and_bounded_history(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        tick_repository = WorldTickRepository(session)
        for _ in range(4):
            snapshot = tick_repository.get_snapshot()
            tick_repository.persist_tick(snapshot.tick, run_tick(snapshot))

        chat_repository = ChatRepository(session)
        _persist_six_turns(chat_repository)
        context = ChatContextAssembler(
            NpcRepository(session),
            chat_repository,
            PromptLoader(),
        ).assemble(
            npc_id="ryan",
            conversation_id=CONVERSATION_ID,
            player_message="当前情况怎么样？",
            history_limit=10,
            prompt_version="v1",
        )

    assert context.npc_id == "ryan"
    assert context.npc_name == "Ryan"
    assert context.role == "Knight"
    assert context.personality == ("optimistic", "brave", "kind")
    assert context.world_id == "aleria-town"
    assert context.world_name == "曦谷"
    assert (
        context.world_day,
        context.world_time,
        context.world_tick,
        context.time_phase,
    ) == (1, "12:00", 4, "day")
    assert (
        context.location_id,
        context.location_name,
        context.current_action,
    ) == ("park", "中央公园", "work")
    assert (context.energy, context.mood, context.social) == (40, 66, 58)
    assert [action.tick for action in context.recent_actions] == [4, 3, 2]
    assert [action.reason_code for action in context.recent_actions] == [
        "knight_training",
        "knight_training",
        "knight_training",
    ]
    assert len(context.conversation_history) == 10
    assert context.conversation_history[0].content == "user-2"
    assert context.conversation_history[-1].content == "assistant-6"
    assert context.player_message == "当前情况怎么样？"
    assert context.player_message not in context.chat_system_prompt
    assert context.player_message not in context.world_lore
    assert context.player_message not in context.player_context_prompt
    assert context.player_message not in context.character_prompt
    assert context.player_quest_context is None


def test_context_assembler_includes_optional_read_only_player_quest_context(
    database_url,
    seed_dir,
):
    class StubPlayerQuestContextReader:
        def __init__(self, player_quest_context):
            self.player_quest_context = player_quest_context

        def get_chat_context(self):
            return self.player_quest_context

    player_quest_context = object()
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        context = ChatContextAssembler(
            NpcRepository(session),
            ChatRepository(session),
            PromptLoader(),
            player_quest_context_reader=StubPlayerQuestContextReader(
                player_quest_context,
            ),
        ).assemble(
            npc_id="grey",
            conversation_id=None,
            player_message="有什么线索？",
            history_limit=10,
            prompt_version="v2",
        )

    assert context.player_quest_context is player_quest_context


def test_context_assembler_uses_empty_history_for_new_conversation(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        context = ChatContextAssembler(
            NpcRepository(session),
            ChatRepository(session),
            PromptLoader(),
        ).assemble(
            npc_id="shir",
            conversation_id=None,
            player_message="你好",
            history_limit=10,
            prompt_version="v1",
        )

    assert context.conversation_history == ()
    assert context.npc_name == "Shir"


def test_context_assembler_maps_missing_authoritative_state_to_unavailable(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        state = session.get(NpcState, "ryan")
        assert state is not None
        session.delete(state)
        session.commit()

        assembler = ChatContextAssembler(
            NpcRepository(session),
            ChatRepository(session),
            PromptLoader(),
        )
        with pytest.raises(
            PromptUnavailableError,
            match="^Chat context is unavailable$",
        ):
            assembler.assemble(
                npc_id="ryan",
                conversation_id=None,
                player_message="你好",
                history_limit=10,
                prompt_version="v1",
            )


def test_context_assembler_preserves_unknown_npc_not_found(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        assembler = ChatContextAssembler(
            NpcRepository(session),
            ChatRepository(session),
            PromptLoader(),
        )
        with pytest.raises(NpcNotFoundError, match="^NPC not found$"):
            assembler.assemble(
                npc_id="missing-npc",
                conversation_id=None,
                player_message="你好",
                history_limit=10,
                prompt_version="v1",
            )


def test_player_quest_chat_context_reader_returns_summary_or_none(
    database_url,
    seed_dir,
):
    try:
        reader_module = importlib.import_module(
            "backend.app.services.player_quest_context"
        )
    except ModuleNotFoundError:
        pytest.fail("player quest chat context reader is missing")

    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        reader = reader_module.PlayerQuestChatContextReader(
            reader_module.PlayerQuestRepository(session),
            reader_module.MissingChildQuestPolicy(),
        )
        context = reader.get_chat_context()

        session.execute(delete(QuestProgress))
        session.commit()
        unavailable = reader.get_chat_context()

    assert context is not None
    assert (
        context.player_id,
        context.location_id,
        context.location_name,
        context.quest_id,
        context.quest_status,
        context.quest_objective,
    ) == (
        "default-player",
        "tavern",
        "星辉酒馆",
        "missing-child",
        "available",
        "查看星辉酒馆的委托板。",
    )
    assert unavailable is None
