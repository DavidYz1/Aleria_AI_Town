# Agent Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tick-only deterministic loop with a versioned, migration-backed, observable Agent Runtime foundation while preserving existing RPG behavior and the synchronous play flow.

**Architecture:** FastAPI remains synchronous in this phase. Deterministic policies emit typed `ActionProposal` values; an Action Registry validates and executes them against one immutable snapshot; a deterministic resolver orders outcomes; and one SQLAlchemy transaction persists the world mutation, AgentRun, proposals, actions, domain events, and factual trace. PostgreSQL with pgvector becomes the deployed database, while SQLite remains the fast test and lightweight local database.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic 1.19, PostgreSQL 17, pgvector 0.8.6 server extension, pgvector-python 0.5, Psycopg 3.3, Vue 3, TypeScript, Pinia, Pytest, Vitest

**Spec:** `docs/superpowers/specs/2026-09-04-ai-native-agent-rpg-runtime-design.md`

## Global Constraints

- Never run `git add`, `git commit`, `git reset`, or `git checkout`. The user reviews and commits each implementation round manually.
- Use TDD for every behavior: write or update a focused failing test, confirm the expected failure, implement the smallest change, and rerun the focused test.
- Preserve `POST /api/world/tick` as a synchronous `200` endpoint during this phase. Async `202` submission belongs to the later production-runtime phase.
- Keep one visible “推进 1 小时” control in the RPG. Runtime-mode controls belong to Agent Lab.
- `world_version` is the optimistic concurrency token for authoritative world mutations; `clock_tick` changes only when game time advances; `event_sequence` provides strict per-world event ordering.
- Player travel, quest transitions, and world advancement mutate `world_version`. Saving an ordinary chat transcript does not.
- Every NPC proposal in one advancement uses the same immutable snapshot and cannot see another proposal's effects.
- The registry is the only authority for legal action types and effects. Do not add database checks that require schema migrations for each future action type.
- Preserve SQLite tests. Isolate PostgreSQL-only behavior by dialect and cover it through an opt-in integration test.
- Alembic must upgrade an existing unversioned SQLite database without deleting gameplay data and create an empty SQLite/PostgreSQL database from zero.
- Persist structured references and concise factual summaries, never hidden reasoning or chain-of-thought.
- LLM cognition, memory, reflection, LangGraph, Celery, Redis, SSE, and multi-NPC dialogue are not part of this phase.
- Finish with unstaged, uncommitted changes and a review report containing changed files, test evidence, risks, and a suggested manual commit message.

## Locked Public Contracts

After this phase, the world contract is:

```python
@dataclass(frozen=True)
class WorldSnapshot:
    id: str
    name: str
    day: int
    time: str
    world_version: int
    clock_tick: int
    event_sequence: int
    locations: tuple[LocationSnapshot, ...]
    npcs: tuple[NpcSnapshot, ...]
```

`POST /api/world/tick` accepts:

```json
{"expected_world_version": 0}
```

Player travel accepts `target_location_id` and `expected_world_version`. Quest interaction accepts quest-local `expected_version` plus global `expected_world_version`. No writable `tick` alias remains.

The initial registry contains exactly `move`, `rest`, `work`, `eat`, `talk`, and `wait`. The existing `social` ID is renamed to `talk`.

## File Responsibility Map

New runtime files:

- `backend/app/agents/contracts.py` — JSON-safe immutable runtime contracts and enums.
- `backend/app/agents/action_registry.py` — legal actions, validation, and effects.
- `backend/app/agents/conflict_resolver.py` — stable ordering and rejection decisions.
- `backend/app/agents/orchestrator.py` — pure deterministic one-hour run.
- `backend/app/database/world_version.py` — shared compare-and-swap for non-agent mutations.
- `backend/app/database/agent_run_repository.py` — ordered run/proposal/event/trace reads.
- `backend/app/schemas/agent_run.py` and `backend/app/api/agent_runs.py` — redaction-safe run detail API.

Migration files:

- `alembic.ini` — migration configuration without credentials.
- `backend/migrations/env.py` — online/offline migration bootstrap.
- `backend/migrations/script.py.mako` — revision template.
- `backend/migrations/versions/0001_legacy_baseline.py` — exact current schema.
- `backend/migrations/versions/0002_world_versioning.py` — version and clock semantic split.
- `backend/migrations/versions/0003_agent_runtime_foundation.py` — runtime records, enriched events, and legacy history backfill.

New test files:

- `tests/backend/test_schema_migrations.py`
- `tests/backend/test_world_versioning.py`
- `tests/backend/test_action_registry.py`
- `tests/backend/test_agent_orchestrator.py`
- `tests/backend/test_agent_run_repository.py`
- `tests/backend/test_agent_run_api.py`
- `tests/backend/test_postgres_runtime.py`

