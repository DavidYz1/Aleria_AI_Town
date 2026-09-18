# AGENTS.md

面向 AI coding agent（Codex、Claude Code 等）的项目级协作规范。

本文件描述**当前仓库的真实约束**。修改本文件前请先验证仓库状态，不要根据记忆或惯例改写。

---

## Project Overview

### 这是什么项目

**Aleria AI Town（曦谷）** 是一个 AI-native agent RPG：以**可信、可解释、可评估的 Agent 行为**为主线，以生产级 AI 全栈工程为技术内核，以可游玩的 RPG 世界作为用户体验与演示外壳。

玩家在一张 2D 小镇地图上移动，与三位 NPC（Ryan、Shir、Grey）对话，推进世界时间和一条主线任务。NPC 不具有全知视角：它们按位置、身份和权限感知世界，形成带来源的长期记忆，并在后续对话中引用这些记忆。

### 当前目标

项目按 Stage 推进，每个 Stage 交付一个**垂直切片**（技术内核 + 玩家可感知效果 + 可复现演示）。

- **已完成**：Foundation（确定性 Agent Runtime）、Stage 2（Perception, Memory and Reflection）、
  Stage 3m（Agent Loop MVP：多步规划、跨 tick 计划复用、分层兜底归因）
- **未开始**：生产级 Stage 3 与 Stage 4–6（见 `docs/superpowers/roadmaps/2026-09-09-ai-native-agent-rpg-stages-2-to-6-cn.md`）

当前进度详见 `CURRENT_STATE.md`。

### 技术栈

| 层 | 技术 | 版本约束来源 |
| --- | --- | --- |
| 前端框架 | Vue 3 + TypeScript | `frontend/package.json`：vue ^3.5.13、typescript ~5.7.2 |
| 前端状态 | Pinia ^3.0.1 | 同上 |
| 游戏渲染 | Phaser 3.90.0（锁定版本） | 同上 |
| 前端构建 | Vite ^6.2.0 | 同上 |
| 前端测试 | Vitest ^3.0.9 + @vue/test-utils + jsdom | 同上 |
| HTTP 客户端 | axios ^1.8.4 | 同上 |
| 后端框架 | FastAPI >=0.115,<1.0 | `backend/requirements.txt` |
| 数据校验 | Pydantic >=2.10,<3.0 + pydantic-settings | 同上 |
| ORM | SQLAlchemy >=2.0,<3.0 | 同上 |
| 迁移 | Alembic >=1.19,<2.0 | 同上 |
| 数据库 | SQLite（本地/测试默认）、PostgreSQL 17 + pgvector 0.8.6（Docker） | `compose.yaml`、`backend/app/database/connection.py` |
| PG 驱动 | psycopg[binary] >=3.3,<4.0 | `backend/requirements.txt` |
| 向量 | pgvector >=0.5,<1.0 | 同上 |
| 后端测试 | pytest >=8.3,<9.0 + httpx | 同上 |
| Python | 3.11+ | 语法特性（`StrEnum`、`X | None`） |

**没有引入**：LangChain、LangGraph、Celery、Redis、Neo4j、任何独立向量数据库。不要在未经 Stage Spec 论证的情况下添加它们。

---

## Repository Structure

