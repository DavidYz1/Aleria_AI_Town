# Aleria AI Town 架构地图

本文件是给新接手的人和 AI agent 的**架构地图**，用于快速建立系统心智模型。

**阅读规则**：本文严格区分 `Implemented`（已有代码与测试支撑）与 `Proposed / Future`（尚不存在）。**不要 import、假设或依赖 Proposed 段的任何内容。**

事实基准：HEAD `2253768`，Alembic head `0004`，backend 709 passed / 4 skipped，frontend 207 passed / 29 files。

---

## Implemented

以下内容在当前仓库中**真实存在**，有代码和测试支撑。

### 技术栈

| 领域 | 已落地 |
| --- | --- |
| 前端 | Vue 3.5 + TypeScript 5.7 + Pinia 3 + Vite 6 |
| 游戏渲染 | Phaser 3.90.0（版本锁定） |
| 后端 | FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic |
| 数据库 | SQLite（本地/测试默认）**与** PostgreSQL 17 + pgvector 0.8.6（Docker 部署路径） |
| 测试 | pytest（53 文件）+ Vitest（30 文件） |

### 已实现的系统能力

- **确定性 World Engine**：时钟推进、角色日程、被动需求漂移、类型化行动
- **Agent Runtime Foundation**：Action Registry、冲突处理、原子 Run Graph 持久化（run / proposal / action / event / trace）
- **三套独立计数器**：`world_version`、`clock_tick`、`event_sequence`
- **NPC Chat**：Provider 抽象（fake / OpenAI-compatible）+ 降级 + Prompt 版本化
- **Player 系统**：本地角色档案、地点移动、主线任务 `missing_child`
- **Stage 2 认知栈**：感知策略、Observation/Memory 投影、逐 NPC checkpoint、Embedding enrichment、权限优先混合检索、证据约束 Reflection、追加式 Belief
- **安全解释面**：`GET /api/npcs/{npc_id}/memory-explanations` + 前端折叠"相关记忆"区
- **Demo Reset**：按 World 清理并重建，含认知数据
- **部署**：Docker Compose（db / backend / web）、nginx、一键启动与部署脚本

### 关于 PostgreSQL 与 pgvector 的准确状态

**代码路径已实现，不是未来规划**：

- `compose.yaml` 固定使用镜像 `pgvector/pgvector:0.8.6-pg17-bookworm`
- `backend/app/database/connection.py` 处理 `postgresql` → `postgresql+psycopg` 归一化与方言差异
- 迁移 `0004_stage2_cognition.py` 在 PostgreSQL 上创建 `Vector` 列，在 SQLite 上使用 JSON 等价物
- `cognition_repository.semantic_scores()` 使用 pgvector 的 `<=>` 距离算子，并在失败时经 savepoint 降级
- 4 个 opt-in PostgreSQL 测试存在：`test_schema_migrations.py:439`、`test_postgres_runtime.py:18`、`test_memory_retrieval.py:280`、`test_chat_repository.py:19`

**但验收边界必须说清楚**：

- Foundation 阶段的 PostgreSQL Runtime Graph 持久化**已完成真实集成验收**（commit `e78714f`）
- **Stage 2 认知表 + 向量检索在 PostgreSQL 上的真实验收尚未执行** —— 这是 Task 5 Step 6 的待办事项。上述 4 个测试在未设置 `TEST_POSTGRES_URL` 时会 skip，当前基线中它们**全部处于 skip 状态**

换言之：**能跑，但 Stage 2 这部分还没有人真的跑过**。

---

## Proposed / Future

以下内容**当前不存在**。它们出现在 Roadmap 和 Stage Spec 中，但没有任何代码实现。

