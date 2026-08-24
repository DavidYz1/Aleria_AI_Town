# Phase 1D World Content and Quest Foundation Design

Status: Proposed for human review

Last Updated: 2026-08-24

## 1. Goal

Phase 1D 在 Phase 1C 已完成的确定性世界、NPC 详情与 Chat 闭环之上，补齐一个可感知、可持久化、可演示的轻量游戏目标：

```text
玩家进入曦谷
    ↓
在星辉酒馆接受“失踪的孩子”任务
    ↓
前往晨曦城堡询问 Grey
    ↓
前往低语森林发现鞋子并找到孩子
    ↓
返回星辉酒馆完成任务
```

本阶段同时完成世界内容与角色表达增强：

- 小镇展示名由“晨曦镇”调整为“曦谷”。
- 酒馆展示名由“星辰酒馆”调整为“星辉酒馆”。
- 在现有酒馆与公园之外增加晨曦城堡和低语森林。
- 让 Ryan、Shir、Grey 的确定性日常行为与地点更符合角色身份。
- 将 Prompt 升级为更清晰的世界设定、玩家边界和角色 Bible。
- 丰富确定性 Mock 的常见问题回答。
- 让 OpenAI-compatible Adapter 同时兼容结构化 JSON 模型和自然文本角色模型。
- 引入固定 `default-player`，只持久化玩家当前位置。
- 实现一个专用、确定性、可审计的任务状态机。
- 在 Vue DOM 页面中先完成任务闭环，为后续 PixiJS 地图提供稳定接口。

Phase 1D 不追求通用 RPG 系统。它的目标是以较小的工程增量增强腾讯作业的可玩性、人格表现、状态持久化和演示完整度。

## 2. Assignment Alignment

腾讯作业的必做闭环已由 Phase 0—1C 覆盖。Phase 1D 主要强化以下评审维度：

- **世界展示**：从两个地点扩充为四个具备叙事功能的地点。
- **NPC 模拟**：仍由 Backend 根据角色、状态、地点和时间确定性决策，且角色行为差异更明显。
- **玩家互动**：在 Chat 之外增加旅行、调查和任务完成反馈。
- **AI 能力**：通过更完整 Prompt、角色差异与 Provider 兼容模式提高真实模型演示质量。
- **故障可用性**：Mock 仍为无 Key 和真实模型失败时的完整体验保障。
- **工程质量**：任务状态由 Backend 权威维护，状态迁移、并发冲突和历史记录可测试、可解释。
- **加分项基础**：形成状态持久化、简单任务/NPC 互动，并为 PixiJS、部署和响应式体验提供稳定数据层。

本阶段不是为了用 Quest 掩盖必做项，而是在必做项已完成的前提下，增加一条评审者能在数分钟内走通的故事线。

## 3. Current Foundation

Phase 1D 建立在以下已实现切片上：

```text
World Read          Deterministic Tick       NPC Detail          NPC Chat
GET /api/world      POST /api/world/tick     GET /api/npcs/:id   POST /api/npcs/:id/chat
WorldService        WorldTickService         NpcService          ChatService
WorldRepository     WorldTickRepository      NpcRepository       ChatRepository
                                                                    + ChatProvider
```

必须保持的现有约束：

- SQLite 是运行时唯一状态源，根目录 JSON 是可重复初始化的种子输入。
- `world_id="aleria-town"`、`location_id="tavern"` 等技术 ID 保持稳定；只调整用户可见名称。
- World Tick 每次严格推进一小时，并以同一个不可变快照为三名 NPC 决策。
- NPC Action 只允许 `move/rest/work/eat/social`，所有 Action 必须校验、执行并与 Event 同事务保存。
- Chat 是独立切片，不调用 World Tick，不修改 NPC State、Action 或 Event。
- `ChatProvider`、Fallback、OpenAI-compatible Adapter 和 Mock Provider 边界继续保留。
- Frontend World、NPC Detail、NPC Chat Store 相互独立，由 `TownView` 协调。
- 当前仓库中 Player、Quest 和 PixiJS 尚未实现。

## 4. Scope

### 4.1 In scope

