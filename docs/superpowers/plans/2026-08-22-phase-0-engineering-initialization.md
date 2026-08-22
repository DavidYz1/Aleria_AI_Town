# Phase 0 Engineering Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first tested Aleria AI Town vertical slice from SQLite seed data through `GET /api/world` to a Vue town overview.

**Architecture:** A FastAPI modular monolith reads the current world through a SQLAlchemy repository and exposes a stable Pydantic response contract. A Vue 3 frontend uses a typed API adapter and Pinia store so the first CSS/DOM view can later be replaced by an open-source interface or PixiJS renderer without changing backend domain contracts.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, pytest, Vue 3, TypeScript, Vite, Pinia, Axios, Vitest, Vue Test Utils.

**Spec:** `docs/superpowers/specs/2026-08-22-phase-0-engineering-initialization-design.md`

## Global Constraints

- Use Python 3.11 or newer and Node.js 20 or newer.
- SQLite is the only runtime state source; `data/*.json` is seed/config input only.
- The public contract uses `tick`, `role`, `location_id`, `current_action`, and integer `energy`/`mood`/`social` values from 0 through 100.
- `GET /api/world` returns exactly two locations and Ryan, Shir, and Grey in persisted `sort_order`.
- Do not implement Tick, NPC Detail, Chat, LLM providers, PixiJS, Quest, RAG, complex Memory, Relationship, multiplayer, authentication, or deployment infrastructure.
- Use TDD for behavior: write the test, run it and confirm the expected failure, write the minimum implementation, then rerun the focused and relevant full suites.
- Do not run `git commit`. After implementation, show `git diff`, untracked files, verification output, and a change explanation for human review.
- Preserve all existing design documents except for the explicitly approved synchronization changes.

---

### Task 1: Establish the monorepo foundation and deterministic SQLite seed

**Files:**

- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/__init__.py`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/database/__init__.py`
- Create: `backend/app/database/connection.py`
- Create: `backend/app/database/models.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/seed.py`
- Create: `backend/data/.gitkeep`
- Create: `data/world.json`
- Create: `data/locations.json`
- Create: `data/npcs.json`
- Create: `prompts/.gitkeep`
- Create: `scripts/seed_world.py`
- Create: `tests/backend/conftest.py`
- Create: `tests/backend/test_seed_world.py`

**Interfaces:**

- Produces: `Settings.database_url: str`, `Settings.frontend_origin: str`, and cached `get_settings() -> Settings`.
- Produces: `Base`, `WorldState`, `Location`, `NpcProfile`, and `NpcState` SQLAlchemy models.
- Produces: `create_engine_and_session(database_url: str) -> tuple[Engine, sessionmaker[Session]]`.
- Produces: `load_seed_data(seed_dir: Path) -> SeedData` and `seed_database(database_url: str, seed_dir: Path) -> None`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Add dependency and repository configuration files**

Create `backend/requirements.txt` with compatible bounded major versions:

```text
fastapi>=0.115,<1.0
uvicorn[standard]>=0.34,<1.0
pydantic>=2.10,<3.0
pydantic-settings>=2.7,<3.0
sqlalchemy>=2.0,<3.0
pytest>=8.3,<9.0
httpx>=0.28,<1.0
```

Create `.env.example`:

