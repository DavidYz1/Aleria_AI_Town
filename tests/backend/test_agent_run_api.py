from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import create_app
from scripts.seed_world import seed_database


@pytest.mark.anyio
async def test_tick_persists_readable_ordered_runtime_graph(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        response = await client.post("/api/world/tick", json={"expected_world_version": 0})
        assert response.status_code == 200
        data = response.json()["data"]
        assert "run" in data
        run = data["run"]
        assert str(UUID(run["id"])) == run["id"]
        assert {k: v for k, v in run.items() if k != "id"} == {
            "mode": "deterministic", "trigger_type": "world_advance", "status": "completed",
            "base_world_version": 0, "resulting_world_version": 1,
            "base_clock_tick": 0, "resulting_clock_tick": 1,
        }
        detail = await client.get(f"/api/agent-runs/{run['id']}")
        assert detail.status_code == 200
        graph = detail.json()["data"]
        assert set(graph) == {"run", "proposals", "events", "trace"}
        assert graph["run"] == run
        assert [p["ordinal"] for p in graph["proposals"]] == [0, 1, 2]
        assert [p["actor_id"] for p in graph["proposals"]] == ["ryan", "shir", "grey"]
        assert [e["event_sequence"] for e in graph["events"]] == [1, 2, 3]
        # 默认 runtime_mode=auto，三个 NPC 各产生一条 planning trace（spec §11），
        # 位置固定在 run_started 之后，因此总数由 14 变为 17。
        assert [t["sequence"] for t in graph["trace"]] == list(range(1, 18))
        assert [t["stage"] for t in graph["trace"][:4]] == [
            "run_started", "planning", "planning", "planning",
        ]
        assert [t["actor_id"] for t in graph["trace"][1:4]] == ["ryan", "shir", "grey"]
        assert all(a["status"] == "executed" for a in data["actions"])
        assert graph["events"] == data["events"]


@pytest.mark.anyio
@pytest.mark.parametrize("run_id,status", [("bad-id", 422), ("00000000-0000-0000-0000-000000000001", 404)])
async def test_run_read_validation_and_missing(database_url, seed_dir, run_id, status):
    seed_database(database_url, seed_dir)
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        response = await client.get(f"/api/agent-runs/{run_id}")
    assert response.status_code == status
    if status == 404:
        assert response.json() == {"success":False,"data":None,"message":"agent run not found"}


@pytest.mark.anyio
async def test_run_read_database_failure_is_safe_503(database_url):
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url), raise_app_exceptions=False), base_url="http://test") as client:
        response = await client.get("/api/agent-runs/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 503
    assert response.json() == {"success": False, "data": None, "message": "agent run is unavailable"}


@pytest.mark.anyio
async def test_player_events_share_gap_free_sequence_with_runs(database_url, seed_dir):
    from sqlalchemy import select
    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.models import Event
    seed_database(database_url, seed_dir)
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        quest = await client.post("/api/quests/missing-child/interact", json={"interaction":"accept_quest", "expected_version":0, "expected_world_version":0})
        assert quest.status_code == 200
        travel = await client.post("/api/player/travel", json={"target_location_id":"castle", "expected_world_version":1})
        assert travel.status_code == 200
        same = await client.post("/api/player/travel", json={"target_location_id":"castle", "expected_world_version":2})
        assert same.status_code == 200
        tick = await client.post("/api/world/tick", json={"expected_world_version":2})
        assert tick.status_code == 200
    _, factory = create_engine_and_session(database_url)
    with factory() as session:
        events = list(session.scalars(select(Event).order_by(Event.id)))
        assert [e.event_type for e in events] == ["quest_transitioned", "player_travelled", "npc_action", "npc_action", "npc_action"]
        assert [e.event_sequence for e in events] == [1,2,3,4,5]
        assert [e.world_version for e in events] == [1,2,3,3,3]
        assert [e.clock_tick for e in events] == [0,0,1,1,1]
        assert events[1].payload_json == {"player_id":"default-player", "from_location_id":"tavern", "to_location_id":"castle"}
        assert events[0].actor_id is events[0].action_id is events[0].source_event_id is None


@pytest.mark.anyio
async def test_run_detail_redacts_provider_metadata_and_untrusted_trace_text(database_url, seed_dir):
    from sqlalchemy import select
    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.models import AgentRun, AgentTraceEntry, ActionProposalRecord, Event
    seed_database(database_url, seed_dir)
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        tick = await client.post("/api/world/tick", json={"expected_world_version":0})
        run_id = tick.json()["data"]["run"]["id"]
        _, factory = create_engine_and_session(database_url)
        with factory() as session:
            run = session.get(AgentRun, run_id)
            run.error_code = "PRIVATE-CREDENTIAL"
            trace = session.scalar(select(AgentTraceEntry).where(AgentTraceEntry.run_id==run_id))
            trace.summary = "PRIVATE-REASONING"
            trace.data_json = {"world_version":0,"prompt":"PRIVATE-PROMPT", "credentials":{"api_key":"PRIVATE-KEY"}, "chain_of_thought":"PRIVATE-THOUGHT"}
            proposal = session.scalar(select(ActionProposalRecord).where(ActionProposalRecord.run_id==run_id))
            proposal.rejection_message = "PRIVATE-EXCEPTION"
            stored_event = session.scalar(select(Event).where(Event.run_id==run_id))
            stored_event.payload_json = {**stored_event.payload_json, "raw_exception":"PRIVATE-RAW"}
            session.commit()
        response = await client.get(f"/api/agent-runs/{run_id}")
    assert response.status_code == 200
    assert "PRIVATE-" not in response.text
    assert response.json()["data"]["trace"][0]["data"] == {}


@pytest.mark.anyio
async def test_run_detail_redacts_out_of_shape_allowed_fact_values(database_url, seed_dir):
    from sqlalchemy import select
    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.models import AgentTraceEntry, ActionProposalRecord, Event
    seed_database(database_url, seed_dir)
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        tick = await client.post("/api/world/tick", json={"expected_world_version":0})
        run_id = tick.json()["data"]["run"]["id"]
        _, factory = create_engine_and_session(database_url)
        with factory() as session:
            proposal = session.scalar(select(ActionProposalRecord).where(ActionProposalRecord.run_id == run_id))
            proposal.payload_json = {"reason_code": "PRIVATE-CREDENTIAL"}
            event = session.scalar(select(Event).where(Event.run_id == run_id))
            event.description = "PRIVATE-PROMPT"
            event.payload_json = {**event.payload_json, "before": "PRIVATE-REASONING"}
            trace = session.scalar(select(AgentTraceEntry).where(AgentTraceEntry.run_id == run_id, AgentTraceEntry.stage == "execution"))
            trace.data_json = {"proposal_ordinal": 0, "before": ["PRIVATE-THOUGHT"]}
            session.commit()
        response = await client.get(f"/api/agent-runs/{run_id}")

    assert response.status_code == 200
    assert "PRIVATE-" not in response.text
    assert response.json()["data"]["proposals"][0]["payload"] == {}
    assert response.json()["data"]["events"][0]["description"] == "Runtime event recorded"
    # 按 stage 定位而不是按下标：trace 拓扑会随 runtime_mode 变化，
    # 写死下标会让这条隐私断言在拓扑变动后悄悄指向别的条目。
    trace_items = response.json()["data"]["trace"]
    execution = next(item for item in trace_items if item["stage"] == "execution")
    assert execution["data"] == {}, "被污染的 execution trace 必须被清空"
    # 非空前提 + 判别力：脱敏必须是选择性的 —— 形状合法的 planning trace
    # 不能被一并清空，否则上一条断言在「全部清空」的实现下也会平凡通过。
    planning = [item for item in trace_items if item["stage"] == "planning"]
    assert len(planning) == 3
    assert all(item["data"].get("goal") and item["data"].get("thought") for item in planning)


@pytest.mark.anyio
async def test_run_detail_rejects_unsafe_rejected_proposal_target_kind_at_write_boundary(database_url, seed_dir):
    from dataclasses import replace
    from backend.app.agents.contracts import ActionProposal, ActionValidation, ResolvedProposal, TraceDraft
    from backend.app.agents.orchestrator import run_deterministic_advance
    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.world_clock_repository import WorldTickPersistenceError, WorldTickRepository

    seed_database(database_url, seed_dir)
    _, factory = create_engine_and_session(database_url)
    with factory() as session:
        repository = WorldTickRepository(session)
        result = run_deterministic_advance(repository.get_snapshot())
        rejected = ActionProposal(
            actor_id="unknown-npc",
            action_type="unregistered",
            target_kind="PRIVATE PROMPT TEXT",
            reason_code="invalid",
        )
        proposal_trace = TraceDraft(1, "proposal", "unknown-npc", "Action proposed", {
            "action_type": "unregistered",
            "target": {"kind": rejected.target_kind, "id": rejected.target_id},
            "reason_code": "invalid", "proposal_ordinal": 3, "source": "deterministic",
        })
        validation_trace = TraceDraft(1, "validation", "unknown-npc", "Proposal validated", {
            "proposal_ordinal": 3, "accepted": False, "code": "unknown_actor",
        })
        complete_traces = (
            result.traces[0],
            *(trace for trace in result.traces if trace.stage == "proposal"),
            proposal_trace,
            *(trace for trace in result.traces if trace.stage == "validation"),
            validation_trace,
            *(trace for trace in result.traces if trace.stage in {"execution", "event"}),
            replace(result.traces[-1], data={**result.traces[-1].data, "rejected_count": 1}),
        )
        result = replace(
            result,
            proposals=(*result.proposals, rejected),
            resolutions=(*result.resolutions, ResolvedProposal(rejected, ActionValidation(False, "unknown_actor", "unavailable"))),
            traces=tuple(
                replace(trace, sequence=sequence)
                for sequence, trace in enumerate(complete_traces, 1)
            ),
        )
        with pytest.raises(WorldTickPersistenceError):
            repository.persist_run(str(UUID("00000000-0000-0000-0000-000000000011")), 0, result)

    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        response = await client.get("/api/agent-runs/00000000-0000-0000-0000-000000000011")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_run_detail_rejects_unsafe_event_causation_reference_at_write_boundary(database_url, seed_dir):
    from dataclasses import replace
    from backend.app.agents.orchestrator import run_deterministic_advance
    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.world_clock_repository import WorldTickPersistenceError, WorldTickRepository

    seed_database(database_url, seed_dir)
    _, factory = create_engine_and_session(database_url)
    with factory() as session:
        repository = WorldTickRepository(session)
        result = run_deterministic_advance(repository.get_snapshot())
        result = replace(result, events=(replace(result.events[0], causation_id="PRIVATE CREDENTIAL TEXT"), *result.events[1:]))
        with pytest.raises(WorldTickPersistenceError):
            repository.persist_run(str(UUID("00000000-0000-0000-0000-000000000012")), 0, result)

    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        response = await client.get("/api/agent-runs/00000000-0000-0000-0000-000000000012")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_public_quest_event_keeps_valid_interaction_fact(database_url, seed_dir):
    from sqlalchemy import select
    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.models import Event
    from backend.app.schemas.agent_run import DomainEventInfo

    seed_database(database_url, seed_dir)
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        response = await client.post(
            "/api/quests/missing-child/interact",
            json={"interaction": "accept_quest", "expected_version": 0, "expected_world_version": 0},
        )
    assert response.status_code == 200
    _, factory = create_engine_and_session(database_url)
    with factory() as session:
        event = session.scalar(select(Event).where(Event.event_type == "quest_transitioned"))

    assert event is not None
    assert DomainEventInfo.model_validate(event).payload == {
        "player_id": "default-player",
        "quest_id": "missing-child",
        "from_status": "available",
        "to_status": "accepted",
        "interaction": "accept_quest",
        "location_id": "tavern",
    }


@pytest.mark.anyio
async def test_run_detail_sanitizes_corrupted_target_and_causation_references(database_url, seed_dir):
    from sqlalchemy import select
    from backend.app.database.connection import create_engine_and_session
    from backend.app.database.models import ActionProposalRecord, Event

    seed_database(database_url, seed_dir)
    async with AsyncClient(transport=ASGITransport(app=create_app(database_url)), base_url="http://test") as client:
        tick = await client.post("/api/world/tick", json={"expected_world_version": 0})
        run_id = tick.json()["data"]["run"]["id"]
        _, factory = create_engine_and_session(database_url)
        with factory() as session:
            proposal = session.scalar(select(ActionProposalRecord).where(ActionProposalRecord.run_id == run_id))
            proposal.target_kind = "PRIVATE PROMPT TEXT"
            proposal.target_id = "PRIVATE CREDENTIAL TEXT"
            event = session.scalar(select(Event).where(Event.run_id == run_id))
            event.causation_id = "PRIVATE CREDENTIAL TEXT"
            session.commit()
        response = await client.get(f"/api/agent-runs/{run_id}")

    assert response.status_code == 200
    assert "PRIVATE " not in response.text
    assert response.json()["data"]["proposals"][0]["target_kind"] is None
    assert response.json()["data"]["proposals"][0]["target_id"] is None
    assert response.json()["data"]["events"][0]["causation_id"] is None
