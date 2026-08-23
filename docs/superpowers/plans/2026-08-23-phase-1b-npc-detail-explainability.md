# Phase 1B NPC 详情与行为解释实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现经过测试的 `GET /api/npcs/{npc_id}` 与 NPC 详情面板，让玩家查看权威当前状态、世界阶段以及最近三条带可读解释的行动历史。

**Architecture:** 新增独立的 NPC 只读查询切片：`NpcRepository → NpcService → FastAPI`，不修改确定性 Tick Engine 和数据库结构。Frontend 使用独立 `npcDetail` Pinia Store 管理选择、竞态与刷新，`TownView` 只负责协调 World Store 与 NPC Detail Store。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2、Pydantic 2、SQLite、pytest；Vue 3、TypeScript、Pinia、Axios、Vitest、Vue Test Utils。

**Spec:** `docs/superpowers/specs/2026-08-23-phase-1b-npc-detail-explainability-design.md`

## Global Constraints

- Phase 1B 只实现 NPC Detail、最近三条 Action 和确定性规则解释。
- 不新增或修改数据库表；复用 `npc_profiles`、`npc_states`、`locations`、`world_state`、`actions`。
- 不实现 Chat、LLM、Mock Provider、Prompt、Memory、Relationship、Background、Goal、PixiJS、Quest 或多人系统。
- 保持 `GET /api/world` 和 `POST /api/world/tick` 公共契约完全兼容。
- 历史解释来自持久化 `reason` 代码，不根据当前状态反推历史决策，不保存或暴露 chain-of-thought。
- 最近 Action 固定为三条，按 `tick DESC, id DESC` 排序，不增加查询参数。
- Backend 继续作为唯一事实来源；Frontend 不自行合成行动历史。
- 所有测试先红后绿；完成后运行 Backend、Frontend、type-check、build 和 `git diff --check`。
- 不执行 `git add`、`git commit` 或任何自动提交；每个任务只留下可人工 review 的工作区 diff。

---

### Task 1：建立确定性行动解释目录

**Files:**
- Create: `backend/app/services/action_explanation.py`
- Create: `tests/backend/test_action_explanation.py`

**Interfaces:**
- Consumes: 数据库 `actions.reason` 的字符串代码，以及服务层已解析的 `target_name: str | None`。
- Produces: `explain_action(reason_code: str, target_name: str | None = None) -> str`。

- [ ] **Step 1：写原因目录覆盖测试**

在 `tests/backend/test_action_explanation.py` 使用字面量参数覆盖当前 Decision Policy 产生的全部 15 个代码：

```python
@pytest.mark.parametrize(
    ("reason_code", "target_name", "expected"),
    [
        ("night_rest", None, "夜晚已经到来，因此选择休息。"),
        ("low_energy", None, "体力较低，因此选择休息恢复。"),
        ("low_social_with_companion", "Grey", "社交需求较高，因此选择与 Grey 交谈。"),
        ("low_social_find_companion", "中央公园", "社交需求较高，因此前往中央公园寻找同伴。"),
        ("low_mood_eat", None, "心情较低，因此选择用餐调整状态。"),
        ("low_mood_find_food", "星辰酒馆", "心情较低，因此前往星辰酒馆用餐。"),
        ("knight_duty_travel", "中央公园", "当前处于骑士履行职责的时间，因此前往中央公园。"),
        ("knight_duty", None, "当前处于骑士履行训练职责的时间。"),
        ("knight_evening_social", "Grey", "傍晚职责结束，因此选择与 Grey 交流。"),
        ("knight_evening_rest", None, "傍晚没有同伴在附近，因此选择休息。"),
        ("assassin_meal_travel", "星辰酒馆", "当前符合刺客的用餐安排，因此前往星辰酒馆。"),
        ("assassin_meal", None, "当前符合刺客的用餐安排，因此选择用餐。"),
        ("guardian_patrol_travel", "中央公园", "当前处于守护者巡查时间，因此前往中央公园。"),
        ("guardian_patrol", None, "当前处于守护者巡查时间，因此执行工作。"),
        ("unknown_role_rest", None, "当前没有匹配的角色例程，因此选择休息。"),
    ],
)
def test_explain_action_maps_every_current_reason_code(
    reason_code, target_name, expected
):
    assert explain_action(reason_code, target_name) == expected
```

