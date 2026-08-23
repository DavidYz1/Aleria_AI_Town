# Phase 1B NPC Detail and Explainability Design

## Goal

Phase 1B completes the NPC information slice required by the assignment. A player can select Ryan, Shir, or Grey and inspect that NPC's profile, authoritative runtime state, current world context, and three most recent persisted actions with deterministic, human-readable explanations.

The implementation extends the current modular-monolith read side. It does not change World Tick behavior, add a database table, or introduce an LLM/Agent/Memory subsystem.

## Scope

In scope:

- `GET /api/npcs/{npc_id}`.
- NPC profile: ID, name, role, and personality traits.
- Current state: location, current action, energy, mood, and social.
- Current world context: day, time, tick, and `morning`/`day`/`evening`/`night` phase.
- The NPC's three most recent actions, newest first.
- Resolved target display names and deterministic Chinese reason text.
- An accessible responsive NPC detail panel.
- Loading, empty history, not-found, unavailable, retry, close, rapid-selection, and Tick-refresh behavior.

Out of scope:

- NPC Chat and player input.
- LLM or Mock Provider integration.
- Prompt files and character prompt authoring.
- Memory, Relationship, Background, Goal, Reflection, or full Decision Trace persistence.
- PixiJS, Quest, multiplayer, authentication, and new database tables.

## User experience

Each NPC card exposes an accessible selection control. Selecting a card opens an `aside` detail panel beside the town content on desktop and below it on narrow screens. The panel is not a modal and does not introduce focus-trap or overlay behavior.

The panel contains:

1. Name, role, and personality traits.
2. Current location, current action, and three numeric needs.
3. Current Day/time and time phase.
4. Up to three recent actions with time, action label, target name, and explanation.

Before the first Tick, the action-history section displays a legitimate empty state instead of synthesizing history from seed state. The seed `current_action` remains visible as current state but is not represented as a persisted historical action.

If the selected NPC remains open when a Tick succeeds or the world is refreshed after a conflict, the detail is reloaded from the Backend. Rapidly selecting Ryan and then Shir must never allow a slower Ryan response to overwrite Shir's panel.

## API contract

### Request

```http
GET /api/npcs/{npc_id}
```

`npc_id` uses the existing stable lowercase ID. Phase 1B has no `limit` query parameter; the assignment-defined limit is exactly three.

### Success response

```json
{
  "success": true,
  "data": {
    "profile": {
      "id": "ryan",
      "name": "Ryan",
      "role": "Knight",
      "personality": ["optimistic", "brave", "kind"]
    },
    "state": {
      "location_id": "park",
      "location_name": "中央公园",
      "current_action": "work",
      "status": {
        "energy": 70,
        "mood": 75,
        "social": 67
      }
    },
    "world_context": {
      "day": 1,
      "time": "09:00",
      "tick": 1,
      "time_phase": "morning"
    },
    "recent_actions": [
      {
        "id": 1,
        "tick": 1,
        "world_time": "09:00",
        "action_type": "work",
        "target_kind": null,
        "target_id": null,
        "target_name": null,
        "reason_code": "knight_duty",
        "reason_text": "上午是骑士履行训练职责的时间。"
      }
    ]
  },
  "message": "ok"
}
```

The endpoint does not return `relationships`, because no relationship model is implemented. It does not return duplicate Event rows: the assignment requests action history, and the linked Event does not add information to this view.

### Error responses

- HTTP 404 with the common error envelope when the NPC profile does not exist.
- HTTP 503 with the common error envelope when the canonical world, NPC state, current location, or database is unavailable.
- A profile without a corresponding state is incomplete data (503), not a missing NPC (404).

Stable messages:

- 404: `NPC not found`
- 503: `NPC detail is unavailable`

## Backend architecture

Phase 1B adds a narrow read-model slice:

```text
GET /api/npcs/{npc_id}
        ↓
NpcService
        ↓
NpcRepository + action explanation function
        ↓
SQLite profile/state/location/world/actions
```

Responsibilities:

- `backend/app/database/npc_repository.py`: execute ordered read queries and return repository dataclasses. It does not produce Pydantic schemas or user-facing Chinese text.
- `backend/app/services/action_explanation.py`: pure, deterministic conversion from stored reason code plus action context to Chinese reason text.
- `backend/app/services/npc_service.py`: resolve target display names, calculate time phase using the existing World clock, and map records into API schemas.
- `backend/app/schemas/npc.py`: define the public response models.
- `backend/app/api/npcs.py`: map not-found and unavailable domain errors to HTTP responses.