| 能力 | 计划所属 Stage | 状态 |
| --- | --- | --- |
| Goal、Goal Arbitration、Plan、Plan Step | Stage 3 | 未实现 |
| LLM Action Decision / LLM `ActionProposal` | Stage 3 | 未实现 |
| 普通 / LLM 双推进 UI | Stage 3 | 未实现 |
| **LangGraph** | Stage 3 | 未实现，已批准在 Stage 3 采用 |
| **LangChain** | — | 未实现，仅在出现可证明的集成需求时才局部采用 |
| **Celery / Redis / Outbox / Worker** | Stage 4 | 未实现 |
| **SSE / 异步 HTTP 202 / 重试编排 / 取消** | Stage 4 | 未实现 |
| NPC-to-NPC 对话、Relationship、Claim 传播 | Stage 5 | 未实现 |
| 完整 Knowledge Graph、Neo4j、RDF、GraphRAG | — | 明确非目标 |
| 独立向量数据库 | — | 明确非目标（使用 pgvector） |
| **Agent Lab**、Replay/Eval Dashboard | Stage 6 | 未实现 |
| **LangSmith** 集成 | Stage 6 | 未实现，作为可选脱敏观测出口 |
| **Aleria MCP Server** | Stage 6 | 未实现，计划为现有 Public API 的薄适配层 |
| Forest Embers 分支扩写、战斗、装备、背包、经济、大地图 | — | 明确非目标 |

**Roadmap 提到某能力 ≠ 当前 Stage 可以实现它。** 不得因为上位文档提及就提前引入。

---

## High Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Frontend  (Vue 3 + Pinia + Phaser)                       │
│   views → components → stores → api adapters             │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP (JSON envelope: success/data/message)
┌────────────────────────▼─────────────────────────────────┐
│ Backend API  (FastAPI routers + DI)                      │
│   9 routers · dependencies.py 提供 Session 与 Provider    │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│ Service Layer                                            │
│   用例编排 · 事务边界 · 公开 DTO 投影                      │
└──────┬──────────────────────────────────┬────────────────┘
       │                                  │
┌──────▼───────────────┐        ┌─────────▼────────────────┐
│ World / Agent Runtime│        │ Cognition (post-commit)  │
│  纯确定性模拟         │        │  感知 → 记忆 → 反思        │
│  Registry 校验行动    │        │  best-effort，可失败      │
└──────┬───────────────┘        └─────────┬────────────────┘
       │                                  │
┌──────▼──────────────────────────────────▼────────────────┐
│ Repository Layer  (SQLAlchemy 2)                         │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│ Persistence   SQLite（默认） / PostgreSQL 17 + pgvector   │
└──────────────────────────────────────────────────────────┘
```

**最重要的架构不变量**：权威世界写入**先提交**，认知投影**后执行**。认知失败永远不回滚权威事务，也不改变世界状态。

---

## Frontend Architecture

### 三层职责

**Views（`frontend/src/views/`）** — 页面级编排，持有 store，装配组件

| 文件 | 职责 |
| --- | --- |
| `BootView.vue` | 启动页 |
| `CharacterCreationView.vue` | 角色创建（姓名 + 职业） |
| `StoryView.vue` | 剧情过场，可跳过 |
| `TownView.vue` | 主游戏页：地图、详情、聊天、任务、推进、重置（532 行，Stage 3 前应拆分） |

**Components（`frontend/src/components/`）** — 纯展示 + 事件上抛，不直接调 API

| 文件 | 职责 |
| --- | --- |
| `TownGameHost.vue` | Phaser 实例宿主，桥接 Vue ↔ Phaser |
| `NpcDetailPanel.vue` | NPC 档案、当前状态、最近行动、**折叠的"相关记忆"区** |
| `NpcChatPanel.vue` | 与 NPC 的对话 |
| `QuestPanel.vue` | 任务目标与交互 |
| `TickPanel.vue` | 世界推进控件 |
| `PlayerLocationPanel.vue` / `LocationCard.vue` / `NpcCard.vue` | 地点与 NPC 卡片 |

**Stores（`frontend/src/stores/`）** — Pinia，持有状态与异步请求

| Store | 职责 | 关键设计 |
| --- | --- | --- |
| `world.ts` | 世界状态、推进、刷新 | `canMutate` 门控 |
| `npcDetail.ts` | NPC 详情 | `requestVersion` 竞态守卫 |
| `npcMemory.ts` | **记忆解释（独立于 detail）** | 独立状态，失败不污染详情 |
| `npcChat.ts` | 按 NPC 分会话的聊天 | `sessionsByNpc` |
| `playerQuest.ts` | 玩家与任务 | — |
| `playerProfile.ts` | 本地角色档案 | localStorage |

**关键约定**：`npcMemory` 与 `npcDetail` 是**两个独立 store**。记忆接口失败时详情、聊天、地图、世界推进必须继续可用。

### Phaser 的职责边界

`frontend/src/game/` 是 Phaser 与 Vue 的桥接层：

- `createTownGame.ts` — 创建 Phaser 实例
- `scenes/BootScene.ts`、`scenes/TownScene.ts` — 资源加载与小镇场景
- `TownGameBridge.ts` — Vue → Phaser 的命令通道（传送玩家、更新 NPC 投影）
- `npcProjection.ts` / `playerMapPosition.ts` / `movement.ts` — 纯函数，把后端语义地点映射为地图坐标

**Phaser 只负责渲染与输入**。它不持有业务状态，不调用 API。像素坐标**不持久化**——后端只保存任务需要的语义地点。

---

## Backend Architecture

### 分层与职责

```
api/          路由：解析请求、注入依赖、映射异常到 HTTP 状态码
  ↓