- 曦谷、星辉酒馆、中央公园、晨曦城堡、低语森林的正式展示内容。
- 保持原有世界和地点 ID 向后兼容。
- 基于现有五种 Action 的角色化时间例程与原因文案。
- Prompt `v2`：Chat System、World Lore、Player Context、三份 Character Bible。
- Mock 常见意图：问候、身份、世界、地点、当前行为、心情、求助、历史和秘密试探。
- Adapter 的 `structured_json` 与 `text` 两种输出模式。
- 固定 `default-player` 和唯一持久化字段 `location_id`。
- 单任务 `missing-child` 的确定性状态机。
- 玩家读取、旅行和任务交互 API。
- Quest 状态迁移历史和事务一致性。
- Chat 只读获取玩家/任务摘要，使 NPC 回复能与当前任务阶段一致。
- Vue DOM 旅行和任务面板闭环。
- Backend、Frontend、API、状态机和 Mock/Adapter 自动化测试。
- README 第一轮结构化重写及相关设计文档同步。

### 4.2 Out of scope

- PixiJS、Cocos、Canvas 地图和 Sprite 动画。
- 通用 Quest Definition/Condition/Reward 编辑器。
- 多任务、随机任务、每日任务或任务生成器。
- 通用背包、物品表、掉落、装备、金币或奖励经济。
- 玩家姓名、职业、等级、属性、账号、登录或多人身份。
- 战斗、寻路、碰撞、地图坐标或传送成本。
- Relationship、长期 Memory、Reflection、Planning、RAG 或 LLM World Tick。
- 由聊天内容、模型输出或 Prompt 指令直接推进 Quest。
- Docker、云部署和线上体验地址；这些进入 Phase 1E。
- 全量视觉重构；PixiJS 地图进入后续 Phase 2。

## 5. Key Architecture Decisions

### 5.1 Stable IDs, revised display names

本阶段不迁移外键或公开技术标识：

| Entity | Stable ID | Display name |
| --- | --- | --- |
| World | `aleria-town` | 曦谷 |
| Tavern | `tavern` | 星辉酒馆 |
| Park | `park` | 中央公园 |
| Castle | `castle` | 晨曦城堡 |
| Forest | `forest` | 低语森林 |

Prompt、Mock、Frontend 和 API 都使用 Backend 返回的展示名，不以中文名称作为逻辑键。

### 5.2 Player is a minimal spatial entity

Phase 1D 只有一个固定玩家：

```text
id = default-player
world_id = aleria-town
location_id = <one valid location>
```

玩家没有姓名、职业、等级、背包、战斗属性或认证身份。这个模型只解决两个问题：

1. Backend 能权威校验玩家是否位于可执行任务交互的地点。
2. 后续 PixiJS 能直接把玩家当前位置映射为一个可视实体。

### 5.3 Quest is a dedicated deterministic scenario

`missing-child` 不是一个由 JSON 条件表达式或 LLM 驱动的通用任务。状态迁移位于专用 Quest Domain Policy 中，所有交互使用有限枚举命令。

```text
available
   └─ accept_quest @ tavern
        ↓
accepted
   └─ ask_grey @ castle
        ↓
briefed_by_grey
   └─ inspect_shoe @ forest
        ↓
shoe_found
   └─ search_child @ forest
        ↓
child_found
   └─ return_child @ tavern
        ↓
completed
```

错误地点、错误前置状态、未知命令和过期版本都由 Backend 拒绝。Frontend 只展示 Backend 返回的可用交互，不能自行跳转状态。

### 5.4 Quest interaction and NPC Chat remain separate

“询问 Grey”通过确定性任务交互命令推进，而不是分析玩家对 Grey 输入的自然语言。

Chat 可以读取当前玩家位置和 Quest 摘要，以便 Grey 在 `accepted` 后自然谈论失踪事件；但 ChatProvider 返回值仍只有 `reply + emotion`，ChatService 仍不能写入 Player/Quest/NPC/World 状态。

### 5.5 Existing Action vocabulary remains stable

不新增 `train/scout/patrol` 数据库 Action Type。三者继续保存为 `work`，通过角色、地点和稳定原因代码表现差异：

| NPC | Routine location | Persisted action | Example reason code | User-facing meaning |
| --- | --- | --- | --- | --- |
| Ryan | `park` | `work` | `knight_training` | 在中央公园训练 |
| Shir | `forest` | `work` | `assassin_scout` | 在低语森林侦察 |
| Grey | `castle` | `work` | `guardian_patrol` | 在晨曦城堡巡逻 |

这样保留 Phase 1A API 和数据库约束，同时让 Phase 1B Action Explanation 展示更鲜明。

### 5.6 Provider compatibility is an Adapter concern

ChatService 不感知 `hy3`、`hy-role`、Gemini、DeepSeek 或本地 Qwen。输出模式由 Adapter 配置决定：

