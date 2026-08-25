import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Conversation,
    ConversationMessage,
    Event,
    NpcState,
    PlayerState,
    QuestEvent,
    QuestProgress,
    WorldAction,
    WorldState,
)
from backend.app.llm.mock import MockChatProvider
from backend.app.main import create_app
from scripts.seed_world import seed_database


@pytest.mark.anyio
async def test_reset_demo_restores_canonical_state_and_removes_demo_history(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    app = create_app(database_url, chat_provider=MockChatProvider())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        accepted = await client.post(
            "/api/quests/missing-child/interact",
            json={"interaction": "accept_quest", "expected_version": 0},
        )
        ticked = await client.post(
            "/api/world/tick",
            json={"expected_tick": 0},
        )
        chatted = await client.post(
            "/api/npcs/ryan/chat",
            json={"conversation_id": None, "message": "你好"},
        )
        travelled = await client.post(
            "/api/player/travel",
            json={"target_location_id": "castle"},
        )
        response = await client.post("/api/demo/reset")

    assert accepted.status_code == 200
    assert ticked.status_code == 200
    assert chatted.status_code == 200
    assert travelled.status_code == 200
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "world_id": "aleria-town",
            "world_tick": 0,
            "player_location_id": "tavern",
            "quest_status": "available",
        },
        "message": "Demo world reset",
    }

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")
        player = session.get(PlayerState, "default-player")
        quest = session.get(
            QuestProgress,
            ("default-player", "missing-child"),
        )
        history_counts = {
            "actions": session.scalar(
                select(func.count()).select_from(WorldAction)
            ),
            "events": session.scalar(select(func.count()).select_from(Event)),
            "quest_events": session.scalar(
                select(func.count()).select_from(QuestEvent)
            ),
            "conversations": session.scalar(
                select(func.count()).select_from(Conversation)
            ),
            "messages": session.scalar(
                select(func.count()).select_from(ConversationMessage)
            ),
        }

    assert world is not None
    assert (world.day, world.time, world.tick) == (1, "08:00", 0)
    assert ryan is not None
    assert (
        ryan.location_id,
        ryan.current_action,
        ryan.energy,
        ryan.mood,
        ryan.social,
    ) == ("park", "rest", 80, 78, 70)
    assert player is not None
    assert player.location_id == "tavern"
    assert quest is not None
    assert (
        quest.status,
        quest.version,
        quest.updated_tick,
    ) == ("available", 0, 0)
    assert history_counts == {
        "actions": 0,
        "events": 0,
        "quest_events": 0,
        "conversations": 0,
        "messages": 0,
    }