services/     用例：编排、事务边界、把领域对象投影为公开 DTO
  ↓
agents/       Agent runtime：契约、行动校验、冲突处理、感知、检索、反思
world/        纯确定性模拟：无 I/O、无数据库、可单元测试
  ↓
database/     repository：SQL、约束、事务内的读写
  ↓
models.py     ORM（20 张表）
```

### Router 清单（`backend/app/main.py` 注册 9 个）

| Router | 主要端点 |
| --- | --- |
| `health.py` | 健康检查 |
| `world.py` | `GET /api/world` |
| `world_clock.py` | `POST /api/world/tick`（同步 200） |
| `agent_runs.py` | `GET /api/agent-runs/{run_id}` |
| `npcs.py` | `GET /api/npcs/{npc_id}`、`GET /api/npcs/{npc_id}/memory-explanations` |
| `npc_chat.py` | `POST /api/npcs/{npc_id}/chat` |
| `player.py` | 玩家状态与移动 |
| `quests.py` | 任务交互 |
| `demo.py` | `POST /api/demo/reset` |

### 依赖注入（`api/dependencies.py`）

这里有一个**容易踩坑的关键设计**：

- `get_session` — 权威业务 Session
- `get_cognition_session` — **独立**的认知 Session，请求级
- `get_cognition_service` — 在认知 Session 上构建 `CognitionProjectionService`，内含 enrichment 与 reflection
- `get_chat_provider` / `get_embedding_provider` / `get_reflection_provider` — 三个互相独立的 Provider

**为什么要两个 Session**：认知投影要求一个**没有打开事务**的 Session。`CognitionProjectionService._require_fresh_session()` 和 `MemoryRetriever.retrieve()` 都会在 `session.in_transaction()` 为真时直接失败。复用权威 Session 会让认知写入隐式加入权威事务，破坏"认知失败不影响权威"的不变量。

### 公开响应契约（`schemas/common.py`）

```python
ApiResponse[T]:   {"success": true,  "data": T,    "message": "ok"}
ErrorResponse:    {"success": false, "data": null, "message": "..."}
```

公开 DTO **必须由专用投影构造**，不得直接序列化 ORM 行。不得返回原始聊天、秘密内容、Embedding、内部评分、Prompt 或 Provider 错误。

---

## World Engine

`backend/app/world/` 是**纯确定性模拟**：无 I/O、无数据库、无随机数，可独立单元测试。

| 文件 | 职责 |
| --- | --- |
| `clock.py` | 时间推进与时段判定（morning / day / evening / night） |
| `role_routines.py` | 按角色与时段的确定性日程 |
| `decision.py` | 由快照决定单个 NPC 的行动提案 |
| `action_rules.py` | 行动合法性规则 |
| `tick_engine.py` | `run_tick(world) -> TickResult` |
| `types.py` | 快照与结果的不可变类型 |

### 一次世界推进的完整流程

```
POST /api/world/tick  {expected_world_version}
  │
  ├─ WorldTickService.advance()
  │    └─ repository.get_snapshot()
  │    └─ 版本校验：snapshot.world_version != expected → 409 冲突
  │
  ├─ run_deterministic_advance(snapshot, registry)        ← agents/orchestrator.py
  │    ├─ 按 (sort_order, id) 稳定排序 NPC
  │    ├─ 对每个 NPC 施加被动需求漂移
  │    ├─ advance_clock() 推进 day/time，clock_tick + 1
  │    ├─ 构造一份**不可变决策快照**
  │    ├─ decide_action(actor, decision_world)  每个 NPC 独立提案
  │    │     ※ 所有 NPC 看到同一份快照，看不到彼此在本次推进中的效果
  │    ├─ resolve_proposals()                  ← Registry 校验 + 确定性冲突处理
  │    │     ※ 结果与提案输入顺序无关
  │    └─ 生成 trace 条目
  │
  ├─ repository.persist_run()                             ← 单个事务原子提交
  │    world_state + npc_states + agent_runs + action_proposals
  │    + actions + events + agent_trace_entries
  │    ※ 版本过期、非法动作或持久化失败 → 不产生半次世界变更
  │
  ├─ 构造 WorldTickData 公开 DTO
  │
  └─ post-commit: cognition.catch_up_world(world_id)      ← best-effort
       失败只记 warning，不影响已返回的成功结果