Existing files change only where required to migrate database, API, services, frontend contracts, tests, deployment, or documentation.

---

### Task 1: Make the Existing Baseline Green and Introduce Alembic

**Files:**
- Modify: `tests/backend/test_story_content.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements.runtime.txt`
- Create: `alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_legacy_baseline.py`
- Modify: `scripts/upgrade_schema.py`
- Modify: `scripts/seed_world.py`
- Modify: `scripts/ensure_demo_world.py`
- Modify: `scripts/start_dev.py`
- Create: `tests/backend/test_schema_migrations.py`
- Modify: `tests/backend/test_seed_world.py`
- Modify: `tests/backend/test_start_dev.py`

**Interfaces:**
- Produces: `upgrade_schema(database_url: str, revision: str = "head") -> None`.
- Produces: Alembic revision `0001` representing the current pre-runtime schema.
- Constraint: migration revisions never import live ORM models.

- [ ] **Step 1: Remove the one stale baseline assertion**

Current verified baseline is `349 passed, 1 failed`. The only failure requires a retired hard-coded public IP in human-facing README prose. Remove that obsolete URL assertion instead of replacing it with another prose change detector; executable deployment behavior remains covered in `tests/backend/test_deploy.py`. Keep the existing heading/order checks unchanged in this phase.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_story_content.py -q -p no:cacheprovider --basetemp .test-tmp\story
```

Expected: the selected file passes.

- [ ] **Step 2: Add migration and PostgreSQL dependencies**

Add to both requirements files:

```text
alembic>=1.19,<2.0
psycopg[binary]>=3.3,<4.0
pgvector>=0.5,<1.0
```

Install the updated development set before running Alembic tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

- [ ] **Step 3: Write migration bootstrap tests**

Define the migration-test helpers and the two entry-path tests in the same file:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Base
from scripts.upgrade_schema import upgrade_schema


REPO_ROOT = Path(__file__).resolve().parents[2]


def migration_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def run_alembic(database_url: str, revision: str) -> None:
    command.upgrade(migration_config(database_url), revision)


def remove_alembic_version_table(database_url: str) -> None:
    engine, _ = create_engine_and_session(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))


def current_revision(database_url: str) -> str | None:
    engine, _ = create_engine_and_session(database_url)
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def head_revision(database_url: str) -> str:
    head = ScriptDirectory.from_config(
        migration_config(database_url)
    ).get_current_head()
    assert head is not None
    return head


def test_upgrade_schema_builds_empty_database_to_head(tmp_path):
    url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    upgrade_schema(url)
    engine, _ = create_engine_and_session(url)
    names = set(inspect(engine).get_table_names())
    assert "alembic_version" in names
    assert set(Base.metadata.tables).issubset(names)


def test_upgrade_schema_adopts_unversioned_legacy_database(tmp_path):
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    run_alembic(url, "0001")
    remove_alembic_version_table(url)
    upgrade_schema(url)
    assert current_revision(url) == head_revision()
```

Run the new file. Expected: failure because Alembic helpers and revision do not exist.

- [ ] **Step 4: Create a credential-free migration environment**

`alembic.ini` sets `script_location = backend/migrations`. `env.py` reads the URL supplied by `scripts.upgrade_schema` or `DATABASE_URL`, uses `Base.metadata` only for comparison, enables `compare_type=True`, and uses batch rendering for SQLite:

```python
context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    compare_type=True,
    render_as_batch=connection.dialect.name == "sqlite",
)
```

- [ ] **Step 5: Write the exact legacy baseline revision**

`0001_legacy_baseline.py` creates these current tables in dependency order:

```text
world_state, locations, npc_profiles, npc_states, player_states,
quest_progress, quest_events, actions, events, conversations,
conversation_messages
```

Use explicit `op.create_table`, named constraints, and `op.create_index` calls matching `models.py`. Downgrade drops the objects in reverse order. Do not call `Base.metadata.create_all` from the revision.

- [ ] **Step 6: Replace runtime `create_all` with Alembic and legacy adoption**

Implement the helpers as follows; `REPO_ROOT` is the existing repository root constant:

```python
LEGACY_REVISION = "0001"
LEGACY_TABLES = frozenset({
    "world_state", "locations", "npc_profiles", "npc_states",
    "player_states", "quest_progress", "quest_events", "actions",
    "events", "conversations", "conversation_messages",
})

def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _is_unversioned_legacy(engine: Engine) -> bool:
    table_names = set(inspect(engine).get_table_names())
    return "alembic_version" not in table_names and table_names == LEGACY_TABLES


def upgrade_schema(database_url: str, revision: str = "head") -> None:
    engine, _ = create_engine_and_session(database_url)
    table_names = set(inspect(engine).get_table_names())
    config = _alembic_config(database_url)
    if _is_unversioned_legacy(engine):
        command.stamp(config, LEGACY_REVISION)
    elif table_names and "alembic_version" not in table_names:
        raise RuntimeError("database schema is partial or unsupported")
    command.upgrade(config, revision)
```

