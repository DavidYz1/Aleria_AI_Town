# CURRENT_STATE.md

项目当前状态快照，供下一个接手的人或 AI agent 使用。

**接手时请先验证本文件是否仍然准确**（对照 `git log -1` 与 `git status`）。状态变化后请更新本文件。

---

## Current Date

**2026-09-13**

---

## Current Git State

| 项 | 值 |
| --- | --- |
| 分支 | `main` |
| HEAD | `85ce338dd6fbea4222c8af19078dfba55333bddb`（短 `85ce338`） |
| HEAD 提交信息 | `feat: complete stage 2 perception memory and reflection` |
| 提交者 / 时间 | David Yang · 2026-09-13 12:44:22 +0800 |
| 远程 | `origin` → `github.com/DavidYz1/Aleria_AI_Town` |
| 与远程的关系 | **本地领先 15 个提交，尚未 push** |
| tracked 工作树 | **clean**（`git diff HEAD` 为空，index 也为空） |
| 未跟踪文件 | 4 份协作文档，**均未入 git**：`AGENTS.md`、`CURRENT_STATE.md`、`docs/ARCHITECTURE.md`、`docs/AI_REVIEW_POLICY.md` |

### 提交历史（近期）

```
85ce338  feat: complete stage 2 perception memory and reflection  ← Stage 2 关闭
2253768  feat: add safe memory explanation api and ui        ← Stage 2 Task 5 段 1
d836f3c  feat: add evidence-bound reflection and beliefs      ← Stage 2 Task 4
91c8a3d  feat: add permission-aware memory retrieval to npc chat  ← Stage 2 Task 3
efc347f  feat: project authoritative sources into npc memories ← Stage 2 Task 2
8ef1a24  feat: add stage 2 cognition schema and source metadata ← Stage 2 Task 1
ba935ae  docs: add AI-native agent RPG stages 2-6 roadmap
9ac8d1f  fix: close historical sqlite migration and git bash startup gaps
e78714f  feat: add PostgreSQL persistence and Docker Compose database setup
951a440  feat(frontend): migrate RPG runtime contract to world versions
a00b234  feat(runtime): persist agent runs atomically with trace support
b1c9e10  feat: add deterministic agent orchestration runtime
9faa58f  feat: add typed action registry foundation
514d0d7  refactor: add schema migrations and separate world_version from clock_tick
```

### 测试基线（在 `85ce338` 上的本机实测，2026-09-13）

> ⚠️ **后端全量不绿。** 下表是在当前 HEAD 上实跑的真实结果，不是引用 Stage 2 执行期间的历史数字。

| 套件 | 结果 |
| --- | --- |
| Backend 全量 | **`7 failed, 713 passed, 5 skipped, 3 warnings in 265.45s`** |
| Backend 四个失败文件（空载隔离重跑） | **`7 failed, 53 passed, 3 warnings in 58.76s`** — 同一组失败，**确定性复现，非 flaky** |
| Frontend | `209 passed, 30 files` ✅ |
| type-check | exit 0 ✅ |
| build | 本会话未跑 |
| PostgreSQL opt-in | 本会话未跑（Docker 未启动） |

5 个 skip 与历史基线一致（四个 `TEST_POSTGRES_URL` opt-in + PowerShell `PATH` 无 POSIX `sh`），**无新增 skip**。warning 从 1 升至 3，新增的 2 个是 `PytestUnhandledThreadExceptionWarning`，由下述失败的线程测试产生；修复后应复测确认它们随之消失。

Backend 从 709 增至 710，来自 Step 5 新增的 Stage 2 acceptance 用例（九步闭环写在单个测试内）。Step 6 对 `test_postgres_runtime.py` 的扩展位于 opt-in 用例中，未设置 URL 时仍计为 skip。

Step 8 完整验证矩阵已执行；外部 live Embedding/Reflection Provider Smoke 未配置、未执行，也未宣称通过。

---

## Completed Work

### 命名说明

项目早期使用 **Phase** 命名（Phase 0、1a–1e、2），`ba935ae` 引入路线图后改用 **Stage** 命名（Stage 2–6）。Stage 2 之前的全部工作统称 **Foundation**。文档中两套术语并存属正常。