```

### 三套计数器的职责

| 计数器 | 含义 | 由谁递增 |
| --- | --- | --- |
| `world_version` | 权威变更的 compare-and-swap 令牌 | 推进、实际移动、任务转换各递增一次 |
| `clock_tick` | 游戏内时间刻度 | **仅**推进递增 |
| `event_sequence` | 每个 World 内无间隔的事件序号 | 事件分配，与推进同事务 |

聊天**不递增任何一个**。认知写入**不递增任何一个**。

---

## Agent Runtime / Memory

### 模块清单（`backend/app/agents/`）

| 文件 | 职责 |
| --- | --- |
| `contracts.py` | 不可变的 proposal / validation / event / trace 契约 |
| `action_registry.py` | 合法行动、目标校验、效果、事件元数据。初始集合：`move / rest / work / eat / talk / wait` |
| `conflict_resolver.py` | 稳定的提案排序与重复/非法提案处理 |
| `orchestrator.py` | 一份不可变决策快照 → 提案 → 解析结果 |
| `cognition_contracts.py` | 冻结的认知内部契约与固定分类值 |
| `perception.py` | 感知策略注册表、权限矩阵、注意力预算、`ObservationDraft` |
| `memory_retrieval.py` | 权限优先的 Hybrid / lexical 排序、预算、稳定 tie-break |
| `reflection.py` | 触发、证据指纹、Draft 校验、Belief 追加、有限重试 |

### 固定分类值（不允许 Provider 扩展枚举）

```python
SourceKind:      event | conversation_turn | authored_knowledge
MemoryType:      episodic | conversation | reflection | knowledge
PerceptionMode:  participant | witnessed | professional_channel | direct_dialogue
RetrievalScope:  player_dialogue | internal_reflection | public_explanation
```

### Memory 数据流

```
权威来源提交（Event / Conversation Turn / Authored Knowledge Seed）
  │
  ▼  post-commit，逐 NPC 有界 catch-up
CognitionProjectionService.catch_up_owner(world_id, npc_id)
  │
  ├─ ① CORE（事务内，必须成功）
  │     get_or_create_state()          读取该 NPC 的 checkpoint
  │     load_source_batch()            自 checkpoint 起的有界批次
  │     PerceptionPolicyRegistry
  │       .project_batch()             按位置/参与者/职业渠道/秘密权限派生
  │                                    → ObservationDraft（含注意力预算裁剪）
  │     persist_core_projection()      写入 observations + memories
  │     session.commit()               checkpoint 前进
  │
  ├─ ② EMBEDDING ENRICHMENT（best-effort，可失败）
  │     EmbeddingEnrichmentService.enrich_pending()
  │     失败只记 warning
  │
  └─ ③ REFLECTION（best-effort，可失败）
        ReflectionEngine.enrich_if_due()
        触发条件：累计 importance ≥ 阈值 且 新记忆数 ≥ 下限；critical 绕过二者
        失败只记 warning