`_is_unversioned_legacy` returns true only when `alembic_version` is absent and the application-table set equals `LEGACY_TABLES`. An unknown partial schema raises `RuntimeError("database schema is partial or unsupported")`. Verified legacy databases are stamped at `0001` and then upgraded; empty databases upgrade directly.

Replace direct `Base.metadata.create_all` calls in `seed_world.py` and `ensure_demo_world.py` with `upgrade_schema(database_url)`, so direct script execution and startup share the same migration path. Add `alembic` to the startup prerequisite module list and change the seed success text from SQLite-specific wording to “Seeded Aleria world.”

- [ ] **Step 7: Verify migrations and the full baseline**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_schema_migrations.py tests\backend\test_start_dev.py tests\backend\test_world_tick.py -q -p no:cacheprovider --basetemp .test-tmp\migrations
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp .test-tmp\baseline-green
```

Expected before later contract work: the original 350 baseline tests plus the new migration tests all pass.

---

### Task 2: Split World Version, Clock Tick, and Event Sequence

**Files:**
- Create: `backend/migrations/versions/0002_world_versioning.py`
- Create: `backend/app/database/world_version.py`
- Modify: `backend/app/database/models.py`
- Modify: `backend/app/world/types.py`
- Modify: `backend/app/schemas/world.py`
- Modify: `backend/app/schemas/world_tick.py`
- Modify: `backend/app/schemas/npc.py`
- Modify: `backend/app/schemas/player.py`
- Modify: `backend/app/schemas/quest.py`
- Modify: `backend/app/schemas/seed.py`
- Modify: `backend/app/schemas/demo.py`
- Modify: `backend/app/quests/types.py`
- Modify: `backend/app/database/world_repository.py`
- Modify: `backend/app/database/npc_repository.py`
- Modify: `backend/app/database/player_quest_repository.py`
- Modify: `backend/app/database/chat_repository.py`
- Modify: `backend/app/services/world_service.py`
- Modify: `backend/app/services/npc_service.py`
- Modify: `backend/app/services/player_quest_service.py`
- Modify: `backend/app/services/chat_context.py`
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/services/demo_reset_service.py`
- Modify: `backend/app/llm/types.py`
- Modify: `backend/app/llm/openai_compatible.py`
- Modify: `backend/app/api/world_tick.py`
- Modify: `backend/app/api/player.py`
- Modify: `backend/app/api/quests.py`
- Modify: `data/world.json`
- Create: `tests/backend/test_world_versioning.py`
- Modify: `tests/backend/test_chat_acceptance.py`
- Modify: `tests/backend/test_chat_context.py`
- Modify: `tests/backend/test_chat_models.py`
- Modify: `tests/backend/test_chat_provider_factory.py`
- Modify: `tests/backend/test_chat_repository.py`
- Modify: `tests/backend/test_chat_service.py`
- Modify: `tests/backend/test_demo_reset_api.py`
- Modify: `tests/backend/test_missing_child_quest.py`
- Modify: `tests/backend/test_mock_chat_provider.py`
- Modify: `tests/backend/test_npc_api.py`
- Modify: `tests/backend/test_npc_repository.py`
- Modify: `tests/backend/test_npc_service.py`
- Modify: `tests/backend/test_openai_compatible_provider.py`
- Modify: `tests/backend/test_phase1d_acceptance.py`
- Modify: `tests/backend/test_phase1e_acceptance.py`
- Modify: `tests/backend/test_player_quest_api.py`
- Modify: `tests/backend/test_player_quest_models.py`
- Modify: `tests/backend/test_player_quest_repository.py`
- Modify: `tests/backend/test_player_quest_service.py`
- Modify: `tests/backend/test_seed_world.py`
- Modify: `tests/backend/test_start_dev.py`
- Modify: `tests/backend/test_world_api.py`
- Modify: `tests/backend/test_world_engine.py`
- Modify: `tests/backend/test_world_tick.py`
- Modify: `scripts/seed_world.py`
- Modify: `scripts/ensure_demo_world.py`

**Interfaces:**
- Produces: `bump_world_version(session, world_id, expected_world_version) -> int`.
- Produces: `WorldVersionConflictError` with message `world version conflict; refresh and retry`.
- Preserves: quest-local `version` independently from global `world_version`.

- [ ] **Step 1: Write semantic version tests**

Add six named tests with this assertion matrix:

| Test | `world_version` delta | `clock_tick` delta | Additional assertion |
| --- | ---: | ---: | --- |
| `test_time_advance_increments_world_version_and_clock_tick_once` | 1 | 1 | day/time advance by one hour |
| `test_player_travel_increments_world_version_without_advancing_clock` | 1 | 0 | player reaches requested location |
| `test_same_location_travel_does_not_increment_world_version` | 0 | 0 | request remains idempotent |
| `test_quest_transition_increments_world_and_quest_versions_only` | 1 | 0 | quest version increases once |
| `test_chat_transcript_does_not_change_world_version_or_clock_tick` | 0 | 0 | both chat messages persist |
| `test_stale_world_version_rejects_travel_and_quest_atomically` | 0 | 0 | player, quest, and history remain unchanged |

Run the file. Expected: failures for missing fields and request parameters.

- [ ] **Step 2: Replace ambiguous world fields**

Change ORM, dataclasses, Pydantic schemas, seed data, and mapping code to `world_version`, `clock_tick`, and `event_sequence`. Timestamp fields become explicit:

```text
WorldState.tick -> clock_tick
WorldAction.tick -> clock_tick
Event.tick -> clock_tick
QuestProgress.updated_tick -> updated_clock_tick
QuestEvent.world_tick -> clock_tick
Conversation.created_tick -> created_clock_tick
ConversationMessage.world_tick -> clock_tick
```

No writable `tick` compatibility property is added.

- [ ] **Step 3: Add shared compare-and-swap**

`backend/app/database/world_version.py` implements:

```python
def bump_world_version(
    session: Session,
    world_id: str,
    expected_world_version: int,
) -> int:
    next_version = expected_world_version + 1
    result = session.execute(
        update(WorldState)
        .where(
            WorldState.id == world_id,
            WorldState.world_version == expected_world_version,
        )
        .values(world_version=next_version)
    )
    if result.rowcount != 1:
        raise WorldVersionConflictError(
            "world version conflict; refresh and retry"
        )
    return next_version
```

Repositories call it inside their existing transaction before mutating player or quest rows.

- [ ] **Step 4: Make migration `0002` preserve existing data**

Perform the exact renames above. Initialize `world_version` from legacy `tick` as a safe starting token and `event_sequence` from the count of existing events in that world, or zero. Use Alembic batch operations on SQLite. On PostgreSQL execute:

```sql
CREATE EXTENSION IF NOT EXISTS vector
```

Downgrade reverses names and removes new counters without deleting gameplay rows.

- [ ] **Step 5: Version player and quest mutations**

`PlayerTravelRequest` contains `target_location_id` and `expected_world_version`. `QuestInteractRequest` contains `interaction`, quest `expected_version`, and `expected_world_version`. Successful non-idempotent travel and successful quest transition each bump `world_version` once in the same transaction. Same-location travel returns current state without a bump. Both stale tokens map to HTTP 409.

- [ ] **Step 6: Update seed, reset, chat, quest, and NPC mappings**

Seed and reset use:

```json
{
  "id": "aleria-town",
  "name": "曦谷",
  "day": 1,
  "time": "08:00",
  "world_version": 0,
  "clock_tick": 0,
  "event_sequence": 0
}
```

Chat remains read-only with respect to world version. NPC action history orders by `clock_tick DESC, id DESC`. Quest policy receives `clock_tick`.

- [ ] **Step 7: Run backend contract verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp .test-tmp\versioning
rg -n "WorldState\.tick|expected_tick|updated_tick|\bworld_tick\b" backend scripts data tests\backend
```

Expected: all tests pass. Search matches are limited to the legacy migration and prose explicitly describing the migration.

---

### Task 3: Add Typed Action Proposals and the Registry

**Files:**
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/agents/contracts.py`
- Create: `backend/app/agents/action_registry.py`
- Modify: `backend/app/world/types.py`
- Modify: `backend/app/world/decision.py`
- Modify: `backend/app/world/action_rules.py`
- Create: `tests/backend/test_action_registry.py`
- Modify: `tests/backend/test_world_engine.py`
- Modify: `tests/backend/test_action_explanation.py`

**Interfaces:**
- Produces: `RuntimeMode`, `ProposalSource`, `ActionProposal`, `ActionValidation`, `DomainEventDraft`, and `TraceDraft`.
- Produces: `ActionRegistry.validate(proposal, actor, world) -> ActionValidation`.
- Produces: `ActionRegistry.execute(proposal, actor, world) -> NpcSnapshot`.
- Produces: `build_default_action_registry()` with six actions.

- [ ] **Step 1: Write registry tests**

Cover exact registry members, unknown actions, actor mismatch, target shape, move location, work duty location, eat tavern location, talk colocation, wait no-op, clamping, and input immutability.

```python
def test_default_registry_action_types():
    assert registry.action_types == (
        "eat", "move", "rest", "talk", "wait", "work"
    )

def test_unknown_action_is_rejected():
    decision = registry.validate(
        ActionProposal(actor_id="grey", action_type="teleport"),
        grey,
        world,
    )
    assert (decision.accepted, decision.code) == (
        False,
        "unknown_action",
    )
```