- `structured_json`：请求并解析严格的 `reply + emotion` JSON。
- `text`：接受自然文本为 `reply`，由 Backend 确定性推导合法 `emotion`。

两种模式最终都返回同一个 `ChatProviderResult`，Fallback 语义和公共 Chat API 不变。

## 6. Target Architecture

### 6.1 New Player/Quest slice

```text
Vue PlayerQuestPanel
        ↓
playerQuest Pinia Store
        ↓
GET  /api/player
POST /api/player/travel
POST /api/quests/missing-child/interact
        ↓
PlayerQuestService
   ├── MissingChildQuestPolicy (pure state machine)
   └── PlayerQuestRepository (transaction + optimistic lock)
        ↓
SQLite player_states + quest_progress + quest_events
```

Suggested Backend structure:

```text
backend/app/
├── api/
│   ├── player.py
│   └── quests.py
├── database/
│   └── player_quest_repository.py
├── quests/
│   ├── __init__.py
│   ├── missing_child.py
│   └── types.py
├── schemas/
│   ├── player.py
│   └── quest.py
└── services/
    └── player_quest_service.py
```

Suggested Frontend structure:

```text
frontend/src/
├── api/playerQuest.ts
├── types/playerQuest.ts
├── stores/playerQuest.ts
└── components/
    ├── PlayerLocationPanel.vue
    └── QuestPanel.vue
```

### 6.2 Read-only Chat enrichment

```text
ChatContextAssembler
   ├── existing NPC/world/action/chat reads
   ├── PromptLoader v2
   └── PlayerQuestRepository.get_context_summary()
        ↓
ChatProviderRequest.player_context + quest_context
        ↓
Mock or OpenAI-compatible Provider
```

Player/Quest 上下文不可作为 Provider 工具，也不包含可执行命令。它只是一段 Backend 生成的只读事实。

## 7. World Content and NPC Routine Design

### 7.1 Location responsibilities

| Location | Purpose in world simulation | Purpose in quest | Future visual purpose |
| --- | --- | --- | --- |
| 星辉酒馆 | 休息、进食、社交 | 接取和交付任务 | 任务板、室内入口 |
| 中央公园 | Ryan 训练、居民放松 | 路线过渡与世界生活感 | 开放中心区域 |
| 晨曦城堡 | Grey 巡逻、守卫秩序 | 获取失踪线索 | 城门与守卫地标 |
| 低语森林 | Shir 侦察、潜在危险 | 找鞋、寻找孩子 | 探索与调查区域 |

### 7.2 Deterministic role routines

状态阈值仍高于角色例程：夜晚/低体力、低社交和低心情规则继续优先。角色默认例程调整为：

- **Ryan / Knight**：morning/day 前往中央公园训练；evening 优先同地点社交，否则休息；night 休息。
- **Shir / Assassin**：morning/day 倾向在星辉酒馆短暂进食或休息；evening 前往低语森林侦察；night 休息。
- **Grey / Guardian**：morning/day/evening 前往晨曦城堡巡逻；night 休息。

`work` 校验从“只能在公园”调整为“角色与职责地点匹配”。未知角色仍安全退回 `rest`。

### 7.3 Initial seed state

- `default-player` 初始位于 `tavern`。
- Ryan 初始位于 `park`。
- Shir 初始位于 `tavern`。
- Grey 初始位于 `castle`。
- `missing-child` 初始状态为 `available`，版本为 `0`。

重跑种子脚本会将当前世界、Player、Quest 和相关历史重置为上述可演示状态。

## 8. Player and Quest Data Model

### 8.1 `player_states`

```text
id           TEXT PRIMARY KEY
world_id     TEXT NOT NULL REFERENCES world_state(id)
location_id  TEXT NOT NULL REFERENCES locations(id)
updated_at   DATETIME NOT NULL
```

Constraints:

- Phase 1D 只允许 `id="default-player"`。
- 同一个玩家只能属于一个 World。
- `location_id` 必须是数据库中的有效地点。
- 不加入未来可能需要但当前没有消费方的字段。

### 8.2 `quest_progress`

```text
player_id    TEXT NOT NULL REFERENCES player_states(id)
quest_id     TEXT NOT NULL
status       TEXT NOT NULL
version      INTEGER NOT NULL CHECK(version >= 0)
updated_tick INTEGER NOT NULL CHECK(updated_tick >= 0)
updated_at   DATETIME NOT NULL

PRIMARY KEY (player_id, quest_id)
```

