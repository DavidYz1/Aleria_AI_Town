from dataclasses import replace
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text

from backend.app.database.chat_repository import ChatRepository
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import (
    Base,
    Event,
    Location,
    NpcProfile,
    NpcState,
    WorldAction,
    WorldState,
)
from backend.app.database.world_clock_repository import (
    WorldTickPersistenceError,
    WorldTickRepository,
)
from backend.app.database.npc_repository import NpcRepository
from backend.app.main import create_app
from backend.app.services.chat_context import ChatContextAssembler, PromptLoader
from backend.app.world.tick_engine import run_tick
from scripts.seed_world import seed_database
from scripts.upgrade_schema import upgrade_schema


@pytest.mark.anyio
@pytest.mark.parametrize("path,payload,want", [
    ("/api/world/tick", {"expected_world_version": 0}, 5),
    ("/api/player/travel", {"target_location_id": "castle", "expected_world_version": 0}, 1),
    ("/api/quests/missing-child/interact", {"interaction": "accept_quest", "expected_version": 0, "expected_world_version": 0}, 1),
    ("/api/npcs/grey/chat", {"message": "A player claim"}, 1),
])
async def test_source_routes_explicitly_enable_post_commit_projection(database_url, seed_dir, path, payload, want):
    # Catches a service that works in isolation but is never enabled in production routes.
    from backend.app.core.config import Settings
    from backend.app.database.models import Observation
    seed_database(database_url, seed_dir)
    app = create_app(database_url, settings=Settings(_env_file=None, chat_provider="mock"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(path, json=payload)
    assert response.status_code == 200 and response.json()["success"] is True
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Observation)) == want


def test_tick_post_commit_failure_preserves_source_and_later_compensates(database_url, seed_dir, caplog):
    # Catches a missing hook, leaking its exception, or rolling back the source transaction.
    from backend.app.database.cognition_repository import CognitionRepository
    from backend.app.database.models import AgentCognitionState, AgentRun, Observation
    from backend.app.services.cognition_projection import CognitionProjectionService
    from backend.app.services.world_clock_service import WorldTickService
    from tests.backend.test_cognition_projection import FailingCoreRepository

    seed_database(database_url, seed_dir)
    engine, factory = create_engine_and_session(database_url)
    with factory() as session, factory() as cognition_session:
        service = WorldTickService(WorldTickRepository(session),
            cognition=CognitionProjectionService(FailingCoreRepository(cognition_session)))
        result = service.advance(0)
        assert result.world.world.world_version == 1
        assert len(result.actions) == len(result.events) == 3
        with factory() as observer:
            world = observer.get(WorldState, "aleria-town")
            assert (world.world_version, world.clock_tick, world.event_sequence) == (1, 1, 3)
            assert observer.scalar(select(func.count()).select_from(Event)) == 3
            assert observer.scalar(select(func.count()).select_from(AgentRun)) == 1
            assert observer.scalar(select(func.count()).select_from(Observation)) == 0
            assert observer.scalar(select(func.count()).select_from(AgentCognitionState)) == 0
        assert any(getattr(record, "category", None) == "core_projection" for record in caplog.records)
        assert "sensitive injected secret" not in caplog.text
        assert CognitionProjectionService(CognitionRepository(cognition_session)).catch_up_world("aleria-town").created_memories == 5
    engine.dispose()


@pytest.mark.anyio
async def test_tick_advances_world_and_records_three_actions_and_events(
    database_url, seed_dir
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["world"]["world"] == {
        "id": "aleria-town",
        "name": "曦谷",
        "day": 1,
        "time": "09:00",
        "world_version": 1,
        "clock_tick": 1,
        "event_sequence": 3,
    }
    assert [
        (action["actor_id"], action["action_type"], action["target_id"])
        for action in body["data"]["actions"]
    ] == [
        ("ryan", "work", None),
        ("shir", "move", "park"),
        ("grey", "work", None),
    ]
    assert len(body["data"]["events"]) == 3
    assert all(event["action_id"] for event in body["data"]["events"])
    assert all(
        "perception_scope" not in event for event in body["data"]["events"]
    )

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 3
        assert session.scalar(select(func.count()).select_from(Event)) == 3
        stored_events = tuple(
            session.scalars(select(Event).order_by(Event.event_sequence))
        )
        shir = session.get(NpcState, "shir")
        assert shir is not None
        assert (shir.location_id, shir.current_action, shir.energy) == (
            "park",
            "move",
            65,
        )
        assert [event.location_id for event in stored_events] == [
            "park", "park", "castle"
        ]
        assert [event.participant_npc_ids_json for event in stored_events] == [
            ["ryan"], ["shir"], ["grey"]
        ]


@pytest.mark.anyio
async def test_stale_expected_world_version_returns_409_without_duplicate_history(
    database_url, seed_dir
):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )
        stale = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )

    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json() == {
        "success": False,
        "data": None,
        "message": "world version conflict; refresh and retry",
    }

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None and world.clock_tick == 1
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 3
        assert session.scalar(select(func.count()).select_from(Event)) == 3