```dotenv
APP_ENV=development
DATABASE_URL=sqlite:///./backend/data/aleria.db
FRONTEND_ORIGIN=http://localhost:5173
LLM_PROVIDER=mock
ENABLE_LLM=false
GEMINI_API_KEY=
OPENAI_API_KEY=
```

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
backend/data/*.db
backend/data/*.db-*
frontend/node_modules/
frontend/dist/
frontend/coverage/
frontend/.vite/
*.log
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Write the failing idempotent-seed test**

Create `tests/backend/conftest.py`:

```python
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'aleria-test.db').as_posix()}"


@pytest.fixture
def seed_dir() -> Path:
    return REPO_ROOT / "data"
```

Create the first test in `tests/backend/test_seed_world.py`:

```python
from sqlalchemy import func, select

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import Location, NpcProfile, NpcState, WorldState
from scripts.seed_world import seed_database


def test_seed_database_is_idempotent(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    seed_database(database_url, seed_dir)

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorldState)) == 1
        assert session.scalar(select(func.count()).select_from(Location)) == 2
        assert session.scalar(select(func.count()).select_from(NpcProfile)) == 3
        assert session.scalar(select(func.count()).select_from(NpcState)) == 3
        world = session.get(WorldState, "aleria-town")
        ryan = session.get(NpcState, "ryan")

    assert world is not None
    assert (world.name, world.day, world.time, world.tick) == ("晨曦镇", 1, "08:00", 0)
    assert ryan is not None
    assert (ryan.location_id, ryan.energy, ryan.mood, ryan.social) == (
        "park",
        80,
        78,
        70,
    )
```

The production change this test catches is a seed implementation that duplicates stable records or fails to restore the canonical initial state.

- [ ] **Step 3: Run the seed test and verify RED**

Run from the repository root:

```bash
pytest tests/backend/test_seed_world.py::test_seed_database_is_idempotent -v
```

Expected: FAIL during collection because `backend.app.database` and `scripts.seed_world` do not exist yet.

- [ ] **Step 4: Implement configuration, models, seed schemas, seed data, and seeding**

Implement `backend/app/core/config.py`:

```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = f"sqlite:///{(REPO_ROOT / 'backend/data/aleria.db').as_posix()}"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Implement `backend/app/database/connection.py` with one engine factory and SQLite foreign-key enforcement:

```python
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def create_engine_and_session(
    database_url: str,
) -> tuple[Engine, sessionmaker[Session]]:
    is_sqlite = database_url.startswith("sqlite")
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    if is_sqlite:
        event.listen(
            engine,
            "connect",
            lambda dbapi_connection, _: dbapi_connection.execute("PRAGMA foreign_keys=ON"),
        )
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
```

Implement `backend/app/database/models.py` with SQLAlchemy 2 typed mappings and database constraints:

```python
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WorldState(Base):
    __tablename__ = "world_state"
    __table_args__ = (
        CheckConstraint("day >= 1"),
        CheckConstraint("tick >= 0"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    tick: Mapped[int] = mapped_column(Integer, nullable=False)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)


class NpcProfile(Base):
    __tablename__ = "npc_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    personality_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)


class NpcState(Base):
    __tablename__ = "npc_states"
    __table_args__ = (
        CheckConstraint("energy BETWEEN 0 AND 100"),
        CheckConstraint("mood BETWEEN 0 AND 100"),
        CheckConstraint("social BETWEEN 0 AND 100"),
    )
    npc_id: Mapped[str] = mapped_column(
        ForeignKey("npc_profiles.id"), primary_key=True
    )
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"), nullable=False)
    current_action: Mapped[str] = mapped_column(String, nullable=False)
    energy: Mapped[int] = mapped_column(Integer, nullable=False)
    mood: Mapped[int] = mapped_column(Integer, nullable=False)
    social: Mapped[int] = mapped_column(Integer, nullable=False)
```

Implement `backend/app/schemas/seed.py` with `SeedWorld`, `SeedLocation`, `SeedNpcStatus`, `SeedNpc`, and `SeedData`. For this first GREEN step, type every need as `int`; use `Field(ge=1)` for day/sort order, `Field(ge=0)` for tick, and `Literal["move", "rest", "work", "eat", "social"]` for `current_action`. The 0-100 boundary is added only after its failing test in Step 6.

Create literal seed files matching the approved contract:

```json
// data/world.json
{"id":"aleria-town","name":"晨曦镇","day":1,"time":"08:00","tick":0}
```

```json
// data/locations.json
[
  {"id":"tavern","name":"星辰酒馆","description":"冒险者交流和休息的地方","sort_order":1},
  {"id":"park","name":"中央公园","description":"居民散步和放松的地方","sort_order":2}
]
```

```json
// data/npcs.json
[
  {"id":"ryan","name":"Ryan","role":"Knight","personality":["optimistic","brave","kind"],"sort_order":1,"state":{"location_id":"park","current_action":"rest","energy":80,"mood":78,"social":70}},
  {"id":"shir","name":"Shir","role":"Assassin","personality":["quiet","introverted","observant"],"sort_order":2,"state":{"location_id":"tavern","current_action":"eat","energy":72,"mood":65,"social":35}},
  {"id":"grey","name":"Grey","role":"Guardian","personality":["reliable","calm","protective"],"sort_order":3,"state":{"location_id":"park","current_action":"work","energy":88,"mood":74,"social":55}}
]
```

Implement `scripts/seed_world.py` so `load_seed_data()` parses all three files into `SeedData`; `seed_database()` calls `Base.metadata.create_all()`, `Session.merge()` for each stable ID, and one final `commit()`. Its CLI uses `get_settings().database_url`, prints a concise success line, and exits non-zero on JSON, validation, or database errors.

- [ ] **Step 5: Run the seed test and verify GREEN**

```bash
pytest tests/backend/test_seed_world.py::test_seed_database_is_idempotent -v
```

Expected: PASS with one world, two locations, three profiles, and three states after two seed runs.

- [ ] **Step 6: Write and verify the invalid-seed RED/GREEN cycle**

Add a test that copies the complete seed fixture into `tmp_path`, changes Ryan's energy to `101`, and calls `load_seed_data()`:

```python
import json
import shutil

import pytest
from pydantic import ValidationError

from scripts.seed_world import load_seed_data


def test_seed_data_rejects_need_outside_zero_to_one_hundred(tmp_path, seed_dir):
    invalid_seed_dir = tmp_path / "data"
    shutil.copytree(seed_dir, invalid_seed_dir)
    npcs_path = invalid_seed_dir / "npcs.json"
    npcs = json.loads(npcs_path.read_text(encoding="utf-8"))
    npcs[0]["state"]["energy"] = 101
    npcs_path.write_text(json.dumps(npcs, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_seed_data(invalid_seed_dir)
```

Run the test against the current integer-only need schema and confirm it fails because no `ValidationError` is raised. Change all three need fields to `Annotated[int, Field(ge=0, le=100)]`, rerun the focused test, then run:

```bash
pytest tests/backend/test_seed_world.py -v
```

Expected: both seed tests PASS.

- [ ] **Step 7: Human review checkpoint — no commit**

Run `git status --short` and `git diff -- . ':!docs'`. Report created files, test output, and any dependency-install issue. Do not stage or commit.

---

### Task 2: Expose the tested `GET /api/world` backend contract

**Files:**

- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/world.py`
- Create: `backend/app/database/world_repository.py`
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/schemas/world.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/world_service.py`
- Create: `backend/app/main.py`
- Create: `tests/backend/test_world_api.py`

**Interfaces:**

- Consumes: `create_engine_and_session()`, SQLAlchemy models, and the seeded database from Task 1.
- Produces: `WorldRepository.get_world_records() -> WorldRecords`.
- Produces: `WorldService.get_world() -> WorldData`.
- Produces: `create_app(database_url: str | None = None) -> FastAPI` and module-level `app`.
- Produces: `GET /api/world -> ApiResponse[WorldData]` or HTTP 503 `ErrorResponse`.

- [ ] **Step 1: Write the failing success-contract API test**

Create `tests/backend/test_world_api.py`:

```python
from fastapi.testclient import TestClient

from backend.app.main import create_app
from scripts.seed_world import seed_database


def test_get_world_returns_canonical_seeded_world(database_url, seed_dir):
    seed_database(database_url, seed_dir)
    client = TestClient(create_app(database_url))

    response = client.get("/api/world")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ok"
    assert body["data"]["world"] == {
        "id": "aleria-town",
        "name": "晨曦镇",
        "day": 1,
        "time": "08:00",
        "tick": 0,
    }
    assert [item["id"] for item in body["data"]["locations"]] == ["tavern", "park"]
    assert [item["id"] for item in body["data"]["npcs"]] == ["ryan", "shir", "grey"]
    assert body["data"]["npcs"][0]["status"] == {
        "energy": 80,
        "mood": 78,
        "social": 70,
    }
```

This catches missing joins, incorrect public names, order drift, and accidental use of legacy `round`/`class` fields.

- [ ] **Step 2: Run the success test and verify RED**

```bash
pytest tests/backend/test_world_api.py::test_get_world_returns_canonical_seeded_world -v
```

Expected: FAIL because `backend.app.main` and the endpoint do not exist.

- [ ] **Step 3: Implement schemas, repository, service, app factory, and route**

In `schemas/common.py`, define a generic Pydantic envelope:

```python
from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str = "ok"


class ErrorResponse(BaseModel):
    success: bool = False
    data: None = None
    message: str
```

In `schemas/world.py`, define `WorldInfo`, `LocationInfo`, `NpcStatus`, `NpcInfo`, and `WorldData`. Use `Field(ge=0, le=100)` on status values and expose only the approved field names.

In `database/world_repository.py`:

- define a `WorldRecords` dataclass containing one `WorldState`, ordered `Location` records, and ordered `(NpcProfile, NpcState)` pairs;
- query locations and profiles with `order_by(sort_order)`;
- join `NpcProfile` to `NpcState` by stable ID;
- raise `WorldUnavailableError("world state is unavailable")` when the world row is absent. Do not translate `SQLAlchemyError` yet; Step 5 adds that behavior after its failing test.

In `services/world_service.py`, map ORM records into `WorldData`; decode `personality_json` through SQLAlchemy's JSON type and do not expose `sort_order`.

Implement the app factory in `backend/app/main.py`:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.world import router as world_router
from backend.app.core.config import get_settings
from backend.app.database.connection import create_engine_and_session


def create_app(database_url: str | None = None) -> FastAPI:
    settings = get_settings()
    _, session_factory = create_engine_and_session(database_url or settings.database_url)
    application = FastAPI(title="Aleria AI Town API")
    application.state.session_factory = session_factory
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    application.include_router(world_router)
    return application


app = create_app()
```

In `api/world.py`, define `get_session(request: Request)` from `request.app.state.session_factory`, create repository/service per request, return `ApiResponse[WorldData]`, and convert only `WorldUnavailableError` into HTTP 503 with the exact safe envelope. Let FastAPI's standard handler deal with unexpected programming errors while logging the original exception server-side.

- [ ] **Step 4: Run the success test and verify GREEN**

```bash
pytest tests/backend/test_world_api.py::test_get_world_returns_canonical_seeded_world -v
```

Expected: PASS.

- [ ] **Step 5: Write the failing unavailable-world test**

```python
def test_get_world_returns_safe_503_when_database_is_uninitialized(database_url):
    client = TestClient(create_app(database_url), raise_server_exceptions=False)

    response = client.get("/api/world")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "data": None,
        "message": "world state is unavailable",
    }
```

Run this test before adding database-exception translation. Expected RED: HTTP 500 rather than 503, proving the test catches the missing domain translation. Catch `SQLAlchemyError` inside the repository, raise `WorldUnavailableError("world state is unavailable")`, convert it in the route to the exact HTTP 503 envelope, and rerun.

- [ ] **Step 6: Verify backend GREEN and OpenAPI contract**

```bash
pytest tests/backend -v
```

Then run a short read-only inspection using `TestClient` to assert `/openapi.json` contains `/api/world`, response `200`, and response `503`. Expected: all backend tests PASS and both documented responses exist.

- [ ] **Step 7: Human review checkpoint — no commit**

Show the backend diff, explain the API-to-service-to-repository boundary, and report exact test counts. Do not stage or commit.

---

### Task 3: Scaffold the typed Vue API adapter and Pinia world store

**Files:**

- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/env.d.ts`
- Create: `frontend/src/types/world.ts`
- Create: `frontend/src/api/world.ts`
- Create: `frontend/src/stores/world.ts`
- Create: `tests/frontend/world.spec.ts`

**Interfaces:**

- Consumes: the Task 2 HTTP response contract.
- Produces: `fetchWorld() -> Promise<WorldData>`.
- Produces: `useWorldStore()` with `data`, `loading`, `error`, `isEmpty`, and `loadWorld(fetcher?)`.

- [ ] **Step 1: Create the Vite/Vue test scaffold**

Create the Vue TypeScript package with these known-compatible dependency ranges and scripts in `frontend/package.json`:

```json
{
  "name": "aleria-ai-town-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "type-check": "vue-tsc -b",
    "test": "vitest run"
  },
  "dependencies": {
    "axios": "^1.8.4",
    "pinia": "^3.0.1",
    "vue": "^3.5.13"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.3",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^26.0.0",
    "typescript": "~5.7.2",
    "vite": "^6.2.0",
    "vitest": "^3.0.9",
    "vue-tsc": "^2.2.8"
  }
}
```

Configure `vite.config.ts` with `plugins: [vue()]` and Vitest `environment: "jsdom"`, `globals: true`, and `include: ["../tests/frontend/**/*.spec.ts"]`.