### Foundation（已完成并提交）

| 阶段 | 交付 |
| --- | --- |
| Phase 0 | 工程初始化 |
| Phase 1a | 确定性 world tick |
| Phase 1b | NPC 详情与可解释性 |
| Phase 1c | NPC Chat Provider 抽象 |
| Phase 1d | 世界内容与任务基础 |
| Phase 1e | 内容圣经、提交与叙事 |
| Phase 2 | RPG 表现层（Phaser 地图、四场景流程） |
| Agent Runtime Foundation | 类型化 Action Registry、确定性编排、原子 Run Graph 持久化、world_version 分离 |
| Foundation Closeout | PostgreSQL 持久化 + Docker Compose、历史 SQLite 迁移与启动脚本修复 |

Foundation 提供的稳定边界：三套独立计数器分离、所有 NPC 消费同一不可变快照、Registry 校验一切行动、accepted proposal 经确定性冲突处理后原子写入、`POST /api/world/tick` 保持同步 200。

### Stage 2：Perception, Memory and Reflection

| Task | 交付 | 提交 | 状态 |
| --- | --- | --- | --- |
| Task 1 | 认知 Schema（六表 + `0004` 迁移）、来源元数据、Conversation Turn 标识、版本化 authored knowledge | `8ef1a24` | ✅ 已完成并提交 |
| Task 2 | 确定性感知策略、注意力预算、幂等核心投影、逐 NPC checkpoint、失败补偿、Demo Reset 认知清理 | `efc347f` | ✅ 已完成并提交 |
| Task 3 | Embedding Provider（fake / OpenAI-compatible）、权限优先 Hybrid Retrieval、pgvector 查询路径、lexical 降级、跨会话 Chat 记忆 | `91c8a3d` | ✅ 已完成并提交 |
| Task 4 | 证据约束 Reflection、追加式 Belief、权限下限推导、原子 claim 与有限重试、显式 cognition DI | `d836f3c` | ✅ 已完成并提交 |
| Task 5 | 安全解释 UI、双数据库验收与 Stage 2 文档 | `2253768`（段 1）+ 未提交段 2 | ✅ **Step 1–10 已完成，等待人类 review / 手动提交** |

每个 Task 的完整执行记录、review 结论、裁定（Ruling）与遗留项见 SDD ledger：
`.superpowers/sdd/2026-09-09-stage-2-perception-memory-reflection-plan-cn/progress.md`

---

## Current Task

### Stage 2 Task 5：交付安全解释 UI、双数据库验收与 Stage 2 文档

Plan 位置：`docs/superpowers/plans/2026-09-09-stage-2-perception-memory-reflection-plan-cn.md` 第 1089 行起，共 10 个 Step。

应用户要求，Task 5 **分两段执行**，每段结束停机由人类 review 并手动提交。

### 段 1（Step 1–4）— ✅ 已完成并提交为 `2253768`

交付内容：

- `GET /api/npcs/{npc_id}/memory-explanations` — 只读安全解释接口，最多 5 条
- `MemoryExplanationService` — 由当前公开 World/Quest 情境构造固定查询，**不接受任何 query / owner / scope / limit / secrecy 参数**
- 前端独立 `useNpcMemoryStore` + `NpcDetailPanel` 内默认折叠的"相关记忆"区
- 14 个文件，1792 insertions

Review 状态：

| 阶段 | 结果 |
| --- | --- |
| Spec review（独立） | **APPROVED** — Critical 0 / Important 0 / Minor 3 |
| Code-quality review（独立） | **NEEDS FIXES** — Critical 0 / Important 1 / Minor 4 |
| Fix round 1/5 | 修复 1 Important + 3 Minor |
| Scoped re-review | **全部 ADDRESSED**，无新增破坏 |

那条 Important 值得记录：隐私测试 `test_get_npc_memory_explanations_never_exposes_the_player_claim` 原本跑在**空列表**上——grey 的唯一 authored knowledge 是 `private/player_dialogue`，且该用例不 tick，所以没有任何 `public/public` 记忆，导致"不泄露"断言平凡通过。修复后守卫为 `0 < len(memories) < len(owned)`，证明硬过滤确实丢弃一部分同时保留另一部分。

