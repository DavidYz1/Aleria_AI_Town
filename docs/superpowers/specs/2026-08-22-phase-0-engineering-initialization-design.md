# Phase 0 Engineering Initialization Design

Version: v1.0

Last Updated: 2026-08-22

## 1. Goal

Initialize the Aleria AI Town monorepo and deliver the first vertical slice:

```text
SQLite -> FastAPI GET /api/world -> Vue 3 frontend -> town overview
```

The frontend must display:

- 晨曦镇
- current day and time
- two locations
- Ryan, Shir, and Grey with their basic runtime state
- loading, success, empty, and request-failure states

## 2. Scope

### Included

- Root project structure: `frontend/`, `backend/`, `docs/`, `data/`, `prompts/`, `tests/`, and `scripts/`.
- Git repository initialization and a project `.gitignore`.
- FastAPI backend with a versioned application boundary and CORS for the local Vite origin.
- SQLite runtime persistence from the first phase.
- Readable JSON seed files under root `data/`; JSON is seed/config input, not runtime state storage.
- A seed script that creates the minimum Phase 0 tables and idempotently inserts the initial world.
- `GET /api/world` using the common API response envelope.
- Vue 3 + TypeScript + Vite frontend using a typed API adapter and Pinia world store.
- A CSS/DOM town overview only; no canvas renderer.
- Backend API tests and frontend store/component tests for the first vertical slice.
- Minimal local startup documentation and `.env.example` without secrets.

### Excluded

- World tick and NPC action execution.
- LLM providers and NPC decision calls.
- NPC detail and chat endpoints.
- PixiJS, Canvas, Cocos, sprites, or animation.
- Quest, RAG, vector retrieval, complex memory, relationships, multiplayer, authentication, and deployment infrastructure.

These exclusions are sequencing decisions, not removals from the long-term design.

## 3. Authoritative Naming and Types

The following names are canonical for implementation and supersede conflicting examples in earlier design documents:

- World counter: `tick`; do not use `round` in code or API payloads.
- NPC occupation field: `role`; do not expose `class` or `occupation` in the Phase 0 API.
- Location reference: `location_id`, always a stable string identifier.
- NPC needs: `energy`, `mood`, and `social`, each an integer from 0 through 100.
- Current behavior: `current_action`, using a canonical action identifier.
- IDs: stable lowercase kebab-case strings in the API and SQLite database.
- World display name: `晨曦镇`; world identifier: `aleria-town`.

The canonical future action set is:

```text
move, rest, work, eat, social
```

Phase 0 stores only an initial `current_action`; it does not implement action transitions.

## 4. Repository Structure

```text
Aleria_AI_Town/
├── .env.example
├── .gitignore
├── README.md
├── backend/
│   ├── __init__.py
│   ├── requirements.txt
│   ├── data/
│   │   └── aleria.db
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── world.py
│       ├── core/
│       │   ├── __init__.py
│       │   └── config.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── connection.py
│       │   ├── models.py
│       │   └── world_repository.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── common.py
│       │   ├── seed.py
│       │   └── world.py
│       └── services/
│           ├── __init__.py
│           └── world_service.py
├── data/
│   ├── locations.json
│   ├── npcs.json
│   └── world.json
├── docs/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── api/world.ts
│       ├── components/LocationCard.vue
│       ├── components/NpcCard.vue
│       ├── stores/world.ts
│       ├── types/world.ts
│       ├── views/TownView.vue
│       ├── App.vue
│       └── main.ts
├── prompts/
├── scripts/
│   └── seed_world.py
└── tests/
    ├── backend/
    │   ├── conftest.py
    │   ├── test_seed_world.py
    │   └── test_world_api.py
    └── frontend/
        ├── TownView.spec.ts
        └── world.spec.ts
```

Empty future subsystem packages are not created in Phase 0.

## 5. Runtime Data Model

SQLite is the only runtime source of truth. Root JSON files are human-readable seed inputs.

### `world_state`