- [ ] **Step 2: Write the failing store lifecycle tests**

Create `tests/frontend/world.spec.ts` with a literal complete `WorldData` fixture. Test loading and success with a deferred promise:

```typescript
it('exposes loading until the world request resolves', async () => {
  const store = useWorldStore()
  let resolve!: (value: WorldData) => void
  const request = new Promise<WorldData>((done) => { resolve = done })

  const pending = store.loadWorld(() => request)
  expect(store.loading).toBe(true)
  expect(store.error).toBeNull()

  resolve(worldFixture)
  await pending

  expect(store.loading).toBe(false)
  expect(store.data?.world.name).toBe('晨曦镇')
})
```

Add separate tests proving a rejected request clears stale data and sets `世界加载失败，请稍后重试。`, and proving empty arrays make `isEmpty` true. Initialize a fresh Pinia in `beforeEach`.

The production break these tests catch is a store that renders stale data, never leaves loading, or hides empty/error states.

- [ ] **Step 3: Run store tests and verify RED**

From `frontend/`:

```bash
npm run test -- ../tests/frontend/world.spec.ts
```

Expected: FAIL because the world types and store do not exist.

- [ ] **Step 4: Implement exact TypeScript contract, API adapter, and store**

In `src/types/world.ts`, define `ApiResponse<T>`, `WorldInfo`, `LocationInfo`, `NpcStatus`, `NpcInfo`, and `WorldData` with names and shapes identical to the approved JSON. Do not add legacy `round`, `class`, or `location` aliases.