- [ ] **Step 2: Define JSON-safe immutable contracts**

```python
class RuntimeMode(StrEnum):
    AUTO = "auto"
    DETERMINISTIC = "deterministic"
    FORCE_DELIBERATION = "force_deliberation"

class ProposalSource(StrEnum):
    DETERMINISTIC = "deterministic"
    EXISTING_PLAN = "existing_plan"
    LLM = "llm"
    FALLBACK = "fallback"

@dataclass(frozen=True)
class ActionProposal:
    actor_id: str
    action_type: str
    target_kind: str | None = None
    target_id: str | None = None
    reason_code: str = ""
    source: ProposalSource = ProposalSource.DETERMINISTIC
    payload: Mapping[str, JsonValue] = field(default_factory=dict)

@dataclass(frozen=True)
class ActionValidation:
    accepted: bool
    code: str
    message: str
```

Define recursive `JsonValue`; payloads cannot contain ORM instances.

- [ ] **Step 3: Move action rules and effects behind registry definitions**

`ActionDefinition` contains `action_type`, required `target_kind`, validation handler, execution handler, event type, and public label. Move current need effects and validation into handlers. `wait` has no target/effect. Keep `clamp_need` pure.

- [ ] **Step 4: Convert deterministic policy**

Change:

```python
def decide_action(
    actor: NpcSnapshot,
    world: WorldSnapshot,
) -> ActionProposal:
```

Use `reason_code`, `ProposalSource.DETERMINISTIC`, and `talk` instead of `social`. Preserve current priority and role routines.

- [ ] **Step 5: Keep one compatibility adapter**

`action_rules.py` delegates to one `DEFAULT_ACTION_REGISTRY`. It may raise `ActionValidationError` for legacy callers, but it contains no duplicated action rules.

- [ ] **Step 6: Verify registry and old deterministic behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_action_registry.py tests\backend\test_world_engine.py tests\backend\test_action_explanation.py -q -p no:cacheprovider --basetemp .test-tmp\registry
```

Expected: outcomes are unchanged except for `social -> talk`.

---

### Task 4: Add Pure Orchestration, Resolution, and Trace Drafts

**Files:**
- Create: `backend/app/agents/conflict_resolver.py`
- Create: `backend/app/agents/orchestrator.py`
- Modify: `backend/app/agents/contracts.py`
- Modify: `backend/app/world/tick_engine.py`
- Create: `tests/backend/test_agent_orchestrator.py`
- Modify: `tests/backend/test_world_engine.py`

**Interfaces:**
- Produces: `resolve_proposals(world, proposals, registry) -> tuple[ResolvedProposal, ...]`.
- Produces: `run_deterministic_advance(world, registry=DEFAULT_ACTION_REGISTRY) -> AgentRuntimeResult`.
- Preserves: `run_tick(world)` as a thin synchronous compatibility entry point.

- [ ] **Step 1: Write resolver and shared-snapshot tests**

Add tests for actor sort order, input-order independence, unknown actors, duplicate actor proposals, invalid proposals, and immutable same-run perception. Duplicate proposals use rejection code `duplicate_actor_proposal`.

- [ ] **Step 2: Define result contracts**

```python
@dataclass(frozen=True)
class ResolvedProposal:
    proposal: ActionProposal
    validation: ActionValidation

@dataclass(frozen=True)
class AgentRuntimeResult:
    world: WorldSnapshot
    proposals: tuple[ActionProposal, ...]
    resolutions: tuple[ResolvedProposal, ...]
    events: tuple[DomainEventDraft, ...]
    traces: tuple[TraceDraft, ...]
```

`DomainEventDraft` includes type, actor, description, JSON payload, visibility, and optional causation reference. `TraceDraft` includes stable sequence, stage, optional actor, summary, JSON data, and visibility.

- [ ] **Step 3: Implement deterministic resolution**

Build actor order from the immutable snapshot. Sort by actor sort order, actor ID, then original proposal ordinal. Reject unknown actors, a second proposal for one actor, and registry-invalid proposals. Resolution never mutates world state.

- [ ] **Step 4: Implement one-hour orchestration**

Execute this order:

```text
advance day/time and clock_tick
apply passive drift
build one immutable decision snapshot
produce all proposals from that snapshot
resolve all proposals
execute accepted proposals independently from that snapshot
increment world_version once
create one npc_action event per accepted proposal
create run/proposal/validation/execution/event trace drafts
return AgentRuntimeResult without database access
```

Every event payload includes action type, target, reason code, and proposal ordinal.

- [ ] **Step 5: Test factual trace output**

```python
assert result.traces[0].stage == "run_started"
assert result.traces[-1].stage == "run_completed"
assert all("chain_of_thought" not in entry.data for entry in result.traces)
```

- [ ] **Step 6: Run pure runtime tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_agent_orchestrator.py tests\backend\test_world_engine.py -q -p no:cacheprovider --basetemp .test-tmp\orchestrator
```