段 1 执行期间做出的裁定（完整版见 ledger）：

1. `source_label` → `source.kind` 用固定全映射表，未知标签视为服务错误
2. `reason_text` 模板按检索模式分别选取（`lexical_fallback` 下 semantic 恒为 0）
3. `catch_up_owner` 失败**降级**而非 503，仅 Memory 读取失败才 503
4. 检索预算用模块常量（limit 5 / char budget 1200），不新增 Settings
5. `allowed_memory_types` 传全部四种，权限交给 scope 规则
6. 超长 `safe_summary` 由 service 确定性截断
7. 来源标签取 `亲历事件 / 听到的说法 / 稳定知识 / 形成的看法`（`plan:1181` 与 `spec:521` 的 `亲历的世界事件` 位于示例块内，非规范条款）
8. fix round 顺带修三条小 Minor，不增加轮次
9. `memoryState` 的 `unread` 分支属于同一缺陷类，在范围内

### 段 2（Step 5–10）— ✅ 实现、验证与增量 re-review 已完成

| Step | 状态 | 执行者 | 内容 |
| --- | --- | --- | --- |
| 5 | ✅ | Codex | 新增 SQLite 重启 HTTP 闭环与前端 acceptance；修复 `phase2Acceptance.spec.ts` catch-all mock 假绿 |
| 6 | ✅ | Codex | 在随机隔离 PostgreSQL schema 真实验证 `0004`、六张认知表、vector 列、ready Embedding、`<=>` hybrid 查询、硬过滤与 lexical fallback |
| 7 | ✅ | Claude Code | 重写 `docs/05`、`docs/06`、`docs/07`、`docs/14` 与 `README.md`，逐字段对齐实现 |
| 8 | ✅ | Codex | 完整验证矩阵；并实跑 `docs/14` 的四文件 PostgreSQL opt-in 命令 |
| 9 | ✅ | Codex | 范围、隐私与 Git Gate 已完成 |
| 10 | ✅ | Codex | 独立双 review 后完成 Fix A–E；限定范围增量 re-review 为 Critical 0 / Important 0 |

Step 5/6 聚焦验证（Codex 报告）：Backend `57 passed, 1 skipped, 1 warning`；Frontend `65 passed（5 files）`；真实 PostgreSQL `14 passed`。Docker 测试容器已停止，数据卷保留。

Step 7 验证（本会话实测）：`test_story_content.py` + `test_deploy.py` 共 `14 passed`（这两个文件断言 README 的标题顺序与 env 块），随后完整 Backend `710 passed, 4 skipped, 1 warning`。Step 7 未修改任何生产或测试代码：`git diff -- backend/ frontend/` 为空。

Step 8 验证（Codex 实测）：Backend PowerShell 全量 `709 passed, 5 skipped, 1 warning`；额外的第五项 skip 是 PowerShell `PATH` 不含 POSIX `sh`，同一 launcher 探针在 Git Bash 单独 `1 passed`。Frontend `209 passed（30 files）`，type-check/build exit 0，两条 Compose config exit 0。复用 Step 6 的隔离 db-only Compose 项目实跑 `docs/14` 四文件 PostgreSQL 命令：`44 passed`，零 skip；随后不带 `-v` 停止容器与网络，数据卷保留。未执行外部 live Embedding/Reflection Smoke。

**独立双 review 已完成**：初审 Spec 为 Critical 0 / Important 2，quality 为 Critical 0 / Important 4；去重后五组阻塞面由同一轮严格 TDD Fix A–E 闭合。按用户要求，修复后没有重建完整 review package，也没有重跑全量 spec review，只读取 fixer 修改 diff、两份既有 Important findings 与相关测试结果。增量 re-review：**PASS — Critical 0 / Important 0**，无新 Critical/Important。

Fix A–E 最终聚焦验证：Embedding/Memory Retrieval/Chat Context/NPC API/文档 guard `77 passed, 1 skipped in 27.35s`。文档 guard 更新前按预期 RED（`1 failed, 2 passed`），状态同步后 GREEN（`3 passed`）；deadline 失败状态边界同样先 RED（`failed != unavailable`）再 GREEN。首轮相关测试曾因指定的 `--basetemp` 父目录不存在产生 fixture 环境错误；改用现有系统 TEMP 后原样全绿，不计为产品失败。随后复用隔离 db-only 项目实跑四个 PostgreSQL/pgvector 文件：`46 passed in 28.73s`，零 skip；容器与网络已停止，数据卷保留。