Implement `src/api/world.ts`:

```typescript
import axios from 'axios'
import type { ApiResponse, WorldData } from '../types/world'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  timeout: 5000,
})

export async function fetchWorld(): Promise<WorldData> {
  const response = await api.get<ApiResponse<WorldData>>('/api/world')
  return response.data.data
}
```

Implement `src/stores/world.ts` with a production-useful injectable boundary:

```typescript
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchWorld } from '../api/world'
import type { WorldData } from '../types/world'

type WorldFetcher = () => Promise<WorldData>

export const useWorldStore = defineStore('world', () => {
  const data = ref<WorldData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const isEmpty = computed(
    () => data.value !== null && (data.value.locations.length === 0 || data.value.npcs.length === 0),
  )

  async function loadWorld(fetcher: WorldFetcher = fetchWorld): Promise<void> {
    loading.value = true
    error.value = null
    try {
      data.value = await fetcher()
    } catch {
      data.value = null
      error.value = '世界加载失败，请稍后重试。'
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, isEmpty, loadWorld }
})
```

- [ ] **Step 5: Run store tests and type checking**

```bash
npm run test -- ../tests/frontend/world.spec.ts
npm run type-check
```

Expected: store tests PASS and TypeScript reports zero errors.

- [ ] **Step 6: Human review checkpoint — no commit**