- [ ] **Step 2：写未知代码回退测试**

```python
def test_explain_action_uses_safe_fallback_for_unknown_history():
    assert explain_action("legacy_reason") == "按照当时的世界规则执行了该行动。"
```

- [ ] **Step 3：运行测试并确认红灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend\test_action_explanation.py -q -p no:cacheprovider`

Expected: collection fails because `backend.app.services.action_explanation` does not exist.

- [ ] **Step 4：实现纯解释函数**

在 `action_explanation.py` 使用不可变字典保存不带目标的模板，并对四类需要目标的原因显式插值。未知代码必须返回固定回退文案；不得读取数据库、当前 NPC 状态或调用 LLM。

```python
FALLBACK_EXPLANATION = "按照当时的世界规则执行了该行动。"
TARGET_REASON_TEXT = {
    "low_social_with_companion": "社交需求较高，因此选择与 {target} 交谈。",
    "low_social_find_companion": "社交需求较高，因此前往 {target} 寻找同伴。",
    "low_mood_find_food": "心情较低，因此前往 {target} 用餐。",
    "knight_duty_travel": "当前处于骑士履行职责的时间，因此前往 {target}。",
    "knight_evening_social": "傍晚职责结束，因此选择与 {target} 交流。",
    "assassin_meal_travel": "当前符合刺客的用餐安排，因此前往 {target}。",
    "guardian_patrol_travel": "当前处于守护者巡查时间，因此前往 {target}。",
}
STATIC_REASON_TEXT = {
    "night_rest": "夜晚已经到来，因此选择休息。",
    "low_energy": "体力较低，因此选择休息恢复。",
    "low_mood_eat": "心情较低，因此选择用餐调整状态。",
    "knight_duty": "当前处于骑士履行训练职责的时间。",
    "knight_evening_rest": "傍晚没有同伴在附近，因此选择休息。",
    "assassin_meal": "当前符合刺客的用餐安排，因此选择用餐。",
    "guardian_patrol": "当前处于守护者巡查时间，因此执行工作。",
    "unknown_role_rest": "当前没有匹配的角色例程，因此选择休息。",
}


def explain_action(reason_code: str, target_name: str | None = None) -> str:
    target_template = TARGET_REASON_TEXT.get(reason_code)
    if target_template is not None:
        return target_template.format(target=target_name or "目标")
    return STATIC_REASON_TEXT.get(reason_code, FALLBACK_EXPLANATION)
```

- [ ] **Step 5：运行解释测试直到绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend\test_action_explanation.py -q -p no:cacheprovider`

Expected: 16 cases pass.

- [ ] **Step 6：人工 review 检查点**

检查 `git diff -- backend/app/services/action_explanation.py tests/backend/test_action_explanation.py`；不得 stage 或 commit。

---

### Task 2：实现 NPC Detail Repository 只读模型

**Files:**
- Create: `backend/app/database/npc_repository.py`
- Create: `tests/backend/test_npc_repository.py`

**Interfaces:**
- Consumes: `CANONICAL_WORLD_ID`、SQLAlchemy `Session`、现有 ORM models。
- Produces:
  - `NpcNotFoundError`
  - `NpcDetailUnavailableError`
  - `NpcActionRecord`
  - `NpcDetailRecords`
  - `NpcRepository.get_detail_records(npc_id: str) -> NpcDetailRecords`

- [ ] **Step 1：定义测试所需的字面量结果**

在测试中先播种数据库；Tick 0 查询 Ryan 时断言 Profile/State/Location/World 正确且 `actions == ()`。不要使用 Repository 自己的映射函数构造期望值。

```python
def test_repository_returns_authoritative_npc_detail_without_history(
    database_url, seed_dir
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        records = NpcRepository(session).get_detail_records("ryan")

    assert records.profile.id == "ryan"
    assert records.state.location_id == "park"
    assert records.location.name == "中央公园"
    assert (records.world.day, records.world.time, records.world.tick) == (1, "08:00", 0)
    assert records.actions == ()
```