三个阶段共享同一个 deadline（cognition_post_commit_budget_seconds，默认 5.0s）
```

**权限继承**：同一个 Event 对不同 NPC 产生**不同的** Observation 集合。对话 Observation 固定为 `secrecy=private` / `disclosure_scope=player_dialogue`。

### Retrieval（`memory_retrieval.py`）

```
RetrievalRequest(world_id, owner_npc_id, world_version, clock_tick,
                 query_text, scope, allowed_memory_types,
                 limit, char_budget, excluded_turn_ids)
  │
  ├─ ① 权限硬过滤（SQL 层，先于任何相似度计算）
  │     SCOPE_RULES[scope] → secrecy / disclosure_scope / lifecycle_state
  │     + owner / world / 非未来时间 / memory_type / 活跃会话去重
  │
  ├─ ② 语义分量（可降级）
  │     provider.embed(query) → 兼容性检查（provider/model/version/dim/input_hash）
  │     PostgreSQL：pgvector `<=>` 距离，包裹在 savepoint 中
  │     SQLite / 降级：内存余弦
  │     任何失败 → mode = "lexical_fallback"
  │
  ├─ ③ 加权排序
  │     hybrid:   0.40·semantic + 0.20·lexical + 0.20·recency + 0.15·imp + 0.05·conf
  │     fallback: 0.45·lexical + 0.25·recency + 0.20·imp + 0.10·conf
  │     disputed 乘 0.85；tie-break 用 memory_id 保证稳定
  │
  └─ ④ 预算截断（limit + char_budget）
```

三个 scope 的权限边界：

| Scope | secrecy | disclosure_scope | 用途 |
| --- | --- | --- | --- |
| `player_dialogue` | public, private | public, player_dialogue | NPC Chat 回复前召回 |
| `internal_reflection` | public, private, secret | public, player_dialogue, internal_only | Reflection 证据候选 |
| `public_explanation` | **public** | **public** | 匿名只读解释接口 |

`public_explanation` 额外保证：**不写 access telemetry**、读后 rollback、`memory_text()` 返回 `safe_summary` 而非对话原文。

### Reflection 与 Belief

- Provider 输出必须**引用真实的证据 Memory ID**，不能创造世界事实
- secrecy / disclosure 由**全部 Provider 可见候选集**的最严格值推导——不能通过省略秘密引用来"洗白"
- Belief **追加式**：新 Belief 一律 active，旧行只标记 `superseded` / `disputed`，支持/反对证据全部保留
- Provider 调用**不持有数据库事务**；保存事务会重新锁定并复核 owner / world / 时间 / lifecycle / 白名单

---

## Persistence Model

### 数据库存储职责（20 张表）

| 分组 | 表 |
| --- | --- |
| 世界与内容 | `world_state`、`locations`、`npc_profiles`、`npc_states` |
| 玩家与任务 | `player_states`、`quest_progress`、`quest_events` |
| Runtime Graph | `agent_runs`、`action_proposals`、`actions`、`events`、`agent_trace_entries` |
| 对话 | `conversations`、`conversation_messages` |
| **认知（Stage 2）** | `agent_cognition_states`、`observations`、`memories`、`memory_evidence`、`beliefs`、`belief_evidence` |

### Migration

链条：`0001_legacy_baseline → 0002_world_versioning → 0003_agent_runtime_foundation → 0004_stage2_cognition`

- ORM（`models.py`）与迁移必须**同构**：相同的 FK、CHECK、UNIQUE 与索引名
- SQLite 与 PostgreSQL 的差异在迁移中显式处理（JSON vs Vector 列）
- 结构变更**只能**通过新 revision；不得改写已有 revision 或伪造 `alembic_version`

### 事务边界

| 场景 | 边界 |
| --- | --- |
| 世界推进 | 单事务提交 world + npc_states + 完整 Run Graph。失败不留半个图 |
| 聊天 Turn | 单事务原子保存共享 `turn_id` 的双消息（user + assistant） |
| 认知 core | 独立事务，提交后 checkpoint 前进 |
| 认知 enrichment | 各自独立，失败不回滚 core |
| 公开解释读取 | 只读，结束时 rollback，不写 telemetry |

**关键约束**（本项目在这里连续踩过三次坑）：`CognitionProjectionService.catch_up_owner()` 与 `MemoryRetriever.retrieve()` 都要求调用时 Session **没有打开事务**，并且绝不会去接管或回滚一个它们没有开启的事务。

### Seed 与 Reset

- Seed 内容在**根目录 `data/`**（被跟踪）：`world.json`、`locations.json`、`npcs.json`、`agent_knowledge.json`
- `agent_knowledge.json` 是**版本化**的 authored knowledge（当前 `stage2-v1`），带 owner、secrecy、disclosure、发生时间基准
- `POST /api/demo/reset` 是**显式破坏性**操作：按 World 清理认知数据并重建 authored knowledge；其他 World 不受影响
- 普通启动、迁移与 `ensure_demo_world` **不重置**认知历史

---

## Development Flow

### 一个新功能从 API 到测试的典型路径

以 Stage 2 Task 5 新增的解释接口为例（真实案例）：

```
① Spec 定义公开契约
   docs/superpowers/specs/...-design-cn.md §14.2
   → 端点路径、响应 envelope、隐私边界、错误码