Show the frontend adapter/store diff and test output. Confirm no component directly imports Axios. Do not stage or commit.

---

### Task 4: Render the first town view with loading, empty, error, and success states

**Files:**

- Create: `frontend/src/components/LocationCard.vue`
- Create: `frontend/src/components/NpcCard.vue`
- Create: `frontend/src/views/TownView.vue`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/style.css`
- Create: `tests/frontend/TownView.spec.ts`

**Interfaces:**

- Consumes: `useWorldStore()` and the Task 3 TypeScript contract.
- Produces: a CSS/DOM town overview whose components only consume typed props.
- Produces: observable loading, empty, error, and success UI states.

- [ ] **Step 1: Write failing view-state and content tests**

Create `tests/frontend/TownView.spec.ts`. Use real Pinia state and replace only the external loading action with a resolved spy so the test exercises real components:

```typescript
it('renders the canonical town, locations, and NPCs from store state', async () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useWorldStore()
  store.data = worldFixture
  vi.spyOn(store, 'loadWorld').mockResolvedValue()

  const wrapper = mount(TownView, { global: { plugins: [pinia] } })
  await flushPromises()

  expect(wrapper.get('h1').text()).toContain('晨曦镇')
  expect(wrapper.text()).toContain('Day 1 · 08:00')
  for (const text of ['星辰酒馆', '中央公园', 'Ryan', 'Shir', 'Grey']) {
    expect(wrapper.text()).toContain(text)
  }
})
```

Add separate tests for:

- `loading=true`: status element contains `正在读取晨曦镇…`;
- `error` set: alert contains the store error and a `重新加载` button;
- `isEmpty=true`: status element contains `世界数据尚未准备完成。`.

The tests assert visible user behavior; the action spy isolates the real HTTP boundary and is not itself the assertion target.

- [ ] **Step 2: Run view tests and verify RED**

```bash
cd frontend
npm run test -- ../tests/frontend/TownView.spec.ts
```

Expected: FAIL because `TownView.vue` and presentation components do not exist.

- [ ] **Step 3: Implement focused presentation components**

`LocationCard.vue` accepts one `LocationInfo` prop and renders its name and description in an `<article>`.

`NpcCard.vue` accepts one `NpcInfo` prop and a required `locationName: string`. It renders name, role, location, current action, personality tags, and labeled numeric Energy/Mood/Social values. It must not mutate the NPC or import the store.

`TownView.vue`:

- calls `store.loadWorld()` in `onMounted`;
- exposes a retry button that calls the same store action;
- checks loading, then error, then empty, then success in that order;
- builds a computed `Map<location_id, location name>` for NPC display;
- renders one location card per location and one NPC card per NPC;
- uses semantic headings, `role="status"` for loading/empty, and `role="alert"` for API failure.

Implement `App.vue` as a direct composition of `TownView`. Implement `main.ts` with `createApp(App).use(createPinia()).mount('#app')` and import `style.css`.

Implement restrained CSS with:

- a readable centered page shell;
- CSS Grid for two locations and three NPC cards;
- visible focus styles and sufficient text contrast;
- status bars for needs without Canvas or animation;
- a one-column layout below 760px.

- [ ] **Step 4: Run view tests and verify GREEN**

```bash
npm run test -- ../tests/frontend/TownView.spec.ts
```

Expected: all view tests PASS.

- [ ] **Step 5: Run the complete frontend verification**

```bash
npm run test
npm run type-check
npm run build
```

Expected: all tests PASS, TypeScript reports zero errors, and Vite creates `frontend/dist` successfully without warnings caused by project code.

- [ ] **Step 6: Human review checkpoint — no commit**

Show component boundaries, screenshots or a local browser preview if available, test output, and the frontend diff. Do not stage or commit.

---

### Task 5: Document and verify the real SQLite-to-browser closure

**Files:**

- Create: `README.md`
- Modify: `.env.example` only if the verified commands require a correction
- Modify: `docs/06_API_Contract.md` only if implementation revealed a contract defect; any change requires explicit explanation
- Modify: `docs/14_Development_Environment.md` only to match commands that were actually executed successfully

**Interfaces:**

- Consumes: all earlier task outputs.
- Produces: repeatable setup, seed, backend start, frontend start, and test instructions.
- Produces: final diff and verification evidence for human review; no Git commit.

- [ ] **Step 1: Write the README from verified behavior**

Include:

- candidate name, repository URL, experience URL, and actual time as clearly labeled user-fillable metadata fields rather than invented values;
- project positioning and current Phase 0 scope;
- Vue/FastAPI/SQLite stack;
- prerequisites;
- virtual environment, backend dependency, frontend dependency, seed, start, and verification commands;
- the exact `GET /api/world` purpose and Swagger URL;
- JSON-as-seed versus SQLite-as-runtime explanation;
- current Mock/LLM status: configured for future use but not implemented in Phase 0;
- completed features, known limitations, and the explicitly deferred systems;
- a short explanation of the API Adapter -> Store -> UI boundary and future open-source frontend migration.

- [ ] **Step 2: Run fresh full backend and frontend verification**

From the repository root:

```bash
pytest tests/backend -v
python scripts/seed_world.py
```

From `frontend/`:

```bash
npm run test
npm run type-check
npm run build
```

Expected: zero backend test failures, zero frontend test failures, zero TypeScript errors, successful production build, and a seeded `backend/data/aleria.db` ignored by Git.

- [ ] **Step 3: Run the real API smoke check**

Start the backend from the repository root:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Request `http://127.0.0.1:8000/api/world` and verify HTTP 200 plus the exact world, location, and NPC IDs. Stop the process cleanly after the check.

