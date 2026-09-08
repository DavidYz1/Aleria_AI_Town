"""Opt-in acceptance: TEST_POSTGRES_URL must be a disposable test database.

This migrates and resets the demo world in that database; never use live data.
The fixture removes only the fresh schema it creates, never a database or volume.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import AgentRun, ActionProposalRecord, Event, WorldAction, WorldState
from backend.app.main import create_app
from scripts.seed_world import seed_database
from scripts.upgrade_schema import upgrade_schema


@pytest.mark.anyio
async def test_postgresql_pgvector_persists_one_complete_runtime(postgres_database_url, seed_dir):
    url = postgres_database_url
    engine, factory = create_engine_and_session(url)
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        upgrade_schema(url)
        seed_database(url, seed_dir)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'")) == "0.8.6"
        app = create_app(url)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/world/tick", json={"expected_world_version": 0})
                assert response.status_code == 200
                data = response.json()["data"]
                run_id = data["run"]["id"]
                assert data["run"]["status"] == "completed"
                assert len(data["actions"]) == 3
                detail = await client.get(f"/api/agent-runs/{run_id}")
                assert detail.status_code == 200
                graph = detail.json()["data"]
                assert [proposal["ordinal"] for proposal in graph["proposals"]] == [0, 1, 2]
                assert [event["event_sequence"] for event in graph["events"]] == [1, 2, 3]
                assert [trace["sequence"] for trace in graph["trace"]] == list(range(1, 15))
                assert graph["trace"][0]["stage"] == "run_started"
                assert graph["trace"][-1]["stage"] == "run_completed"
            with factory() as session:
                assert session.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.world_id == "aleria-town")) == 1
                for model in (ActionProposalRecord, WorldAction, Event):
                    assert session.scalar(select(func.count()).select_from(model).where(model.run_id == run_id)) == 3
                world = session.get(WorldState, "aleria-town")
                assert (world.world_version, world.clock_tick, world.event_sequence) == (1, 1, 3)
        finally:
            app.state.session_factory.kw["bind"].dispose()
    finally:
        engine.dispose()
