# Phase 1A Deterministic World Tick Design

## Goal and scope

Phase 1A adds one user-triggered, deterministic one-hour world tick to the Phase 0 vertical slice. A successful tick advances the town clock, lets Ryan, Shir, and Grey each choose one action from the same immutable world snapshot, validates and executes those actions, persists the new state plus history in one transaction, and returns the complete updated world.

In scope: `POST /api/world/tick`, deterministic NPC rules, numeric state changes, action/event history, optimistic concurrency, a frontend advance button, and visible tick results. Out of scope: LLM calls, prompts, memory/RAG, quests, PixiJS, NPC chat, multiplayer, and event sourcing.

## World clock and time phases

One tick equals one in-world hour. Time rolls over from `23:00` to `00:00` and increments the day. NPC rules use four half-open phases:

- `morning`: 06:00–11:59
- `day`: 12:00–17:59
- `evening`: 18:00–21:59
- `night`: 22:00–05:59

The clock is advanced before NPC decisions. Passive drift (`energy -2`, `mood -1`, `social -3`) is applied and clamped to 0–100 before the decision snapshot is built.

## Deterministic decision policy

All NPCs decide from the same immutable post-drift snapshot. Tie-breaking always uses persisted `sort_order`; decisions must not depend on database iteration order or other actions in the current tick.

Priority order:

1. At night, or when energy is at most 30, choose `rest`.
2. When social is at most 40, choose `social` with the lowest-order co-located NPC; if none is co-located, choose `move` to the location of the lowest-order other NPC.
3. When mood is at most 35, choose `eat` at the tavern or `move` to the tavern.
4. Apply role and phase routine:
   - Knight: `work` in the park during morning/day, moving there first; in evening socialize with a co-located NPC when possible, otherwise rest.
   - Assassin: `eat` in the tavern during morning/day/evening, moving there first.
   - Guardian: `work` in the park during morning/day/evening, moving there first.
   - Unknown roles: `rest`.

Each decision records a stable machine-readable reason. This policy is isolated behind a decision function so Phase 2 agents can replace it without changing tick orchestration.

## Actions and state effects

Allowed actions remain `move`, `rest`, `work`, `eat`, and `social`.

- `move`: target must be a valid location; set location; energy -5.
- `rest`: no target; energy +15; mood +2.
- `work`: no target and actor must be in the park; energy -8; mood -2.
- `eat`: no target and actor must be in the tavern; energy +5; mood +8.
- `social`: target must be a different NPC in the same snapshot location; energy -2; mood +5; social +15.

Every updated numeric value is clamped to 0–100. Each action updates only its actor. Therefore execution order cannot leak one NPC's current-tick changes into another NPC's outcome. Invalid actions abort the whole tick.

## Persistence and transaction boundary

Phase 1A adds append-only `actions` and `events` tables. `npc_states` and `world_state` remain the current-state projection. A transaction performs:

1. Load and verify the canonical world at `expected_tick`.
2. Build the deterministic tick result in memory.
3. Conditionally update `world_state` where `tick = expected_tick`.
4. Update all NPC states.
5. Insert one action and one linked event for every NPC.
6. Commit once; otherwise roll back everything.

`actions` has one row per `(world_id, tick, actor_id)`. It stores action type, optional polymorphic target kind/id, reason, status, and world time. `events` links one-to-one to an action and stores a deterministic human-readable description. No memory, relationship, snapshot, or generic entity tables are introduced.

## API contract

`POST /api/world/tick` request:

```json
{"expected_tick": 0}
```

Successful responses use the existing envelope and contain complete authoritative data:

```json
{
  "success": true,
  "data": {
    "world": {"world_id": "aleria-town", "name": "晨曦镇"},
    "actions": [],
    "events": []
  },
  "message": "ok"
}
```

The real `world` object is the complete existing `WorldData` schema. A stale `expected_tick` returns HTTP 409 with the existing error envelope. Missing/uninitialized world data returns 503. `GET /api/world` remains backward compatible.

## Frontend behavior

The town view adds a single “推进 1 小时” control. While a request is active it is disabled and displays progress. On success, the store replaces its world with the complete response and displays the tick's actions and events. A general failure preserves the last valid world. A 409 triggers a world reload and explains that another tick already advanced the state.

## Verification

Tests cover phase boundaries and day rollover, deterministic decisions, role/time routines, clamps and validation, same-snapshot behavior, transaction rollback, optimistic-concurrency conflict, API envelopes, frontend request state/error behavior, and action/event rendering. Existing Phase 0 tests must continue to pass.