```
Aleria_AI_Town/
├── frontend/          Vue 3 + Phaser 前端
│   └── src/
│       ├── api/       后端接口适配器（axios + envelope 解包 + 类型化错误）
│       ├── components/ 展示组件（NpcDetailPanel、NpcChatPanel、QuestPanel 等）
│       ├── views/     页面级视图（BootView、CharacterCreationView、StoryView、TownView）
│       ├── stores/    Pinia store（world、npcDetail、npcChat、npcMemory、playerQuest、playerProfile）
│       ├── game/      Phaser 桥接层（TownGameBridge、scenes/、movement、npcProjection）
│       ├── types/     后端 DTO 的 TypeScript 镜像
│       └── player/    本地玩家档案（localStorage）
│
├── backend/           FastAPI 后端
│   ├── app/
│   │   ├── api/       路由层（9 个 router + dependencies.py 的 DI）
│   │   ├── services/  用例服务层（编排、事务边界、公开 DTO 投影）
│   │   ├── database/  ORM models + repository + connection
│   │   ├── agents/    Agent runtime（contracts、action_registry、orchestrator、
│   │   │              conflict_resolver、perception、memory_retrieval、reflection、
│   │   │              planner、planning_contracts）
│   │   ├── world/     纯确定性世界模拟（clock、tick_engine、role_routines、action_rules）
│   │   ├── llm/       Provider 抽象（chat / embedding / reflection / planning，各有 fake 与 OpenAI-compatible）
│   │   ├── quests/    任务策略（missing_child）
│   │   ├── schemas/   Pydantic 公开契约
│   │   └── core/      Settings
│   ├── migrations/    Alembic（versions/ 下 0001–0006）
│   └── data/          本地 SQLite 文件（**被 .gitignore，仅 .gitkeep 被跟踪**）
│
├── docs/              权威设计文档
│   ├── 00–15_*.md     项目定位、需求、世界观、架构、API 契约、数据库、Prompt、路线图等
│   ├── ARCHITECTURE.md 架构地图（Implemented / Proposed 分离）
│   └── superpowers/
│       ├── roadmaps/  跨 Stage 路线图
│       ├── specs/     每个 Stage/Phase 的已批准中文设计
│       └── plans/     每个 Stage/Phase 的逐文件实施计划
│
├── tests/
│   ├── backend/       pytest（59 个 test_*.py）
│   └── frontend/      Vitest（30 个文件）
│
├── scripts/           运维与开发脚本
│                      seed_world.py（播种）、upgrade_schema.py（迁移）、
│                      ensure_demo_world.py、start_dev.py + start-dev.{sh,ps1,cmd}、
│                      deploy.py + deploy.{sh,ps1,cmd}
│
├── data/              版本化 Seed 内容（**被跟踪**）
│                      world.json、locations.json、npcs.json、agent_knowledge.json
│
├── prompts/           Prompt 版本目录 v1 / v2 / v3
├── deploy/            nginx.conf
└── .superpowers/sdd/  SDD 执行记录（ledger、brief、report、review diff），git-ignored
```

**易混淆点**：根目录 `data/` 是**被跟踪的 Seed 内容**；`backend/data/` 是**被忽略的本地数据库文件**。两者职责完全不同。

---

## Development Rules

### 开发前必读

按以下顺序阅读，**不要跳过**：

1. **`CURRENT_STATE.md`** — 当前 HEAD、已完成工作、进行中的 Task、已知风险。这是你接手时的第一份文件。
2. **`docs/ARCHITECTURE.md`** — 架构地图，明确区分已实现与未来规划。
3. **当前 Stage 的 Spec** — `docs/superpowers/specs/` 下对应文件。**Spec 是约束的最终权威。**
4. **当前 Stage 的 Plan** — `docs/superpowers/plans/` 下对应文件，逐文件、逐 Step 的实施计划。
5. **SDD ledger** — `.superpowers/sdd/<plan-basename>/progress.md`，记录每个 Task 的完成状态、review 结论、已做的裁定（Ruling）和遗留的 deferred minor。
6. **`docs/AI_REVIEW_POLICY.md`** — review 流程规范：等级判定、baseline 机制、复核包输入规则、增量 re-review。**交付前必须据此定级。**

### 文档优先级

冲突时按此优先级裁决：

```
Spec  >  Plan  >  Roadmap  >  docs/0X_*.md  >  代码注释
```

- **Spec 是 binding authority**，Plan 是对 Spec 的论证。两者冲突以 Spec 为准。
- **Roadmap 不授权实现**。路线图提到某能力，不等于当前 Stage 可以实现它。
- **示例块不是规范**。Spec 和 Plan 中的 JSON / 代码示例若与正文规范条款冲突，以正文为准（该情形在 Stage 2 Task 5 已实际发生并被裁定）。
- 冲突无法由文档解决时，做出裁定、在 ledger 记录 `Ruling: <决定> — <理由> — <若错的代价>`，然后继续；不要停下来等待。

### 修改架构前必须确认边界

以下改动**必须**先确认它在当前 Stage Spec 的授权范围内：

- 新增或修改 Public API 的请求、响应或状态码
- 新增数据库表、列或约束
- 改变事务边界或 Session 归属
- 改变 `world_version` / `clock_tick` / `event_sequence` 的语义
- 引入新的第三方框架或基础设施依赖
- 放宽任何权限 scope 或披露规则

**跨 Stage 不变量**（任何 Stage 都不得违反）：

1. RPG 世界权威属于 Backend。LLM、工作流引擎、前端和队列都不能直接写世界状态。
2. 事实、感知、记忆、信念分层。NPC 听到的说法不是世界事实；模型推断也不是事实。
3. 统一行动入口。所有策略最终生成同一套类型化 Proposal，经同一套校验、冲突处理和提交。
4. 普通模式始终可用。模型、Embedding 或队列失败时，基础 RPG 仍能继续游玩。
5. 可解释 ≠ 暴露思维链。只展示事实引用、规则结果、记忆来源和安全错误。
6. Schema 增量演进。使用 Alembic；不得删库、重建或伪造版本来让测试通过。

