# Phase 1A Deterministic World Tick Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested, user-triggered, deterministic one-hour World Tick from Vue UI through FastAPI and SQLite, with atomic state/history persistence and optimistic concurrency.

**Architecture:** Keep the World Engine pure and database-independent. The application service coordinates it with a transactional repository; HTTP and Vue adapters translate contracts without owning domain rules. Every NPC decides from one post-drift immutable snapshot.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, pytest; Vue 3, TypeScript, Pinia, Axios, Vitest, Vue Test Utils.

**Approved constraints:** No PixiJS, Quest, RAG, complex Memory, LLM agent, or multiplayer work. Do not stage or commit automatically; stop with a reviewable diff and test evidence.

---

### Task 1: Define clock and deterministic decision behavior

**Files:**
- Create: `backend/app/world/__init__.py`
- Create: `backend/app/world/types.py`
- Create: `backend/app/world/clock.py`
- Create: `backend/app/world/decision.py`
- Test: `tests/backend/test_world_engine.py`

- [ ] Write literal, table-driven failing tests for hour/day rollover and the four time-phase boundaries.
- [ ] Write failing decision tests proving initial morning actions are Ryan=`work`, Shir=`move`, Grey=`work`, and proving role/time, low-energy, low-social, and low-mood priority branches.
- [ ] Run `pytest tests/backend/test_world_engine.py -q` and confirm failures are for missing behavior.
- [ ] Implement immutable engine value types, `advance_clock`, `get_time_phase`, and deterministic `decide_action` with `sort_order` tie-breaking.
- [ ] Run the focused tests until green, then refactor without changing behavior.

### Task 2: Validate/execute actions and assemble a pure tick

**Files:**
- Create: `backend/app/world/action_rules.py`
- Create: `backend/app/world/tick_engine.py`
- Modify: `tests/backend/test_world_engine.py`

- [ ] Add failing tests for target validation, location requirements, 0–100 clamping, stable event descriptions, repeatability, and same-snapshot/order-independent outcomes.
- [ ] Run the focused test and observe the intended failures.
- [ ] Implement passive drift, action validation/effects, one-action-per-NPC tick orchestration, and deterministic event records.
- [ ] Run `pytest tests/backend/test_world_engine.py -q` until green.

### Task 3: Add Phase 1A persistence and atomic repository

**Files:**
- Modify: `backend/app/database/models.py`
- Create: `backend/app/database/world_tick_repository.py`
- Modify: `tests/backend/conftest.py`
- Create: `tests/backend/test_world_tick.py`

- [ ] Add failing integration tests proving a tick atomically updates clock/NPCs and inserts exactly three actions/events.
- [ ] Add failing tests proving invalid execution rolls back every write and two requests using the same expected tick cannot both persist.
- [ ] Implement constrained `Action` and `Event` models and a repository transaction using `UPDATE ... WHERE tick = expected_tick`.
- [ ] Flush action IDs before linked events, commit once, and map persisted state back to domain/API data.
- [ ] Run `pytest tests/backend/test_world_tick.py -q` until green.

### Task 4: Expose the World Tick API

**Files:**
- Create: `backend/app/schemas/world_tick.py`
- Create: `backend/app/services/world_tick_service.py`
- Create: `backend/app/api/world_tick.py`
- Modify: `backend/app/main.py`
- Modify: `tests/backend/test_world_tick.py`

- [ ] Add failing HTTP tests for 200 complete response, 409 stale tick, 503 uninitialized database, schema validation, and unchanged `GET /api/world` compatibility.
- [ ] Implement typed request/result schemas, service orchestration, error mapping, router registration, and POST CORS support.
- [ ] Run focused backend tests, then `pytest tests/backend -q`.

### Task 5: Add frontend Tick state and API adapter

**Files:**
- Create: `frontend/src/types/worldTick.ts`
- Modify: `frontend/src/api/world.ts`
- Modify: `frontend/src/stores/world.ts`
- Create: `tests/frontend/worldTick.spec.ts`
- Modify: `tests/frontend/fixtures.ts`

- [ ] Add failing tests proving the request sends the current `expected_tick`, prevents duplicate submissions, updates the world on success, preserves it on ordinary failure, and reloads after 409.
- [ ] Implement Tick response types, a typed conflict error, API adapter, and Pinia state/actions (`advancing`, `tickError`, `lastTick`).
- [ ] Run `npm test -- --run tests/frontend/worldTick.spec.ts` until green.

### Task 6: Complete the visible frontend loop

**Files:**
- Create: `frontend/src/components/TickPanel.vue`
- Modify: `frontend/src/views/TownView.vue`
- Modify: `frontend/src/style.css`
- Modify: `tests/frontend/TownView.spec.ts`

- [ ] Add failing component tests for the advance control, busy state, error notice, updated clock/status, and action/event result rendering.
- [ ] Implement an accessible button and compact Tick result panel without introducing a game-rendering library.
- [ ] Run all frontend tests, then `npm run type-check` and `npm run build`.

### Task 7: Synchronize contracts and verify the closure

**Files:**
- Modify: `README.md`
- Modify: `docs/03_World_Model.md`
- Modify: `docs/05_Engineering_Architecture.md`
- Modify: `docs/06_API_Contract.md`
- Modify: `docs/07_Database_Schema.md`
- Modify: `docs/09_Decision_Log.md`
- Modify: `docs/11_Project_Structure.md`
- Modify: `docs/13_Development_Roadmap.md`

- [ ] Document exact phase boundaries, deterministic priority/effects, transaction model, request/response/error contract, new file tree, and roadmap completion without describing out-of-scope future work as implemented.
- [ ] Recreate/seed a disposable SQLite database and verify GET → POST Tick → GET returns one consistent state and three linked action/event rows.
- [ ] Run full backend tests, full frontend tests, type-check, and production build from a clean process.
- [ ] Inspect `git diff --check`, `git status --short`, and the complete diff; do not stage or commit.
- [ ] Present modified files, core implementation, exact test commands/results, risks, and next-step recommendations for human review.