@pytest.mark.anyio
async def test_tick_exposes_and_persists_canonical_talk(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")
        grey = session.get(NpcState, "grey")
        assert world is not None and ryan is not None and grey is not None
        world.time = "17:00"
        ryan.social = 43
        grey.location_id = "park"
        session.commit()

    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/world/tick",
            json={"expected_world_version": 0},
        )
        current_world = await client.get("/api/world")
        current_ryan = await client.get("/api/npcs/ryan")

    assert response.status_code == 200
    body = response.json()["data"]
    ryan_action = next(
        action for action in body["actions"] if action["actor_id"] == "ryan"
    )
    ryan_state = next(
        npc for npc in body["world"]["npcs"] if npc["id"] == "ryan"
    )
    assert ryan_action["action_type"] == "talk"
    assert ryan_state["current_action"] == "talk"
    assert current_world.status_code == 200
    public_ryan = next(
        npc
        for npc in current_world.json()["data"]["npcs"]
        if npc["id"] == "ryan"
    )
    assert public_ryan["current_action"] == "talk"
    assert current_ryan.status_code == 200
    detail = current_ryan.json()["data"]
    assert detail["state"]["current_action"] == "talk"
    assert detail["recent_actions"][0]["action_type"] == "talk"

    with session_factory() as session:
        stored_action = session.scalar(
            select(WorldAction).where(WorldAction.actor_id == "ryan")
        )
        stored_state = session.get(NpcState, "ryan")
        assert stored_action is not None and stored_state is not None
        assert stored_action.action_type == "talk"
        assert stored_state.current_action == "talk"
        chat_context = ChatContextAssembler(
            NpcRepository(session),
            ChatRepository(session),
            PromptLoader(),
        ).assemble(
            npc_id="ryan",
            conversation_id=None,
            player_message="你在做什么？",
            history_limit=10,
            prompt_version="v1",
        )

    assert chat_context.current_action == "talk"
    assert chat_context.recent_actions[0].action_type == "talk"


def test_repository_rolls_back_clock_state_and_history_on_invalid_result(
    database_url, seed_dir
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        repository = WorldTickRepository(session)
        result = run_tick(repository.get_snapshot())
        broken_npc = replace(result.world.npcs[0], location_id="missing-place")
        broken_result = replace(
            result,
            world=replace(
                result.world,
                npcs=(broken_npc, *result.world.npcs[1:]),
            ),
        )

        with pytest.raises(WorldTickPersistenceError):
            repository.persist_tick(0, broken_result)

    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")
        assert world is not None and (world.time, world.clock_tick) == ("08:00", 0)
        assert ryan is not None and ryan.location_id == "park"
        assert session.scalar(select(func.count()).select_from(WorldAction)) == 0
        assert session.scalar(select(func.count()).select_from(Event)) == 0


@pytest.mark.anyio
async def test_tick_returns_503_when_database_is_uninitialized(database_url):
    transport = ASGITransport(app=create_app(database_url), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )

    assert response.status_code == 503
    assert response.json()["message"] == "world state is unavailable"


@pytest.mark.anyio
async def test_tick_rejects_partially_initialized_canonical_world(database_url):
    engine, session_factory = create_engine_and_session(database_url)
    Base.metadata.create_all(engine)
    with session_factory() as session:
        session.add(
            WorldState(
                id="aleria-town",
                name="晨曦镇",
                day=1,
                time="08:00",
                clock_tick=0,
                world_version=0,
                event_sequence=0,
            )
        )
        session.commit()

    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )

    assert response.status_code == 503
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None and world.clock_tick == 0


def test_schema_upgrade_adopts_legacy_schema_without_resetting_world_state(
    database_url,
):
    engine, session_factory = create_engine_and_session(database_url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0001")
    with engine.begin() as connection:
        connection.execute(
            text(
            "INSERT INTO world_state (id, name, day, time, tick) "
            "VALUES ('aleria-town', '晨曦镇', 7, '16:00', 44)"
            )
        )
        connection.execute(text("DROP TABLE alembic_version"))

    upgrade_schema(database_url)

    assert {"actions", "events"}.issubset(inspect(engine).get_table_names())
    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None
        assert (
            world.day,
            world.time,
            world.clock_tick,
            world.world_version,
            world.event_sequence,
        ) == (7, "16:00", 44, 44, 0)


@pytest.mark.anyio
async def test_tick_rejects_negative_expected_world_version(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/world/tick", json={"expected_world_version": -1}
        )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_tick_allows_documented_frontend_origin(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/world/tick",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]


@pytest.mark.anyio
async def test_get_world_matches_world_returned_by_latest_tick(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    transport = ASGITransport(app=create_app(database_url))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tick = await client.post(
            "/api/world/tick", json={"expected_world_version": 0}
        )
        current = await client.get("/api/world")

    assert tick.status_code == current.status_code == 200
    assert tick.json()["data"]["world"] == current.json()["data"]