② Plan 定义逐文件实施步骤
   docs/superpowers/plans/...-plan-cn.md Task 5 Step 1-4
   → 文件清单、DTO 字段的确切定义、RED 命令

③ RED：先写测试
   tests/backend/test_memory_explanation_service.py   ← 服务层行为
   tests/backend/test_npc_api.py                      ← HTTP 契约与隐私
   运行，确认因"模块不存在 / 路由未注册"而失败

④ GREEN：自内向外实现
   backend/app/schemas/npc.py           ← Pydantic 公开 DTO
   backend/app/services/memory_explanation.py
                                        ← 固定情境查询 + 安全投影
                                          消费既有 MemoryRetriever，
                                          不重新实现权限过滤
   backend/app/api/npcs.py              ← 路由 + DI + 异常到状态码

⑤ 前端 RED → GREEN
   tests/frontend/npcMemory.spec.ts     ← store 竞态、错误、清理
   frontend/src/types/npc.ts            ← DTO 镜像
   frontend/src/api/npc.ts              ← 适配器
   frontend/src/stores/npcMemory.ts     ← 独立 store
   frontend/src/components/NpcDetailPanel.vue  ← 折叠 UI
   frontend/src/views/TownView.vue      ← 接线

⑥ 验证矩阵
   pytest tests/backend  →  npm test  →  npm run type-check

⑦ 独立 review（spec 合规 + 代码质量）→ 修复 → scoped re-review

⑧ 人类 review → 人类手动 commit
```

### 分层原则

- **向内依赖**：`api → services → agents/world → database`。反向依赖是设计错误。
- **`world/` 保持纯净**：无 I/O、无数据库、无随机。它的可测试性是整个确定性保证的基础。
- **repository 不做业务判断**：它管 SQL 与约束；编排与事务边界归 service。
- **不要重新实现已有边界**：权限过滤属于 `SCOPE_RULES` 与 SQL 硬过滤，服务层**不得**再加一层应用态过滤。

### 对新 agent 最容易犯的错误的提醒

1. 在权威事务里做认知写入 → 破坏失败隔离
2. 复用带事务的 Session 调用 `retrieve()` / `catch_up_owner()` → 直接抛错
3. 在服务层重新过滤权限 → 与 SQL 硬过滤重复且可能不一致
4. 把 Roadmap 中的 Proposed 能力当作已存在
5. 写出在空集合上恒真的负向测试
