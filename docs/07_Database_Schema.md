# Aleria AI Town Database Schema

Version: v3.1 · Updated: 2026-09-17

## Authority and modes

The implemented model is `backend/app/database/models.py`; versioned schema changes live in `backend/migrations/versions/`. Runtime facts are persisted through repositories. Root `data/*.json` files are seeds, not live state.

Local development and fast tests use SQLite. Docker uses PostgreSQL 17 with `pgvector/pgvector:0.8.6-pg17-bookworm`, accessed through Psycopg 3. Migration 0002 enables the `vector` extension on PostgreSQL only; 0004 re-runs `CREATE EXTENSION IF NOT EXISTS vector` before creating the cognition tables so a fresh isolated schema also succeeds.

The ORM and the migrations are **isomorphic**: every FK, CHECK, UNIQUE and index carries the same explicit name in both. Adding a column to one without the other is a defect.

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
| `events` | World/run/action/actor references, event type, world_version/clock_tick/event_sequence, structured payload_json, description, source/causation/correlation references, visibility/secrecy, timestamps, **plus the 0004 perception metadata below** |
| `agent_trace_entries` | run_id, sequence, stage, actor, factual summary/data_json, visibility, created_at |
| `conversations` | UUID string id, world/NPC boundary, created_clock_tick, timestamps |
| `conversation_messages` | Conversation foreign key, user/assistant role, content/emotion/provider/fallback/prompt metadata, clock_tick, timestamp, **plus the 0004 turn identity below** |
| `agent_cognition_states` | Per-owner projection checkpoint and reflection accumulators |
| `observations` | Per-NPC private perception derived from an authoritative source |
| `memories` | Long-term memory with provenance, permissions, lifecycle and embedding |
| `memory_evidence` | Ordered edges from a derived memory to the memories it cites |
| `beliefs` | Append-only belief revisions with confidence and lifecycle |
| `belief_evidence` | Supporting/contradicting evidence edges per belief |
| `agent_plans` | Procedural memory: UUID string id, world/owner/source-run references, goal + goal_reason + thought, ordered `steps_json`, `current_step_index`, status (`active`/`completed`/`abandoned`), created/updated clock_tick, provider/model/prompt_version, latency_ms, tokens_used, **plus the 0006 `evidence_memory_ids_json`** |
| `alembic_version` | Current schema revision (head: 0006) |

Integer history IDs use autoincrement. JSON columns hold structured facts. SQLAlchemy uses timezone-aware timestamp declarations; public DTOs normalize SQLite's returned timestamps to UTC. API DTOs are deliberate projections, not raw table dumps.

## Source metadata added by 0004

Cognition needs the *historical* audience of a source, not a recomputed one. Free text never defines who perceived an event, so 0004 records the audience on the authoritative row at write time.

`events` gains, all nullable so historical rows stay valid:

| Column | Type | Constraint |
| --- | --- | --- |
| `location_id` | String | FK `fk_events_location_id_locations` → `locations.id` |
| `perception_scope` | String | `ck_events_perception_scope`: NULL or one of `world_public`, `location`, `participants`, `professional`, `private` |
| `participant_npc_ids_json` | JSON | — |
| `witness_npc_ids_json` | JSON | — |
| `professional_channels_json` | JSON | — |
| `attention_priority` | Float | `ck_events_attention_priority`: NULL or between 0 and 1 |
| `is_critical` | Integer | `ck_events_is_critical`: NULL or in (0, 1) |

`conversation_messages` gains:

| Column | Type | Constraint |
| --- | --- | --- |
| `turn_id` | String(36) | Shared by the user/assistant pair of one turn |
| `world_version` | Integer | `ck_conversation_messages_world_version`: NULL or >= 0 |
| `world_time` | String(5) | — |

plus `uq_conversation_messages_conversation_turn_role` on `(conversation_id, turn_id, role)` and index `ix_conversation_messages_turn_id_id` on `(turn_id, id)`.

**Legacy null policy:** every 0004 column on a pre-existing table is nullable and every new CHECK is written as `column IS NULL OR <condition>`. Rows written before 0004 keep NULL perception metadata and NULL turn identity; the projector treats an incomplete source as unperceivable and skips it rather than inventing an audience. No backfill fabricates history.

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

## Cognition tables and constraints

```text
world_state ─┬─ agent_cognition_states ─ (per-owner checkpoint)
             ├─ observations ─── memories ─┬─ memory_evidence
             │                             └─ beliefs ─ belief_evidence
             └─ (events, conversation_messages are the sources)
```

### `agent_cognition_states`

Composite primary key `(world_id, owner_npc_id)`; both columns are foreign keys. Holds the projection cursors `last_event_sequence` and `last_conversation_message_id`, the reflection accumulators `reflection_accumulated_importance`, `reflection_memory_count`, `reflection_pending_critical`, the last successful source cursor (`last_reflection_source_created_at`, `last_reflection_source_memory_id`, `last_reflection_evidence_fingerprint`) and the in-flight attempt slot (`reflection_attempt_fingerprint`, `reflection_attempt_count`, `reflection_attempt_status`).