`version` 每次成功迁移递增一，用于拒绝重复点击和多标签页的过期请求。旅行不会改变 Quest version。

`quest_progress` 和 `quest_events` 使用可复用的最小存储形状，但 Phase 1D Repository 只支持 `missing-child`。合法状态集合由专用 Domain Policy 校验，不把单任务状态枚举固化为数据库 CHECK，避免未来增加第二个任务时先迁移表结构。这不等于实现通用 Quest Definition/Condition Engine。

### 8.3 `quest_events`

```text
id            INTEGER PRIMARY KEY AUTOINCREMENT
player_id     TEXT NOT NULL REFERENCES player_states(id)
quest_id      TEXT NOT NULL
from_status   TEXT NOT NULL
to_status     TEXT NOT NULL
interaction   TEXT NOT NULL
location_id   TEXT NOT NULL REFERENCES locations(id)
world_tick    INTEGER NOT NULL CHECK(world_tick >= 0)
created_at    DATETIME NOT NULL
```

Index:

```text
INDEX ix_quest_events_player_quest_id
    (player_id, quest_id, id)
```

每次状态迁移和对应 Event 在同一事务中提交。`quest_events` 是任务审计历史，不复用只允许 `npc_action` 的现有 `events` 表，也不伪装为 NPC Action。

### 8.4 No inventory table

鞋子只是 `shoe_found` 状态的叙事含义，不创建 Item 或 Inventory。孩子也不是可移动实体；`child_found` 表示玩家已找到并护送孩子，返回酒馆后进入 `completed`。

### 8.5 Schema upgrade and seed reset

新增表可以继续由 `upgrade_schema.py`/SQLAlchemy `create_all` 非破坏性创建。

`seed_world.py` 是对 canonical world 的显式重置，需要按外键顺序清理：

```text
quest_events
    ↓
quest_progress
    ↓
player_states
    ↓
conversation_messages / conversations
    ↓
events / actions
    ↓
world, locations, NPC profiles and current states reseed
    ↓
default-player + missing-child initial progress seed
```

真实运行中的 Player/Quest 状态不能由普通应用启动隐式覆盖。

## 9. Quest Domain Design

### 9.1 Pure transition policy

核心策略接收不可变输入：

```text
QuestSnapshot
├── quest_id
├── status
├── version
├── player_location_id
└── world_tick

QuestCommand
├── interaction
└── expected_version
```

输出：

```text
QuestTransition
├── from_status
├── to_status
├── interaction
├── location_id
└── event_text_code
```

策略不访问数据库、HTTP、Prompt 或 LLM，因此每条迁移都可以用参数化单元测试覆盖。

### 9.2 Transition rules

| Current status | Required interaction | Required location | Next status | Objective after transition |
| --- | --- | --- | --- | --- |
| `available` | `accept_quest` | `tavern` | `accepted` | 去晨曦城堡询问 Grey |
| `accepted` | `ask_grey` | `castle` | `briefed_by_grey` | 去低语森林寻找线索 |
| `briefed_by_grey` | `inspect_shoe` | `forest` | `shoe_found` | 沿鞋子附近的痕迹继续寻找 |
| `shoe_found` | `search_child` | `forest` | `child_found` | 护送孩子返回星辉酒馆 |
| `child_found` | `return_child` | `tavern` | `completed` | 任务已完成 |
| `completed` | none | none | `completed` | 可回顾任务结果 |

### 9.3 Authoritative available interactions

Backend 根据当前 Player location 和 Quest status 派生 `available_interactions`。Frontend 不维护第二份状态机，只根据该数组渲染按钮。

例如：

```json
{
  "status": "accepted",
  "objective": "前往晨曦城堡询问 Grey。",
  "available_interactions": []
}
```

玩家旅行到 `castle` 后：

```json
{
  "status": "accepted",
  "objective": "前往晨曦城堡询问 Grey。",
  "available_interactions": [
    {
      "id": "ask_grey",
      "label": "询问 Grey"
    }
  ]
}
```

## 10. API Contract

所有成功响应继续使用现有 `ApiResponse<T>` 包装。

### 10.1 Read player and quest state

```http
GET /api/player
```

Success data:

```json
{
  "player": {
    "id": "default-player",
    "location_id": "tavern",
    "location_name": "星辉酒馆"
  },
  "quest": {
    "id": "missing-child",
    "title": "失踪的孩子",
    "status": "available",
    "version": 0,
    "objective": "查看星辉酒馆的委托板。",
    "available_interactions": [
      {
        "id": "accept_quest",
        "label": "接受委托"
      }
    ],
    "recent_events": []
  }
}
```