---

## Engineering Practices

### TDD 是强制流程，不是建议

本项目所有 Stage 2 代码均以严格 TDD 产出，ledger 中留有每一轮 RED/GREEN 的命令与真实输出。继续保持。

**RED → GREEN → REFACTOR**

1. **RED** — 先写聚焦测试，运行它，**确认它因为目标行为缺失而失败**。记录确切命令与失败输出。
   - 因为拼写错误、import 错误或 fixture 问题而失败**不算 RED**，要先修掉再重跑。
2. **GREEN** — 写能让该测试通过的最小实现，重跑确认通过。
3. **REFACTOR** — 在测试保护下整理命名与结构，不改变行为。

### 测试可信度要求

- **禁止空洞断言**。对集合的 `all(...)` / `every(...)` / 循环断言必须配一个非空前提断言，否则空集合会让它恒真。本项目已因此产生过一条 Important finding：一条隐私测试跑在空列表上，看起来全绿却什么都没证明。
- 负向测试（证明"不泄露"、"不发生"）必须证明该条件在**非空、有区分度**的真实数据上成立。
- 无法直接测试的改动（如纯注释）应通过变异验证：临时反转条件确认测试会失败，再还原。
- 测试验证**真实行为**，不验证 mock 的行为。

### 小范围修改

- 一次只做一件事。单个变更应当能被一次 review 读完。
- 严格遵守 Plan 给出的文件清单。需要超出清单时，先做裁定并记录理由。
- 不要顺手重构任务范围之外的代码。发现问题记录下来，不要就地展开。
- 文件职责单一。新文件超出 Plan 预期规模时，报告而不是自行拆分。

### 验证基线

