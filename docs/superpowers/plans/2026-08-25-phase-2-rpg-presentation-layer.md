# Phase 2 RPG Presentation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留现有 Backend 权威、World Tick 和失踪孩子任务闭环的前提下，增加角色创建、剧情过场和一张可移动、可点击 NPC 的 Phaser 2D RPG 地图。

**Architecture:** Vue 负责 `boot → create → story → town` 页面流程、本地角色档案和现有 DOM 业务面板；Phaser 3.90.0 只负责 Scene 3 的地图、碰撞、镜头、键盘移动与 Sprite 点击。Backend 继续提供 NPC、World State、任务和语义地点，聊天请求只临时接收经过校验的玩家显示名与职业，不修改 Player Schema，也不保存 Phaser 坐标。

**Tech Stack:** Vue 3.5、TypeScript 5.7、Pinia 3、Vite 6、Vitest 3、Phaser 3.90.0、FastAPI、Pydantic、SQLAlchemy、pytest、Tiled JSON、localStorage

**Spec:** `docs/superpowers/specs/2026-08-25-phase-2-rpg-presentation-layer-design.md`

## Global Constraints

- 固定使用 `phaser@3.90.0`，不使用 Phaser 4、PixiJS 或 `phaser-jsx`。
- Backend 继续作为 NPC、World State、任务和语义地点的唯一权威来源。
- 不修改 ORM `PlayerState`、数据库表或迁移脚本。
- 玩家显示名、职业和 `introCompleted` 只保存在 `localStorage` key `aleria.player-profile.v1`。
- 玩家 Phaser `(x, y)` 只存在于当前浏览器 Scene，不持久化、不调用 Backend。
- 保留现有 `/api/player/travel` 和地点 DOM 控件；WASD/方向键不得触发该 API。
- 单张室外地图必须包含酒馆、公园、城堡、森林入口和 3 个 Backend NPC。
- 不增加战斗、敌人、背包、物品、技能、装备、多地图或室内地图。
- 第三方美术采用 CC0 优先，并在 `THIRD_PARTY_ASSETS.md` 逐项记录来源、作者、许可、修改和仓库路径。
- 自动测试不得访问真实 LLM、真实 API Key 或外部素材网站。
- 执行者不得执行 Git 提交；每个 Module 结束后停止，展示 Diff 和测试证据，由用户 review 后自行提交。

---

## File Structure Map

### Frontend 本地角色与页面流程

- Create: `frontend/src/player/playerProfile.ts` — 本地档案类型、职业元数据、名称校验、版本化存取。
- Create: `frontend/src/stores/playerProfile.ts` — 当前会话档案、持久化警告和创建/完成剧情动作。
- Create: `frontend/src/gameFlow.ts` — 无 UI 依赖的应用流程状态转换。
- Create: `frontend/src/views/BootView.vue` — Scene 0 启动页。
- Create: `frontend/src/views/CharacterCreationView.vue` — Scene 1 取名与三职业选择。
- Create: `frontend/src/views/StoryView.vue` — Scene 2 分段剧情与跳过。
- Modify: `frontend/src/App.vue` — 组合四个应用场景。
- Modify: `frontend/src/style.css` — 场景共用视觉变量和响应式样式。
- Create: `tests/frontend/playerProfile.spec.ts` — 档案校验、存储异常与版本回退。
- Create: `tests/frontend/gameFlow.spec.ts` — 流程纯函数测试。
- Create: `tests/frontend/AppFlow.spec.ts` — 四场景组件集成测试。

### Chat 玩家自述上下文

- Modify: `backend/app/schemas/chat.py` — 可选 `PlayerProfileInput` 严格请求模型。
- Modify: `backend/app/llm/types.py` — `PlayerProfileChatContext` 与 Provider request 字段。
- Modify: `backend/app/services/chat_service.py` — schema 到只读 prompt context 的枚举映射。
- Modify: `backend/app/services/chat_context.py` — 将玩家自述随当次请求组装进 Provider request。
- Modify: `backend/app/llm/openai_compatible.py` — 渲染明确标记为不可信、非权威的玩家自述块。
- Modify: `backend/app/llm/mock.py` — Mock 问候和身份回答体现名称/职业，但不推断过去。
- Modify: `frontend/src/types/chat.ts` — 可选聊天请求档案类型。
- Modify: `frontend/src/stores/npcChat.ts` — 发送和重试时附带当前档案。
- Modify: `frontend/src/views/TownView.vue` — 把当前本地档案交给 Chat store。
- Modify: `tests/backend/test_chat_schemas.py`
- Modify: `tests/backend/test_chat_context.py`
- Modify: `tests/backend/test_chat_service.py`
- Modify: `tests/backend/test_mock_chat_provider.py`
- Modify: `tests/backend/test_openai_compatible_provider.py`
- Modify: `tests/backend/test_npc_chat_api.py`
- Modify: `tests/frontend/chatApi.spec.ts`
- Modify: `tests/frontend/npcChat.spec.ts`
- Modify: `tests/frontend/TownView.spec.ts`

### Phaser 地图内核

- Modify: `frontend/package.json`、`frontend/package-lock.json` — 精确锁定 Phaser 3.90.0。
- Create: `frontend/src/game/contracts.ts` — Vue/Phaser 共享输入、事件和 Controller 接口。
- Create: `frontend/src/game/movement.ts` — 无 Phaser 依赖的归一化移动计算。
- Create: `frontend/src/game/npcProjection.ts` — Backend `location_id` 到地图锚点及稳定偏移。
- Create: `frontend/src/game/TownGameBridge.ts` — 输入快照和轻量订阅桥。
- Create: `frontend/src/game/scenes/BootScene.ts` — 资源加载和失败事件。
- Create: `frontend/src/game/scenes/TownScene.ts` — Tilemap、玩家、NPC、碰撞、镜头和点击。
- Create: `frontend/src/game/createTownGame.ts` — Phaser Game 的唯一创建与销毁入口。
- Create: `frontend/src/components/TownGameHost.vue` — Vue 生命周期与 Phaser Controller 适配。
- Create: `frontend/public/assets/phase2/maps/town.json` — 48×36、32px 的单张室外 Tiled 地图。
- Create: `frontend/public/assets/phase2/tiles/tiny-town-32.png` — Tiny Town 2× nearest-neighbor 归一化 tileset。
- Create: `frontend/public/assets/phase2/sprites/adventurer-mage.png`
- Create: `frontend/public/assets/phase2/sprites/adventurer-ranger.png`
- Create: `frontend/public/assets/phase2/sprites/adventurer-cleric.png`
- Create: `frontend/public/assets/phase2/sprites/npcs.png`
- Create: `frontend/public/assets/phase2/audio/page-turn.ogg`
- Create: `THIRD_PARTY_ASSETS.md`
- Create: `tests/frontend/movement.spec.ts`
- Create: `tests/frontend/npcProjection.spec.ts`
- Create: `tests/frontend/TownGameBridge.spec.ts`
- Create: `tests/frontend/townMap.spec.ts`
- Create: `tests/frontend/TownGameHost.spec.ts`