| Column | Type | Constraint |
| --- | --- | --- |
| `id` | text | primary key |
| `name` | text | not null |
| `day` | integer | not null, at least 1 |
| `time` | text | not null, `HH:MM` |
| `tick` | integer | not null, at least 0 |

### `locations`

| Column | Type | Constraint |
| --- | --- | --- |
| `id` | text | primary key |
| `name` | text | not null |
| `description` | text | not null |
| `sort_order` | integer | not null, unique display order |

### `npc_profiles`

| Column | Type | Constraint |
| --- | --- | --- |
| `id` | text | primary key |
| `name` | text | not null |
| `role` | text | not null |
| `personality_json` | text | not null, JSON array |
| `sort_order` | integer | not null, unique display order |

### `npc_states`

| Column | Type | Constraint |
| --- | --- | --- |
| `npc_id` | text | primary key, foreign key to `npc_profiles.id` |
| `location_id` | text | not null, foreign key to `locations.id` |
| `current_action` | text | not null |
| `energy` | integer | not null, 0-100 |
| `mood` | integer | not null, 0-100 |
| `social` | integer | not null, 0-100 |

The current location exists only in `npc_states`; it is not duplicated in the profile table.

## 6. Initial Seed Data

The initial world is deterministic:

- World: `aleria-town`, display name `晨曦镇`, day 1, time `08:00`, tick 0.
- Locations: `tavern` / `星辰酒馆` at sort order 1 and `park` / `中央公园` at sort order 2.
- Ryan: sort order 1, Knight, at `park`, `rest`, energy 80, mood 78, social 70.
- Shir: sort order 2, Assassin, at `tavern`, `eat`, energy 72, mood 65, social 35.
- Grey: sort order 3, Guardian, at `park`, `work`, energy 88, mood 74, social 55.

The seed script is idempotent: rerunning it leaves one record per stable identifier and restores the declared initial values.

## 7. API Contract

### Request

```http
GET /api/world
```

### Success

```json
{
  "success": true,
  "data": {
    "world": {
      "id": "aleria-town",
      "name": "晨曦镇",
      "day": 1,
      "time": "08:00",
      "tick": 0
    },
    "locations": [
      {
        "id": "tavern",
        "name": "星辰酒馆",
        "description": "冒险者交流和休息的地方"
      },
      {
        "id": "park",
        "name": "中央公园",
        "description": "居民散步和放松的地方"
      }
    ],
    "npcs": [
      {
        "id": "ryan",
        "name": "Ryan",
        "role": "Knight",
        "personality": ["optimistic", "brave", "kind"],
        "location_id": "park",
        "current_action": "rest",
        "status": {
          "energy": 80,
          "mood": 78,
          "social": 70
        }
      },
      {
        "id": "shir",
        "name": "Shir",
        "role": "Assassin",
        "personality": ["quiet", "introverted", "observant"],
        "location_id": "tavern",
        "current_action": "eat",
        "status": {
          "energy": 72,
          "mood": 65,
          "social": 35
        }
      },
      {
        "id": "grey",
        "name": "Grey",
        "role": "Guardian",
        "personality": ["reliable", "calm", "protective"],
        "location_id": "park",
        "current_action": "work",
        "status": {
          "energy": 88,
          "mood": 74,
          "social": 55
        }
      }
    ]
  },
  "message": "ok"
}
```

`locations` and `npcs` are ordered by persisted `sort_order` to keep the initial demo deterministic.

### Database unavailable or uninitialized

```json
{
  "success": false,
  "data": null,
  "message": "world state is unavailable"
}
```

The endpoint returns HTTP 503 for this condition. Internal exception details are logged by the backend and are not returned to the client.

## 8. Backend Boundaries

- `api/world.py` handles HTTP routing and response status only.
- `world_service.py` owns the application use case and maps repository records to the public response schema.
- `world_repository.py` owns read queries and returns domain-shaped records without FastAPI dependencies.
- `models.py` defines Phase 0 SQLAlchemy persistence models only.
- `schemas/world.py` defines the public Pydantic v2 API contract.
- `connection.py` owns engine and session lifecycle.
- `config.py` reads configuration; no other module reads environment variables directly.