`recent_events` 最多返回最近五条，按发生顺序展示：

```json
{
  "id": 1,
  "from_status": "available",
  "to_status": "accepted",
  "interaction": "accept_quest",
  "description": "你在星辉酒馆接受了寻找失踪孩子的委托。"
}
```

### 10.2 Travel

```http
POST /api/player/travel
Content-Type: application/json
```

Request:

```json
{
  "target_location_id": "castle"
}
```

Rules:

- Target 必须是当前 World 的有效地点。
- 旅行只修改 `player_states.location_id`，不推进 World Tick、NPC 或 Quest。
- 重复前往当前地点是幂等成功。
- Success 返回与 `GET /api/player` 相同的最新数据，便于 Store 原子替换状态。

Errors:

- HTTP 404：Player 或地点不存在。
- HTTP 503：状态读取或持久化失败。

### 10.3 Interact with the quest

```http
POST /api/quests/missing-child/interact
Content-Type: application/json
```

Request:

```json
{
  "interaction": "ask_grey",
  "expected_version": 1
}
```

Rules:

- `interaction` 只能是已定义枚举。
- `expected_version` 必须等于当前 Quest version。
- 当前状态、当前位置和 interaction 必须形成合法迁移。
- Success 在一个事务中更新 Quest progress 并写入 Quest Event。
- Success 返回最新 Player/Quest data。

Errors:

- HTTP 404：Player 或 Quest 不存在。
- HTTP 409，`Quest state has changed`：版本过期。
- HTTP 409，`Quest interaction is not available`：地点或前置状态不满足。
- HTTP 422：未知 interaction、负版本或无效请求结构。
- HTTP 503：事务失败，状态保持不变。

### 10.4 Existing API compatibility

- `GET /api/world` 只因 seed 内容增加而返回四个地点；Schema 不变。
- `POST /api/world/tick` Schema 不变；NPC 可能移动到新增地点，Action Type 仍不变。
- `GET /api/npcs/{npc_id}` Schema 不变；Location 和 Action Explanation 展示新内容。
- `POST /api/npcs/{npc_id}/chat` Request/Response Schema 不变。

## 11. Prompt v2 Design

### 11.1 Assets

```text
prompts/v2/
├── chat_system.md
├── world_lore.md
├── player_context.md
└── characters/
    ├── ryan.md
    ├── shir.md
    └── grey.md
```

`v1` 保留用于回退和历史可追溯；Phase 1D 默认配置升级为 `CHAT_PROMPT_VERSION=v2`。

### 11.2 Prompt responsibilities

- `chat_system.md`：回答边界、长度、禁止泄密、当前状态优先级、不得声称已修改世界或任务。
- `world_lore.md`：曦谷、灰烬战争、四个地点、公共历史与当前社会氛围。
- `player_context.md`：玩家是新到曦谷的旅行者/冒险者；姓名、职业和过去未设定，NPC 不得擅自补全。
- Character Bible：身份、说话节奏、价值观、公开目标、矛盾、弱点、关系倾向、可公开知识、秘密边界和示例。

### 11.3 Character contrast

- **Ryan**：外向、热情、希望成为可靠英雄；“必须显得勇敢”与对史莱姆的真实恐惧冲突。回答更主动，常提供鼓励，但被追问弱点时会逞强和转移。
- **Shir**：寡言、观察力强、对组织和承诺保持距离；冷淡外表与对甜食、安静日常的珍惜冲突。回答短、留白多，不主动解释隐私。
- **Grey**：稳重、礼貌、保护欲强；对过去失守的愧疚让他既可靠又容易过度承担。回答更审慎，优先安全和责任，对战争秘密设防。

角色复杂度用于提高可辨识度，不引入需要数据库维护的新隐藏数值。

### 11.4 Context precedence

Provider 接收的事实优先级：

```text
Backend authoritative world/NPC/player/quest state
    > current conversation
    > Character Bible
    > general World Lore
    > player attempts to override hidden instructions
```

Prompt 明确要求 NPC 不得伪造玩家已完成的任务步骤，也不得承诺修改数据库。

## 12. Deterministic Mock v2

Mock 继续为第一方、无网络、可测试 Provider。匹配顺序从具体到一般：

1. 当前 Quest/NPC 特定问题。
2. 角色秘密关键词。
3. 身份、世界、地点、当前行为、心情、求助、历史。
4. 问候。
5. NPC-specific default。