任何改动完成前必须跑（Windows）：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider
npm --prefix frontend test
npm --prefix frontend run type-check
```

跑 pytest 时**必须显式指定 `--basetemp` 到有写权限的目录，且不要在沙箱内运行** —— 沙箱会创建 Windows `0700` 权限的临时目录导致无效结果（本项目已实际发生过两次无效运行）。

**不得引入新的 skip 或新的 warning。** 当前基线的 5 个 skip 全部是 `TEST_POSTGRES_URL` 未设置的 opt-in PostgreSQL 测试，1 个 warning 是既有的 Starlette/httpx 弃用提示。

这条规则针对的是**静默停用测试**。新增 opt-in PostgreSQL 用例会让 skip 数上升，属于允许的例外，但必须同步本文、`docs/14` 与能力基线中的数字，并在交付时明确说明多出来的那一项是什么。

**通过数取决于 shell**：`test_start_dev.py` 的 shell launcher 探针在 PATH 中没有 POSIX `sh` 时会跳过，因此 Windows PowerShell 下会比 Git Bash 与 Linux CI 少一项通过、多一项 skip。报告数字时必须带上环境，不要把 PowerShell 下少的那一项当成漏跑。

当前 HEAD 的具体通过数见 `docs/eval/2026-09-17-capability-baseline.md`，**不要在本文重复维护** —— 每加一个测试都要同步多处，迟早漂移。

### Review Baseline

上一节的“验证基线”指的是**测试基线**（多少条通过、多少 skip）。本节的 **Review Baseline** 是另一件事：一个可复现的**仓库状态锚点**，用来让下一次 review 只看增量。

两者不相关，不要混用。

- **完整规范见 `docs/AI_REVIEW_POLICY.md`**。本节只记三条硬约束。
- **交付前必须定级**（R0–R3）并建立或更新 baseline，位置 `.superpowers/sdd/baselines/`（跨 plan 共享，已被 git 忽略）。
- **基线与复核包的生成只使用只读 git 命令**：`status` / `diff` / `hash-object`（不加 `-w`）/ `rev-parse` / `log` / `check-ignore`。不写 index、不写 HEAD、不写 objects、不碰工作树。**上一节的 Git Rules 不因为引入 baseline 而放宽。**

`scripts/review_baseline.py` **尚不存在**（属 `AI_REVIEW_POLICY.md` 第 9 章 Proposed）。在它就绪之前按该文§6.6 的手工流程执行，不要 import 或调用它。

---

## Database Safety Rules

### 严格禁止

- **禁止删除 `backend/data/aleria.db`**。该文件被 `.gitignore` 忽略（`backend/data/*.db`），**git 无法恢复它**。删除即永久丢失本地演示数据。
- **禁止重置或清空用户数据**作为"让测试通过"的手段。
- **禁止直接用 SQL 或外部工具修改数据库文件**的结构。
- **禁止破坏 migration**：不得删除、改写或重编号已存在的 revision（当前链为 `0001 → 0002 → 0003 → 0004 → 0005 → 0006`），不得伪造 `alembic_version` 的值。
- **禁止 `docker compose down -v`**：`-v` 会删除 PostgreSQL 数据卷 `aleria_postgres_data`。普通 `down` 保留数据。
- **禁止让测试写入 `backend/data/aleria.db`**。所有迁移、Reset 与失败恢复测试必须使用临时数据库（`tmp_path` fixture）。

### 所有结构变更必须通过 migration

1. 在 `backend/migrations/versions/` 新建 revision，`down_revision` 指向当前 head。
2. 同步更新 `backend/app/database/models.py`，保持 ORM 与迁移**同构**（同样的 FK、CHECK、UNIQUE、索引名）。
3. 在 `tests/backend/test_schema_migrations.py` 补充覆盖：空库升级到新 head、已有库原地升级并保留数据、重复运行幂等。
4. SQLite 与 PostgreSQL 的差异（JSON vs JSONB、Vector 列）必须在迁移中显式处理并各自测试。

### 备份约定

`backend/data/` 下已存在两个历史备份（`aleria.legacy-*.db`、`aleria.before-foundation-closeout-*.db`）。做高风险迁移前按同样的命名方式先备份：`aleria.before-<变更名>-<时间戳>.db`。

---

## Git Rules

### 本项目的提交工作流：agent 不提交

**这是本仓库最重要的 Git 规则。**

AI agent **不得执行**：`git add`、`git commit`、`git reset`、`git checkout`、`git switch`、`git clean`、`git stash`、任何形式的 `git push`。

Agent 的产出保持在**工作树中，未暂存、未提交**。由人类 review 后手动提交。Agent 可以给出建议的提交信息，但不能自己执行提交。

这条规则存在的原因：Stage 2 的每个 Task 都由人类逐一 review 后手动提交，提交历史才保持了一个 Task 一个 commit 的可审查粒度。

### 其余规则

- **修改前先 `git status`**，确认工作树状态与你以为的一致。接手一个会话时尤其如此——上一个 agent 可能留下了未提交的工作。
- **保持 diff 可审查**：一次改动聚焦一个主题；不要在功能改动里混入无关的格式化。
- **提交前跑测试**（由人类执行提交，但 agent 应在交付前跑完验证矩阵并报告真实数字）。
- **不要用 `git checkout --` 或 `git restore` 丢弃他人的未提交改动**。发现意外改动应报告，不要自行清理。
- 本仓库有 `.gitattributes` 配置行尾，`git diff` 出现 `LF will be replaced by CRLF` 警告属正常。

---

## AI Agent Rules

### 不要重复设计已有架构

接手前先确认某能力**是否已经存在**。本项目已实现的内容远多于表面看起来的：权限优先的混合检索、证据约束的反思、逐 NPC 的投影 checkpoint、三套独立计数器、Provider 抽象与降级——这些都已落地并有测试。

在写任何新设计之前：

1. 读 `docs/ARCHITECTURE.md` 的 **Implemented** 段。
2. 在 `backend/app/` 下搜索相关关键词。
3. 读对应 Stage 的 Spec，确认该能力的边界已经被定义过。

### 区分 implemented 与 proposed

`docs/ARCHITECTURE.md` 严格分为 **Implemented** 与 **Proposed / Future** 两段。

- **Implemented** 段的内容有代码和测试支撑，可以直接依赖。
- **Proposed / Future** 段的内容**尚不存在**。不要 import 它、不要假设它的接口、不要写"等 X 完成后"的占位代码。

Roadmap 与 Spec 中出现的能力名称（LangGraph、Outbox、Agent Lab 等）属于后者，除非 `ARCHITECTURE.md` 的 Implemented 段明确列出。

### 交接约定

- 完成工作后更新 `CURRENT_STATE.md`：HEAD、完成范围、review 状态、遗留风险、下一步建议。
- 做出的每一个裁定都写进 ledger：`Ruling: <决定> — <理由> — <若错的代价>`。沉默的决定等于没有决定。
- 发现但未修的问题记为 deferred minor 并写入 ledger，不要静默丢弃。
- 报告真实结果：测试失败就说失败并附输出；跳过了某步就说跳过。不要把"未执行"写成"通过"。

### 边界

以下情况**停下来问人**，不要自行推进：

- 不可逆或破坏性操作（删除数据、重置数据库、强制推送）
- 安全敏感的改动（认证、密钥、权限放宽）
- 影响工作区之外的副作用（合并、推送共享分支、发布）
- 计划本身已崩坏，任何前进路径都只能靠猜