No API handler reads SQLite directly.

## 9. Frontend Boundaries and Future Migration

- `api/world.ts` is the only module that knows the backend URL and response envelope.
- `stores/world.ts` owns loading, success, empty, and error state.
- `TownView.vue` composes presentation components and does not call HTTP directly.
- Location and NPC components consume typed props and contain no domain mutations.
- The frontend never changes world or NPC state locally.

A future open-source frontend migration replaces components, styling, assets, and the renderer. It must preserve the API adapter and store boundary. Backend DTOs are not redesigned to match a downloaded template.

## 10. Data Flow

```text
Application start
    -> seed script has created SQLite state
    -> Vue TownView mounts
    -> Pinia world store enters loading
    -> typed API adapter requests GET /api/world
    -> FastAPI route calls WorldService
    -> WorldService calls WorldRepository
    -> repository reads one world, two locations, and three joined NPC states
    -> Pydantic serializes the public contract
    -> store records success or a user-facing error
    -> TownView renders the corresponding state
```

## 11. Error Handling

- Missing or invalid seed JSON: the seed script exits non-zero and identifies the invalid record.
- Missing database tables or world row: repository raises a domain-specific unavailable error; API returns HTTP 503 with the common failure envelope.
- Frontend network or non-success response: store clears stale world data and exposes a concise retryable message.
- Empty location or NPC arrays: frontend renders an explicit empty-state message rather than a blank page.

## 12. Testing Strategy

TDD applies to behavior code.

Backend tests use a temporary SQLite database with real SQLAlchemy sessions and the FastAPI test client. They verify:

- the endpoint returns the declared envelope and HTTP 200;
- the payload contains exactly two seeded locations and Ryan, Shir, and Grey;
- status values are integers in the 0-100 range;
- an uninitialized database returns HTTP 503 and the safe failure envelope.

Frontend tests verify:

- the store exposes loading before the request resolves;
- a successful response renders 晨曦镇, the time, both locations, and all three NPCs;
- an API failure renders an understandable retryable error;
- an empty response renders an explicit empty state.

The final Phase 0 verification runs backend tests, frontend tests, frontend type checking, and the production frontend build. A manual local smoke check confirms the browser reaches the real backend rather than a mocked response.

## 13. Documentation Synchronization

Before implementation, update these documents so their canonical examples agree with this specification:

- `03_World_Model.md`: use `tick`, `role`, numeric needs, stable string IDs, and the canonical action set.
- `06_API_Contract.md`: replace the Phase 0 `GET /api/world` example with the complete response in this specification.
- `07_Database_Schema.md`: clarify string identifiers, remove duplicated current location, and mark tables by implementation phase.
- `09_Decision_Log.md`: record SQLite-from-Phase-0, JSON-as-seed-only, canonical contract naming, and renderer-independent frontend boundaries.
- `11_Project_Structure.md`: align backend package names and Phase 0 repository structure.
- `13_Development_Roadmap.md`: make Phase 0 a tested SQLite-to-frontend vertical slice and retain later features in later phases.
- `14_Development_Environment.md`: document the seed command, database path, and separate backend/frontend test commands.

The earlier documents remain historical design context; this specification is authoritative for Phase 0 when an older example conflicts with it.

## 14. Acceptance Criteria

Phase 0 is complete only when:

1. A fresh checkout can install documented dependencies and seed SQLite without secrets.
2. The backend starts and `GET /api/world` returns the exact public shape defined above.
3. The frontend starts and displays 晨曦镇, `Day 1 08:00`, two locations, and Ryan/Shir/Grey.
4. Loading, empty, and API-error states are visible and tested.
5. Backend tests, frontend tests, TypeScript checks, and the frontend production build all pass.
6. No PixiJS, Quest, RAG, complex Memory, or multiplayer code is present.