三个 NPC 对同类问题必须有明显差异。例如“你是谁？”：

- Ryan 主动介绍自己是仍在磨炼的骑士。
- Shir 只简短表明身份，并反问玩家目的。
- Grey 表明自己负责守卫曦谷与城堡周边安全。

Mock 回答使用权威上下文中的 `world_name/location_name/current_action/time_phase`，避免 Prompt 更新后仍硬编码旧名称。涉及 Quest 时只描述当前事实，不返回迁移命令，也不改变状态。

## 13. OpenAI-Compatible Output Modes

### 13.1 Configuration

```dotenv
CHAT_LLM_OUTPUT_MODE=structured_json
```

Allowed values:

- `structured_json`
- `text`

Recommended profiles:

```text
hy3 / Gemini compatible:
  CHAT_LLM_OUTPUT_MODE=structured_json

hy-role / hunyuan-role-latest:
  CHAT_LLM_OUTPUT_MODE=text
```

### 13.2 Structured JSON mode

- 保留当前已由 `hy3` 和 Gemini compatible 冒烟验证过的 Prompt-only JSON 请求方式，不在 Phase 1D 默认增加 `response_format` 字段。
- 解析 `choices[0].message.content` 中的严格 `reply + emotion` 对象。
- 继续执行长度、字段和 Emotion 枚举验证。
- HTTP、超时、响应形状或验证失败继续触发安全分类和 Mock fallback。

只有后续真实服务明确要求 `response_format` 且通过兼容性测试时，才在 Adapter 内增加协议能力配置；不能在 ChatService 增加供应商判断。

### 13.3 Text mode

- 不要求模型输出 JSON，也不发送结构化输出参数。
- `message.content` 经 strip 后直接作为 `reply`。
- 非字符串、空文本或超过 500 字符的内容视为验证失败并 fallback。
- `emotion` 由 Backend 确定性映射：`mood <= 35` 时为 `concerned`；否则 Ryan 为 `cheerful`、Shir 为 `reserved`、Grey 为 `thoughtful`，未知 NPC 为 `neutral`。
- API、数据库和 Frontend 仍得到相同的 `reply + emotion`。

Text mode 是对角色模型协议差异的兼容，不是降低 Backend 校验或允许模型控制游戏。

### 13.4 Security and observability

继续只记录安全错误类别：

```text
provider=<label> category=<safe_category> status=<code-or-dash>
```

禁止记录 API Key、Authorization Header、完整 Prompt、完整上游响应正文或隐藏推理。

## 14. Frontend Experience

### 14.1 DOM-first vertical slice

Phase 1D 先在当前 Vue/CSS 页面完成任务体验：

- Header 或独立面板展示“你位于：地点”。
- Location Card 提供“前往此处”，并标记当前地点。
- Quest Panel 展示标题、状态、当前目标和最近进展。
- 只有 Backend 返回的 `available_interactions` 才显示交互按钮。
- 到达城堡后可“询问 Grey”；到达森林后依次调查鞋子、寻找孩子；回酒馆后交付。
- NPC Detail/Chat 仍保持现有选择方式。

### 14.2 Store boundaries

新增 `playerQuest` Store，不导入 World、NPC Detail 或 NPC Chat Store。`TownView` 负责：

- 页面加载时并行请求 World 与 Player/Quest。
- 旅行或任务交互成功后用返回数据替换 Player/Quest 状态。
- 根据位置和 Quest 数据组合界面，但不推导新的状态迁移。

### 14.3 UI states

必须覆盖：

- 初始 loading。
- 旅行中和任务交互中禁用重复操作。
- Player/Quest 加载失败与重试。
- 旅行失败不改变本地位置。
- 409 后重新读取权威状态并给出清晰提示。
- 任务完成态不再显示推进按钮。
- 小屏幕下地点、NPC 和 Quest 面板保持可读。

## 15. Error Handling and Transaction Boundaries

### 15.1 Travel

一次旅行只包含一项 Player State 更新。数据库失败时回滚，Frontend 保留旧状态并显示错误。

### 15.2 Quest interaction

一次 Quest 交互事务包含：

```text
load authoritative player + quest
    ↓
compare expected_version
    ↓
validate pure transition
    ↓
update status/version/tick
    ↓
insert quest_event
    ↓
commit
```

任一步失败都不留下半迁移或孤立 Event。

### 15.3 Chat enrichment failure

Player/Quest 是 Phase 1D Chat 的增强上下文，不应使既有 Chat 主闭环变脆弱：