- [ ] **Step 2：写最近三条排序测试**

使用现有 `WorldTickRepository` 和 `run_tick` 连续推进四次，然后查询 Ryan：

```python
assert [action.tick for action in records.actions] == [4, 3, 2]
assert len(records.actions) == 3
```

同时断言每条记录包含 `id`、`world_time`、`action_type`、`target_kind`、`target_id`、`reason`。

- [ ] **Step 3：写目标名称批量解析测试**

构造一条 `target_kind="location", target_id="park"` 和一条 `target_kind="npc", target_id="grey"` 的历史记录，断言：

```python
assert records.target_names[("location", "park")] == "中央公园"
assert records.target_names[("npc", "grey")] == "Grey"
```

未解析的目标不得删除 Action，后续 Service 使用原始 ID 回退。

- [ ] **Step 4：写 404 与不完整数据测试**

- 未知 Profile：`NpcNotFoundError("NPC not found")`。
- Profile 存在但 State 缺失：`NpcDetailUnavailableError("NPC detail is unavailable")`。
- World 或当前 Location 缺失：同样返回 unavailable。

- [ ] **Step 5：运行 Repository 测试并确认红灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend\test_npc_repository.py -q -p no:cacheprovider`

Expected: fails because `NpcRepository` is missing.

- [ ] **Step 6：实现 Repository dataclasses 与查询**

使用以下稳定结构：

```python
@dataclass(frozen=True)
class NpcActionRecord:
    id: int
    tick: int
    world_time: str
    action_type: str
    target_kind: str | None
    target_id: str | None
    reason: str


@dataclass(frozen=True)
class NpcDetailRecords:
    profile: NpcProfile
    state: NpcState
    location: Location
    world: WorldState
    actions: tuple[NpcActionRecord, ...]
    target_names: dict[tuple[str, str], str]
```

查询顺序固定为：

```python
select(WorldAction).where(
    WorldAction.world_id == CANONICAL_WORLD_ID,
    WorldAction.actor_id == npc_id,
).order_by(WorldAction.tick.desc(), WorldAction.id.desc()).limit(3)
```

收集最多三条记录的 `location_target_ids` 与 `npc_target_ids` 后，分别执行 `Location.id.in_(location_target_ids)` 和 `NpcProfile.id.in_(npc_target_ids)` 查询，禁止循环内查询。

- [ ] **Step 7：运行 Repository 测试直到绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend\test_npc_repository.py -q -p no:cacheprovider`

- [ ] **Step 8：人工 review 检查点**

确认 Repository 只读、无 commit、无 DTO 文案、无 N+1 查询；不得 stage 或 commit。

---

### Task 3：定义 NPC API Schema 与 Service 映射

**Files:**
- Create: `backend/app/schemas/npc.py`
- Create: `backend/app/services/npc_service.py`
- Create: `tests/backend/test_npc_service.py`

**Interfaces:**
- Consumes: `NpcRepository.get_detail_records`、`explain_action`、`get_time_phase`、现有 `ActionId`/`NpcStatus`。
- Produces:
  - `NpcProfileDetail`
  - `NpcStateDetail`
  - `NpcWorldContext`
  - `NpcRecentAction`
  - `NpcDetailData`
  - `NpcService.get_detail(npc_id: str) -> NpcDetailData`

- [ ] **Step 1：写 Service 成功映射测试**

使用真实 SQLite Repository，不 mock 数据库。断言完整字面量字段：

```python
detail = NpcService(NpcRepository(session)).get_detail("ryan")
assert detail.profile.model_dump() == {
    "id": "ryan",
    "name": "Ryan",
    "role": "Knight",
    "personality": ["optimistic", "brave", "kind"],
}
assert detail.state.location_name == "中央公园"
assert detail.world_context.time_phase == "morning"
```

- [ ] **Step 2：写 Action DTO 解释与目标回退测试**

断言已解析目标使用中文/名称；未解析目标仍保留 `target_id`，并设置 `target_name` 为原始 ID。断言 API 字段使用 `reason_code`/`reason_text`，不暴露数据库字段名 `reason`。

