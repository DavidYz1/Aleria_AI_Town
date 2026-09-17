# Aleria AI Town Engineering Architecture

Version: v3.1 · Updated: 2026-09-17

## Current implementation

Aleria is a modular monolith: Vue 3/Pinia handles interaction, Phaser 3.90.0 renders the RPG, and FastAPI owns world facts. SQLAlchemy repositories persist state in SQLite for local light mode or PostgreSQL for Docker deployment.

The observable agent runtime is synchronous. Each NPC either reuses an active plan or asks the planning provider for a new one; everything downstream of the proposal stays deterministic:

```text
Snapshot -> plan reuse | LLM planning -> ActionProposal -> Registry validation
-> deterministic resolution -> atomic world/run/action/event/trace commit
```

`POST /api/world/tick` returns HTTP 200 after persistence completes. The RPG exposes one “推进 1 小时” control. There is no background queue. The request accepts `runtime_mode`: `auto` (default — plan reuse or LLM planning) or `deterministic` (skip planning entirely).

Cognition is a second, strictly subordinate pipeline. Authoritative sources commit first; per-NPC perception, memory, embedding and reflection are projected afterwards and may fail without changing any authoritative outcome.

## Runtime boundaries

| Module | Responsibility |
| --- | --- |
| `app/world/` | Clock, deterministic role routines and compatibility entry points |
| `app/agents/contracts.py` | Immutable proposal, validation, event and trace contracts |
| `app/agents/action_registry.py` | Legal actions, target validation, effects and event metadata |
| `app/agents/conflict_resolver.py` | Stable proposal ordering and duplicate/invalid proposal resolution |
| `app/agents/orchestrator.py` | One immutable decision snapshot, proposals and resolved result |
| `app/agents/planning_contracts.py` | Frozen planning contracts: `AgentDecision`, plan steps and the MCP-shaped tool manifest |
| `app/agents/planner.py` | Eight-section context assembly, retrieval budget, active-plan reuse and plan lifecycle |
| `llm/planning_provider.py` | Independent fake/OpenAI-compatible planning provider using native tool calling |
| `services/world_clock_service.py` | Application coordination and public response mapping |
| `database/world_clock_repository.py` | Validate the result graph, compare-and-swap world version, commit once |
| `database/agent_run_repository.py` | Ordered, read-only persisted run graph |
| `schemas/agent_run.py` | Public factual trace/event projection and unsafe-value redaction |
| `app/agents/cognition_contracts.py` | Frozen cognition contracts and the fixed source/memory/perception/scope vocabularies |
| `app/agents/perception.py` | Perception policy registry, permission matrix, attention budget and `ObservationDraft` |
| `app/agents/memory_retrieval.py` | Permission-first hybrid/lexical ranking, budgets and stable tie-breaks |
| `app/agents/reflection.py` | Reflection triggering, evidence fingerprints, draft validation and append-only beliefs |
| `database/cognition_repository.py` | Source scan, checkpoint, core projection, enrichment, retrieval and evidence persistence |
| `services/cognition_projection.py` | Bounded per-owner catch-up, the core transaction and best-effort post-commit enrichment |
| `services/memory_explanation.py` | Fixed public-context query and safe explanation projection |
| `llm/embedding_provider.py`, `llm/reflection_provider.py` | Independent fake/OpenAI-compatible providers with their own settings |

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
Authoritative World/NPC/Player/Quest + bounded history
+ permission-filtered long-term Memory + Prompt v3
-> ChatProvider -> reply validation -> atomic user/assistant transcript
-> post-commit projection of the completed turn
```

The default Mock runs without a key. Non-Mock providers use one OpenAI-compatible adapter with structured JSON or text output, with explicit Mock fallback. Provider calls happen outside the database write transaction. Chat cannot advance time, perform NPC actions or complete quests. Prompt assets preserve role knowledge boundaries and exclude complete Author Truth.

Before the reply is assembled, retrieval runs in the `player_dialogue` scope and excludes memories whose source turn is still inside the active history window, so recall supplements the transcript instead of duplicating it. The current message only influences the *next* turn: its own turn is projected after the transcript commits. A memory, embedding or reflection failure degrades the reply context but never fails the chat.

## Cognition pipeline

The binding invariant is **authoritative-source-first, cognition-after**. World/Quest/Travel events and complete conversation turns commit in their existing transactions; cognition is then projected by a bounded, per-NPC checkpoint.

```text
authoritative commit
  -> CognitionProjectionService.catch_up_owner | catch_up_world
       (1) CORE        transactional, must succeed
             checkpoint -> bounded source batch -> PerceptionPolicyRegistry
             -> Observation + Memory -> commit -> checkpoint advances
       (2) EMBEDDING   best-effort, may fail
       (3) REFLECTION  best-effort, may fail