Expected: deterministic equality, shared snapshot, stable order, rejection, and trace tests pass.

---

### Task 5: Persist the Runtime Graph Atomically and Expose Trace Reads

**Files:**
- Modify: `backend/app/database/models.py`
- Create: `backend/migrations/versions/0003_agent_runtime_foundation.py`
- Modify: `backend/app/database/world_tick_repository.py`
- Create: `backend/app/database/agent_run_repository.py`
- Modify: `backend/app/services/world_tick_service.py`
- Create: `backend/app/schemas/agent_run.py`
- Modify: `backend/app/schemas/world_tick.py`
- Create: `backend/app/api/agent_runs.py`
- Modify: `backend/app/api/world_tick.py`
- Modify: `backend/app/main.py`
- Create: `tests/backend/test_agent_run_repository.py`
- Create: `tests/backend/test_agent_run_api.py`
- Modify: `tests/backend/test_world_tick.py`
- Modify: `tests/backend/test_seed_world.py`

**Interfaces:**
- Produces: `persist_run(run_id, expected_world_version, result) -> PersistedAgentRun`.
- Produces: `AgentRunRepository.get_detail(run_id) -> AgentRunDetailRecord`.
- Produces: `GET /api/agent-runs/{run_id}`.
- Changes: synchronous tick response gains `run` summary.

- [ ] **Step 1: Write persistence invariants**

Add tests proving complete atomic write, no history on stale version, rollback on malformed result, gap-free event sequence across runs, ordered read models, canonical reset cleanup, and preservation of other worlds.

- [ ] **Step 2: Add extensible persistence models**

Create:

```text
AgentRun:
  id, world_id, mode, trigger_type, status,
  base/result world_version, base/result clock_tick,
  correlation_id, created_at, started_at, completed_at, error_code

ActionProposalRecord:
  id, run_id, ordinal, actor_id, action_type,
  target_kind, target_id, reason_code, source, payload_json,
  status, rejection_code, rejection_message

AgentTraceEntry:
  id, run_id, sequence, stage, actor_id,
  summary, data_json, visibility, created_at
```

Update `WorldAction` with run/proposal references, world version, clock tick, reason code, and `executed` status. Enrich `Event` with world version, clock tick, event sequence, nullable actor/action/source event, JSON payload, visibility, secrecy, causation ID, correlation ID, and creation time. Do not constrain action types in SQL.

Migration `0003` drops the legacy action-type, target-kind, action-status, and event-type checks. Extensibility is enforced by application registries and schema validation instead of repeated table rewrites.

- [ ] **Step 3: Backfill existing history in migration `0003`**

For each legacy `(world_id, clock_tick)` group, create one synthetic completed deterministic run. Create accepted proposals in actor order, attach actions, and assign events a contiguous per-world sequence in old ID order. Preserve descriptions and timestamps. Never edit migrations `0001` or `0002` after this point.

- [ ] **Step 4: Persist one run with one commit**

`persist_run` must validate base/result versions and clock values; compare-and-swap `WorldState.world_version`; update clock, NPCs, and event counter; insert run, every accepted/rejected proposal, accepted actions, ordered events, and trace; then commit once. Any conflict, validation error, or database exception rolls back all rows.

Update player travel and quest persistence to emit `player_travelled` and `quest_transitioned` domain events in their existing transactions. Allocate each event's sequence from `WorldState.event_sequence`; ordinary chat transcript persistence emits no domain event. This makes event ordering span both player and NPC mutations.

- [ ] **Step 5: Add redaction-safe response schemas**

Tick response includes:

```json
{
  "run": {
    "id": "uuid",
    "mode": "deterministic",
    "trigger_type": "world_advance",
    "status": "completed",
    "base_world_version": 0,
    "resulting_world_version": 1,
    "base_clock_tick": 0,
    "resulting_clock_tick": 1
  },
  "world": {},
  "actions": [],
  "events": []
}
```

Run detail includes summary, proposals, events, and trace. It excludes prompts, secrets, credentials, raw exceptions, and hidden reasoning.

- [ ] **Step 6: Add run read API**

`GET /api/agent-runs/{run_id}` returns 404 for unknown UUID, 422 for malformed UUID, and 503 for persistence failure. Proposals, events, and trace are explicitly ordered by ordinal/event sequence/trace sequence.

- [ ] **Step 7: Make demo reset runtime-aware**

Delete trace, events, actions, proposals, and runs for the canonical world in foreign-key-safe order. Preserve other worlds and reset canonical counters to zero.