### 最终组合与文档

- Modify: `frontend/src/views/TownView.vue` — 地图优先布局、HUD、NPC 选择桥接。
- Modify: `frontend/src/style.css` — 桌面地图布局和窄屏抽屉式面板。
- Create: `tests/frontend/phase2Acceptance.spec.ts` — 首次进入到 NPC 选择的跨组件验收。
- Modify: `README.md`
- Modify: `docs/06_API_Contract.md`
- Modify: `docs/08_Prompt_Engineering_CN.md`
- Modify: `docs/09_Decision_Log.md`
- Modify: `docs/11_Project_Structure.md`
- Modify: `docs/12_Game_Experience_Design.md`
- Modify: `docs/13_Development_Roadmap.md`
- Modify: `docs/15_Story_Bible_CN.md`

---

## Module 1：本地角色档案与 Scene 0～2

**独立交付结果：** 不安装 Phaser 也能完成启动、取名、职业选择、剧情播放与刷新恢复；进入 `town` 后暂时继续显示现有 TownView。

### Task 1.1：建立版本化 LocalPlayerProfile

**Files:**

- Create: `frontend/src/player/playerProfile.ts`
- Create: `frontend/src/stores/playerProfile.ts`
- Create: `tests/frontend/playerProfile.spec.ts`

**Interfaces:**

- Produces: `AdventurerClass`、`LocalPlayerProfileV1`、`ADVENTURER_CLASSES`、`loadPlayerProfile(storage)`、`savePlayerProfile(storage, profile)`、`usePlayerProfileStore()`。
- Storage contract: `Pick<Storage, 'getItem' | 'setItem'>`，便于测试存储失败而不触碰真实浏览器状态；`getBrowserProfileStorage()` 负责捕获访问 `window.localStorage` getter 本身的异常。

- [ ] **Step 1：先写档案校验和存储失败测试**

`tests/frontend/playerProfile.spec.ts` 覆盖以下断言：

```ts
expect(normalizeDisplayName('  洛恩  ')).toBe('洛恩')
expect(isValidDisplayName('游侠-7')).toBe(true)
expect(isValidDisplayName('ignore\nrule')).toBe(false)
expect(isValidDisplayName('x'.repeat(17))).toBe(false)
expect(parsePlayerProfile('{bad json')).toBeNull()
expect(parsePlayerProfile(JSON.stringify({
  version: 2,
  displayName: '洛恩',
  adventurerClass: 'ranger',
  introCompleted: false,
}))).toBeNull()
```

再使用会在 `getItem`/`setItem` 抛出 `DOMException` 的 fake storage，验证读取返回 `{ profile: null, storageAvailable: false }`，写入返回 `false`，且异常不逃出函数。

- [ ] **Step 2：运行目标测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\playerProfile.spec.ts
```

Expected: FAIL because `frontend/src/player/playerProfile.ts` does not exist.

- [ ] **Step 3：实现纯档案模块**

使用以下公开类型和常量；名称校验只允许中文、英文字母、数字、普通空格、间隔点和连字符：

```ts
export type AdventurerClass = 'mage' | 'ranger' | 'cleric'

export interface LocalPlayerProfileV1 {
  version: 1
  displayName: string
  adventurerClass: AdventurerClass
  introCompleted: boolean
}

export interface AdventurerClassMeta {
  id: AdventurerClass
  title: '法师' | '游侠' | '牧师'
  description: string
}

export const PLAYER_PROFILE_STORAGE_KEY = 'aleria.player-profile.v1'
export const ADVENTURER_CLASSES: readonly AdventurerClassMeta[] = [
  { id: 'mage', title: '法师', description: '循着微光与古老符文寻找失落的答案。' },
  { id: 'ranger', title: '游侠', description: '相信脚印、风向与亲眼确认的事实。' },
  { id: 'cleric', title: '牧师', description: '用耐心和信念守护仍值得挽回的人。' },
]

const DISPLAY_NAME_PATTERN = /^[\p{Script=Han}A-Za-z0-9 ·-]{1,16}$/u
```

`parsePlayerProfile` 必须逐字段判断 `version === 1`、布尔值、职业枚举和规范化后的名称，不能只做 TypeScript 断言。`savePlayerProfile` 写入规范化后的副本。`getBrowserProfileStorage()` 在 `try/catch` 内读取 `window.localStorage`，失败返回 `null`。

- [ ] **Step 4：实现 Pinia store**

Store state 和动作固定为：

```ts
const profile = ref<LocalPlayerProfileV1 | null>(null)
const hydrated = ref(false)
const storageWarning = ref<string | null>(null)

function hydrate(storage: ProfileStorage | null = getBrowserProfileStorage()): void
function createProfile(
  displayName: string,
  adventurerClass: AdventurerClass,
  storage: ProfileStorage | null = getBrowserProfileStorage(),
): void
function completeIntro(
  storage: ProfileStorage | null = getBrowserProfileStorage(),
): void
```

`createProfile` 先校验再写 `profile`；持久化失败时仍保留当前会话 profile，并设置 `storageWarning = '当前浏览器无法保存角色，本次选择仅在此会话有效。'`。`completeIntro` 只把当前 profile 的 `introCompleted` 改为 `true`，无 profile 时直接返回。

- [ ] **Step 5：运行目标测试并确认 GREEN**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\playerProfile.spec.ts
npm run type-check
```

Expected: PASS.

### Task 1.2：建立可测试的四场景流程

**Files:**

- Create: `frontend/src/gameFlow.ts`
- Create: `tests/frontend/gameFlow.spec.ts`

**Interfaces:**

- Consumes: `LocalPlayerProfileV1 | null`。
- Produces: `GameStage`、`destinationAfterBoot(profile)`、`destinationAfterProfileCreated()`、`destinationAfterStory()`。

- [ ] **Step 1：写流程分支失败测试**

```ts
expect(destinationAfterBoot(null)).toBe('create')
expect(destinationAfterBoot({ ...profile, introCompleted: false })).toBe('story')
expect(destinationAfterBoot({ ...profile, introCompleted: true })).toBe('town')
expect(destinationAfterProfileCreated()).toBe('story')
expect(destinationAfterStory()).toBe('town')
```

