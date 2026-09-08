# Aleria AI Town Engineering Architecture

Version: v2.0 · Updated: 2026-09-07

## Current implementation

Aleria is a modular monolith: Vue 3/Pinia handles interaction, Phaser 3.90.0 renders the RPG, and FastAPI owns world facts. SQLAlchemy repositories persist state in SQLite for local light mode or PostgreSQL for Docker deployment.

The observable agent runtime is synchronous and deterministic:

```text
Snapshot -> ActionProposal -> Registry validation
-> deterministic resolution -> atomic world/run/action/event/trace commit
```

`POST /api/world/tick` returns HTTP 200 after persistence completes. The RPG exposes one “推进 1 小时” control. There is no background queue or runtime-mode selector.

## Runtime boundaries

| Module | Responsibility |
| --- | --- |
| `app/world/` | Clock, deterministic role routines and compatibility entry points |
| `app/agents/contracts.py` | Immutable proposal, validation, event and trace contracts |
| `app/agents/action_registry.py` | Legal actions, target validation, effects and event metadata |
| `app/agents/conflict_resolver.py` | Stable proposal ordering and duplicate/invalid proposal resolution |
| `app/agents/orchestrator.py` | One immutable decision snapshot, proposals and resolved result |
| `services/world_clock_service.py` | Application coordination and public response mapping |
| `database/world_clock_repository.py` | Validate the result graph, compare-and-swap world version, commit once |
| `database/agent_run_repository.py` | Ordered, read-only persisted run graph |
| `schemas/agent_run.py` | Public factual trace/event projection and unsafe-value redaction |

Each NPC proposes from the same immutable decision snapshot after the common clock/needs update. It cannot observe another NPC's effects in that advance. Resolution is independent of proposal input order. The registry initially contains exactly `move`, `rest`, `work`, `eat`, `talk`, and `wait`; `social` remains a needs field but is no longer an action ID.

Persistence checks the graph and legal effects before writing. The authoritative world, NPC states, completed run, proposals (including rejections), executed actions, events and factual traces commit in one transaction. A stale version, malformed result or database failure cannot leave partial world changes or partial run history.

## Three independent counters

| Counter | Changes when |
| --- | --- |
| `world_version` | World advancement, actual player travel or a quest transition changes authoritative state |
| `clock_tick` | The player advances game time by one hour |
| `event_sequence` | A domain event is added, with strict gap-free ordering within its world |

Travel to the current location is an idempotent success without a new mutation. Quest interaction checks both quest-local `expected_version` and global `expected_world_version`. Chat transcript persistence changes none of these counters.

## Existing gameplay and chat slices

NPC detail uses bounded repository reads to return profile, current state and the latest three actions with deterministic explanations. Player/Quest uses the fixed `default-player`, semantic location IDs and the dedicated Missing Child state machine. Asking Grey requires current co-location; Vue displays backend objectives instead of copying quest rules.

Chat is a separate chain:

```text
Authoritative World/NPC/Player/Quest + bounded history + Prompt v3
-> ChatProvider -> reply validation -> atomic user/assistant transcript
```

The default Mock runs without a key. Non-Mock providers use one OpenAI-compatible adapter with structured JSON or text output, with explicit Mock fallback. Provider calls happen outside the database write transaction. Chat cannot advance time, perform NPC actions or complete quests. Prompt assets preserve role knowledge boundaries and exclude complete Author Truth.

## Frontend

Vue and independent Pinia stores own world, NPC detail, per-NPC chat and Player/Quest state; TownView coordinates refreshes. Phaser owns pixels, collision, camera, animation and hit testing. Keyboard location entry and fast travel go through the same backend semantic-location contract. DOM controls provide a usable alternative if the map cannot load.

The run API is available for inspection; Agent Lab UI and runtime mode controls remain future work.

## Persistence and deployment

Alembic revisions `0001 -> 0002 -> 0003` upgrade empty SQLite/PostgreSQL databases and supported unversioned legacy SQLite databases while preserving gameplay data. Startup runs `scripts.upgrade_schema`, then `scripts.ensure_demo_world`, then Uvicorn. Explicit reseeding/reset is a separate destructive demo operation.

Local `.env.example` keeps SQLite with cross-thread access and foreign keys enabled. Compose uses Psycopg 3 via `postgresql+psycopg://` and `pgvector/pgvector:0.8.6-pg17-bookworm`. PostgreSQL has a named volume and readiness check; backend waits for healthy database, web waits for healthy backend. Only web publishes a base host port. The host-side PostgreSQL test override binds to loopback port 55432 by default.

The migration enables pgvector, but there are no vector-valued ORM columns yet. SQLite remains the fast automated-test default. Real PostgreSQL tests require `TEST_POSTGRES_URL` and run serially in independent empty test schemas.

## Deferred capabilities

Memory, embeddings/retrieval, reflection, beliefs, LangGraph, LLM-generated plans/proposals, relationships, multi-NPC dialogue, Agent Lab, Celery, Redis, transactional outbox, async HTTP 202 submission, SSE, retries, cancellation and budgets are not implemented in this phase. Supporting a PostgreSQL deployment does not by itself provide multi-worker runtime scheduling.

See [API contract](06_API_Contract.md), [database schema](07_Database_Schema.md), and [development environment](14_Development_Environment.md).