- [ ] **Step 3：运行 Service 测试并确认红灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend\test_npc_service.py -q -p no:cacheprovider`

- [ ] **Step 4：实现 Pydantic schemas**

字段必须与设计规格完全一致：

```python
class NpcRecentAction(BaseModel):
    id: int
    tick: int = Field(ge=1)
    world_time: str
    action_type: ActionId
    target_kind: Literal["location", "npc"] | None
    target_id: str | None
    target_name: str | None
    reason_code: str
    reason_text: str
```

`NpcDetailData` 固定包含 `profile`、`state`、`world_context`、`recent_actions`。

- [ ] **Step 5：实现 Service 映射**

- 使用 `get_time_phase(records.world.time)`。
- 使用 `records.target_names.get((kind, id), id)` 解析目标显示名。
- 使用 `explain_action(action.reason, target_name)` 生成说明。
- 无历史时返回空列表，不从 `current_action` 伪造记录。

- [ ] **Step 6：运行 Service 与解释测试直到绿灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend\test_npc_service.py tests\backend\test_action_explanation.py -q -p no:cacheprovider`

- [ ] **Step 7：人工 review 检查点**

检查 Schema 字段与 Spec JSON 一致，Service 无 SQL、Repository 无 Pydantic；不得 stage 或 commit。

---

### Task 4：暴露 GET NPC Detail API

**Files:**
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/api/npcs.py`
- Modify: `backend/app/api/world.py`
- Modify: `backend/app/api/world_tick.py`
- Modify: `backend/app/main.py`
- Create: `tests/backend/test_npc_api.py`

**Interfaces:**
- Consumes: 共享 `get_session`、`NpcRepository`、`NpcService`、`ApiResponse`/`ErrorResponse`。
- Produces: `GET /api/npcs/{npc_id}`。

- [ ] **Step 1：写 200 契约测试**

真实播种并推进一次 Tick；使用 `ASGITransport` 请求 `/api/npcs/ryan`，断言：

- HTTP 200、公共 envelope。
- Profile/State/World Context 完整。
- `recent_actions` 长度为 1。
- `reason_code == "knight_duty"`。
- `reason_text == "当前处于骑士履行训练职责的时间。"`。

- [ ] **Step 2：写历史三条与空历史 HTTP 测试**

- Tick 0 请求 Shir：`recent_actions == []`。
- 连续四 Tick 请求 Ryan：返回 Tick `[4, 3, 2]`，没有第四条。

- [ ] **Step 3：写错误响应测试**

```python
assert missing.status_code == 404
assert missing.json() == {
    "success": False,
    "data": None,
    "message": "NPC not found",
}
```

未初始化数据库及 Profile/State 部分缺失分别断言 503 与 `NPC detail is unavailable`。

- [ ] **Step 4：运行 API 测试并确认红灯**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend\test_npc_api.py -q -p no:cacheprovider`

Expected: 404 route or import failure before implementation.

- [ ] **Step 5：提取共享 Session Dependency**

把当前 `backend/app/api/world.py` 中的 `get_session` 原样移动到 `backend/app/api/dependencies.py`：

```python
def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session
```

`world.py`、`world_tick.py` 和新 `npcs.py` 都从该模块导入。不得改变 Session 生命周期；运行现有 World/Tick API 测试确认契约未变。

- [ ] **Step 6：实现 Router 与错误映射**

```python
@router.get(
    "/api/npcs/{npc_id}",
    response_model=ApiResponse[NpcDetailData],
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_npc_detail(npc_id: str, session: Session = Depends(get_session)):
    service = NpcService(NpcRepository(session))
    try:
        detail = service.get_detail(npc_id)
    except NpcNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    except NpcDetailUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(message=str(exc)).model_dump(),
        )
    return ApiResponse(data=detail)
```

404 只映射 `NpcNotFoundError`；Repository unavailable/SQLAlchemy failure统一映射 503。不要用裸 `except Exception`。

- [ ] **Step 7：在 App 注册 Router**

在 `backend/app/main.py` 引入 `npcs_router` 并 `include_router`。现有 CORS 已允许 GET，不增加 Middleware。