Stage 2 已由人类于 2026-09-13 提交为 `85ce338`。

> ⚠️ **但 Stage 2 尚不能视为完全关闭。** 提交后在 `85ce338` 上跑后端全量，出现 **7 个确定性失败**（详见下方 Current Risks 第 0 条）。根因是 Fix A–E 只跑了五个聚焦文件、未跑全量矩阵。

---

## Current Risks

### 高（阻塞 Stage 3）

**0. `85ce338` 上 7 个后端测试确定性失败。**

失败清单：

```
tests/backend/test_chat_service.py::test_slow_embedding_allows_another_chat_to_advance[pre]
tests/backend/test_chat_service.py::test_slow_embedding_allows_another_chat_to_advance[post]
tests/backend/test_chat_service.py::test_cancelled_chat_waits_for_session_worker_before_request_cleanup[pre]
tests/backend/test_chat_service.py::test_cancelled_chat_waits_for_session_worker_before_request_cleanup[post]
tests/backend/test_cognition_projection.py::test_shared_deadline_stops_reflection_after_embedding_consumes_budget
tests/backend/test_memory_explanation_service.py::test_failed_catch_up_degrades_and_still_reads_projected_memories
tests/backend/test_stage2_acceptance.py::test_stage2_http_closure_survives_restart_and_cognition_failures
```

**根因（已定位，非推测）**：Stage 2 Task 5 Fix A–E 给 `EmbeddingProvider.embed` 加了 `timeout_seconds` 关键字参数（`backend/app/llm/embedding_provider.py:56`），`backend/app/services/cognition_projection.py:74` 在存在 deadline 时改为调用 `embed(content, timeout_seconds=remaining)`（`catch_up_owner` 总是设 deadline）。

仓库共 **19 个 `def embed` 测试替身**，只有 **5 个**被同步到新签名——而这 5 个恰好全部位于 Fix A–E 当时跑过的五个聚焦文件内（`test_embedding_provider.py` ×3、`test_memory_retrieval.py` ×1、`test_npc_api.py` ×1）。其余 14 个替身仍是旧签名 `def embed(self, text)`，被关键字调用时抛 `TypeError`。

**一个比失败本身更严重的后果**：`test_shared_deadline_stops_reflection_after_embedding_consumes_budget` 现在**已不再测 deadline**。它的 `SlowEmbedding.embed` 本应把虚拟时钟推到 6 秒以耗尽预算，但因为签名不匹配，`embed` 根本未被执行（日志可见两条 `Embedding enrichment unavailable`），测试实际走的是“provider 抛异常”分支。

**待验证的次生风险**：部分仍为绿的测试可能是**因错误原因而绿**——例如 `def embed(self, text): raise RuntimeError(...)` 这类“provider 失败”替身，现在可能在自身函数体执行前就抛了 `TypeError`，于是测的是 `TypeError` 处理而不是 provider 错误处理。**这一条尚未验证，不得当作结论；修复时必须逐个确认。**

**修复边界**：这是测试替身与生产接口不同步，不是生产逻辑缺陷。先判定每个替身应该接受 `timeout_seconds` 还是应该断言它，**不要用 `**kwargs` 一括子吞掉**——那会把现在能发现问题的信号也屏蔽掉。

### 已解决（本轮 Step 5–6）

**1. Stage 2 PostgreSQL / pgvector 已完成真实验收。**

使用 `pgvector/pgvector:0.8.6-pg17-bookworm` 与随机隔离 schema，真实执行 `test_schema_migrations.py + test_postgres_runtime.py`：`14 passed`。验证包括 PostgreSQL 连接、Alembic `0004`、六张认知表、`memories.embedding` 的 vector 类型、Reset、ready Embedding 写入、真实 hybrid 检索、secret/cross-owner 硬过滤与 provider 失败后的 lexical fallback。