- [ ] **Step 4: Run the real browser closure**

With the backend running, start the frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Open the reported local URL and verify:

- 晨曦镇 and `Day 1 · 08:00` are visible;
- 星辰酒馆 and 中央公园 are visible;
- Ryan, Shir, and Grey show location, action, and three numeric status values;
- the browser console has no application errors;
- stopping the backend and refreshing shows the failure state;
- restarting the backend and choosing retry restores the world.

- [ ] **Step 5: Audit scope and contract compliance**

Run searches proving no implementation of deferred systems and no legacy public fields:

```bash
rg -n "PixiJS|Quest|RAG|vector|multiplayer|websocket" frontend backend scripts tests
rg -n '"round"|"class"|"location"\s*:' frontend backend scripts tests data
```

Expected: no deferred-system implementation and no legacy public-contract field names. Documentation mentions are allowed and must be distinguished from implementation hits.

- [ ] **Step 6: Present the final human-review package — no commit**

Provide:

```bash
git status --short
git diff --stat
git diff
```

Because the original design documents began untracked in this newly initialized repository, also compare the seven synchronized documents against the preserved pre-edit copies so the reviewer sees only the actual synchronization delta. Summarize:

- files created and modified;
- architecture and contract decisions;
- RED/GREEN evidence for each behavior;
- exact test/build results;
- known limitations;
- any deviation from this plan.

Do not stage or commit. Wait for explicit human review and submission instructions.