- [ ] **Step 8：运行全部 Backend 测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp "C:\Users\yangzhaoting\.codex\.chatgpt-projects\g-p-6a87f34c7b548191a925938d17aacd47\.pytest-tmp\phase1b-backend"`

Expected: 新增测试和现有 41 个测试全部通过。

- [ ] **Step 9：人工 review 检查点**

检查 OpenAPI response model、404/503 语义和 World/Tick 回归；不得 stage 或 commit。

---

### Task 5：实现 Frontend NPC 类型、API Adapter 与竞态安全 Store

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/types/npc.ts`
- Create: `frontend/src/api/npc.ts`
- Modify: `frontend/src/api/world.ts`
- Create: `frontend/src/stores/npcDetail.ts`
- Modify: `tests/frontend/fixtures.ts`
- Create: `tests/frontend/npcDetail.spec.ts`

**Interfaces:**
- Consumes: Backend `NpcDetailData` 契约、现有 `ApiResponse<T>` 和共享 Axios client。
- Produces:
  - `fetchNpcDetail(npcId: string) -> Promise<NpcDetailData>`
  - `NpcNotFoundError`
  - `useNpcDetailStore()`，包含 `selectedNpcId`、`data`、`loading`、`error`、`selectNpc`、`refresh`、`retry`、`close`。

- [ ] **Step 1：新增完整 TypeScript fixture 与失败测试**

Fixture 必须包含 Spec 中所有字段，不使用 Partial。首先断言：

```typescript
await store.selectNpc('ryan', () => Promise.resolve(npcDetailFixture))
expect(store.selectedNpcId).toBe('ryan')
expect(store.data?.recent_actions[0].reason_code).toBe('knight_duty')
expect(store.loading).toBe(false)
```

- [ ] **Step 2：写 loading、404、普通失败和 retry 测试**

- Promise 未完成时 `loading === true`。
- `NpcNotFoundError` 映射为“没有找到这位居民。”。
- 其他错误映射为“居民详情加载失败，请稍后重试。”。
- 错误后仍保留 `selectedNpcId`，允许 retry。

- [ ] **Step 3：写快速切换竞态测试**

创建 Ryan/Shir 两个可控 Promise：先选择 Ryan，再选择 Shir，先完成 Shir，最后完成 Ryan。最终必须仍为 Shir：

```typescript
expect(store.selectedNpcId).toBe('shir')
expect(store.data?.profile.id).toBe('shir')
```

- [ ] **Step 4：写关闭失效与 refresh 测试**

- `close()` 后完成旧 Promise，不得恢复选择或数据。
- `refresh()` 对当前 ID 发起请求，未选择时不请求。
- refresh 期间保留现有详情，成功后原子替换。

- [ ] **Step 5：运行 Store 测试并确认红灯**

Run: `npm test -- --run ..\tests\frontend\npcDetail.spec.ts`

- [ ] **Step 6：提取共享 Axios client 并实现 DTO/API Adapter**

新增 `frontend/src/api/client.ts`，把 `frontend/src/api/world.ts` 当前的 Axios 配置原样移动过去：

```typescript
import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  timeout: 5000,
})
```

`world.ts` 改为从 `client.ts` 导入 `api`，保留 `axios.isAxiosError` 所需的 Axios import 和全部既有行为。`npc.ts` 使用同一个 client，不创建第二套 base URL/timeout 配置。

`npc.ts` 的联合类型与 Backend Literal 对齐。`fetchNpcDetail` 请求：

```typescript
api.get<ApiResponse<NpcDetailData>>(`/api/npcs/${encodeURIComponent(npcId)}`)
```

Axios 404 转换为 `NpcNotFoundError`，其他错误原样抛出。

- [ ] **Step 7：实现请求令牌 Store**

Store 内部使用非响应式 `let requestVersion = 0`。每次 select/refresh 递增并捕获版本；只有版本和 `selectedNpcId` 都匹配时才能修改数据、错误或 loading。`close()` 递增版本并清空所有公开状态。

- [ ] **Step 8：运行 Store 测试与 type-check**

Run: `npm test -- --run ..\tests\frontend\npcDetail.spec.ts`

Run: `npm run type-check`

- [ ] **Step 9：人工 review 检查点**