- Player/Quest 记录存在时加入只读上下文。
- 记录缺失或读取失败时使用“玩家/任务上下文不可用”的安全摘要，仍可继续 NPC Chat。
- NPC/world/prompt 等 Phase 1C 必需上下文仍按原规则处理。

## 16. Testing Strategy

继续使用 TDD，并按模块保留人工 review 检查点。

### 16.1 World content and deterministic engine

- Seed 校验四个稳定 Location ID 和新展示名。
- `GET /api/world` 返回曦谷与四个地点。
- 三名 NPC 的默认时间例程和目标地点参数化测试。
- `work` 对正确角色/地点成功，对错误组合拒绝。
- 现有 need priority、immutable snapshot、transaction 和 409 Tick 测试继续通过。
- Action Explanation 将新 reason code 映射为角色化中文文案。

### 16.2 Prompt, Mock and Adapter

- Prompt v2 文件完整、非空且只支持已知 NPC。
- Player/Quest 上下文不包含执行能力。
- 三名 NPC 对常见意图产生确定且不同的 Mock 回复。
- Mock 使用当前展示名而非旧硬编码名称。
- Structured JSON mode 请求、解析和验证测试。
- Text mode 自然文本、空内容、过长内容和 Emotion 映射测试。
- 真实 Provider 失败时 fallback、provider 标记和安全日志测试保持通过。

### 16.3 Player and Quest domain

- 六个状态和五条合法迁移逐条单元测试。
- 每条迁移的错误地点、错误状态和错误命令测试。
- `completed` 终态不可再次推进。
- Travel 有效地点、无效地点和同地点幂等测试。
- Quest version 冲突返回 409。
- 状态与 Quest Event 同事务提交；注入失败时全部回滚。
- 重启/新 Session 后 Player location 和 Quest status 仍存在。
- Seed reset 恢复 `tavern + available + version 0`。

### 16.4 API and Frontend

- 三个新 API 的成功、404、409、422、503 契约测试。
- PlayerQuest Store loading、success、failure、retry、double-submit 和 stale response 测试。
- QuestPanel 在每一状态只渲染 Backend 允许的交互。
- TownView 加载和旅行协调测试。
- Frontend type-check、unit tests、production build。
- Mock 模式完整 E2E：接受任务到完成任务。
- 可选手工 smoke：hy3 structured JSON 与 hy-role text 各完成一次 NPC Chat。

## 17. Documentation Deliverables

Phase 1D 完成时同步：

- `README.md`：按项目介绍/玩法与角色、快速启动、架构与决策、API、AI/Mock、测试、AI 工具使用与人工修正案例、已知限制、路线图重组。
- `docs/00_Project_Context.md`：曦谷命名与当前完成状态。
- `docs/02_Product_Design.md`：四地点、玩家和任务体验。
- `docs/03_World_Model.md`：最小 Player/Quest 实际模型。
- `docs/04_NPC_Agent_Design.md`：新增地点上的角色例程。
- `docs/05_Engineering_Architecture.md`：Player/Quest Slice 和 Provider output mode。
- `docs/06_API_Contract.md`：三个新 API。
- `docs/07_Database_Schema.md`：三个新表与重置顺序。
- `docs/08_Prompt_Engineering_CN.md`：Prompt v2、角色冲突与输出模式。
- `docs/09_Decision_Log.md`：稳定 ID、专用 Quest、DOM-first、Text Adapter 决策。
- `docs/11_Project_Structure.md`：新增目录与文件职责。
- `docs/12_Game_Experience_Design.md`：失踪孩子任务链。
- `docs/13_Development_Roadmap.md`：Phase 1D/1E/2 的优先级。
- `.env.example`：`CHAT_LLM_OUTPUT_MODE` 及安全说明。

文档同步在功能与测试稳定后完成，避免提前描述尚未落地的能力。

## 18. Development Modules

### Module 0 — Close current Provider diagnostics

- 单独 review 当前 `.env.example`、`openai_compatible.py` 和对应测试的未提交变更。
- 确认安全错误分类和 30 秒示例超时是否保留。
- 由用户人工提交后再进入 Phase 1D，避免 diff 混杂。

### Module 1 — World content and role routines

- 改名与新增地点。
- Seed 和 World API 验证。
- 角色例程、Action 校验与 Action Explanation。
- Backend 单元/API 回归测试。

### Module 2 — Prompt v2, Mock v2 and output modes