测试使用 `aleria-stage2-postgres` 专用 Compose project；容器和网络已通过不带 `-v` 的 `down` 停止，数据卷保留。

**2. `phase2Acceptance.spec.ts` 对新接口的假绿已修复。**

先加真实 Memory 形状断言，稳定复现 RED：`expected 'Memory相关记忆暂时无法读取' to contain '共 2 条'`。随后把 GET mock 改为严格 URL 感知，detail 与 memory 分别返回完整 fixture，未知 URL 显式失败；目标文件恢复 `2 passed`。用户在本轮指令中明确授权修复 acceptance 假绿。

### 已解决（本轮 Step 7）

**3. 四份权威文档与 README 的过时内容已重写。**

| 文档 | 主要变更 |
| --- | --- |
| `docs/05` v3.0 | 新增 Cognition pipeline 章节（权威提交 → post-commit、逐 NPC checkpoint、core/enrichment 边界、双 Session 约束、三 scope 权限表、排序公式）与 Stage 3 接口边界；`0003` → `0004`；Memory/embedding/reflection 移出 Deferred |
| `docs/06` v3.0 | 新增 4.3 解释接口章节：完整 envelope、逐字段约束表、404/503、五条上限与隐私边界；Chat flow 补上检索与投影两步并显式标注契约不变 |
| `docs/07` v3.0 | 新增 0004 来源元数据表、legacy null 策略、认知六表逐约束清单（FK/CHECK/UNIQUE/索引名）、SQLite JSON 与 PostgreSQL vector 差异、forward-only downgrade；head 改为 `0004` |
| `docs/14` v3.0 | 删除「Memory…均未实现」的过时断言；新增 Stage 2 认知配置全量环境变量与 fake 默认说明；PostgreSQL 验收描述补上 Stage 2 向量层；补齐四个 opt-in 测试文件的命令 |
| `README.md` | 新增「记忆闭环演示」章节（线索 → 挤出 history → 重启 → 再问 → 展开记忆）与「Claim 不是事实」说明；核心原则增加分层与认知从属两条；已知限制补 5 条 |

原「`docs/14:14` 会误导后续 agent」的风险已消除。

### 已解决（本轮 Step 10 Fix A–E）

**4. 未认证公开 GET 的 provider/write 边界已收口。**

`GET /api/npcs/{npc_id}/memory-explanations` 保留 Spec §13.2 的有界 core catch-up，因此积压时可推进 Observation、Memory 与 per-owner checkpoint；它跳过 Embedding/Reflection enrichment，公开查询使用本地确定性 embedding，不调用配置的 live provider。core 已追平后，重复 GET 不改变 cognition 行或 enrichment 状态。匿名接口仍无鉴权，但固定 owner/query/scope/limit 且只返回 `public/public` 安全投影。

### 低（已记录的 deferred minor）

5. `memory_explanation.py:88` 用 `semantic > 0` 近似 retriever 的真实判据 `memory.id in scores`；余弦恰好 clamp 到 0 的记忆按 hybrid 排序却按 lexical 解释。**只影响文案准确性，不泄露**。精确修复需在 `RetrievedMemory` 上加标志，超出段 1 范围。
6. `spec:521` 的示例标签 `亲历的世界事件` 与实现的 `亲历事件` 仍不一致。Step 7 已按裁定 7 在 `docs/06` 写入实现的真实取值，Spec 作为已批准的历史文档未改动；若日后重读 Spec 产生疑问，以 `docs/06` 与 `SOURCE_LABELS` 为准。
7. `npcMemory.ts` 与 `npcDetail.ts` 近乎逐行重复；brief 要求的是状态独立而非代码独立，等第三个同类 store 出现再抽工厂。
8. `MALFORMED_MEMORY_MESSAGE` 与 store 通用失败文案重复。
9. `TownView.spec.ts` 1154 行 / 35 用例，`TownView.vue` 532 行；纯增量且保留全部既有断言，Stage 3 前应拆分。
10. Task 4 遗留：一条权限变更回归用 `all(...)` 未断言存在成功派生行，空结果可空洞通过。
11. Task 3 遗留：多 app 重启测试未显式 dispose Engine，可能触发 SQLite `ResourceWarning`。本轮新增 acceptance 已显式 dispose 三个 app 的 Engine，没有复制该问题。