CHECK constraints: `ck_cognition_states_event_cursor` (>= 0), `ck_cognition_states_message_cursor` (>= 0), `ck_cognition_states_reflection_importance` (>= 0), `ck_cognition_states_reflection_count` (>= 0), `ck_cognition_states_pending_critical` (in 0,1), `ck_cognition_states_attempt_count` (**between 0 and 2** — the database enforces the at-most-one-retry rule), `ck_cognition_states_attempt_status` (in `idle`, `failed`, `succeeded`).

### `observations`

String(36) primary key. FKs to `world_state`, `npc_profiles`, `events`, and twice to `conversation_messages` (`source_user_message_id`, `source_assistant_message_id`).

- `uq_observations_owner_source_policy` on `(world_id, owner_npc_id, source_key, policy_version)` — this is what makes projection idempotent and re-runnable.
- `ck_observations_source_reference_shape` — a three-branch CHECK binding `source_kind` to exactly the reference columns it may use: `event` requires `source_event_id` and forbids all turn columns; `conversation_turn` requires `source_turn_id` **and both** message ids and forbids `source_event_id`; `authored_knowledge` forbids all four. A half-populated source cannot be stored.
- Vocabulary CHECKs: `ck_observations_source_kind` (`event`, `conversation_turn`, `authored_knowledge`), `ck_observations_perception_mode` (`participant`, `witnessed`, `professional_channel`, `direct_dialogue`), `ck_observations_secrecy` (`public`, `private`, `secret`), `ck_observations_disclosure_scope` (`public`, `player_dialogue`, `internal_only`), `ck_observations_lifecycle_state` (`active`, `archived`, `disputed`, `superseded`), `ck_observations_is_critical` (0,1).
- Time CHECKs: `ck_observations_world_version` and `ck_observations_clock_tick`, both >= 0.
- Indexes: `ix_observations_owner_occurred` on `(world_id, owner_npc_id, occurred_clock_tick, id)`, `ix_observations_source_event`, `ix_observations_source_turn`.

### `memories`

String(36) primary key, FKs to `world_state`, `npc_profiles` and `observations`.

- `uq_memories_source_observation` on `source_observation_id` — one observation yields at most one memory.
- `uq_memories_authored_source` on `(world_id, owner_npc_id, authored_source_id, authored_source_version)` — re-seeding the same authored-knowledge version cannot duplicate it.
- `ck_memories_source_reference_shape` — a three-branch CHECK: `episodic`/`conversation` require `source_observation_id` and forbid authored columns; `knowledge` requires both authored columns and forbids the observation; `reflection` forbids all three, because a reflection's provenance lives in `memory_evidence` rather than in a single source.
- Vocabulary CHECKs: `ck_memories_memory_type` (`episodic`, `conversation`, `reflection`, `knowledge`), `ck_memories_secrecy`, `ck_memories_disclosure_scope`, `ck_memories_lifecycle_state`, `ck_memories_embedding_status` (`ready`, `failed`, `unavailable`).
- Range CHECKs: `ck_memories_importance` and `ck_memories_confidence` between 0 and 1, `ck_memories_emotional_valence` between -1 and 1, `ck_memories_embedding_dimensions` (NULL or > 0), `ck_memories_access_count` (>= 0), and four `>= 0` checks on occurred/created world_version and clock_tick.
- Indexes: `ix_memories_owner_lifecycle_occurred` on `(world_id, owner_npc_id, lifecycle_state, occurred_clock_tick, id)` — the permission hard filter's access path — and `ix_memories_embedding_space` on `(embedding_provider, embedding_model, embedding_version, embedding_dimensions)`.

**Dialect difference.** `memories.embedding` is a pgvector `Vector` on PostgreSQL and a plain `sa.JSON` array on SQLite; the migration selects the type from the live dialect. The five accompanying columns (`embedding_provider`, `embedding_model`, `embedding_version`, `embedding_input_hash`, `embedding_dimensions`) identify the embedding space, and retrieval only compares vectors whose full identity **and** `embedding_input_hash` match the current query. A model or dimension change therefore invalidates old vectors by mismatch instead of silently comparing incompatible spaces.

### `memory_evidence`

Composite PK `(derived_memory_id, evidence_memory_id)`, both FKs to `memories`. `uq_memory_evidence_derived_ordinal` on `(derived_memory_id, ordinal)` keeps citation order stable; `ck_memory_evidence_ordinal` (>= 0); `ck_memory_evidence_no_self_reference` forbids a memory citing itself.

### `beliefs`

String(36) primary key, FKs to `world_state`, `npc_profiles`, a self-FK `supersedes_belief_id` and `source_reflection_memory_id` → `memories`.