The existing `WorldTickRepository` remains dedicated to Tick snapshot/persistence. Phase 1B must not add NPC Detail queries to it. The existing World read/Tick mapping duplication is acknowledged but is not refactored in this phase because the NPC endpoint is a narrow query and the stable World Tick path should not be disturbed without a concrete consumer benefit.

## Action explanation contract

The database keeps the existing `actions.reason` value as a stable machine code. The API exposes it as `reason_code` and adds derived `reason_text`; the Tick API remains backward compatible and continues exposing its current `reason` field.

Every currently emitted reason code must have an explicit Chinese template:

- `night_rest`
- `low_energy`
- `low_social_with_companion`
- `low_social_find_companion`
- `low_mood_eat`
- `low_mood_find_food`
- `knight_duty_travel`
- `knight_duty`
- `knight_evening_social`
- `knight_evening_rest`
- `assassin_meal_travel`
- `assassin_meal`
- `guardian_patrol_travel`
- `guardian_patrol`
- `unknown_role_rest`

Templates may interpolate resolved target names but must not recalculate a historical decision from the NPC's current post-action state. Unknown historical codes use the safe fallback `按照当时的世界规则执行了该行动。` rather than failing the entire detail request.

This explanation is an auditable rule summary, not hidden chain-of-thought and not a full Agent Trace.

## Query and data rules

- Profile lookup is by exact stable NPC ID.
- The canonical world is `aleria-town`.
- Recent actions use `WHERE world_id = 'aleria-town' AND actor_id = :npc_id ORDER BY tick DESC, id DESC LIMIT 3`.
- The existing `(actor_id, tick)` index supports this access pattern; Phase 1B adds no migration.
- Location target names come from `locations`; NPC target names come from `npc_profiles`.
- Target names are resolved in a bounded batch, not with one query per action.
- If a historical polymorphic target can no longer be resolved, the API preserves `target_id` and uses that ID as `target_name` rather than dropping the record.
- Numeric status values continue to use the existing 0–100 API constraints.

## Frontend architecture

Phase 1B adds an independent NPC detail slice:

- `frontend/src/types/npc.ts`: API DTO types.
- `frontend/src/api/npc.ts`: `fetchNpcDetail(npcId)` only.
- `frontend/src/stores/npcDetail.ts`: selection, loading, error, data, close, retry, refresh, and latest-request protection.
- `frontend/src/components/NpcDetailPanel.vue`: presentational panel with no network calls.

`NpcCard.vue` emits selection and does not call the API. `TownView.vue` coordinates the World Store and NPC Detail Store. The World Store must not import or mutate the NPC Detail Store.

The detail store uses a monotonically increasing request token. Only the response belonging to the current selected NPC and latest token may update `data`, `loading`, or `error`. Closing the panel invalidates an in-flight request.

When the authoritative world Tick changes and an NPC remains selected, `TownView` asks the detail store to refresh. This preserves store independence while preventing stale state/history after Tick success or conflict reload.

## Testing strategy

Backend behavior tests:

- Known NPC returns exact profile, state, location name, and world phase.
- No history returns an empty list.
- Four or more actions return exactly the newest three in deterministic order.
- Location and NPC targets are resolved without losing IDs.
- Every current reason code produces stable non-empty explanation text.
- Unknown reason codes use the fallback.
- Unknown NPC returns 404.
- Missing state/location/world and uninitialized database return 503.
- Existing `GET /api/world` and `POST /api/world/tick` contracts remain unchanged.

Frontend behavior tests:

- Selecting an NPC shows loading and then authoritative detail.
- Empty action history is announced clearly.
- 404 and general failure expose retry and keep the selected identity.
- Close clears selection and invalidates the current request.
- A late response for a previously selected NPC cannot overwrite the current selection.
- Action target and explanation are rendered.
- After Tick changes, the open detail refreshes and shows the latest action first.
- Existing Town, Tick, Store, type-check, and production-build validation remains green.

## Acceptance criteria

Phase 1B is complete when:

1. Clicking Ryan, Shir, or Grey opens the same reusable detail panel with their distinct data.
2. The panel displays authoritative current state and current world phase.
3. It displays zero to three persisted actions, newest first, with readable target names and deterministic explanations.
4. A successful Tick refreshes an open panel without race-induced stale data.
5. 404, unavailable, loading, empty-history, retry, and close states are covered by tests.
6. No database table, Chat, LLM, Memory, Relationship, PixiJS, Quest, or multiplayer implementation is introduced.
7. Backend tests, Frontend tests, TypeScript checking, and production build all pass.
8. Code and documentation changes are left uncommitted for human review.
