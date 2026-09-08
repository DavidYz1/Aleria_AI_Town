# Aleria AI Town Database Schema

Version: v2.0 · Updated: 2026-09-07

## Authority and modes

The implemented model is `backend/app/database/models.py`; versioned schema changes live in `backend/migrations/versions/`. Runtime facts are persisted through repositories. Root `data/*.json` files are seeds, not live state.

Local development and fast tests use SQLite. Docker uses PostgreSQL 17 with `pgvector/pgvector:0.8.6-pg17-bookworm`, accessed through Psycopg 3. Migration 0002 enables the `vector` extension on PostgreSQL only. No vector ORM columns, memory tables or embedding/retrieval features exist yet.

## Current tables

| Table | Main fields and relationships |
| --- | --- |
| `world_state` | Stable id/name, day/time, nonnegative world_version, clock_tick, event_sequence |
| `locations` | Stable id/name/description and unique sort_order |
| `npc_profiles` | Stable id/name/role, personality_json, unique sort_order |
| `npc_states` | NPC primary/foreign key, location foreign key, current_action, energy/mood/social in 0–100 |
| `player_states` | Fixed player id, world and location foreign keys, updated_at |
| `quest_progress` | Composite player_id/quest_id key, status, local version, updated_clock_tick, updated_at |
| `quest_events` | Player/quest transition, interaction, location, clock_tick, created_at |
| `agent_runs` | UUID string id, world_id, mode, trigger_type, status, base/resulting world_version and clock_tick, correlation_id, timestamps, optional error_code |
| `action_proposals` | run_id, ordinal, actor, action/target, reason_code, source, payload_json, status and rejection details |
| `actions` | world/run/proposal references, actor/action/target, reason_code, executed status, world_version, clock_tick, world_time, created_at |
| `events` | World/run/action/actor references, event type, world_version/clock_tick/event_sequence, structured payload_json, description, source/causation/correlation references, visibility/secrecy, timestamps |
| `agent_trace_entries` | run_id, sequence, stage, actor, factual summary/data_json, visibility, created_at |
| `conversations` | UUID string id, world/NPC boundary, created_clock_tick, timestamps |
| `conversation_messages` | Conversation foreign key, user/assistant role, content/emotion/provider/fallback/prompt metadata, clock_tick, timestamp |
| `alembic_version` | Current schema revision (head: 0003) |

Integer history IDs use autoincrement. JSON columns hold structured facts. SQLAlchemy uses timezone-aware timestamp declarations; public DTOs normalize SQLite's returned timestamps to UTC. API DTOs are deliberate projections, not raw table dumps.

## Runtime graph and constraints

```text
world_state -> agent_runs -> action_proposals -> actions -> events
                          -> agent_trace_entries
```

- Proposal `(run_id, ordinal)` and trace `(run_id, sequence)` are unique.
- Action `(world_id, clock_tick, actor_id)` is unique.
- Event `(world_id, event_sequence)` is unique; `action_id` is nullable and unique.
- Event actor/action/run references may be null for player travel or quest events.
- The registry owns legal action IDs, targets and effects. The database does not enumerate action IDs in a CHECK requiring a new migration for each action.
- The initial action registry is `move/rest/work/eat/talk/wait`; `social` is still the NPC needs column.

One successful advance commits the world/NPC state and complete runtime graph once. Failed or stale runs leave no partial graph. Persistence validates structured facts and effects, and the public API reconstructs safe factual summaries rather than exposing raw prompts, provider metadata or hidden reasoning.

## Concurrency and time

`world_version` is the compare-and-swap token for authoritative mutations. Advancement, actual travel and quest transitions increment it once. Only advancement increments `clock_tick`; chat changes neither. Event allocation shares the same transaction and produces a gap-free sequence per world. Quest transitions also use their local `quest_progress.version`.

All NPC proposals in one advance use one immutable snapshot. Persisted current state and history are separate; no historical world snapshot table or rollback/replay service exists.

## Migrations and seed behavior

From repository root, with the active environment selecting `DATABASE_URL`:

```bash
python -m scripts.upgrade_schema
python -m scripts.ensure_demo_world
```

The first command applies Alembic to head without resetting gameplay. The second seeds only when the demo world is absent. A supported, complete unversioned legacy schema is stamped at 0001 before migration. Partial/unrecognized unversioned schemas are rejected. Back up existing data before migration.

| Revision | Role |
| --- | --- |
| 0001 | Legacy baseline tables |
| 0002 | Distinct world_version/clock_tick/event_sequence; PostgreSQL vector extension |
| 0003 | Runtime graph, structured events/traces, legacy action/run backfill; social action renamed to talk |

Legacy actions/events are retained and associated with deterministic historical runs during backfill. A migration is not equivalent to SQLAlchemy `create_all`.

`python -m scripts.seed_world` and `POST /api/demo/reset` explicitly reset the target demo world, clearing its quest/chat/runtime history in foreign-key-safe order. Other worlds are preserved. Use `ensure_demo_world` for normal startup.

## Storage and acceptance

Compose stores PostgreSQL data in `aleria_postgres_data:/var/lib/postgresql/data`. The base database has no host port. The existing `aleria_data` SQLite volume is retained for explicitly configured SQLite deployments; there is no automatic SQLite-to-PostgreSQL gameplay-data transfer.

Fast tests create temporary SQLite databases. The two opt-in PostgreSQL tests use only `TEST_POSTGRES_URL`, which must identify a dedicated disposable database with schema/extension privileges. Each creates a unique empty `aleria_test_<uuid>` schema and uses its own search_path, ensuring both migration-from-zero and runtime acceptance are independent of test order. Cleanup drops only that test-owned schema, never the database or named Docker volume. A pre-existing public vector extension is reused; an extension newly created in the owned schema is cleaned up with it. Run these tests serially.

Runtime acceptance checks extension 0.8.6, synchronous completion, one run, three proposals/actions/events, trace sequences 1–14, world_version 1, clock_tick 1 and event_sequence 3. An absent URL is reported as an explicit skip; it does not establish PostgreSQL compatibility.

## Deferred tables

Unified entities, player profiles/accounts, relationships, memories/vector columns, world_snapshots, inventory and general quest definitions remain future work. They are not part of the current schema.