- [ ] **Step 8: Run persistence/API tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_agent_run_repository.py tests\backend\test_agent_run_api.py tests\backend\test_world_tick.py tests\backend\test_seed_world.py -q -p no:cacheprovider --basetemp .test-tmp\persistence
```

Expected: all selected tests pass, including rollback and stale-result cases.

---

### Task 6: Migrate the Frontend Contract Without Changing the RPG Flow

**Files:**
- Modify: `frontend/src/types/world.ts`
- Modify: `frontend/src/types/worldTick.ts`
- Modify: `frontend/src/types/npc.ts`
- Modify: `frontend/src/types/playerQuest.ts`
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/api/world.ts`
- Modify: `frontend/src/api/playerQuest.ts`
- Modify: `frontend/src/stores/world.ts`
- Modify: `frontend/src/stores/playerQuest.ts`
- Modify: `frontend/src/views/TownView.vue`
- Modify: `frontend/src/components/TickPanel.vue`
- Modify: `frontend/src/components/NpcDetailPanel.vue`
- Modify: `tests/frontend/fixtures.ts`
- Modify: `tests/frontend/world.spec.ts`
- Modify: `tests/frontend/worldTick.spec.ts`
- Modify: `tests/frontend/TickPanel.spec.ts`
- Modify: `tests/frontend/TownView.spec.ts`
- Modify: `tests/frontend/phase2Acceptance.spec.ts`
- Modify: `tests/frontend/NpcDetailPanel.spec.ts`
- Modify: `tests/frontend/npcDetail.spec.ts`
- Modify: `tests/frontend/demoApi.spec.ts`
- Modify: `tests/frontend/playerQuestApi.spec.ts`
- Modify: `tests/frontend/playerQuest.spec.ts`

**Interfaces:**
- Consumes: `WorldInfo` with three counters and synchronous `AgentRunSummary`.
- Produces: `advanceWorldTick(expectedWorldVersion: number)`.
- Preserves: current duplicate-click and conflict-refresh behavior.

- [ ] **Step 1: Update tests before TypeScript types**

Assert the request uses current `world_version`, response replaces all three counters, and player travel refreshes the world before another mutation.

```typescript
expect(advance).toHaveBeenCalledWith(0)
expect(store.data?.world).toMatchObject({
  world_version: 1,
  clock_tick: 1,
  event_sequence: 3,
})
```

- [ ] **Step 2: Rename contracts and add run summary**

```typescript
export interface WorldInfo {
  id: string
  name: string
  day: number
  time: string
  world_version: number
  clock_tick: number
  event_sequence: number
}

export interface AgentRunSummary {
  id: string
  mode: 'deterministic'
  trigger_type: 'world_advance'
  status: 'completed'
  base_world_version: number
  resulting_world_version: number
  base_clock_tick: number
  resulting_clock_tick: number
}
```

Actions use `clock_tick`. Events also expose `world_version` and `event_sequence`.

- [ ] **Step 3: Send global concurrency tokens**

Tick posts `{expected_world_version}`. Travel posts `{target_location_id, expected_world_version}`. Quest interaction posts `{interaction, expected_version, expected_world_version}`.

- [ ] **Step 4: Refresh after player/quest mutations**

`TownView` passes the current world version into player/quest store mutations. After success, reload the world store before enabling another mutation. Keep existing in-flight guards and conflict messages.

- [ ] **Step 5: Keep technical versions out of gameplay controls**

Display:

```vue
<h3>第 {{ tick.world.world.clock_tick }} 回合 · {{ tick.world.world.time }}</h3>
```

Watch `world_version` to refresh an open NPC detail. Do not add mode toggles or Agent Lab UI.

- [ ] **Step 6: Verify frontend**

Run:

```powershell
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build
```

Expected: every command exits zero. If the sandbox blocks `frontend/node_modules/.vite-temp`, rerun verification with approved host permissions; do not alter product code to bypass the sandbox.

---

### Task 7: Enable PostgreSQL/pgvector and Complete Acceptance

**Files:**
- Modify: `backend/app/database/connection.py`
- Modify: `compose.yaml`
- Create: `compose.postgres-test.yaml`
- Modify: `backend/Dockerfile`
- Modify: `.env.example`
- Modify: `.env.production.example`
- Create: `tests/backend/test_postgres_runtime.py`
- Modify: `tests/backend/test_deploy.py`
- Modify: `README.md`
- Modify: `docs/05_Engineering_Architecture.md`
- Modify: `docs/06_API_Contract.md`
- Modify: `docs/07_Database_Schema.md`
- Modify: `docs/09_Decision_Log.md`
- Modify: `docs/14_Development_Environment.md`

**Interfaces:**
- Produces: Docker deployment on `pgvector/pgvector:0.8.6-pg17-bookworm`.
- Consumes: `postgresql+psycopg://` database URLs.
- Preserves: SQLite default in local `.env.example` and automated tests.

- [ ] **Step 1: Write opt-in PostgreSQL acceptance test**