```

All three stages share one deadline (`COGNITION_POST_COMMIT_BUDGET_SECONDS`, default 5.0). An expired budget stops further provider work; late results are not persisted. Stage 2 and 3 failures are logged under a fixed safe category and never roll back stage 1 or the authoritative source.

Cognition owns a **separate request-scoped Session** (`get_cognition_session`), distinct from the authoritative `get_session`. Both `catch_up_owner()` and `MemoryRetriever.retrieve()` refuse a Session that already has an open transaction, and neither adopts nor rolls back a transaction it did not begin. Reusing the authoritative Session would silently enlist cognition writes in the authoritative transaction and break failure isolation.

Each NPC advances its own cursors independently (`last_event_sequence`, `last_conversation_message_id`), so one owner's failure cannot stall another's. Projection is idempotent: `(world_id, owner_npc_id, source_key, policy_version)` is unique for observations, and a memory derived from an observation is unique per source observation.

Permission filtering is a **SQL hard filter applied before any similarity ranking**, never an application-layer post-filter. Three scopes exist:

| Scope | secrecy | disclosure_scope | Use |
| --- | --- | --- | --- |
| `player_dialogue` | public, private | public, player_dialogue | Recall before an NPC chat reply |
| `internal_reflection` | public, private, secret | public, player_dialogue, internal_only | Reflection evidence candidates |
| `public_explanation` | public | public | Anonymous read-only explanation API |

Ranking is deterministic. With usable embeddings the score is `0.40·semantic + 0.20·lexical + 0.20·recency + 0.15·importance + 0.05·confidence`; degraded to lexical it is `0.45·lexical + 0.25·recency + 0.20·importance + 0.10·confidence`. Disputed memories are multiplied by 0.85 and ties break on memory id. Any embedding failure switches the whole result to `lexical_fallback` rather than mixing modes.

Reflection is evidence-bound: the provider must cite real, same-owner memory IDs and cannot create world facts. Secrecy and disclosure are derived from the strictest values across the entire provider-visible candidate set, so omitting a secret citation cannot launder its permission. Beliefs are append-only — a revision inserts a new active row and only marks the prior row `superseded` or `disputed`, preserving supporting and contradicting evidence.

The `public_explanation` retrieval itself writes no access telemetry and rolls back its read. The anonymous endpoint may first advance bounded core catch-up (Observation, Memory and the per-owner checkpoint) after a restart or backlog, but it skips Embedding/Reflection enrichment and uses a local deterministic query embedding rather than a configured live provider. Once core catch-up is current, repeated GETs leave cognition state unchanged; a live-space mismatch safely degrades to lexical ranking.

## Frontend

Vue and independent Pinia stores own world, NPC detail, per-NPC chat, NPC memory and Player/Quest state; TownView coordinates refreshes. Phaser owns pixels, collision, camera, animation and hit testing. Keyboard location entry and fast travel go through the same backend semantic-location contract. DOM controls provide a usable alternative if the map cannot load.

`useNpcMemoryStore` is deliberately separate from `useNpcDetailStore`: selecting an NPC issues two independent reads, so a failing explanation request cannot pollute the detail state. The panel's “相关记忆” section is collapsed by default and its failure leaves detail, chat, map and world advancement fully usable. Closing the panel and Demo Reset clear both stores.

The run API is available for inspection; Agent Lab UI and runtime mode controls remain future work.

## Persistence and deployment

Alembic revisions `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006` upgrade empty SQLite/PostgreSQL databases and supported unversioned legacy SQLite databases while preserving gameplay data. Startup runs `scripts.upgrade_schema`, then `scripts.ensure_demo_world`, then Uvicorn. Explicit reseeding/reset is a separate destructive demo operation.

Local `.env.example` keeps SQLite with cross-thread access and foreign keys enabled. Compose uses Psycopg 3 via `postgresql+psycopg://` and `pgvector/pgvector:0.8.6-pg17-bookworm`. PostgreSQL has a named volume and readiness check; backend waits for healthy database, web waits for healthy backend. Only web publishes a base host port. The host-side PostgreSQL test override binds to loopback port 55432 by default.

Revision `0004` creates the vector-valued `memories.embedding` column: a pgvector `Vector` on PostgreSQL and a JSON array on SQLite. Both dialects run the same retrieval code — PostgreSQL computes distance with the `<=>` operator inside a savepoint so a failed vector query degrades to lexical ranking without reusing an aborted transaction, while SQLite scores cosine similarity in Python. SQLite remains the fast automated-test default. Real PostgreSQL tests require `TEST_POSTGRES_URL` and run serially in independent empty test schemas.

## Interface boundary for LLM planning

Stage 3m orchestrates Goal → Plan → typed `ActionProposal` **without** LangGraph: `app/agents/planner.py` calls the provider directly. It uses exactly three surfaces, and nothing more:

1. **Permission-filtered cognition reads.** The planner reads Memory, reflection and current Belief through the existing scopes and hard filter, in the `internal_reflection` scope. It does not widen a scope, bypass `SCOPE_RULES`, or query cognition tables directly. What the plan API returns is re-filtered through `public_explanation`, so a citation the caller may not see is absent rather than redacted.
2. **The existing Action Registry.** LLM-derived intentions become the same typed `ActionProposal` and pass the same validation, conflict resolution and atomic commit. There is no second execution path that writes world state.
3. **The post-commit projection contract.** Cognition stays subordinate to authoritative commits, and no provider call is held inside a database transaction.

LangGraph and LangChain are **not used**. The Stage 2 checkpoint is not a general task queue and must not be repurposed as one.

## Deferred capabilities

LangGraph, LangChain, NPC-to-NPC dialogue, relationships, claim propagation, knowledge graphs, Agent Lab, LangSmith, an MCP transport layer (stdio/SSE — only the manifest shape is aligned), Celery, Redis, transactional outbox, async HTTP 202 submission, SSE, distributed retries and asynchronous cancellation are not implemented. Bounded provider calls and a shared post-commit cognition budget are implemented. Supporting a PostgreSQL deployment does not by itself provide multi-worker runtime scheduling.

Memory, embeddings, permission-first retrieval, reflection and beliefs are **no longer deferred** — they are implemented and described above. Goal/Plan entities and LLM-generated action proposals are **no longer deferred** either — see the planning surfaces above.

See [API contract](06_API_Contract.md), [database schema](07_Database_Schema.md), and [development environment](14_Development_Environment.md).