### 环境注意事项

- **pytest 必须在沙箱外运行**，并显式指定 `--basetemp` 到有写权限的目录。沙箱会创建 Windows `0700` 权限的临时目录导致无效结果（本项目已实际发生两次）。
- `backend/data/*.db` 被 `.gitignore` 忽略，**删除后 git 无法恢复**。

---

## Review Baseline

本小节是接手 agent 的第一判据，用于决定下一次 review 的增量起点。机制见 `docs/AI_REVIEW_POLICY.md`。

| 项 | 值 |
| --- | --- |
| 当前 approved 基线 | **无** — 尚未建立 |
| 当前 before 基线 | `B0001-stage2-close-before` |
| 基线路径 | `.superpowers/sdd/baselines/B0001-stage2-close-before/` |
| 基线对应 HEAD | `85ce338` |
| 基线 scope | 8 个含陈旧 `embed` 替身的后端测试文件 |
| 未清零 findings | **Backend 全量 7 failed**（Current Risks 第 0 条） |
| 下一个 gate | R1（仅测试改动，但改动了断言语义与 mock 边界） |

**为什么现在没有 approved 基线**：`AI_REVIEW_POLICY` §3.4 规定 approved 基线的含义是“该状态已被判定为 Critical 0 / Important 0”。`85ce338` 上有 7 个确定性失败，不满足该定义，因此它只能作为 `before` 基线（供待做的修复轮算增量）。

**什么时候会有 approved 基线**：7 个失败清零、完整验证矩阵全绿且无新增 warning 后，建立 `B0002-stage2-close-approved`，它才是 Stage 3 的增量起点。

⚠️ **禁止把 `before` 基线当作下一个 gate 的增量起点**（policy 红线 10）。

---

## Next Recommended Step

### 下一步应该做什么

**修复 14 个陈旧的 `embed` 测试替身，让后端全量回绿。** 这是 Stage 3 的硬前置条件：在一个已知 7 失败的基线上开新 Stage，后续每一次回归都无法区分新旧问题。

步骤：

1. 逐个判定 19 个 `def embed` 替身：该接受 `timeout_seconds` 还是该断言它。**不允许用 `**kwargs` 统一吞掉。**
2. 对 `test_shared_deadline_stops_reflection_after_embedding_consumes_budget`，修复后必须确认它真的重新测到 deadline（用变异验证：临时拿掉 deadline 判断，确认测试会失败）。
3. 审查仍为绿的 provider-失败类替身是否因 `TypeError` 而错误地绿。
4. 跑**完整**验证矩阵（后端全量 + 前端全量 + type-check），确认 3 个 warning 降回 1 个。
5. 建立 `B0002-stage2-close-approved`，写入本小节。

### 由哪个 agent 做

这是有界的测试修复，不涉及生产逻辑，中档模型即可。但第 2、3 步需要判断“这个测试到底在测什么”，不能机械地改签名。

按 `AI_REVIEW_POLICY` 定级：**R1**（仅测试改动，但改动了断言语义与 mock 边界）——一席独立 reviewer，输入为 `B0001 → 当前工作树` 的增量包。若修复过程中发现必须改生产代码，则升级定级并记 Ruling。

### 后续（Stage 3 前）

- 把 4 份协作文档纳入 git（目前全部未跟踪，换机器 clone 后全部丢失）。
- 根 `.gitignore` 补 `/.superpowers/`（`AI_REVIEW_POLICY` §3.3 隐患，尚未执行）。
- Stage 3 Plan 预声明 Review Level 与 binding 条款锚点（§7.3），并加一条全局约束：每个 Task ≤ 8 文件、只命中一类触发条款，超出就拆。

### 必须遵守的约束

- **不执行任何 git 写命令**。产出保持未暂存、未提交，由人类 review 后手动提交。
- 严格 TDD，每项行为先 RED 并确认失败原因正确。
- 不得引入新的 skip 或新的 warning。
- **修复完成后必须跑完整验证矩阵**，聚焦子集不得替代（`AI_REVIEW_POLICY` §5.2 硬规则、红线 13/14）。