Read `TEST_POSTGRES_URL` and skip with one explicit reason when absent. When present: upgrade, seed, verify extension version `0.8.6`, execute one run, and assert one completed run, three proposals/actions/events, ordered trace, `world_version == 1`, and `clock_tick == 1`.

- [ ] **Step 2: Add internal PostgreSQL service**

```yaml
db:
  image: pgvector/pgvector:0.8.6-pg17-bookworm
  environment:
    POSTGRES_DB: ${POSTGRES_DB:-aleria}
    POSTGRES_USER: ${POSTGRES_USER:-aleria}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
    interval: 5s
    timeout: 5s
    retries: 12
  volumes:
    - aleria_postgres_data:/var/lib/postgresql/data
```

Backend depends on healthy `db` and defaults to a `postgresql+psycopg` URL in Compose. The base deployment does not publish database port 5432.

Create `compose.postgres-test.yaml` solely for host-side integration tests:

```yaml
services:
  db:
    ports:
      - "127.0.0.1:${TEST_POSTGRES_PORT:-55432}:5432"
```

- [ ] **Step 3: Keep dialect handling narrow**

SQLite retains `check_same_thread=False` and foreign keys. PostgreSQL uses normal engine arguments and Psycopg 3. Do not register vector-valued ORM columns yet; this phase enables the extension, and the memory phase introduces the first vector column.

- [ ] **Step 4: Update deployment tests and documentation**

Tests assert the pinned image, healthy dependency, named PostgreSQL volume, and unchanged web/backend health checks. Documentation explains:

```text
Snapshot -> ActionProposal -> Registry validation
-> deterministic resolution -> atomic world/run/action/event/trace commit
```

Update API examples, migration commands, SQLite light mode, PostgreSQL Docker mode, and the decision to defer async submission.

- [ ] **Step 5: Run complete automated verification**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp .test-tmp\final
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build
docker compose --env-file .env.production.example config --quiet
git diff --check
git status --short
```

Expected: tests, type checking, build, and Compose validation pass; `git diff --check` prints nothing.

- [ ] **Step 6: Run PostgreSQL smoke verification when Docker is available**

Run through the test-only Compose override; never add a host database port to the base topology:

```powershell
$env:POSTGRES_PASSWORD = "aleria-test-only"
$env:TEST_POSTGRES_PORT = "55432"
docker compose -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example up -d --build db backend
$env:TEST_POSTGRES_URL = "postgresql+psycopg://aleria:aleria-test-only@127.0.0.1:55432/aleria"
.\.venv\Scripts\python.exe -m pytest tests\backend\test_postgres_runtime.py -q -p no:cacheprovider --basetemp .test-tmp\postgres
docker compose -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example down
```

Expected: the PostgreSQL test passes. `down` keeps the named database volume because it does not use `-v`.

- [ ] **Step 7: Stop for user review**

Report changed files grouped by runtime, persistence, API, frontend, deployment, and docs; exact test results; PostgreSQL smoke status; contract changes; known risks; and suggested manual commit message `feat: establish observable agent runtime foundation`.

Leave every file unstaged and uncommitted.

## Phase Acceptance Checklist

- [ ] Existing deterministic outcomes remain stable, except `social` is intentionally renamed to `talk`.
- [ ] Every deterministic decision has proposal, validation, execution, event, and trace records.
- [ ] Advancement, travel, and quest transition increment `world_version` once; only advancement increments `clock_tick`.
- [ ] Events have a gap-free per-world `event_sequence`.
- [ ] Proposals use one immutable snapshot and resolve independently of input order.
- [ ] Invalid, duplicate, stale, or failed runs cannot partially mutate the world.
- [ ] Existing SQLite databases upgrade without data loss; empty SQLite/PostgreSQL databases reach Alembic head.
- [ ] Docker uses PostgreSQL with pgvector; fast tests remain on SQLite.
- [ ] `/api/world/tick` stays synchronous and the RPG keeps one advance control.
- [ ] `GET /api/agent-runs/{run_id}` returns a redaction-safe factual trace.
- [ ] Backend and frontend tests, type checking, build, Compose validation, and diff checks pass.
- [ ] The agent performed no Git staging or commit.

## Deferred to Later Plans

- Memory, embeddings, retrieval, beliefs, reflection, and LangGraph.
- LLM goals, plans, and proposals plus runtime mode controls.
- Celery, Redis, transactional outbox, async `202`, SSE, retries, cancellation, and budgets.
- Relationships, NPC conversations, secrecy propagation, and social conflict rules.
- Forest Embers branching, Agent Lab UI, benchmark dashboard, and live-model evaluation.

## Primary References

- Alembic migration environment: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- pgvector server and Docker tags: https://github.com/pgvector/pgvector
- pgvector SQLAlchemy/Psycopg support: https://github.com/pgvector/pgvector-python
- Psycopg 3 installation: https://pypi.org/project/psycopg/