`uq_beliefs_source_reflection_memory` means one reflection produces at most one belief revision. CHECKs: `ck_beliefs_confidence` (0–1), `ck_beliefs_lifecycle_state` (`active`, `disputed`, `superseded`), and `>= 0` on created world_version and clock_tick. Index `ix_beliefs_owner_lifecycle_created` on `(world_id, owner_npc_id, lifecycle_state, created_clock_tick, id)`.

Revision is append-only: a new row is inserted `active`, and the superseded row is only re-labelled. History, including contradicting evidence, is never deleted.

### `belief_evidence`

Composite PK `(belief_id, memory_id, evidence_role)` — the same memory may appear once per role. `uq_belief_evidence_role_ordinal` on `(belief_id, evidence_role, ordinal)`; `ck_belief_evidence_role` (`supporting`, `contradicting`); `ck_belief_evidence_ordinal` (>= 0).

### Downgrade

`0004.downgrade()` deliberately raises `RuntimeError`. Dropping the cognition tables would destroy provenance that cannot be reconstructed from the authoritative sources, so the migration is forward-only by design.

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
| 0004 | Event/message source metadata, six cognition tables, dialect-specific embedding column; forward-only |
| 0005 | `agent_plans` — procedural memory for multi-step LLM plans reused across ticks |
| 0006 | `agent_plans.evidence_memory_ids_json` — the memory ids retrieved into the planning context; nullable, because plans written before this revision genuinely have no such record |

Legacy actions/events are retained and associated with deterministic historical runs during backfill. A migration is not equivalent to SQLAlchemy `create_all`.

`python -m scripts.seed_world` and `POST /api/demo/reset` explicitly reset the target demo world, clearing its quest/chat/runtime history in foreign-key-safe order. Since 0004 the reset also clears that world's cognition data in foreign-key-safe order — `belief_evidence`, `beliefs`, `memory_evidence`, `memories`, `observations`, `agent_cognition_states` — and since 0005 its procedural memory as well: `agent_plans` is deleted before `agent_runs`, because `source_run_id` points at it. Leaving an active plan behind would make the first tick after a reset reuse the previous world's plan instead of replanning. The reset then rewrites the versioned authored knowledge from `data/agent_knowledge.json`. Other worlds are preserved. Normal startup, migration and `ensure_demo_world` never reset cognition history.

Authored knowledge is versioned content, not an unversioned prompt: each item carries an owner, `secrecy`, `disclosure_scope`, importance, confidence and an occurrence baseline, and the file carries a version string (currently `stage2-v1`) that participates in `uq_memories_authored_source`.

## Storage and acceptance

Compose stores PostgreSQL data in `aleria_postgres_data:/var/lib/postgresql/data`. The base database has no host port. The existing `aleria_data` SQLite volume is retained for explicitly configured SQLite deployments; there is no automatic SQLite-to-PostgreSQL gameplay-data transfer.

Fast tests create temporary SQLite databases. The opt-in PostgreSQL tests use only `TEST_POSTGRES_URL`, which must identify a dedicated disposable database with schema/extension privileges. Each creates a unique empty `aleria_test_<uuid>` schema and uses its own search_path, ensuring both migration-from-zero and runtime acceptance are independent of test order. Cleanup drops only that test-owned schema, never the database or named Docker volume. A pre-existing public vector extension is reused; an extension newly created in the owned schema is cleaned up with it. Run these tests serially.

Runtime acceptance checks extension 0.8.6, `alembic_version` = 0006, that `memories.embedding` reports PostgreSQL data type `vector`, that all six cognition tables exist, synchronous completion, one run, three proposals/actions/events, trace sequences 1–17, world_version 1, clock_tick 1 and event_sequence 3. The acceptance tick runs in the default `auto` runtime mode, so `run_started` is followed by one `planning` entry per NPC; the 1–14 sequence in `docs/06` describes a purely deterministic advance and both remain correct.

A separate opt-in case covers demo reset against a **non-empty** `agent_plans`: it ticks first so procedural memory exists, asserts the count is above zero, resets, and asserts the world's plans and runs are both gone. The acceptance case above resets before the first tick, so on its own it only proves that deleting zero rows does not fail.

Vector acceptance additionally writes ready embeddings and runs real retrieval against them: two same-owner public memories, one `secret` memory and one belonging to another NPC. It asserts the `<=>` query returns exactly the two permitted ids in a stable order across repeated runs, that the secret and cross-owner rows never appear, and that forcing the embedding provider to fail yields `mode = "lexical_fallback"` with `error_code = "embedding_unavailable"` and the same permitted id set. It also asserts `access_count` stays 0, proving the read wrote no telemetry.

An absent URL is reported as an explicit skip; it does not establish PostgreSQL compatibility. A skipped run must never be recorded as a passing acceptance.

## Deferred tables

Unified entities, player profiles/accounts, relationships, claim-propagation graphs, world_snapshots, inventory and general quest definitions remain future work. They are not part of the current schema.

Memory and vector columns are **no longer deferred** — see the cognition tables above.