- [ ] **Step 2：运行测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\gameFlow.spec.ts
```

Expected: FAIL because the flow module is missing.

- [ ] **Step 3：实现最小有限状态模块**

```ts
export type GameStage = 'boot' | 'create' | 'story' | 'town'

export function destinationAfterBoot(
  profile: LocalPlayerProfileV1 | null,
): Exclude<GameStage, 'boot'> {
  if (profile === null) return 'create'
  return profile.introCompleted ? 'town' : 'story'
}

export const destinationAfterProfileCreated = (): GameStage => 'story'
export const destinationAfterStory = (): GameStage => 'town'
```

- [ ] **Step 4：运行测试并确认 GREEN**

Run the same Vitest target. Expected: PASS.

### Task 1.3：实现 Boot、角色创建和剧情 Vue 场景

**Files:**

- Create: `frontend/src/views/BootView.vue`
- Create: `frontend/src/views/CharacterCreationView.vue`
- Create: `frontend/src/views/StoryView.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/style.css`
- Create: `tests/frontend/AppFlow.spec.ts`

**Interfaces:**

- `BootView`: prop `hasProfile: boolean`；emit `continue`。
- `CharacterCreationView`: emit `created(displayName: string, adventurerClass: AdventurerClass)`。
- `StoryView`: props `displayName: string`、`classTitle: string`；emit `complete`。
- `App.vue`: 是唯一拥有 `GameStage` 的组件，并通过 PlayerProfile store 持久化流程。

- [ ] **Step 1：先写跨场景组件测试**

`AppFlow.spec.ts` 使用新 Pinia 和清空后的 localStorage，验证：

```ts
expect(wrapper.get('[data-scene="boot"]').exists()).toBe(true)
await wrapper.get('[data-action="continue"]').trigger('click')
expect(wrapper.get('[data-scene="create"]').exists()).toBe(true)
await wrapper.get('input[name="displayName"]').setValue('洛恩')
await wrapper.get('[data-class="ranger"]').trigger('click')
await wrapper.get('form').trigger('submit')
expect(wrapper.get('[data-scene="story"]').text()).toContain('洛恩')
await wrapper.get('[data-action="skip-story"]').trigger('click')
expect(wrapper.findComponent(TownView).exists()).toBe(true)
expect(JSON.parse(localStorage.getItem(PLAYER_PROFILE_STORAGE_KEY)!)).toMatchObject({
  displayName: '洛恩',
  adventurerClass: 'ranger',
  introCompleted: true,
})
```

另写已有 `introCompleted: true` 档案的测试：仍先显示启动页，点击“继续冒险”后直接进入 TownView。

- [ ] **Step 2：运行测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\AppFlow.spec.ts
```

Expected: FAIL because scene components are missing.

- [ ] **Step 3：实现三个场景的固定内容**

`StoryView` 使用以下四段内容，每次只显示一段；按钮支持“继续”、最后一段“进入曦谷”和始终可用的“跳过”：

```ts
const passages = [
  '潮湿的草叶贴在掌心。你在曦谷城外醒来，只记得一道陌生的印记。',
  '名字仍属于你，过去却像被雾吞没。你只能先选择此刻要走的道路。',
  '酒馆的告示、公园的旧痕、城堡的残卷与森林的低语，都指向同一个未解的问题。',
  '先去认识这座小镇的居民。也许他们知道你从哪里来，也许他们同样在寻找答案。',
]
```

CharacterCreationView 的三张职业卡必须来自 `ADVENTURER_CLASSES`，提交时调用同一名称校验函数；错误文案为 `名称需为 1～16 个中文、字母、数字或常用分隔符。`。

- [ ] **Step 4：组合 App.vue**

应用启动时调用 `profileStore.hydrate()`，stage 初值仍为 `boot`。事件转换固定为：

```ts
function continueFromBoot(): void {
  stage.value = destinationAfterBoot(profileStore.profile)
}

function createPlayer(name: string, adventurerClass: AdventurerClass): void {
  profileStore.createProfile(name, adventurerClass)
  stage.value = destinationAfterProfileCreated()
}

function completeStory(): void {
  profileStore.completeIntro()
  stage.value = destinationAfterStory()
}
```

storageWarning 在 create/story/town 场景顶部以 `role="status"` 显示，不能阻断继续。

- [ ] **Step 5：补充视觉样式**

在 `style.css` 定义 `--ink`、`--moss`、`--gold`、`--parchment`、`--danger` 五个颜色变量；三个过场视图使用同一个 `.cinematic-shell` 和 `.cinematic-card`，职业卡有明确的选中态与 `:focus-visible`。窄于 760px 时三职业卡变为单列。

- [ ] **Step 6：运行 Module 1 回归**

Run:

```powershell
Set-Location frontend
npm test
npm run type-check
npm run build
```

Expected: all PASS；生产构建仍未包含 Phaser。

### Module 1 人工 Review 门

- [ ] 展示首次创建、刷新恢复和已完成剧情三条流程；
- [ ] 展示非法名称与 localStorage 抛错时的行为；
- [ ] 展示 Frontend 全量测试、类型检查和构建结果；
- [ ] 展示工作区 Diff 和未提交文件列表；
- [ ] 停止执行，等待用户 review；
- [ ] 用户自行提交。建议提交说明：`feat: add local adventurer onboarding flow`。

---

## Module 2：玩家名称与职业进入 NPC 对话上下文

**独立交付结果：** 现有 Chat API 可选接收严格校验的本地档案，Mock 和真实 Provider 都能安全使用称谓；数据库 Player、World、NPC 和 Quest 模型不变。

### Task 2.1：扩展 Chat request schema 和领域类型

**Files:**

- Modify: `backend/app/schemas/chat.py`
- Modify: `backend/app/llm/types.py`
- Modify: `tests/backend/test_chat_schemas.py`

**Interfaces:**

- Produces schema: `PlayerProfileInput(display_name, adventurer_class)`。
- Produces domain type: `PlayerProfileChatContext(display_name, adventurer_class, class_title)`。
- `NpcChatRequest.player_profile` 默认为 `None`，现有客户端保持兼容。

- [ ] **Step 1：先写合法、规范化和拒绝测试**

```py
request = NpcChatRequest.model_validate({
    "message": "你好",
    "player_profile": {
        "display_name": "  洛恩  ",
        "adventurer_class": "ranger",
    },
})
assert request.player_profile is not None
assert request.player_profile.display_name == "洛恩"
```

参数化拒绝：空白名、17 字符名、包含换行、职业 `warrior`、`player_profile` 内额外字段 `instructions`。再断言 `NpcChatRequest(message="你好").player_profile is None`。

