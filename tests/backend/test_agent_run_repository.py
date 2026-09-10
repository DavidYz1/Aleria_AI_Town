from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, text

from backend.app.agents.contracts import ActionProposal, ActionValidation, ResolvedProposal, TraceDraft
from backend.app.agents.orchestrator import run_deterministic_advance
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import AgentRun, ActionProposalRecord, AgentTraceEntry, Event, NpcState, WorldAction, WorldState
from backend.app.database.world_clock_repository import WorldTickRepository, WorldTickConflictError, WorldTickPersistenceError
from backend.app.services.demo_reset_service import DemoResetService, load_seed_data
from scripts.seed_world import seed_database


@pytest.fixture
def factory(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    return create_engine_and_session(database_url)[1]


def counts(session):
    return tuple(session.scalar(select(func.count()).select_from(model)) for model in (AgentRun, ActionProposalRecord, WorldAction, Event, AgentTraceEntry))


@pytest.mark.parametrize("mutation,stage", [
    ("boundaries_only", None),
    *(("missing", stage) for stage in ("proposal", "validation", "execution", "event")),
    *(("duplicate", stage) for stage in ("run_started", "proposal", "validation", "execution", "event", "run_completed")),
    ("reordered_ordinals", "proposal"),
    ("reordered_phases", "validation"),
    ("reordered_execution_event", "execution"),
])
def test_incomplete_or_duplicate_trace_topology_is_rejected_before_writes(factory, mutation, stage):
    with factory() as session:
        repository = WorldTickRepository(session)
        base = repository.get_snapshot()
        result = run_deterministic_advance(base)
        traces = list(result.traces)
        if mutation == "boundaries_only":
            traces = [traces[0], traces[-1]]
        else:
            index = next(i for i, trace in enumerate(traces) if trace.stage == stage)
            if mutation == "missing":
                traces.pop(index)
            elif mutation == "duplicate":
                traces.insert(index, traces[index])
            elif mutation in {"reordered_ordinals", "reordered_execution_event"}:
                traces[index], traces[index + 1] = traces[index + 1], traces[index]
            elif mutation == "reordered_phases":
                traces.insert(1, traces.pop(index))
        malformed = replace(result, traces=tuple(
            replace(trace, sequence=sequence)
            for sequence, trace in enumerate(traces, 1)
        ))
        writes = []

        def record_write(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                writes.append(statement)

        event.listen(session.bind, "before_cursor_execute", record_write)
        try:
            with pytest.raises(WorldTickPersistenceError):
                repository.persist_run(str(uuid4()), 0, malformed)
        finally:
            event.remove(session.bind, "before_cursor_execute", record_write)
        assert writes == []
        assert counts(session) == (0, 0, 0, 0, 0)
        # Includes all counters, day/time, every NPC location/action/need and locations.
        assert repository.get_snapshot() == base


def test_complete_graph_commits_once_and_preserves_rejected_proposals(factory):
    with factory() as session:
        repository = WorldTickRepository(session)
        result = run_deterministic_advance(repository.get_snapshot())
        rejected = ActionProposal(actor_id="unknown-npc", action_type="unregistered", reason_code="invalid")
        proposal_trace = TraceDraft(1, "proposal", "unknown-npc", "Action proposed", {
            "action_type": "unregistered", "target": None,
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
            resolutions=(*result.resolutions, ResolvedProposal(rejected, ActionValidation(False, "unknown_actor", "Actor is unavailable"))),
            traces=tuple(
                replace(trace, sequence=sequence)
                for sequence, trace in enumerate(complete_traces, 1)
            ),
        )
        commits = []
        event.listen(session, "after_commit", lambda _: commits.append(True))
        assert hasattr(repository, "persist_run")
        persisted = repository.persist_run(str(uuid4()), 0, result, correlation_id=str(uuid4()))
        assert commits == [True]
        assert counts(session) == (1,4,3,3,16)
        assert [(trace.stage, trace.data_json.get("proposal_ordinal")) for trace in session.scalars(
            select(AgentTraceEntry).order_by(AgentTraceEntry.sequence)
        )] == [
            ("run_started", None),
            ("proposal", 0), ("proposal", 1), ("proposal", 2), ("proposal", 3),
            ("validation", 0), ("validation", 1), ("validation", 2), ("validation", 3),
            ("execution", 0), ("event", 0), ("execution", 1), ("event", 1),
            ("execution", 2), ("event", 2), ("run_completed", None),
        ]
        assert [p.status for p in session.scalars(select(ActionProposalRecord).order_by(ActionProposalRecord.ordinal))] == ["accepted","accepted","accepted","rejected"]
        assert all(a.run_id == persisted.run.id and a.proposal_id is not None for a in persisted.actions)
        assert [e.payload_json["proposal_ordinal"] for e in persisted.events] == [0,1,2]
        assert all(e.correlation_id == persisted.run.correlation_id for e in persisted.events)
        assert [
            (
                e.location_id,
                e.perception_scope,
                e.participant_npc_ids_json,
                e.witness_npc_ids_json,
                e.professional_channels_json,
                e.attention_priority,
                e.is_critical,
            )
            for e in persisted.events
        ] == [
            ("park", "location", ["ryan"], ["ryan", "shir"], [], 0.25, 0),
            ("park", "location", ["shir"], ["ryan", "shir"], [], 0.25, 0),
            ("castle", "location", ["grey"], ["grey"], [], 0.25, 0),
        ]
        assert session.get(WorldState, "aleria-town").event_sequence == 3


def test_npc_target_event_persists_sorted_participants_and_location_witness_snapshot(factory):
    with factory() as session:
        ryan = session.get(NpcState, "ryan")
        shir = session.get(NpcState, "shir")
        assert ryan is not None and shir is not None
        ryan.social = 43
        shir.location_id = "park"
        shir.energy = 30
        session.commit()

        repository = WorldTickRepository(session)
        result = run_deterministic_advance(repository.get_snapshot())
        proposal = next(
            proposal for proposal in result.proposals if proposal.actor_id == "ryan"
        )
        assert (
            proposal.action_type,
            proposal.target_kind,
            proposal.target_id,
        ) == ("talk", "npc", "shir")

        persisted = repository.persist_run(str(uuid4()), 0, result)
        stored = next(event for event in persisted.events if event.actor_id == "ryan")

        assert stored.location_id == "park"
        assert stored.participant_npc_ids_json == ["ryan", "shir"]
        assert stored.participant_npc_ids_json == sorted(
            set(stored.participant_npc_ids_json)
        )
        assert stored.witness_npc_ids_json == ["ryan", "shir"]


@pytest.mark.parametrize("broken", ["version", "clock", "sequence", "npc", "resolution", "event", "trace", "empty_trace", "unknown_action", "event_reason", "event_target", "boolean_version"])
def test_malformed_result_rolls_back_everything(factory, broken):
    with factory() as session:
        repository = WorldTickRepository(session)
        result = run_deterministic_advance(repository.get_snapshot())
        if broken == "version": result = replace(result, world=replace(result.world, world_version=3))
        if broken == "clock": result = replace(result, world=replace(result.world, clock_tick=4))
        if broken == "sequence": result = replace(result, world=replace(result.world, event_sequence=9))
        if broken == "npc": result = replace(result, world=replace(result.world, npcs=(replace(result.world.npcs[0], location_id="missing"), *result.world.npcs[1:])))
        if broken == "resolution": result = replace(result, resolutions=result.resolutions[1:])
        if broken == "event": result = replace(result, events=tuple(reversed(result.events)))
        if broken == "trace": result = replace(result, traces=(replace(result.traces[0], sequence=2), *result.traces[1:]))
        if broken == "empty_trace": result = replace(result, traces=())
        if broken == "unknown_action":
            proposal = replace(result.proposals[0], action_type="unregistered")
            result = replace(result, proposals=(proposal,*result.proposals[1:]), resolutions=(replace(result.resolutions[0],proposal=proposal),*result.resolutions[1:]), events=(replace(result.events[0],payload={**result.events[0].payload,"action_type":"unregistered"}),*result.events[1:]))
        if broken == "event_reason": result = replace(result, events=(replace(result.events[0],payload={**result.events[0].payload,"reason_code":"fabricated"}),*result.events[1:]))
        if broken == "event_target": result = replace(result, events=(result.events[0],replace(result.events[1],payload={**result.events[1].payload,"target":{"kind":"location","id":"castle"}}),result.events[2]))
        if broken == "boolean_version": result = replace(result,world=replace(result.world,world_version=True))
        assert hasattr(repository, "persist_run")
        with pytest.raises(WorldTickPersistenceError):
            repository.persist_run(str(uuid4()), 0, result)
        assert counts(session) == (0,0,0,0,0)
        world = session.get(WorldState, "aleria-town")
        assert (world.world_version,world.clock_tick,world.event_sequence,world.time) == (0,0,0,"08:00")
        assert session.get(NpcState,"shir").location_id == "tavern"


def test_stale_run_leaves_no_history_and_events_continue_without_gaps(factory):
    with factory() as first, factory() as second:
        repo = WorldTickRepository(first)
        stale_repo = WorldTickRepository(second)
        stale = run_deterministic_advance(stale_repo.get_snapshot())
        assert hasattr(repo, "persist_run")
        repo.persist_run(str(uuid4()), 0, run_deterministic_advance(repo.get_snapshot()))
        with pytest.raises(WorldTickConflictError):
            stale_repo.persist_run(str(uuid4()), 0, stale)
        repo.persist_run(str(uuid4()), 1, run_deterministic_advance(repo.get_snapshot()))
    with factory() as session:
        assert counts(session) == (2,6,6,6,28)
        assert list(session.scalars(select(Event.event_sequence).order_by(Event.event_sequence))) == [1,2,3,4,5,6]


def test_database_insert_failure_rolls_back_cas_and_all_graph_rows(factory):
    with factory() as session:
        # A real database failure after inserts, not a mocked repository failure.
        session.execute(text("CREATE TRIGGER fail_trace BEFORE INSERT ON agent_trace_entries BEGIN SELECT RAISE(ABORT, 'test failure'); END"))
        session.commit()
        repo = WorldTickRepository(session)
        result = run_deterministic_advance(repo.get_snapshot())
        assert hasattr(repo, "persist_run")
        with pytest.raises(WorldTickPersistenceError): repo.persist_run(str(uuid4()), 0, result)
        assert counts(session) == (0,0,0,0,0)
        assert session.get(WorldState,"aleria-town").world_version == 0


def test_reset_deletes_runtime_graph_and_preserves_other_world(factory, seed_dir):
    with factory() as session:
        repo = WorldTickRepository(session)
        assert hasattr(repo, "persist_run")
        persisted = repo.persist_run(str(uuid4()), 0, run_deterministic_advance(repo.get_snapshot()))
        session.add(WorldState(id="other", name="Other", day=1,time="08:00",clock_tick=1,world_version=1,event_sequence=0))
        session.flush()
        other_id = str(uuid4())
        session.add(AgentRun(id=other_id,world_id="other",mode="deterministic",trigger_type="world_advance",status="completed",base_world_version=0,resulting_world_version=1,base_clock_tick=0,resulting_clock_tick=1,correlation_id=str(uuid4()),created_at=persisted.run.created_at,started_at=persisted.run.started_at,completed_at=persisted.run.completed_at))
        session.flush()
        other_proposal = ActionProposalRecord(run_id=other_id,ordinal=0,actor_id="ryan",action_type="work",reason_code="knight_training",source="deterministic",payload_json={},status="accepted")
        session.add(other_proposal)
        session.flush()
        other_action = WorldAction(world_id="other",run_id=other_id,proposal_id=other_proposal.id,actor_id="ryan",action_type="work",reason_code="knight_training",clock_tick=1,world_version=1,world_time="09:00")
        session.add(other_action)
        session.flush()
        session.add(Event(world_id="other",run_id=other_id,action_id=other_action.id,actor_id="ryan",event_type="npc_action",world_version=1,clock_tick=1,event_sequence=1,description="Other world action",world_time="09:00",payload_json={},correlation_id=str(uuid4())))
        session.add(AgentTraceEntry(run_id=other_id,sequence=1,stage="run_completed",actor_id=None,summary="Completed",data_json={},visibility="private",created_at=persisted.run.created_at))
        session.get(WorldState,"other").event_sequence = 1
        session.commit()
        DemoResetService(session).reset(load_seed_data(seed_dir))
        assert counts(session) == (1,1,1,1,1)
        assert session.get(AgentRun, other_id) is not None
        assert session.get(WorldState,"other").event_sequence == 1
        world = session.get(WorldState,"aleria-town")
        assert (world.world_version,world.clock_tick,world.event_sequence) == (0,0,0)


def test_travel_refreshes_event_counter_after_another_session_advances(factory):
    from backend.app.database.player_quest_repository import PlayerQuestRepository
    with factory() as first, factory() as second:
        # Keep an older world object alive in the session identity map.
        old_world = first.get(WorldState,"aleria-town")
        player_repo = PlayerQuestRepository(first)
        player_repo.get_state("default-player","missing-child")
        repo = WorldTickRepository(second)
        repo.persist_run(str(uuid4()), 0, run_deterministic_advance(repo.get_snapshot()))
        assert old_world.event_sequence == 0
        player_repo.travel("default-player","missing-child","castle",1)
    with factory() as session:
        assert list(session.scalars(select(Event.event_sequence).order_by(Event.event_sequence))) == [1,2,3,4]
        assert session.get(WorldState,"aleria-town").event_sequence == 4


@pytest.mark.parametrize("broken", ["target", "current_action", "state_effect", "event_type", "trace_actor", "trace_ordinal", "trace_boolean", "causation_type"])
def test_malformed_graph_is_rejected_before_any_database_write(factory, broken):
    with factory() as session:
        repo = WorldTickRepository(session)
        result = run_deterministic_advance(repo.get_snapshot())
        if broken == "target":
            proposal = replace(result.proposals[1], target_id="missing-place")
            result = replace(result, proposals=(result.proposals[0],proposal,result.proposals[2]), resolutions=(result.resolutions[0],replace(result.resolutions[1],proposal=proposal),result.resolutions[2]), events=(result.events[0],replace(result.events[1],payload={**result.events[1].payload,"target":{"kind":"location","id":"missing-place"}}),result.events[2]))
        if broken == "current_action": result = replace(result,world=replace(result.world,npcs=(replace(result.world.npcs[0],current_action="unregistered"),*result.world.npcs[1:])))
        if broken == "state_effect": result = replace(result,world=replace(result.world,npcs=(replace(result.world.npcs[0],energy=result.world.npcs[0].energy + 1),*result.world.npcs[1:])))
        if broken == "event_type": result = replace(result,events=(replace(result.events[0],event_type="invented_event"),*result.events[1:]))
        if broken == "trace_actor": result = replace(result,traces=(result.traces[0],replace(result.traces[1],actor_id="missing-actor"),*result.traces[2:]))
        if broken == "trace_ordinal": result = replace(result,traces=(result.traces[0],replace(result.traces[1],data={"proposal_ordinal":99}),*result.traces[2:]))
        if broken == "trace_boolean": result = replace(result,traces=(replace(result.traces[0],sequence=True),*result.traces[1:]))
        if broken == "causation_type": result = replace(result,events=(replace(result.events[0],causation_id=["invalid"]),*result.events[1:]))
        writes = []
        def record_write(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                writes.append(statement)
        event.listen(session.bind, "before_cursor_execute", record_write)
        try:
            with pytest.raises(WorldTickPersistenceError):
                repo.persist_run(str(uuid4()), 0, result)
            assert writes == []
        finally:
            event.remove(session.bind, "before_cursor_execute", record_write)
        assert counts(session) == (0,0,0,0,0)


def test_runtime_events_preserve_causation_visibility_and_json_facts(factory):
    with factory() as session:
        repo = WorldTickRepository(session)
        result = run_deterministic_advance(repo.get_snapshot())
        cause = str(uuid4())
        result = replace(result, events=(replace(result.events[0],causation_id=cause,visibility="private"), *result.events[1:]))
        persisted = repo.persist_run(str(uuid4()),0,result)
        session.expire_all()
        stored = session.get(Event,persisted.events[0].id)
        assert (stored.causation_id,stored.visibility,stored.secrecy) == (cause,"private","private")
        assert stored.payload_json == {"action_type":"work","target":None,"reason_code":"knight_training","proposal_ordinal":0}


def test_all_rejected_runtime_still_records_completed_run_and_all_traces(factory):
    from backend.app.agents.action_registry import ActionRegistry
    registry = ActionRegistry(())
    with factory() as session:
        repo = WorldTickRepository(session,registry=registry)
        result = run_deterministic_advance(repo.get_snapshot(),registry=registry)
        persisted = repo.persist_run(str(uuid4()),0,result)
        assert persisted.run.status == "completed"
        assert counts(session) == (1,3,0,0,8)
        assert session.get(WorldState,"aleria-town").event_sequence == 0
        assert [p.rejection_code for p in session.scalars(select(ActionProposalRecord).order_by(ActionProposalRecord.ordinal))] == ["unknown_action","unknown_action","unknown_action"]


def test_submitted_wait_resolution_controls_runtime_effects(factory):
    """A legal submitted proposal must be replayed, not replaced by policy output."""
    with factory() as session:
        repository = WorldTickRepository(session)
        base = repository.get_snapshot()
        result = run_deterministic_advance(base)
        ryan = base.npcs[0]
        wait = replace(
            result.proposals[0],
            action_type="wait",
            reason_code="manual_wait",
        )
        drifted_ryan = replace(
            ryan,
            energy=max(0, ryan.energy - 2),
            mood=max(0, ryan.mood - 1),
            social=max(0, ryan.social - 3),
        )
        mismatch = replace(
            result,
            proposals=(wait, *result.proposals[1:]),
            resolutions=(replace(result.resolutions[0], proposal=wait), *result.resolutions[1:]),
            events=(
                replace(
                    result.events[0],
                    payload={
                        "action_type": "wait",
                        "target": None,
                        "reason_code": "manual_wait",
                        "proposal_ordinal": 0,
                    },
                ),
                *result.events[1:],
            ),
        )
        accepted_wait = replace(
            mismatch,
            world=replace(
                mismatch.world,
                npcs=(drifted_ryan, *mismatch.world.npcs[1:]),
            ),
            traces=tuple(
                replace(
                    trace,
                    data={
                        "action_type": "wait",
                        "target": None,
                        "reason_code": "manual_wait",
                        "proposal_ordinal": 0,
                        "source": "deterministic",
                    },
                ) if trace.stage == "proposal" and trace.actor_id == "ryan" else
                replace(
                    trace,
                    data={
                        "proposal_ordinal": 0,
                        "action_type": "wait",
                        "before": {
                            "location_id": drifted_ryan.location_id,
                            "current_action": drifted_ryan.current_action,
                            "energy": drifted_ryan.energy,
                            "mood": drifted_ryan.mood,
                            "social": drifted_ryan.social,
                        },
                        "after": {
                            "location_id": drifted_ryan.location_id,
                            "current_action": drifted_ryan.current_action,
                            "energy": drifted_ryan.energy,
                            "mood": drifted_ryan.mood,
                            "social": drifted_ryan.social,
                        },
                    },
                ) if trace.stage == "execution" and trace.actor_id == "ryan" else
                replace(trace, data={"proposal_ordinal": 0, "event_type": "npc_action"})
                if trace.stage == "event" and trace.actor_id == "ryan" else trace
                for trace in mismatch.traces
            ),
        )

        with pytest.raises(WorldTickPersistenceError):
            repository.persist_run(str(uuid4()), 0, mismatch)

        persisted = repository.persist_run(str(uuid4()), 0, accepted_wait)

    assert persisted.actions[0].action_type == "wait"


@pytest.mark.parametrize("record", ["proposal", "event", "trace"])
def test_runtime_facts_reject_unstructured_free_text_at_write_boundary(factory, record):
    """Only stage-specific factual shapes may cross the persistence boundary."""
    with factory() as session:
        repository = WorldTickRepository(session)
        result = run_deterministic_advance(repository.get_snapshot())
        if record == "proposal":
            proposal = replace(
                result.proposals[0],
                payload={"reason_code": "PRIVATE-CREDENTIAL"},
            )
            result = replace(
                result,
                proposals=(proposal, *result.proposals[1:]),
                resolutions=(replace(result.resolutions[0], proposal=proposal), *result.resolutions[1:]),
            )
        if record == "event":
            result = replace(
                result,
                events=(
                    replace(result.events[0], payload={**result.events[0].payload, "before": "PRIVATE-PROMPT"}),
                    *result.events[1:],
                ),
            )
        if record == "trace":
            trace = next(trace for trace in result.traces if trace.stage == "execution")
            result = replace(
                result,
                traces=tuple(
                    replace(trace, data={**trace.data, "before": ["PRIVATE-REASONING"]})
                    if candidate is trace else candidate
                    for candidate in result.traces
                ),
            )

        with pytest.raises(WorldTickPersistenceError):
            repository.persist_run(str(uuid4()), 0, result)


def test_runtime_event_description_is_derived_from_validated_facts(factory):
    with factory() as session:
        repository = WorldTickRepository(session)
        result = run_deterministic_advance(repository.get_snapshot())
        result = replace(
            result,
            events=(replace(result.events[0], description="PRIVATE-CREDENTIAL"), *result.events[1:]),
        )

        persisted = repository.persist_run(str(uuid4()), 0, result)

    assert persisted.events[0].description == "Ryan 工作"