- Prompt v2 与可选的 Player/Quest 只读上下文结构；在 Module 3 接入真实 Repository 前使用明确的“上下文不可用”摘要。
- 丰富 Mock 常见意图。
- Adapter structured JSON/text 模式。
- Provider/Prompt/Mock 测试。

### Module 3 — Player and Quest backend

- 数据模型、schema upgrade/seed reset。
- 纯任务状态机、Repository、Service 和三个 API。
- 将 Chat 的可选 Player/Quest 摘要接入真实只读 Repository，并验证读取失败不会破坏 Chat。
- 事务、并发、持久化和 API 测试。

### Module 4 — Frontend DOM quest loop

- API/Types/Store。
- Player Location 与 Quest Panel。
- TownView 协调、错误态、响应式布局和 Frontend 测试。

### Module 5 — E2E acceptance and documentation

- Mock 全任务链 E2E。
- 可选真实 Provider smoke。
- 全量回归、type-check 和 production build。
- README 结构化重写与设计文档同步。

每个 Module 均遵循：测试先行 → 最小实现 → 回归验证 → 展示 diff → 用户 review/commit → 下一模块。Codex 不自动执行 Git commit。

## 19. Phase Boundary and Recommended Roadmap

```text
Phase 1D  World Content + Prompt + Quest Foundation
    ↓
Phase 1E  README + Docker + Online Deployment + Demo Packaging
    ↓
Phase 2   PixiJS four-location map + player/NPC visual movement
    ↓
Phase 3   lightweight Relationship/Memory if time permits
    ↓
Phase 4   advanced Agent planning/reflection/LLM action decisions
```

前端地图优先于复杂 Agent：腾讯作业对可运行闭环、可见交互和演示质量的要求更直接，而现有确定性规则已经满足“Backend 根据角色、状态、时间和地点生成 NPC 决策”的基础要求。

## 20. Acceptance Criteria

Phase 1D 只有在以下条件全部满足时才算完成：

- `GET /api/world` 展示曦谷、星辉酒馆、中央公园、晨曦城堡和低语森林。
- Ryan、Shir、Grey 在新增地点上具有稳定、可解释且可测试的角色例程。
- Mock 对高频问题提供符合人物设定的差异化回答。
- `hy3` 可使用 structured JSON 模式，`hy-role` 可使用 text 模式，而 ChatProvider/ChatService/API 不出现供应商分支。
- `default-player` 位置在 SQLite 中持久化。
- 玩家能从星辉酒馆开始，完成五次合法任务迁移并回到酒馆交付。
- 跳步、错误地点、重复提交和过期版本均被 Backend 拒绝。
- Quest 完成不修改 World Tick、NPC State、NPC Action 或 Event。
- Chat 可以描述当前任务事实，但不能推进任务。
- Mock 模式在无 API Key 时完整可玩。
- Backend/Frontend 自动化测试、类型检查和生产构建通过。
- README 和相关设计文档与实际实现一致。
- 所有变更保持未提交，供用户人工 review 和 Git commit。

## 21. Risks and Controls

| Risk | Control |
| --- | --- |
| Quest 扩张成通用 RPG 框架 | 只实现 `missing-child` 专用 Policy 和有限命令 |
| Chat 自然语言误触发状态变化 | Chat 与 Quest Command 完全分离 |
| 新地点破坏旧 Tick 规则 | 保持 Action Type，参数化角色职责地点并回归原测试 |
| `hy-role` 不返回 JSON | Adapter text mode，Backend 确定性补齐 emotion |
| Prompt 过长导致成本与迟延增加 | 分层资产、删除重复说明、只传有界历史与摘要 |
| Frontend 重复实现状态机 | Backend 返回 objective 与 available_interactions |
| Player 模型过早膨胀 | 只保存 id/world/location，不加账号和角色成长字段 |
| 任务状态写入一半 | Progress 与 Quest Event 同事务提交 |
| Phase 1D 影响既有验收闭环 | 新切片独立；现有四个公共 API 保持兼容 |

## 22. Explicit Deferred Decisions

以下问题不在 Phase 1D 预先决定：

- PixiJS 使用何种开源 Tilemap、Sprite 或素材许可。
- 玩家和 NPC 是否需要地图坐标、碰撞或寻路。
- Quest 是否在未来抽象为数据驱动定义。
- 是否增加任务奖励、物品或多个 Player。
- Chat 历史是否转化为长期 Memory。
- 是否使用 LLM 参与 World Action 决策。

只有后续阶段出现真实消费方时，才为这些能力增加模型和接口。