- [ ] **Step 2：运行目标测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_chat_schemas.py -q -p no:cacheprovider
```

Expected: FAIL because `player_profile` is not defined.

- [ ] **Step 3：实现严格嵌套模型**

```py
from pydantic import BaseModel, ConfigDict, Field, field_validator

AdventurerClass = Literal["mage", "ranger", "cleric"]
PLAYER_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9\u3400-\u4DBF\u4E00-\u9FFF ·-]+$"
)

class PlayerProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=16)
    adventurer_class: AdventurerClass

    @field_validator("display_name", mode="before")
    @classmethod
    def validate_display_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not PLAYER_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid display name")
        return normalized
```

在 `NpcChatRequest` 增加 `player_profile: PlayerProfileInput | None = None`。在 `llm/types.py` 新增 frozen dataclass `PlayerProfileChatContext`，并在 `ChatProviderRequest` 增加 `player_profile: PlayerProfileChatContext | None`。

- [ ] **Step 4：运行 schema 测试并确认 GREEN**

Run the same pytest target. Expected: PASS.

### Task 2.2：把自述上下文传到 Provider 且不持久化

**Files:**

- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/services/chat_context.py`
- Modify: `tests/backend/test_chat_context.py`
- Modify: `tests/backend/test_chat_service.py`
- Modify: `tests/backend/test_npc_chat_api.py`

**Interfaces:**

- `ChatContextAssembler.assemble(..., player_profile: PlayerProfileChatContext | None)`。
- `PLAYER_CLASS_TITLES = {'mage': '法师', 'ranger': '游侠', 'cleric': '牧师'}` 只存在于服务层枚举映射。

- [ ] **Step 1：写 Provider 捕获和数据库隔离失败测试**

在 `test_chat_service.py` 调用：

```py
request=NpcChatRequest.model_validate({
    "message": "你认识我吗？",
    "player_profile": {
        "display_name": "洛恩",
        "adventurer_class": "ranger",
    },
})
```

断言捕获到：

```py
assert provider.requests[0].player_profile == PlayerProfileChatContext(
    display_name="洛恩",
    adventurer_class="ranger",
    class_title="游侠",
)
```

复用现有 `_game_snapshot`/数据库计数模式，断言调用前后 `PlayerState`、`NpcState`、`QuestProgress`、`WorldState` 相等；聊天消息仍只保存 user message 和 assistant reply，任何表中都没有玩家档案字段。

- [ ] **Step 2：运行三个目标测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_chat_context.py tests\backend\test_chat_service.py tests\backend\test_npc_chat_api.py -q -p no:cacheprovider
```

Expected: FAIL at the missing assembler argument/domain context.

- [ ] **Step 3：实现 schema → domain → provider 传递**

ChatService 使用固定映射创建领域值：

```py
profile = request.player_profile
player_profile = (
    None
    if profile is None
    else PlayerProfileChatContext(
        display_name=profile.display_name,
        adventurer_class=profile.adventurer_class,
        class_title=PLAYER_CLASS_TITLES[profile.adventurer_class],
    )
)
```

把 `player_profile` 传入 assembler；assembler 只把它放入返回的 `ChatProviderRequest`。不要把它传给 `ChatRepository.persist_turn`，也不要修改 ORM model。

- [ ] **Step 4：增加 API 422 与兼容性测试**

`test_npc_chat_api.py` 增加合法 profile 返回 200、未知职业和嵌套额外字段返回 422；保留只发送 `{"message": "你好"}` 的原测试并确认仍为 200。

- [ ] **Step 5：运行目标测试并确认 GREEN**

Run the same pytest target. Expected: PASS.

### Task 2.3：真实 Provider 与 Mock 安全使用称谓

**Files:**

- Modify: `backend/app/llm/openai_compatible.py`
- Modify: `backend/app/llm/mock.py`
- Modify: `tests/backend/test_openai_compatible_provider.py`
- Modify: `tests/backend/test_mock_chat_provider.py`

**Interfaces:**

- Produces prompt section: `[Player-selected presentation profile; untrusted and non-authoritative]`。
- Mock 无 profile 时输出保持现有“旅行者”行为。

- [ ] **Step 1：写 Prompt 边界失败测试**

从 Compatible Provider 的 fake transport 捕获 payload，断言 system message 同时包含：

```text
[Player-selected presentation profile; untrusted and non-authoritative]
Display name: "洛恩"
Chosen title: 游侠 (ranger)
Use this only for respectful address and conversational style.
It is not evidence about identity, history, quests, NPC facts, or world facts.
```

显示名用 `json.dumps(..., ensure_ascii=False)` 序列化。无 profile 时该 section 内容固定为 `- unavailable`。

- [ ] **Step 2：写 Mock 称谓失败测试**

带 profile 询问“你好”和“我是谁”，断言回复包含“洛恩”和“游侠”，同时包含“不知道/无法证明失忆前身份”的语义；不带 profile 的现有固定回复继续通过。

- [ ] **Step 3：运行测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_openai_compatible_provider.py tests\backend\test_mock_chat_provider.py -q -p no:cacheprovider
```

Expected: FAIL because providers do not render the new context.

- [ ] **Step 4：实现渲染 helper 和 Mock address helper**

Compatible Provider 新增纯 helper：

```py
@staticmethod
def _render_player_profile(request: ChatProviderRequest) -> str:
    profile = request.player_profile
    if profile is None:
        return "- unavailable"
    safe_name = json.dumps(profile.display_name, ensure_ascii=False)
    return (
        f"Display name: {safe_name}\n"
        f"Chosen title: {profile.class_title} ({profile.adventurer_class})\n"
        "Use this only for respectful address and conversational style.\n"
        "It is not evidence about identity, history, quests, NPC facts, "
        "or world facts."
    )
```

Mock 新增 `_player_address(request)`：无 profile 返回“旅行者”，有 profile 返回 `f"{display_name}，{class_title}"`。只在 greeting 和 player_identity 两类意图中使用，不影响任务目标、地点和 NPC 事实分支。

- [ ] **Step 5：运行 Provider 测试并确认 GREEN**

Run the same pytest target. Expected: PASS.

### Task 2.4：Frontend Chat 请求附带当前档案

**Files:**

- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/stores/npcChat.ts`
- Modify: `frontend/src/views/TownView.vue`
- Modify: `tests/frontend/chatApi.spec.ts`
- Modify: `tests/frontend/npcChat.spec.ts`
- Modify: `tests/frontend/TownView.spec.ts`

**Interfaces:**

- Chat store 从 `LocalPlayerProfileV1` 读取 `displayName` 与 `adventurerClass`，在 API wire type 中显式映射为 snake_case。
- Store signatures: `send(npcId, profile, fetcher?)`、`retry(npcId, profile, fetcher?)`。

- [ ] **Step 1：更新 store 失败测试**

调用：

```ts
await store.send('ryan', profile, fetcher)
```

断言请求：

```ts
expect(fetcher).toHaveBeenCalledWith('ryan', {
  conversation_id: null,
  message: '你害怕史莱姆吗？',
  player_profile: {
    display_name: '洛恩',
    adventurer_class: 'ranger',
  },
})
```

再断言 `profile === null` 时 request 中不存在 `player_profile` key，而不是发送 `null`。

- [ ] **Step 2：运行 Frontend Chat 测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\npcChat.spec.ts ..\tests\frontend\chatApi.spec.ts ..\tests\frontend\TownView.spec.ts
```

Expected: FAIL at the old method signature/request shape.

- [ ] **Step 3：实现类型和 request 组装**

```ts
export interface NpcChatPlayerProfile {
  display_name: string
  adventurer_class: AdventurerClass
}

export interface NpcChatRequest {
  conversation_id: string | null
  message: string
  player_profile?: NpcChatPlayerProfile
}
```

Store 使用条件 spread；TownView 从 `usePlayerProfileStore()` 读取 `profile` 并在发送和重试时传入。重试必须读取当下档案，而不是缓存首次发送的 profile。

- [ ] **Step 4：运行 Module 2 全量回归**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider
Set-Location frontend
npm test
npm run type-check
npm run build
```

Expected: all PASS；没有数据库 migration 文件变化。

### Module 2 人工 Review 门

- [ ] 展示合法/非法 Chat payload 与无 profile 兼容响应；
- [ ] 展示 Mock 使用名称/职业但不补全失忆前身份；
- [ ] 展示 ORM/数据库 schema 零变化和隔离测试；
- [ ] 展示 Backend/Frontend 全量验证与工作区 Diff；
- [ ] 停止执行，等待用户 review；
- [ ] 用户自行提交。建议提交说明：`feat: add local adventurer context to npc chat`。

---

## Module 3：Phaser 单地图、移动与 NPC 视觉投影

**独立交付结果：** 可单独挂载 TownGameHost，显示一张 48×36 室外地图，三职业可用 WASD/方向键移动并碰撞，三 NPC 根据 Backend location 投影并可点击。

### Task 3.1：安装 Phaser 并建立纯逻辑边界

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/game/contracts.ts`
- Create: `frontend/src/game/movement.ts`
- Create: `frontend/src/game/npcProjection.ts`
- Create: `tests/frontend/movement.spec.ts`
- Create: `tests/frontend/npcProjection.spec.ts`

**Interfaces:**

```ts
export interface NpcVisualProjection {
  id: string
  name: string
  locationId: string
  anchorName: string
  offsetX: number
  offsetY: number
}

export interface TownGameInput {
  profile: LocalPlayerProfileV1
  npcs: NpcVisualProjection[]
}

export interface TownGameController {
  updateNpcs(npcs: NpcVisualProjection[]): void
  destroy(): void
}
```

- [ ] **Step 1：写移动归一化失败测试**

```ts
expect(resolveVelocity({ up: true, down: false, left: false, right: false }, 160))
  .toEqual({ x: 0, y: -160 })
const diagonal = resolveVelocity(
  { up: true, down: false, left: false, right: true },
  160,
)
expect(Math.hypot(diagonal.x, diagonal.y)).toBeCloseTo(160)
expect(resolveVelocity(
  { up: true, down: true, left: true, right: true },
  160,
)).toEqual({ x: 0, y: 0 })
```

- [ ] **Step 2：写 NPC 投影失败测试**

固定映射：

```ts
export const LOCATION_ANCHORS = {
  tavern: 'location:tavern',
  park: 'location:park',
  castle: 'location:castle',
  forest: 'location:forest',
} as const
```

断言未知地点映射到 `location:fallback`；同一 NPC id 每次得到相同偏移；三个 NPC 的偏移属于 `[-24, 0, 24]` 的有限格点且不会全部重叠。

- [ ] **Step 3：运行测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\movement.spec.ts ..\tests\frontend\npcProjection.spec.ts
```

Expected: FAIL because game modules are missing.

- [ ] **Step 4：精确安装 Phaser**

Run:

```powershell
Set-Location frontend
npm install --save-exact phaser@3.90.0
```

Expected: `package.json` dependency is exactly `"phaser": "3.90.0"` and lockfile resolves the same version.

- [ ] **Step 5：实现纯函数**

`resolveVelocity` 先分别计算 `right-left` 与 `down-up`，零向量直接返回；非零向量乘以 `speed / Math.hypot(x, y)`。`projectNpcs` 只读取 `id/name/location_id`，使用稳定字符串 hash 选择有限偏移，不调用随机数、不读取 Phaser Scene。

- [ ] **Step 6：运行测试和类型检查并确认 GREEN**

Run movement/projection tests and `npm run type-check`. Expected: PASS.

### Task 3.2：导入 CC0 素材并建立地图契约

**Files:**

- Create: `frontend/public/assets/phase2/maps/town.json`
- Create: `frontend/public/assets/phase2/tiles/tiny-town-32.png`
- Create: `frontend/public/assets/phase2/sprites/adventurer-mage.png`
- Create: `frontend/public/assets/phase2/sprites/adventurer-ranger.png`
- Create: `frontend/public/assets/phase2/sprites/adventurer-cleric.png`
- Create: `frontend/public/assets/phase2/sprites/npcs.png`
- Create: `frontend/public/assets/phase2/audio/page-turn.ogg`
- Create: `THIRD_PARTY_ASSETS.md`
- Create: `tests/frontend/townMap.spec.ts`
- Modify: `frontend/src/views/StoryView.vue`
- Modify: `tests/frontend/AppFlow.spec.ts`

**Interfaces:**

- Map: Tiled JSON `orthogonal`、48×36 tiles、tilewidth/tileheight 32。
- Required layers: `ground`、`decor-below`、`collision`、`decor-above`、`objects`。
- Required objects: `player_spawn`、`location:tavern`、`location:park`、`location:castle`、`location:forest`、`location:fallback`。
- Normalized adventurer sheets: 32×32 frames，frame 0–2 down、3–5 side、6–8 up；向右通过 side frames + `flipX`。
- NPC sheet: Ryan/Shir/Grey 三个 32×32 idle frames，顺序固定为 0/1/2。
- Story cue: `/assets/phase2/audio/page-turn.ogg`，只在用户主动推进段落后以 0.2 音量播放，播放失败不阻断文本推进。

- [ ] **Step 1：先写地图 JSON 契约测试**

`townMap.spec.ts` 使用 `fileURLToPath(new URL('../../frontend/public/assets/phase2/maps/town.json', import.meta.url))` 和 `readFileSync` 读取地图，断言尺寸、五个 layer 名、六个 object 名、tileset name 为 `tiny-town-32`、image 为 `../tiles/tiny-town-32.png`，并断言地点坐标在地图边界内且互不相同。

- [ ] **Step 2：运行测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\townMap.spec.ts
```