确认 World Store 未导入 NPC Detail Store，fixture 完整，旧请求无法覆盖新选择；不得 stage 或 commit。

---

### Task 6：实现可访问的 NPC Detail Panel

**Files:**
- Create: `frontend/src/components/NpcDetailPanel.vue`
- Create: `tests/frontend/NpcDetailPanel.spec.ts`

**Interfaces:**
- Consumes props: `selectedNpcId: string | null`、`detail: NpcDetailData | null`、`loading: boolean`、`error: string | null`。
- Produces emits: `close`、`retry`。

- [ ] **Step 1：写关闭、loading、error、empty-history 测试**

- 无选择时不渲染 `aside`。
- loading 时 `role="status"` 显示“正在读取居民档案…”。
- error 时 `role="alert"`，重试按钮 emit `retry`。
- 关闭按钮具备 `aria-label="关闭居民详情"` 并 emit `close`。
- 空历史显示“还没有已记录的行动。”。

- [ ] **Step 2：写完整内容渲染测试**

使用真实完整组件和 fixture，断言 Ryan、Knight、三个性格、中央公园、三项数值、`Day 1 · 09:00 · morning`、行动目标与 `reason_text` 均可见。

- [ ] **Step 3：运行组件测试并确认红灯**

Run: `npm test -- --run ..\tests\frontend\NpcDetailPanel.spec.ts`

- [ ] **Step 4：实现 Presentational Panel**

根节点使用：

```vue
<aside v-if="selectedNpcId" class="npc-detail-panel" aria-labelledby="npc-detail-heading">
```

组件不得 import Store 或 API。历史列表以 `action.id` 为 key；Action label 使用本地只读映射；`reason_text` 原样展示。

- [ ] **Step 5：实现响应式 scoped CSS**

- Desktop：面板清晰独立但不遮挡 Town 内容。
- Mobile：自然堆叠为单列。
- 保持现有绿色/米色视觉 token，不加入全局 CSS 框架或动画依赖。
- `prefers-reduced-motion` 下不要求额外动画，因为本阶段不引入转场。

- [ ] **Step 6：运行组件测试与 type-check**

Run: `npm test -- --run ..\tests\frontend\NpcDetailPanel.spec.ts`

Run: `npm run type-check`

- [ ] **Step 7：人工 review 检查点**

确认 Panel 不联网、不读 Store、语义化元素完整；不得 stage 或 commit。

---

### Task 7：接通 NPC Card、TownView 与 Tick 后刷新

**Files:**
- Modify: `frontend/src/components/NpcCard.vue`
- Modify: `frontend/src/views/TownView.vue`
- Modify: `tests/frontend/TownView.spec.ts`
- Create: `tests/frontend/NpcCard.spec.ts`

**Interfaces:**
- Consumes: `useWorldStore`、`useNpcDetailStore`、`NpcDetailPanel`。
- Produces: `NpcCard` emit `select: [npcId: string]`；Town 页面 NPC 详情完整闭环。

- [ ] **Step 1：写 NpcCard 选择测试**

卡片保留现有展示，并增加显式 `查看详情` 按钮：

```typescript
await wrapper.get('button').trigger('click')
expect(wrapper.emitted('select')).toEqual([['ryan']])
```

不要把整个 `<article>` 改为不可访问的 click handler，也不要在按钮内部包裹 `<dl>`。

- [ ] **Step 2：写 TownView 选择和关闭集成测试**

使用真实 Pinia Store，mock 仅限网络 fetcher/Store action 边界。点击 Ryan 的“查看详情”后断言 `npcDetailStore.selectedNpcId == "ryan"`；Panel close 后为 null。

- [ ] **Step 3：写 Tick 后刷新测试**

先选 Ryan 并设置详情，再让 `worldStore.data.world.tick` 从 0 变为 1；断言 detail store 的 refresh 被调用一次。相同 Tick 的普通响应式更新不得重复刷新。

- [ ] **Step 4：运行 View/Card 测试并确认红灯**

Run: `npm test -- --run ..\tests\frontend\NpcCard.spec.ts ..\tests\frontend\TownView.spec.ts`

- [ ] **Step 5：修改 NpcCard 为显式选择组件**

新增：

```typescript
const emit = defineEmits<{ select: [npcId: string] }>()
```

按钮调用 `emit('select', npc.id)`；卡片不导入 API/Store。

- [ ] **Step 6：在 TownView 协调两个 Store**

- `selectNpc(id)` 调用 `npcDetailStore.selectNpc(id)`。
- 渲染 `NpcDetailPanel` 并连接 close/retry。
- 使用以下 watch；只有旧、新 Tick 都存在且发生变化，并且当前有选择时才 refresh：

```typescript
watch(
  () => worldStore.data?.world.tick,
  (nextTick, previousTick) => {
    if (
      nextTick !== undefined
      && previousTick !== undefined
      && nextTick !== previousTick
      && npcDetailStore.selectedNpcId !== null
    ) {
      void npcDetailStore.refresh()
    }
  },
)
```
- World Store 不感知 NPC Detail Store。

- [ ] **Step 7：运行全部 Frontend 测试**

Run: `npm test`

Expected: Phase 0、Phase 1A 与 Phase 1B 全部测试通过。

- [ ] **Step 8：运行 type-check 与生产构建**

Run: `npm run type-check`

Run: `npm run build`

- [ ] **Step 9：人工 review 检查点**

重点检查 watch 不产生重复请求、Card 仍可访问、Panel 在移动端自然堆叠；不得 stage 或 commit。

---

### Task 8：同步公共文档并完成端到端验证

**Files:**
- Modify: `README.md`
- Modify: `docs/05_Engineering_Architecture.md`
- Modify: `docs/06_API_Contract.md`
- Modify: `docs/09_Decision_Log.md`
- Modify: `docs/11_Project_Structure.md`
- Modify: `docs/13_Development_Roadmap.md`

**Interfaces:**
- Consumes: 已通过测试的最终 API/UI 行为。
- Produces: 与实现一致的 Phase 1B 文档和人工 review 包。

- [ ] **Step 1：更新 API 契约**

把 `GET /api/npcs/{npc_id}` 从未来示例改为 Phase 1B 权威契约，完整列出 `profile/state/world_context/recent_actions`，删除未实现的 `relationships` 返回承诺，并记录 404/503。

- [ ] **Step 2：更新架构与 ADR**

记录：

- 独立 NPC read slice，不污染 Tick Repository。
- `reason` 机器代码在 Detail DTO 中转换为 `reason_code + reason_text`。
- 规则解释不是 chain-of-thought 或 Agent Trace。
- Frontend Store 独立，TownView 负责跨 Store 协调。

- [ ] **Step 3：更新 README、结构和 Roadmap**

说明可点击 NPC、最近三条持久化行动、Tick 后刷新；明确 Chat/LLM/Memory/Relationship 仍未实现。不要把 Phase 1C/Phase 2 内容写成已完成。

- [ ] **Step 4：运行最终 Backend 验证**

Run: `.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp "C:\Users\yangzhaoting\.codex\.chatgpt-projects\g-p-6a87f34c7b548191a925938d17aacd47\.pytest-tmp\phase1b-final-backend"`

记录精确 passed 数量和退出码 0。

- [ ] **Step 5：运行最终 Frontend 验证**

Run: `npm test`

Run: `npm run type-check`

Run: `npm run build`

记录测试文件/用例数量、type-check 退出码和 Vite build 结果。

- [ ] **Step 6：执行只读 HTTP 冒烟闭环**

使用 disposable SQLite：seed → `GET /api/npcs/ryan`（空历史）→ Tick → `GET /api/npcs/ryan`（一条历史）。断言第二次详情的 Tick/状态与 `GET /api/world` 一致，最近行动为 Tick 1。

- [ ] **Step 7：执行 diff 与范围审查**

Run: `git diff --check`

Run: `git status --short`

Run: `git diff --stat`

确认没有 Chat、LLM、Memory、Relationship、PixiJS、Quest、认证或新数据库表；确认暂存区为空，不提交 Git。

- [ ] **Step 8：输出人工 review 包**

最终交付必须包含：修改文件列表、核心实现、API/UX 效果、测试命令与精确结果、已知限制、Phase 1C 建议以及完整 diff 摘要。