Expected: FAIL because the map file is missing.

- [ ] **Step 3：导入并归一化固定素材来源**

地图基础只使用 Kenney Tiny Town 1.1（CC0，16×16，https://kenney.nl/assets/tiny-town），以 nearest-neighbor 放大 2× 后导出 `tiny-town-32.png`；不做平滑插值。

职业和 NPC 只使用 Eldiran 的 `RPGCharacterSprites32x32.png`（CC0，https://opengameart.org/content/32x32-rpg-character-sprites）。从原 sheet 选择法师、弓手游侠、牧师、骑士、刺客、守卫外观，归一化为上述 frame 契约。若某个选中角色缺少 side walk，side standing frame 重复三次；不从许可不明的参考仓库补帧。

剧情翻页提示音使用 Kenney Interface Sounds 1.0（CC0，https://kenney.nl/assets/interface-sounds）中的单个短 click 音效，复制并规范命名为 `page-turn.ogg`。不引入背景音乐，避免自动播放和额外音频控制范围。

- [ ] **Step 4：建立单张地图**

地图使用以下固定布局锚点（像素坐标）：

```text
player_spawn      768, 704
location:tavern   416, 704
location:park     768, 544
location:castle  1152, 288
location:forest  1280, 864
location:fallback 768, 608
```

西南为酒馆、中心为公园、东北为城堡、东南为森林入口；道路连通四处。`collision` 只在建筑实体、水体、地图边界、密集树木和岩石处放 tile，路径和地点锚点保持可达。`decor-above` 放树冠和屋檐，避免遮挡出生点与 NPC 锚点。

- [ ] **Step 5：写素材许可清单**

`THIRD_PARTY_ASSETS.md` 为三个来源各记录：作品名、URL、作者、CC0、下载版本/日期、2× 放大、裁切归一化或重命名说明、所有目标文件路径。明确 `D:\pythonproject\素材` 两个参考项目只用于架构参考，未复制其图片。

- [ ] **Step 6：接入非阻断剧情提示音**

StoryView 在用户点击继续时执行：

```ts
const cue = new Audio('/assets/phase2/audio/page-turn.ogg')
cue.volume = 0.2
void cue.play().catch(() => undefined)
```

跳过和首次组件挂载不播放。`AppFlow.spec.ts` 注入 fake Audio，断言继续段落调用一次 `play`，reject 时仍能显示下一段。

- [ ] **Step 7：运行地图契约并人工验图**

Run map test. Expected: PASS。用 Tiled 或图片预览确认四个地点一眼可辨、所有碰撞路径可达、Sprite 无平滑模糊。

### Task 3.3：实现 Bridge、BootScene 和 TownScene

**Files:**

- Create: `frontend/src/game/TownGameBridge.ts`
- Create: `frontend/src/game/scenes/BootScene.ts`
- Create: `frontend/src/game/scenes/TownScene.ts`
- Create: `frontend/src/game/createTownGame.ts`
- Create: `tests/frontend/TownGameBridge.spec.ts`

**Interfaces:**

```ts
type BridgeListener<T> = (payload: T) => void

class TownGameBridge {
  getInput(): TownGameInput
  updateNpcs(npcs: NpcVisualProjection[]): void
  onNpcsUpdated(listener: BridgeListener<NpcVisualProjection[]>): () => void
  emitNpcSelected(npcId: string): void
  onNpcSelected(listener: BridgeListener<string>): () => void
  emitLoadFailed(message: string): void
  onLoadFailed(listener: BridgeListener<string>): () => void
  clear(): void
}
```

- [ ] **Step 1：写 Bridge 订阅/退订/清理失败测试**

测试 updateNpcs 只发最新不可变数组、unsubscribe 后不再调用、`clear()` 后 NPC selection 和 load failure listener 都不再收到事件。

- [ ] **Step 2：运行测试并确认 RED**

Run `TownGameBridge.spec.ts`. Expected: FAIL because the class is missing.

- [ ] **Step 3：实现无 Phaser 依赖的 Bridge**

内部用三个 `Set<BridgeListener<...>>`；构造时复制 input 和 NPC 数组；每次发事件遍历 `[...listeners]`，防止 listener 在回调中修改 Set 导致漏调用。

- [ ] **Step 4：实现 BootScene**

加载 key 固定为：

```text
town-map
town-tiles
adventurer-mage
adventurer-ranger
adventurer-cleric
npc-sprites
```

BootScene 在 `loaderror` 时记录首个失败资源 key；`complete` 后若有错误则 `bridge.emitLoadFailed('地图资源加载失败，请重试。')`，否则启动 `TownScene`。资源 URL 全部以 `/assets/phase2/` 开头。

- [ ] **Step 5：实现 TownScene 地图、玩家和输入**

TownScene 必须：

1. 用 `map.addTilesetImage('tiny-town-32', 'town-tiles')` 绑定 tileset，创建五个 Tiled layers，`collision.setCollisionByExclusion([-1])` 并隐藏 collision layer；
2. 从 `player_spawn` 创建与职业对应的 Arcade Sprite；
3. 为每个职业建立 `down/side/up` walk 动画；
4. 同时读取 CursorKeys 和 `W/A/S/D`，交给 `resolveVelocity(..., 160)`；
5. 速度为零播放对应方向 idle frame；side 向右设置 `flipX=true`，向左 false；
6. 为玩家添加 collision layer collider；
7. 相机 `startFollow(player, true, 0.12, 0.12)`，边界为完整地图；
8. Scene pause、blur 和 shutdown 时把 velocity 设为零并退订 Bridge。

方向键 `preventDefault` 只对 Canvas 已获得交互焦点时生效；输入框、textarea、button 焦点下不得劫持键盘。

- [ ] **Step 6：实现 NPC 投影、tween 与点击**

读取 objects layer 六个锚点。每个 Backend NPC 按固定 frame 创建 interactive Sprite，目标位置为锚点 + stable offset。Bridge 更新时：

- 已存在 NPC：300ms tween 到新位置；同位置不创建 tween；
- 新 NPC：创建 Sprite；
- 已消失 NPC：destroy Sprite；
- 未知 location：使用 fallback，并在 `import.meta.env.DEV` 下 `console.warn`；
- `pointerdown` 调用 `bridge.emitNpcSelected(npcId)`；
- NPC Sprite 设置高于 ground/decor-below、低于 decor-above 的 depth。

- [ ] **Step 7：实现唯一 create/destroy 入口**

`createTownGame(parent, input, callbacks)` 创建一个 Bridge、BootScene、TownScene 和 Phaser.Game；返回 Controller。`destroy()` 必须幂等：退订 callbacks、`bridge.clear()`、`game.destroy(true)`，第二次调用无效果。

- [ ] **Step 8：运行纯逻辑测试、类型检查和构建**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\movement.spec.ts ..\tests\frontend\npcProjection.spec.ts ..\tests\frontend\TownGameBridge.spec.ts ..\tests\frontend\townMap.spec.ts
npm run type-check
npm run build
```

Expected: PASS；Vite production bundle 包含 Phaser chunk 和地图静态资源。

### Task 3.4：Vue 生命周期封装 TownGameHost

**Files:**

- Create: `frontend/src/components/TownGameHost.vue`
- Create: `tests/frontend/TownGameHost.spec.ts`

**Interfaces:**

- Props: `profile: LocalPlayerProfileV1`、`npcs: NpcVisualProjection[]`、可选 `factory: TownGameFactory`（测试注入）。
- Emits: `npcSelected(npcId: string)`。
- UI state: loading、load error + retry、mounted game。

- [ ] **Step 1：写 Host 生命周期失败测试**

注入 fake factory/controller，验证：mount 调用一次 factory；npcs prop 改变只调用 `controller.updateNpcs`，不重建 game；`npcSelected` callback 转为 Vue emit；unmount 调用一次 destroy；load failure 显示 `role="alert"` 和“重试加载地图”按钮；重试先 destroy 再创建新实例。

- [ ] **Step 2：运行测试并确认 RED**

Run `TownGameHost.spec.ts`. Expected: FAIL because component is missing.

- [ ] **Step 3：实现 Host**

模板只包含 `.town-game-frame`、Phaser parent div、加载状态和错误重试。组件 watch 使用 `{ deep: true }` 更新 NPC 投影；profile 在当前 town session 不变化，因此不重建。默认 factory 通过动态 import `../game/createTownGame` 获得，避免单元测试在模块加载阶段创建 WebGL 环境。

- [ ] **Step 4：运行 Module 3 自动与人工验证**

Run Frontend 全量测试、type-check、build。再启动本地页面的独立 Host 调试入口或临时在 TownView 挂载（调试改动验收后删除），人工确认 WASD/方向键、斜向速度、碰撞、镜头、三职业动画、NPC tween 和点击事件。

### Module 3 人工 Review 门

- [ ] 展示 `package.json` 精确 Phaser 版本和 production build；
- [ ] 展示地图五层、六锚点和四地点截图；
- [ ] 演示三职业移动、碰撞、镜头和三 NPC 点击；
- [ ] 展示 `THIRD_PARTY_ASSETS.md` 与未复制参考仓库素材的声明；
- [ ] 展示自动测试、类型检查、构建和工作区 Diff；
- [ ] 停止执行，等待用户 review；
- [ ] 用户自行提交。建议提交说明：`feat: add phaser town map and local movement`。

---

## Module 4：TownView 集成、回归验收和文档收口

**独立交付结果：** 四个场景形成完整演示；地图 NPC 点击复用现有详情与聊天；World Tick 后 NPC 视觉投影更新；原任务、语义 travel 和 Backend 权威全部保留。

### Task 4.1：把 TownGameHost 接入 TownView

**Files:**

- Modify: `frontend/src/views/TownView.vue`
- Modify: `frontend/src/style.css`
- Modify: `tests/frontend/TownView.spec.ts`

**Interfaces:**

- Consumes: `worldStore.data.npcs`、`projectNpcs`、PlayerProfile store、现有 `selectNpc`。
- Produces: `TownGameHost @npc-selected="selectNpc"`；不直接从 Phaser 调 API。

- [ ] **Step 1：先写 TownView 地图集成失败测试**

用 stub `TownGameHost` 并让其暴露 `npcs` props，断言 worldFixture 的三个 NPC 都被投影；触发 `npcSelected('ryan')` 后现有 `npcDetailStore.selectNpc` 被调用并显示 Detail/Chat。修改 world store 中 Ryan 的 `location_id` 后，Host 收到的 Ryan `anchorName` 变为对应新地点。

保留并强化现有 travel 测试：点击 LocationCard 才调用 `/api/player/travel`；TownGameHost 初始化和 NPC projection 更新不得产生 travel POST。

- [ ] **Step 2：运行 TownView 测试并确认 RED**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\TownView.spec.ts
```

Expected: FAIL because TownGameHost is not mounted.

- [ ] **Step 3：实现地图优先布局**

在 world data 可用时，将 `TownGameHost` 放在 TickPanel 之前。布局顺序固定为：

1. 标题与 Backend 世界时间；
2. 地图 + 右侧/窄屏底部 HUD；
3. World Tick；
4. 玩家语义地点与 Quest；
5. 四个语义 travel LocationCard；
6. NPC 卡片作为 Canvas 不可用时的可访问替代入口；
7. 已选择 NPC 的 Detail 和 Chat。

地图加载失败不能隐藏 DOM NPC 卡片和任务控件。NPC 详情打开时桌面为右侧面板，窄于 900px 改为页面下方单列。

- [ ] **Step 4：运行 TownView 测试并确认 GREEN**

Run the same Vitest target. Expected: PASS.

### Task 4.2：建立 Phase 2 跨组件验收

**Files:**

- Create: `tests/frontend/phase2Acceptance.spec.ts`

**Interfaces:**

- Consumes: App、PlayerProfile store、TownView、TownGameHost factory 注入或组件 stub、真实 Pinia stores 与 fake API。
- Produces: 无真实 WebGL/网络的演示路径回归。

- [ ] **Step 1：写首次体验验收测试**

完整路径：boot → 创建“洛恩/游侠” → 跳过剧情 → world/player API 完成 → TownView 出现 → 地图 Host 收到三 NPC → Host 选择 Grey → Detail 与 Chat 出现 → 发送消息。断言 Chat POST 含 player_profile，world tick 和 quest version 在聊天前后不变。

- [ ] **Step 2：写已有档案验收测试**

预置 `introCompleted: true` 的“弥娅/牧师”，boot 后直接 town；TownGameHost 初始化不经 Axios，LocationCard travel 仍调用现有 `/api/player/travel`。World Tick 更新 NPC location 后只改变 Host projection，Phaser 坐标不进入 API payload；真实按键网络行为在 Task 4.5 浏览器验收。

- [ ] **Step 3：运行验收并修正只属于集成层的问题**

Run:

```powershell
Set-Location frontend
npm test -- ..\tests\frontend\phase2Acceptance.spec.ts
```

Expected: PASS。若失败源于某个模块公共接口不一致，修正接口与该模块目标测试，不在验收测试中绕过。

### Task 4.3：同步文档和面试叙事

**Files:**

- Modify: `README.md`
- Modify: `docs/06_API_Contract.md`
- Modify: `docs/08_Prompt_Engineering_CN.md`
- Modify: `docs/09_Decision_Log.md`
- Modify: `docs/11_Project_Structure.md`
- Modify: `docs/12_Game_Experience_Design.md`
- Modify: `docs/13_Development_Roadmap.md`
- Modify: `docs/15_Story_Bible_CN.md`

- [ ] **Step 1：更新当前体验和启动说明**

README 当前体验改为四场景流程，并写明 WASD/方向键、单地图四地点和点击 NPC。技术栈增加 Phaser 3.90.0。已知限制明确像素坐标不持久化、职业无数值系统、没有战斗/背包/多地图。

- [ ] **Step 2：更新 API 和 Prompt 边界**

`docs/06_API_Contract.md` 给出带/不带 `player_profile` 的 Chat request，列出名称和职业校验、嵌套额外字段 422，以及“不写 Player Schema”。`docs/08_Prompt_Engineering_CN.md` 记录玩家自述块是不可信非权威上下文，不能覆盖 World Fact、NPC 知识和 Quest。

- [ ] **Step 3：更新设计决策与项目结构**

Decision Log 记录 Phaser 胜过 PixiJS、Vue DOM 与 Canvas 分工、双层位置模型、CC0 素材策略。Project Structure 写清 `player/`、`game/`、public phase2 assets 和新增测试职责。

- [ ] **Step 4：更新体验、路线和 Story Bible**

Game Experience 写四个 Scene 和地图交互；Roadmap 将 Phase 2 标记为当前完成能力，但不把 Phase 2B/部署写成已完成；Story Bible 将职业定义为“失忆后玩家选择的行事方式”，明确 NPC 不得把它当作失忆前身份证据。

### Task 4.4：全量自动验证和静态边界扫描

- [ ] **Step 1：运行 Backend 全量测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider
```

Expected: all PASS；无真实 Provider 网络请求。

- [ ] **Step 2：运行 Frontend 全量测试、类型检查和生产构建**

Run:

```powershell
Set-Location frontend
npm test
npm run type-check
npm run build
```

Expected: all PASS；build 输出包含静态地图与 Phaser bundle。

- [ ] **Step 3：确认没有 Player Schema、坐标 API 或越界系统**

Run:

```powershell
git diff -- backend\app\database backend\app\schemas\player.py scripts\upgrade_schema.py
rg -n "player_(x|y)|position_(x|y)|travel.*WASD|inventory|equipment|combat|skill" backend frontend\src
git diff --check
```

Expected: 第一个命令无输出；第二个命令不出现新 Backend 坐标字段/API 或玩法系统实现（文案、测试名称和明确否定可人工排除）；`git diff --check` 无错误。

- [ ] **Step 4：确认第三方素材清单完整**

逐一将 `frontend/public/assets/phase2` 下文件与 `THIRD_PARTY_ASSETS.md` 对照；没有来源记录的二进制素材不得保留在最终 Diff。

### Task 4.5：浏览器人工验收

- [ ] Mock 模式启动 Backend 和 Frontend；
- [ ] 清空 `aleria.player-profile.v1`，完成法师创建和完整剧情；
- [ ] 刷新后确认名称/职业保留且直接从启动页进入 town；
- [ ] 分别创建或临时切换测试游侠、牧师外观，确认三套 Sprite 正确；
- [ ] 用 WASD 和方向键移动，确认斜向速度、边界、建筑、水体和树木碰撞；
- [ ] 确认地图上酒馆、公园、城堡、森林入口清晰且道路可达；
- [ ] 确认三 NPC 来自 Backend；推进 Tick 后 NPC 按新语义地点 tween；
- [ ] 点击 Ryan、Shir、Grey，确认各自详情、状态和聊天可用；
- [ ] 询问“你认识我吗”，确认回复使用当前名称/职业但不编造过去；
- [ ] 完成失踪孩子任务，确认现有语义 travel 控件和五步迁移不受 WASD 影响；
- [ ] 模拟 Backend 失败、地图资源失败和 localStorage 失败，确认都有可读提示且 DOM 任务/NPC 入口仍可用；
- [ ] 在 1440×900、1024×768、390×844 三种视口检查布局；
- [ ] 从 town 切换/卸载组件或触发热更新，确认页面只有一个 Canvas、一次 NPC 点击回调。

### Module 4 人工 Review 门

- [ ] 展示四场景完整录屏或现场路径；
- [ ] 展示 Phaser 坐标与 Backend 语义地点分离的网络请求证据；
- [ ] 展示 NPC 点击、World Tick 投影、Chat profile 和原任务闭环；
- [ ] 展示素材许可、文档变化、全量测试、构建与 `diff --check`；
- [ ] 展示最终工作区完整 Diff 和未提交文件列表；
- [ ] 停止执行，等待用户最终 review；
- [ ] 用户自行提交。建议提交说明：`feat: integrate phase 2 rpg presentation flow`。

---

## Final Completion Criteria

- 四个 Scene 可连贯进入，已有档案路径正确；
- 玩家名称、职业、剧情完成状态版本化保存在 localStorage；
- Backend Player Schema、ORM、数据库和 migration 无变化；
- Chat profile 可选、严格校验、只用于当次上下文；
- Phaser 3.90.0 单地图包含四地点和三 Backend NPC；
- WASD/方向键移动、归一化斜向速度、碰撞、镜头和职业外观工作；
- Phaser `(x, y)` 不持久化、不调用任何 travel/position API；
- NPC 点击复用现有 Detail/Chat，World Tick 后视觉投影更新；
- 原世界推进、语义 travel 和失踪孩子任务闭环通过回归；
- 没有战斗、背包、技能、装备、多地图和室内地图；
- 所有第三方素材都有 CC0 来源记录；
- Backend pytest、Frontend Vitest、TypeScript、Vite build 和 `git diff --check` 全部通过；
- 执行期间所有提交均由用户 review 后自行完成。

## Execution Handoff

计划按四个 Module 执行，每个 Module 结束立即暂停，不跨 review 门。

1. **Subagent-Driven（推荐）**：每个 Task 使用新的子代理实现并做两阶段 review；根代理仍不提交 Git。
2. **Inline Execution**：在当前会话按 Module 批量执行，Module 结束后汇报并等待用户 review；根代理不提交 Git。
