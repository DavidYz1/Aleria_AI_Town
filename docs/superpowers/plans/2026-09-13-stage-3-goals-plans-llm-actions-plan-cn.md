# Stage 3 Goals, Plans and Constrained LLM Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 每个 Task 结束即停机，等待独立 Review、用户 Review 与人类手动提交；不得连续执行两个 Task。

**Goal:** 在不改变 Aleria AI Town 权威世界规则的前提下，为 NPC 增加版本化 Identity/Drives、注册式 Goal、三至五步 Rolling Plan、受约束 Planning/Action Decision Provider、安全 fallback，以及普通/LLM 双推进和只读 Intent UI。

**Architecture:** Stage 3 保持同步 `POST /api/world/tick` 与现有单一 Action Registry/Conflict Resolver/CAS/原子 Run Graph。确定性代码生成并仲裁 Goal、验证 Plan、判断 trigger/进度/循环；LLM 只返回有界 Draft。四张 Intent 表保存跨 Run lifecycle，Provider 调用期间不持有数据库事务，最终 Goal/Plan/Proposal/Action/Event 在同一个权威提交中落地。

**Tech Stack:** Python 3.11+、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、SQLite、PostgreSQL 17、pgvector 0.8.6、httpx、pytest、Vue 3、Pinia、TypeScript、Vitest、Phaser 3.90.0。

**Spec:** `docs/superpowers/specs/2026-09-13-stage-3-goals-plans-llm-actions-design-cn.md`

## 0. 执行前置条件

1. 本 Plan 必须先经用户 Review 并由人类手动提交；Plan 未批准时不得执行 Task 1。
2. Task 1 开始前按 `AGENTS.md` 六项顺序重读，并核对 `git log -1 --oneline` 与 `git status --porcelain -uall`。
3. 初始增量起点为 `B0002-stage2-close-approved`（HEAD `6a25028`）。必须运行：

   ```powershell
   git diff 6a25028 --stat
   git status --porcelain -uall
   ```

4. 将输出与 `.superpowers/sdd/baselines/index.md` 的“B0002 之后的已知漂移”逐项比对。批准后的 Stage 3 Spec 与 Plan 属本阶段判据文档，应在 Task 1 前由人类提交并纳入新的 Stage 3 起点记录；任何其他表外差异均为 `OUT_OF_SCOPE_DRIFT`，未裁定前不得实现。
5. 新建 `.superpowers/sdd/2026-09-13-stage-3-goals-plans-llm-actions-plan-cn/progress.md` 只用于执行台账；基线与复核包继续按 `docs/AI_REVIEW_POLICY.md` §3–§6 的现行手工流程生成，不调用尚不存在的 `scripts/review_baseline.py`。

## 1. 全局约束

- **Task 粒度是硬约束：** 每个 Task 最多八个文件，并且只允许命中 `docs/AI_REVIEW_POLICY.md` §2.3 触发表中的一类条款。若实现或 fix 需要第九个文件，或出现第二类触发条款，立即停止，写入 `Ruling`，把剩余改动拆为新 Task；不得通过提高 Review Level 继续合并。
- **Task 抬头三行不可删：** `Review Level`、`Binding 条款锚点`、`证据要求` 必须随 Plan 行号变动同步更新，复核包必须摘录这些原文。
- **严格 TDD：** 每项行为先写 RED，运行并确认失败原因是目标能力缺失；import、拼写、fixture、权限或环境错误不算 RED。随后只写让该行为通过的最小实现，再做受测试保护的重构。
- **判别性证据：** 所有“不泄露 / 不发生 / 不调用 / 不写入”断言必须在非空、有区分度的数据上证明；集合过滤固定满足 `0 < visible < total`，Provider 不调用必须使用调用计数，rollback 必须同时断言权威与 Intent 表均为空或未变化。
- **不执行任何 git 写命令：** agent 禁止 `git add/commit/reset/checkout/switch/clean/stash/push`。每个 Task 只给建议提交信息，停机由人类 Review 后手动提交。
- **一个 Task 一个 Gate：** Critical/Important 未清零不得进入下一 Task；每条定级、范围裁定、deferred minor 都写入 ledger。修复轮只可缩小 reviewer 读取范围，不能缩小验证矩阵。
- **每个 Task 完成后跑完整验证矩阵：** 聚焦 RED/GREEN 不能替代以下三条命令；pytest 必须在沙箱外运行，并为每次运行生成新的、可写的 `--basetemp`：

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

- **完整矩阵判据：** 三条命令都必须记录本机真实数字/exit code；不得新增 skip 或 warning。任何 gate 宣布通过前，controller 必须亲眼看到完整输出（`AI_REVIEW_POLICY.md` §5.2、红线 13/14）。
- **测试替身接口规则：** 改动任何公开或内部接口前先用 `rg` 盘点定义、调用方和测试替身。若某接口被至少两个测试文件构造过替身，必须在同一 Task 的八文件上限内逐个对齐；无法容纳时改用兼容适配器或先拆 Task。无论是否拆分，该 Task 仍必须跑完整矩阵。
- SQLite 与 PostgreSQL 17 使用同一领域语义；迁移、约束、并发与 rollback 必须在真实 PostgreSQL 路径验收。测试不得写入或删除 `backend/data/aleria.db`。
- 不改变 `world_version`、`clock_tick`、`event_sequence` 的职责。成功世界推进各只递增一次前两者，`event_sequence` 只随真实 Event 增长；Goal/Plan 变化不单独递增计数器。
- 不放宽 Stage 2 Retrieval hard filter、scope、secrecy 或 disclosure；Player Claim、Reflection、Belief 不是 World Fact。
- 不新增行动类型；只使用 `move/rest/work/eat/talk/wait`。不实现 `investigate/share_information/report`。
- 不引入 LangChain、LangGraph、Celery、Redis、Outbox、Worker、SSE、异步 202、独立向量库或 Proposed/Future 接口。
- Public DTO 一律由安全投影构造；不返回 ORM、Provider 原文/错误、Prompt、秘密 evidence、内部评分或 hidden reasoning。
- 普通推进必须保持 Stage 2 deterministic 结果、同步 200 和离线可用；Fake/live Provider 失败不能损坏世界或把成功语义改成模型专属 5xx。

## 2. 文件职责与稳定接口

| 文件 | 单一职责 |
| --- | --- |
| `backend/migrations/versions/0005_stage3_goals_plans.py` | Identity 列、四张 Intent 表与 Run Graph 关联列的 forward-only migration |
| `backend/app/agents/intent_contracts.py` | 冻结的 Identity、Goal、Plan、condition、trigger、Intent delta 内部契约 |
| `backend/app/agents/goal_registry.py` | `goal-types-v1`、三类候选、eligibility/evaluator、确定性 plan builder |
| `backend/app/agents/goal_arbitration.py` | `goal-arbitration-v1` 评分、切换阈值与稳定 tie-break |
| `backend/app/agents/plan_policy.py` | Plan validator、condition evaluator、replanning trigger 与 loop guard |
| `backend/app/database/intent_repository.py` | Identity/active Intent 读取、evidence 复验与事务内 Intent staging；绝不自行 commit |
| `backend/app/services/deliberation_context.py` | 有界 Memory/Belief/World/Quest 上下文与输出白名单；读取结束后不留事务 |
| `backend/app/llm/planning_provider.py` | Planning request/draft Protocol、Fake 与 live adapter/factory |
| `backend/app/llm/action_decision_provider.py` | Action Decision request/draft Protocol、Fake 与 live adapter/factory |
| `backend/app/llm/structured_http.py` | 两个 live adapter 共用的单次 OpenAI-compatible 结构化 HTTP 调用 |
| `backend/app/agents/deliberation.py` | 单 NPC 共享 deadline、一次 schema repair、validator 与 deterministic fallback |
| `backend/app/agents/auto_orchestrator.py` | 已验证 Intent 决策到每 NPC 一个 Proposal，再进入既有统一执行链 |
| `backend/app/services/world_clock_service.py` | 模式选择、至多一个 deliberating NPC、Provider 外事务边界与 post-commit cognition |
| `backend/app/database/world_clock_repository.py` | CAS 后在一个事务提交 World、Run Graph 与 Intent delta |
| `backend/app/schemas/intent.py`、`backend/app/services/intent_service.py` | Public Intent DTO 与固定安全投影 |
| `frontend/src/types/intent.ts`、`api/intent.ts`、`stores/npcIntent.ts` | Intent 前端类型、适配器和独立竞态安全状态 |
| `frontend/src/components/NpcIntentPanel.vue` | “当前打算”纯展示，不调 API、不进入 Phaser |

### Review 触发隔离表

| Task | 唯一触发类 | 明确不在该 Task 内 |
| --- | --- | --- |
| 1 | Alembic / 数据库 Schema | Repository 并发、World transaction、Public API |
| 2 | 单层 `agents/` 有界实现 | DB、Provider、API |
| 3 | 并发 | migration、commit 边界、Public API |
| 4 | 跨 Stage 信息分层不变量 | scope 放宽、Provider、Public API |
| 5 | 单层 `llm/` 有界契约/Fake | 外部 HTTP、retry/deadline |
| 6 | 外部 Provider 调用 | repair/backoff/共享 deadline、DB、API |
| 7 | retry/timeout 预算编排 | 真实 HTTP adapter、DB、API |
| 8 | 跨 Stage 统一行动入口不变量 | Provider 调用、DB、Public API |
| 9 | transaction / Session 归属 | migration、新并发策略、Public API |
| 10 | Tick Public API | transaction/schema 规则、frontend |
| 11 | Public DTO 安全投影 | router/状态码、Provider、DB 写入 |
| 12 | Intent Public API | 投影规则改动、frontend |
| 13–16 | 单层 `frontend/` 有界实现 | backend、Public API 变更、Phaser 业务状态 |
| 17–18 | 权威文档 | 生产代码、测试替身、Stage 关闭结论 |

Task 6 的 per-call timeout 只是把已验证 Request budget 交给 HTTP client，不拥有 repair、重试或跨调用 deadline；这些只在 Task 7 实现。Task 9 只把 Task 3 已批准的并发策略纳入事务，不新增锁/重试算法。若 reviewer 认定某个 delta 实际跨入“明确不在”列，Gate 立即失败并拆 Task。

以下接口名在首次定义后视为稳定；后续 Task 不得改名或加参数。确需改变时，先执行测试替身盘点并拆出独立接口 Task：

```python
class PlanningProvider(Protocol):
    def plan(self, request: PlanningRequest) -> PlanningDraft: ...

class ActionDecisionProvider(Protocol):
    def decide(self, request: ActionDecisionRequest) -> ActionProposalDraft: ...

class DeliberationEngine:
    def deliberate(self, context: DeliberationContext) -> DeliberationOutcome: ...

class IntentRepository:
    def load_identity(self, npc_id: str) -> IdentityProfile | None: ...
    def load_active(self, world_id: str, owner_npc_id: str, *, for_update: bool = False) -> ActiveIntent | None: ...
    def stage_delta(self, delta: IntentRunDelta) -> None: ...

class WorldTickService:
    def advance(self, expected_world_version: int, mode: RuntimeMode = RuntimeMode.DETERMINISTIC) -> WorldTickData: ...
```

---

### Task 1：建立 `0005` Intent Schema 与版本化 Identity Seed
**Review Level:** R3（触发：新增 / 修改 Alembic revision，或数据库表、列、约束）
**Binding 条款锚点:** spec:§8 L157-L182、spec:§16 L394-L479、spec:§21.3 L639-L649、plan:L120-L197
**证据要求:** 空 SQLite 与真实 `0004` 升级到 `0005`、legacy Identity 保持 null、四表/列/约束 ORM 同构、非法 Identity 与 FK/CHECK/UNIQUE 在非空 fixture 上失败、真实 PostgreSQL 路径零 skip

**Files（8）：**

- Create: `backend/migrations/versions/0005_stage3_goals_plans.py`
- Modify: `backend/app/database/models.py`
- Modify: `backend/app/schemas/seed.py`
- Modify: `backend/app/services/demo_reset_service.py`
- Modify: `data/npcs.json`
- Modify: `tests/backend/test_schema_migrations.py`
- Create: `tests/backend/test_stage3_models.py`
- Modify: `tests/backend/test_seed_world.py`

**Interfaces:**

- Produces Alembic head `0005` and ORM classes `AgentGoal`, `AgentGoalEvidence`, `AgentPlan`, `AgentPlanStep`.
- Adds nullable `NpcProfile.identity_version/identity_json`, non-null `AgentRun.fallback_used`, nullable `ActionProposalRecord.goal_id/plan_step_id`.
- Extends `SeedNpc` with the exact `identity-v1` structure; does not change any Public API.

- [ ] **Step 1：写 Schema/Seed RED**

  在三个测试文件先固定：`0005` head、四张表、所有 FK/CHECK/UNIQUE/index 名、legacy null、forward-only downgrade、Identity 列表/Drive 边界、Reset 写完整 Identity。关键断言必须包含：

  ```python
  assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
  assert {"agent_goals", "agent_goal_evidence", "agent_plans", "agent_plan_steps"} <= set(inspect(engine).get_table_names())
  assert legacy_identity == (None, None)
  with pytest.raises((IntegrityError, ValueError)):
      persist_invalid_goal_or_identity()
  ```

- [ ] **Step 2：运行聚焦 RED 并核对失败原因**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task1-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_schema_migrations.py tests\backend\test_stage3_models.py tests\backend\test_seed_world.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 只因 revision `0005`、新表/列/约束或 Identity 字段尚不存在而失败；先排除旧 migration、临时目录或 fixture 故障。

- [ ] **Step 3：实现 migration 与同构 ORM**

  Migration 与 ORM 使用相同 vocabulary：

  ```text
  agent_goals: active/completed/failed/superseded
  agent_goal_evidence: supporting/contradicting; exactly one of memory_id/belief_id
  agent_plans: deterministic/llm/fallback; active/completed/failed/superseded
  agent_plan_steps: pending/active/completed/failed/skipped/superseded
  failure_strategy: retry/replan/fallback
  agent_runs.mode: deterministic/auto
  ```

  既有 `agent_runs` 的 `fallback_used` 迁移时以 false 回填，再收紧为 non-null；应用态默认 false。`action_proposals.goal_id/plan_step_id` 都是 nullable FK，legacy 行保持 null。`downgrade()` 必须明确 `raise RuntimeError`。不得用删库、重建或伪造 `alembic_version` 通过测试。

- [ ] **Step 4：实现 Identity Seed 与 Reset**

  `SeedNpc` 固定 `identity_version="identity-v1"`；三类必填列表各 1–5 项，`fears/prohibitions` 各 0–5 项，每项 trim 后 1–120 字符；`drives` 必须且只能含六个 0–1 有限数值。为 Ryan/Shir/Grey 写 authored 内容，Reset 写入 JSON，legacy upgrade 不回填。

- [ ] **Step 5：聚焦 GREEN、真实 PostgreSQL 与同构检查**

  重跑 Step 2，随后在已设置 `TEST_POSTGRES_URL` 的 PostgreSQL 17/pgvector 环境运行相同 migration/model 用例；记录 SQLite 数字和 PostgreSQL 零 skip 输出。用 SQLAlchemy inspector 逐名比较 ORM 与 migration 约束，不能只检查“表存在”。

- [ ] **Step 6：完整矩阵、R3 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task1-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Boundary package，三席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add stage 3 intent schema and npc identities`。agent 停机，等待人类提交。

---

### Task 2：实现确定性 Goal Registry、仲裁、Plan 与防循环策略
**Review Level:** R1（触发：单层内的有界实现，仅 `agents/`）
**Binding 条款锚点:** spec:§9 L184-L208、spec:§10 L210-L233、spec:§11 L235-L253、spec:§12 L255-L280、spec:§21.1 L621-L628、plan:L199-L279
**证据要求:** 三个固定 Goal Type/动作白名单、评分每个分量与 0.10 切换门槛、稳定 tie-break、三至五步/条件白名单、全部 trigger 顺序、两次失败/三次无进展/两 tick 冷却均有会先失败的纯单元测试

**Files（7）：**

- Create: `backend/app/agents/intent_contracts.py`
- Create: `backend/app/agents/goal_registry.py`
- Create: `backend/app/agents/goal_arbitration.py`
- Create: `backend/app/agents/plan_policy.py`
- Create: `tests/backend/test_goal_registry.py`
- Create: `tests/backend/test_goal_arbitration.py`
- Create: `tests/backend/test_plan_policy.py`

**Interfaces:**

- Produces immutable `IdentityProfile`, `GoalEvidenceRef`, `GoalCandidate`, `RegisteredCondition`, `PlanStepDraft`, `GoalPlanDraft`, `ActiveIntent`, `IntentRunDelta`, `DeliberationContext`, `DeliberationOutcome`, plus `EMPTY_INTENT_DELTA`.
- Produces `GoalTypeRegistry`, `DEFAULT_GOAL_REGISTRY`, `PlanPolicy`, `GOAL_REGISTRY_VERSION = "goal-types-v1"`, `ARBITRATION_VERSION = "goal-arbitration-v1"`.
- Produces pure functions `generate_candidates(...)`, `arbitrate_goal(...)`, `evaluate_replan_reasons(...)`, `is_looping(...)`; `PlanPolicy.validate(...)` and `.build_fallback(...)` own Plan semantics.

- [ ] **Step 1：写领域策略 RED**

  先写纯测试，固定枚举和函数签名：

  ```python
  assert [item.goal_type for item in GOAL_TYPES] == [
      "recover_energy", "perform_role_duty", "follow_up_salient_clue"
  ]
  assert score.total == pytest.approx(clamp(
      .20 * score.base_priority + .20 * score.urgency +
      .15 * score.drive_alignment + .10 * score.personality_alignment +
      .15 * score.evidence_strength + .10 * score.quest_relevance +
      .10 * score.commitment - .10 * score.risk - .10 * score.switching_cost
  ))
  assert evaluate_replan_reasons(fixture) == (
      "critical_event", "goal_completed", "precondition_changed"
  )
  ```

  另测 unknown Goal/action/condition/target、prohibition 绕过、2-step/6-step Plan、相同分数乱序输入、Claim 事实权重、Relationship 占位值。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task2-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_goal_registry.py tests\backend\test_goal_arbitration.py tests\backend\test_plan_policy.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因新 contracts/registry/policy 不存在而失败，不接受 fixture 构造错误。

- [ ] **Step 3：写最小纯实现**

  `goal_registry.py` 复用 `backend.app.world.decision` 的低能量边界和 `WORK_LOCATION_BY_ROLE`，固定 sort order 10/20/30 与 Spec 动作白名单。`goal_arbitration.py` 不读 DB、不调用 Provider、不使用时间或随机数。`plan_policy.py` 的 `PlanPolicy` 只接受注册条件：

  ```python
  CONDITION_TYPES = frozenset({
      "npc_at_location", "energy_at_least", "quest_status_is", "action_executed"
  })
  REPLAN_ORDER = (
      "critical_event", "goal_completed", "goal_failed", "precondition_changed",
      "action_failed", "loop_detected", "player_intervention", "no_valid_plan",
  )
  ```

- [ ] **Step 4：聚焦 GREEN 与变异验证**

  重跑 Step 2。临时把切换阈值 `0.10` 改为 `0.09`、失败上限 `2` 改为 `3`，分别确认对应测试 RED，再还原并重跑 GREEN；不得保留变异。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task2-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Lite package，一席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add deterministic goal and plan policies`。agent 停机，等待人类提交。

---

### Task 3：实现并发安全的 Intent Repository
**Review Level:** R2（触发：涉及并发）
**Binding 条款锚点:** spec:§10 L210-L233、spec:§16.1–§16.4 L398-L452、spec:§21.3 L639-L649、plan:L281-L346
**证据要求:** Repository 不自行 commit；active Goal/Plan 唯一、revision 单调、evidence 同 owner/world/非未来；两个独立 Session 的竞争写只有一个成功；SQLite 与真实 PostgreSQL 给出判别性结果

**Files（3）：**

- Create: `backend/app/database/intent_repository.py`
- Create: `tests/backend/test_intent_repository.py`
- Modify: `tests/backend/test_postgres_runtime.py`

**Interfaces:**

- Implements the stable `IntentRepository` interface from §2.
- `stage_delta()` may `add/flush` only after caller has entered final write phase; it never calls `commit()` or `rollback()`.
- `load_active(..., for_update=True)` returns a model-independent `ActiveIntent`, ordered by stable IDs, or raises `IntentPersistenceError` on duplicate/invalid rows.

- [ ] **Step 1：写 Repository RED**

  覆盖真实非空 Goal→Plan→3 Step→Evidence 图、无 evidence Goal、跨 owner/world/future evidence、重复 active、revision 逆序、非法 ordinal。并发测试使用两个独立 `Session` 与明确交错，不用同一 Session 假装并发：

  ```python
  with factory() as first, factory() as second:
      first_repo.load_active(WORLD, NPC, for_update=True)
      second_attempt = try_stage_competing_intent(second)
      first.commit()
      assert exactly_one_active(factory(), WORLD, NPC)
      assert second_attempt in {"conflict", "rejected"}
  ```

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task3-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_intent_repository.py tests\backend\test_postgres_runtime.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因 `IntentRepository` 不存在而失败；未设置 PostgreSQL 时的既有 opt-in skip 不能冒充并发证据。

- [ ] **Step 3：实现最小 Repository**

  所有写入先验证完整 delta，再按 Goal→Evidence→Plan→Step 顺序 stage。锁定/复读 owner 的 active Intent 后才接受 replacement；对跨方言无法完全由 constraint 表达的唯一 active 语义做事务内复验。异常统一为固定类别：

  ```python
  class IntentConflictError(RuntimeError): ...
  class IntentPersistenceError(RuntimeError): ...
  ```

  错误消息不得包含 Memory/Belief 正文或 Provider 文本。

- [ ] **Step 4：聚焦 GREEN 与真实 PostgreSQL**

  重跑 Step 2 的 SQLite 用例；随后设置独立 `TEST_POSTGRES_URL`，运行两个文件并要求 PostgreSQL 并发用例实际执行、零 skip。失败后断言 session rollback 由调用者完成且数据库无半条图。

- [ ] **Step 5：完整矩阵、R2 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task3-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Standard package，契约/质量两席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: persist concurrent npc goals and plans`。agent 停机，等待人类提交。

---

### Task 4：建立权限不扩张的 Deliberation Context
**Review Level:** R3（触发：触及跨 Stage 不变量“事实、感知、记忆、信念分层”）
**Binding 条款锚点:** spec:§5.2 L113-L120、spec:§14 L337-L352、spec:§20 L608-L617、spec:§21.2 L630-L637、plan:L348-L409
**证据要求:** owner/world/非未来/lifecycle/secrecy/disclosure 继续由既有 hard filter 决定；8 Memory/3 Belief/2400 字符边界；Claim 明确隔离；非法引用白名单外；沿用既有 access telemetry 语义且 Provider 调用前零开放事务；隐私测试满足 `0 < visible < total`

**Files（4）：**

- Create: `backend/app/services/deliberation_context.py`
- Modify: `backend/app/database/cognition_repository.py`
- Create: `tests/backend/test_deliberation_context.py`
- Modify: `tests/backend/test_cognition_repository.py`

**Interfaces:**

- Produces `DeliberationContextAssembler.assemble(snapshot, identity, candidate, active_intent, trigger_reasons) -> DeliberationContext`.
- Adds `CognitionRepository.current_beliefs(world_id, owner_npc_id, world_version, clock_tick, limit) -> tuple[BeliefContext, ...]` with the same owner/world/time/lifecycle hard boundary.
- Reuses `MemoryRetriever` and existing scope rules; does not add or modify a `RetrievalScope` member.

- [ ] **Step 1：写 Context/隐私 RED**

  构造同 owner 可见、同 owner secret、cross-owner、cross-world、future、superseded 与 player Claim 的非空集合。断言：

  ```python
  assert 0 < len(context.memories) < len(all_memories)
  assert len(context.memories) <= 8
  assert len(context.beliefs) <= 3
  assert sum(len(item.text) for item in (*context.memories, *context.beliefs)) <= 2400
  assert session.in_transaction() is False
  assert set(recorded_access_ids) <= set(context.memory_ids)
  ```

  另断言 Claim 带固定 source/speaker 标签，且其指令文本不能改变 system/allowlist 区域。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task4-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_deliberation_context.py tests\backend\test_cognition_repository.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因 Context Assembler/current belief read surface 不存在而失败；空集合断言不算有效 RED。

- [ ] **Step 3：实现有界读取与冻结 Context**

  Memory 保留既有 `MemoryRetriever` 的权限优先排序与稳定 tie-break；current Belief 按 `(created_at DESC, id ASC)` 稳定取数。不截断单条记录；若下一条会超过 2400 字符则整体丢弃该条。输出白名单由请求中真实 entity/Memory/Belief/Goal/Plan/Step ID 的冻结集合构成。既有非 public retrieval access telemetry 可在独立事务提交，但提交/rollback 后才能返回 Context；任何 cognition read 故障抛 `DeliberationContextUnavailable`，调用方不得向 Provider 发送残缺 context。

- [ ] **Step 4：聚焦 GREEN 与变异验证**

  重跑 Step 2；临时去掉 cross-owner SQL 条件，确认 `0 < visible < total` 用例失败后还原。另用调用计数证明 assembler 不调用 Planning/Action Provider、不执行 cognition catch-up。

- [ ] **Step 5：完整矩阵、R3 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task4-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Boundary package，三席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: assemble bounded deliberation context`。agent 停机，等待人类提交。

---

### Task 5：定义 Planning/Action Decision 契约与确定性 Fake
**Review Level:** R1（触发：单层内的有界实现，仅 `llm/`）
**Binding 条款锚点:** spec:§13.1–§13.4 L282-L321、spec:§21.2 L630-L637、plan:L411-L482
**证据要求:** 两个独立 Protocol、冻结且 `extra=forbid` 的 request/draft、3–5 Step、ID allowlist 字段、Fake 固定输入固定输出；Fake 与 live 将共用同一 schema，Fake 不被计为 fallback

**Files（4）：**

- Create: `backend/app/llm/planning_provider.py`
- Create: `backend/app/llm/action_decision_provider.py`
- Create: `tests/backend/test_planning_provider.py`
- Create: `tests/backend/test_action_decision_provider.py`

**Interfaces:**

- Produces final stable `PlanningRequest`, raw `PlanningStepDraft`, `PlanningDraft`, `PlanningProvider` and `FakePlanningProvider`; Task 7 validates/maps raw steps into Task 2 `PlanStepDraft`.
- Produces final stable `ActionDecisionRequest`, `ActionProposalDraft`, `ActionDecisionProvider` and `FakeActionDecisionProvider`.
- Both request types include `timeout_seconds` and `repair_feedback: tuple[str, ...] = ()`; later Tasks may populate them but may not change the method signatures.

- [ ] **Step 1：写 Schema/Fake RED**

  先固定严格 schema：

  ```python
  class PlanningDraft(BaseModel):
      model_config = ConfigDict(extra="forbid", frozen=True)
      internal_description: str = Field(min_length=1, max_length=400)
      steps: tuple[PlanningStepDraft, ...] = Field(min_length=3, max_length=5)

  class PlanningProvider(Protocol):
      def plan(self, request: PlanningRequest) -> PlanningDraft: ...

  class ActionDecisionProvider(Protocol):
      def decide(self, request: ActionDecisionRequest) -> ActionProposalDraft: ...
  ```

  测 unknown field、非有限 timeout、2/6 Steps、非法 ID 形状、多个 Proposal、不可执行 next Step；同一 Fake request 连续两次结果必须完全相等。跨请求 allowlist 成员校验留给 Task 7 的 Backend validator，不在结构 schema 中复制。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task5-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_planning_provider.py tests\backend\test_action_decision_provider.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因两个 Provider 模块/类型不存在而失败。

- [ ] **Step 3：实现严格契约与 Fake**

  Request 只接受冻结的安全 Context、Goal/Plan/唯一 next Step、允许 action/condition/entity IDs、remaining timeout 和 repair feedback。Fake 只从允许集合稳定选择，排序不得使用 Python random/hash/UTC；Fake 产物仍经过 Pydantic schema，不能返回已验证的 `ActionProposal`。

- [ ] **Step 4：聚焦 GREEN 与接口盘点**

  重跑 Step 2。运行：

  ```powershell
  rg -n "PlanningProvider|ActionDecisionProvider|def plan\(|def decide\(" backend tests
  ```

  确认只有本 Task 定义与测试使用新接口，没有平行 Protocol 或宽松 `**kwargs` 替身。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task5-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Lite package，一席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add structured deliberation provider contracts`。agent 停机，等待人类提交。

---

### Task 6：实现独立 Live Provider Adapter 与配置
**Review Level:** R2（触发：涉及外部 Provider 调用）
**Binding 条款锚点:** spec:§13.4 L314-L321、spec:§13.5 L323-L335、spec:§19 L586-L606、spec:§21.2 L630-L637、plan:L484-L561
**证据要求:** Planning/Action 与 Chat/Embedding/Reflection 配置、实例和日志完全分离；OpenAI-compatible payload 严格、有短 timeout/64 KiB 响应上限；HTTP/transport/JSON/shape 错误归固定安全类别；明确 live 配置不完整时绝不伪装 Fake 成功

**Files（8）：**

- Create: `backend/app/llm/structured_http.py`
- Modify: `backend/app/llm/planning_provider.py`
- Modify: `backend/app/llm/action_decision_provider.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `tests/backend/test_planning_provider.py`
- Modify: `tests/backend/test_action_decision_provider.py`
- Create: `tests/backend/test_deliberation_config.py`

**Interfaces:**

- Adds `OpenAICompatiblePlanningProvider`, `build_planning_provider(settings)`.
- Adds `OpenAICompatibleActionDecisionProvider`, `build_action_decision_provider(settings)`.
- Adds `StructuredProviderError(category: Literal["configuration", "timeout", "transport", "http_status", "response_too_large", "response_json", "response_shape"])`.
- `create_app(..., planning_provider=None, action_decision_provider=None)` stores two independent providers in application state; existing call sites remain valid.

- [ ] **Step 1：写 Live/Config RED**

  使用 `httpx.MockTransport` 固定验证 endpoint、auth、model、structured JSON body、超时值和 64 KiB 上限。分别构造 401、500、timeout、invalid JSON、unknown field、oversize；日志捕获断言不含 API key、玩家原文、response body。配置测试固定：

  ```python
  assert Settings(_env_file=None).planning_provider == "fake"
  assert Settings(_env_file=None).action_decision_provider == "fake"
  assert Settings(_env_file=None).deliberation_budget_seconds == 8.0
  with pytest.raises(ValidationError):
      Settings(_env_file=None, deliberation_budget_seconds=30.1)
  ```

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task6-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_planning_provider.py tests\backend\test_action_decision_provider.py tests\backend\test_deliberation_config.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因 live classes/factories/settings 不存在而失败，不接受真实网络、DNS 或 Key 缺失作为 RED。

- [ ] **Step 3：实现单次 HTTP Adapter**

  `structured_http.py` 每次只做一次 HTTP 调用和一次 JSON 提取，不做 repair/backoff。使用 Request 的 `timeout_seconds`，读取响应前检查 `Content-Length`，流式累计也不得超过 65,536 bytes。Provider 文件把响应交给 Task 5 schema；错误只抛固定 category：

  ```python
  raise StructuredProviderError(category="response_shape") from None
  ```

- [ ] **Step 4：实现配置、factory 与 app state 注入**

  Planning/Action 各自拥有 provider/base_url/api_key/model/auth_mode/timeout 字段，单次 timeout `gt=0, le=30`；共享 `deliberation_budget_seconds=8.0, gt=0, le=30`。`fake` 是默认。明确选择 `openai_compatible` 但配置不全时 factory 返回会抛 `configuration` 的 unavailable adapter，不回退成 Fake。

- [ ] **Step 5：聚焦 GREEN、泄露变异与替身盘点**

  重跑 Step 2。临时把 error log 加入 response body，确认日志隐私测试 RED 后还原。再运行：

  ```powershell
  rg -n "create_app\(|PlanningProvider|ActionDecisionProvider|planning_provider|action_decision_provider" tests backend
  ```

  新增可选 `create_app` 参数不能迫使既有测试改写；禁止用 `**kwargs` 吞掉签名问题。

- [ ] **Step 6：完整矩阵、R2 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task6-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Standard package，契约/质量两席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add live planning and action providers`。agent 停机，等待人类提交。

---

### Task 7：实现共享 Deadline、一次 Repair 与确定性 Fallback
**Review Level:** R2（触发：涉及重试、超时）
**Binding 条款锚点:** spec:§12 L255-L280、spec:§13.5 L323-L335、spec:§19 L586-L606、spec:§21.2 L630-L637、plan:L563-L629
**证据要求:** Planning 与 Action 各至多一次 schema repair；网络/timeout/cancel/budget 不 repair；`min(provider_timeout, remaining)`；deadline 后成功也丢弃；失败只影响一个 NPC并返回合法 fallback；虚拟时钟与调用计数证明分支真实执行

**Files（2）：**

- Create: `backend/app/agents/deliberation.py`
- Create: `tests/backend/test_deliberation_engine.py`

**Interfaces:**

- Implements `DeliberationEngine.deliberate(context) -> DeliberationOutcome`.
- Constructor receives `PlanningProvider`, `ActionDecisionProvider`, `GoalTypeRegistry`, `PlanPolicy`, `provider_timeout_seconds`, `budget_seconds`, and injectable `monotonic`.
- Returns only validated `GoalPlanDraft + ActionProposalDraft` or deterministic fallback outcome; never returns raw Provider text/error.

- [ ] **Step 1：写 Deadline/Repair/Fallback RED**

  为每个分支使用具名 fake，记录 `calls`、每次 request timeout 和虚拟时钟。至少固定：首次 schema invalid→一次 repair→success；两次 schema invalid→fallback；network/timeout→零 repair；Planning 耗尽预算→Action 零调用；Provider 返回后时钟越 deadline→结果丢弃；invalid ID/action/condition→repair；context unavailable→两个 Provider 零调用。

  ```python
  assert planning.calls == 2
  assert action.calls == 0
  assert outcome.source == "fallback"
  assert all(0 < call.timeout_seconds <= remaining_at_call for call in planning.requests)
  ```

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task7-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_deliberation_engine.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因 `DeliberationEngine` 不存在而失败；若 fake 本身未被调用，测试必须失败而不是平凡变绿。

- [ ] **Step 3：实现最小状态机**

  使用显式顺序函数，不引入工作流框架：

  ```python
  context -> planning_once -> validate
          -> schema_invalid ? planning_repair_once -> validate : continue
          -> action_once -> validate
          -> schema_invalid ? action_repair_once -> validate : continue
          -> DeliberationOutcome
  any unavailable/deadline/second-invalid -> deterministic fallback
  ```

  每次调用前后都检查 monotonic deadline；repair feedback 只含固定 validation code，不含秘密正文或 Provider 原文。

- [ ] **Step 4：聚焦 GREEN 与判别力验证**

  重跑 Step 2。把虚拟 Planning 耗时从 9 秒变为 0 秒，确认“Action 零调用”测试 RED 后还原；把 repair 上限临时放到 2，确认调用次数测试 RED 后还原。

- [ ] **Step 5：完整矩阵、R2 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task7-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Standard package，契约/质量两席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: bound deliberation repair and fallback`。agent 停机，等待人类提交。

---

### Task 8：把 Auto 决策接入唯一 Action 执行链
**Review Level:** R3（触发：触及跨 Stage 不变量“统一行动入口”）
**Binding 条款锚点:** spec:§5.1 L102-L111、spec:§7 L144-L155、spec:§15.1 L354-L374、spec:§15.3 L385-L392、spec:§21.1 L621-L628、plan:L631-L689
**证据要求:** 所有 NPC 同一 decision Snapshot、每 NPC 恰好一个 Proposal、四种 source 正确、LLM/fallback 仍过同一 Registry/Conflict Resolver、非法 Draft 零效果、deterministic 固定 fixture 与 Task 前逐 Proposal/Event 完全相同

**Files（5）：**

- Modify: `backend/app/agents/contracts.py`
- Modify: `backend/app/agents/orchestrator.py`
- Create: `backend/app/agents/auto_orchestrator.py`
- Modify: `tests/backend/test_agent_orchestrator.py`
- Create: `tests/backend/test_auto_orchestrator.py`

**Interfaces:**

- Adds optional `goal_id` and `plan_step_id` to `ActionProposal`, defaulting to null so existing callers remain source-compatible.
- Produces `run_proposal_advance(snapshot, proposals) -> AgentRuntimeResult`; existing `run_deterministic_advance(snapshot)` delegates to it without observable change.
- Produces `run_auto_advance(snapshot, intents_by_npc, outcomes_by_npc) -> Stage3AdvanceResult`.

- [ ] **Step 1：盘点共享契约替身并写 RED**

  先运行并把命中测试文件数写入 ledger：

  ```powershell
  rg -l "ActionProposal\(" tests\backend tests\frontend
  rg -l "run_deterministic_advance|AgentRuntimeResult" tests\backend
  ```

  然后写 RED：乱序 NPC/Proposal 输入仍稳定；三个 NPC 只读同一 Snapshot；existing plan、llm、fallback 都经过 Registry；非法 LLM action 被拒绝且无 Event；一个 NPC 不能产生两个最终 Proposal；deterministic baseline 的完整 Proposal/Resolution/Event/Trace 相等。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task8-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_agent_orchestrator.py tests\backend\test_auto_orchestrator.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 新 auto/shared execution 接口不存在而失败；既有 deterministic tests 在实现前仍须保持 GREEN，并分别记录。

- [ ] **Step 3：抽取共享执行器并实现 Auto Adapter**

  只抽取“Proposal→Registry→Conflict→effect/Event/Trace”已有逻辑；不得改 Action Registry、Conflict Resolver、passive drift 或 clock。Auto adapter 只能把已经验证的 next Step/Draft 转成 `ActionProposal`；其他 NPC走 `existing_plan` 或确定性 `fallback`。任何未验证文本不得进入 proposal payload/trace。

- [ ] **Step 4：聚焦 GREEN 与 deterministic 等价变异**

  重跑 Step 2。临时绕过 Registry 直接执行一个虚构 action，确认非法 Draft 测试 RED后还原。比较固定 Seed 的 deterministic 结果对象，不得只比较计数。

- [ ] **Step 5：完整矩阵、R3 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task8-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  本 Task 修改共享 `ActionProposal`，无论可选字段是否兼容都必须全量。生成 Boundary package，三席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: route auto decisions through action runtime`。agent 停机，等待人类提交。

---

### Task 9：原子提交 Intent 与同步 World Run
**Review Level:** R3（触发：改变事务边界或 Session 归属）
**Binding 条款锚点:** spec:§5.3 L121-L126、spec:§15 L354-L383、spec:§16.5–§16.6 L454-L479、spec:§19 L586-L606、spec:§21.3 L639-L649、plan:L691-L746
**证据要求:** Provider 调用时权威/认知 Session 均无开放事务；返回后复读版本与 hard filter；CAS 后 Goal/Plan/Step/Proposal/Action/Event 单事务；commit/flush/CAS 故障零半图；普通模式零 Intent 读写

**Files（5）：**

- Modify: `backend/app/database/world_clock_repository.py`
- Modify: `backend/app/database/intent_repository.py`
- Modify: `backend/app/services/world_clock_service.py`
- Create: `tests/backend/test_stage3_world_tick_service.py`
- Modify: `tests/backend/test_world_clock.py`

**Interfaces:**

- Extends `WorldTickRepository.persist_run(..., mode="deterministic", fallback_used=False, intent_delta=EMPTY_INTENT_DELTA)` with backwards-compatible keyword-only arguments.
- `WorldTickService.advance(expected_world_version, mode=RuntimeMode.DETERMINISTIC)` becomes the stable signature declared in §2.
- Auto mode uses a detached Snapshot, `DeliberationContextAssembler`, `DeliberationEngine`, `run_auto_advance`, then one fresh CAS write transaction; deterministic mode continues current path and never loads Intent/Provider.

- [ ] **Step 1：盘点接口与写事务 RED**

  ```powershell
  rg -l "persist_run\(|WorldTickService\(|\.advance\(" backend tests\backend
  ```

  若发现至少两个测试文件构造 `WorldTickRepository`/`WorldTickService` 替身，先保证新增参数有默认值并逐一列入证据。RED 必须注入：Provider 回调检查 `session.in_transaction() is False`；CAS 冲突；Goal/Plan flush 失败；Run Graph flush 失败；commit 失败；post-commit cognition 失败。并发锁定已由 Task 3 独立验证，本 Task 不新增并发策略。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task9-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_stage3_world_tick_service.py tests\backend\test_world_clock.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因 mode/Intent transaction 协调尚不存在而失败；既有 deterministic 用例必须单独保持 GREEN。

- [ ] **Step 3：实现 Provider 外事务与最终原子提交**

  Auto 流程固定：读取并冻结 Snapshot→结束读事务→组装 Context 并结束 cognition read transaction→调用 Provider→新事务复读/验证→CAS→stage Intent delta→Run Graph→commit。`persist_run` 在任何异常上统一 rollback；Intent Repository 不自行 commit。新 Plan/全部 Step/首 Proposal link 同时落地，失败尝试同事务更新。

- [ ] **Step 4：聚焦 GREEN、故障注入与真实 PostgreSQL**

  重跑 Step 2。每个故障点均断言 World/三计数器/四 Intent 表/Run Graph 的前后快照；不是只断言抛异常。设置 `TEST_POSTGRES_URL` 跑本 Task transaction/rollback 用例，要求零 skip。

- [ ] **Step 5：完整矩阵、R3 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task9-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Boundary package，三席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: persist stage 3 intent with world runs`。agent 停机，等待人类提交。

---

### Task 10：演进同步 Tick Public API 与 Run Summary
**Review Level:** R2（触发：新增 / 修改 Public API 的请求、响应或状态码）
**Binding 条款锚点:** spec:§7 L144-L155、spec:§17.1 L481-L503、spec:§19 L586-L606、spec:§21.4 L651-L660、plan:L748-L805
**证据要求:** `mode` 省略=`deterministic`、只接受 `deterministic/auto`、`force_deliberation` 422；两模式同步 200/共享 409/503；`fallback_used` 语义准确；普通模式 Provider 调用与 Intent 写入计数均为零；三计数器与旧 Action/Event fixture 不变

**Files（7）：**

- Modify: `backend/app/schemas/world_clock.py`
- Modify: `backend/app/schemas/agent_run.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/api/world_clock.py`
- Modify: `tests/backend/test_world_clock.py`
- Modify: `tests/backend/test_agent_run_api.py`
- Create: `tests/backend/test_stage3_acceptance.py`

**Interfaces:**

- `WorldTickRequest.mode: Literal["deterministic", "auto"] = "deterministic"`.
- `AgentRunSummary.mode: Literal["deterministic", "auto"]` and `fallback_used: bool`.
- `get_world_tick_service(...) -> WorldTickService` owns API-layer construction from the providers stored by Task 6; response/status mapping remains in the existing route.

- [ ] **Step 1：盘点 DTO/Service 替身并写 Public API RED**

  ```powershell
  rg -l "WorldTickRequest|AgentRunSummary|WorldTickService|advance_world_clock" tests\backend tests\frontend backend frontend
  ```

  在已有 API tests 与 Stage 3 acceptance 先写：省略 mode；显式 deterministic；auto Fake 成功；auto provider failure fallback 200；非法/force 422；stale 409；repository failure 503；Run detail 四种 source 的安全形状。所有“零调用/零写入”使用非空初始数据库与 spy counter。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task10-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_world_clock.py tests\backend\test_agent_run_api.py tests\backend\test_stage3_acceptance.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因 request mode、fallback field 或 API DI 尚未暴露而失败；现有无 mode 请求仍须单独保持 GREEN。

- [ ] **Step 3：实现最小 Public 契约与依赖接线**

  Route 只把已验证 enum 交给 `WorldTickService.advance(...)`，不接受 model/NPC/force/deadline 字段。Provider/Draft/budget 失败由 service 转成 `fallback_used=true` 的正常 200；只有既有 WorldUnavailable/Persistence 映射 503，CAS 映射 409。Run detail 继续丢弃 raw provider/repair/error。

- [ ] **Step 4：完成 Backend HTTP 闭环 GREEN**

  重跑 Step 2。Stage 3 acceptance 用固定 Seed 连续 `auto` 推进，dispose Engine 后重建 app，证明 active Plan 继续；再注入失败 Provider，证明仅推进一次且 Action 合法。断言必须包括完整三计数器和 Goal/Plan 行数，不能只看 HTTP 200。

- [ ] **Step 5：完整矩阵、R2 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task10-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  本 Task 改共享 Public schema，必须按盘点结果核对所有测试替身。生成 Standard package，契约/质量两席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: expose deterministic and auto world ticks`。agent 停机，等待人类提交。

---

### Task 11：构造只读安全 Intent Projection
**Review Level:** R2（触发：修改权威投影或公开 DTO 的构造路径）
**Binding 条款锚点:** spec:§17.2 L505-L562、spec:§20 L608-L617、spec:§21.4 L651-L660、plan:L807-L868
**证据要求:** goal/plan null 对称、最多一个 Goal/一个 Plan/五 Step；安全模板不复制 Provider/evidence；Public 字段集合与完整内部字段集合满足 `0 < public < internal` 且隐藏 evidence 非空；读取零 cognition/provider/write/telemetry；Repository 故障固定安全错误

**Files（3）：**

- Create: `backend/app/schemas/intent.py`
- Create: `backend/app/services/intent_service.py`
- Create: `tests/backend/test_intent_service.py`

**Interfaces:**

- Produces `NpcGoalInfo`, `NpcPlanStepInfo`, `NpcPlanInfo`, `NpcIntentData` with exact Spec fields.
- Produces `NpcIntentService.get(npc_id: str) -> NpcIntentData` and `NpcIntentUnavailableError`.
- Service accepts `IntentRepository` and deterministic label readers; it never receives a Provider.

- [ ] **Step 1：写安全投影 RED**

  构造 active Goal/Plan/3 Steps，Provider internal description 含秘密 marker，evidence 集同时含 public/private/secret。断言返回只有规范字段，摘要来自 registry template，秘密 marker、evidence IDs/数量、scores、conditions、attempt count 全部不在 `model_dump_json()` 中；同时断言隐藏 evidence 非空，且 `0 < len(public_field_set) < len(internal_field_set)`。

  另测无 Intent 的双 null、孤立 active Goal/Plan 视为 service error、超过五 Step 拒绝、NPC 不存在、Repository 故障，以及调用前后所有表 row count/telemetry 不变。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task11-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_intent_service.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因 Intent schema/service 不存在而失败；空 evidence 或空 response 不算隐私 RED。

- [ ] **Step 3：实现固定投影**

  DTO 用 `extra="forbid"`；service 只读取当前 NPC 的 active pair，按 ordinal 投影最多五 Step。`summary/reason_text` 由 `goal_type + public NPC/location label + fixed reason code` 决定：

  ```python
  return NpcIntentData(
      npc_id=npc_id,
      goal=project_goal(active.goal),
      plan=project_plan(active.plan),
  )
  ```

  禁止 `model_validate(orm)` 直接公开内部行，禁止 catch-up、Provider 和 access telemetry。

- [ ] **Step 4：聚焦 GREEN 与泄露变异**

  重跑 Step 2。临时把 `internal_description` 映射到 `summary`，确认秘密 marker 测试 RED 后还原；再证明 service 构造图中没有 Provider 对象。

- [ ] **Step 5：完整矩阵、R2 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task11-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Standard package，契约/质量两席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: project safe npc intent summaries`。agent 停机，等待人类提交。

---

### Task 12：新增 NPC Intent Public API
**Review Level:** R2（触发：新增 / 修改 Public API 的请求、响应或状态码）
**Binding 条款锚点:** spec:§17.2 L505-L562、spec:§19 L586-L606、spec:§20 L608-L617、plan:L870-L923
**证据要求:** `GET /api/npcs/{npc_id}/intent` envelope 与字段逐项匹配；无 query/owner/scope/include-secret/write 控制面；404/503 固定安全；GET 不调用 cognition/planning/action providers且不修改任意表；现有 NPC Detail/Memory/Chat 端点不回归

**Files（2）：**

- Modify: `backend/app/api/npcs.py`
- Create: `tests/backend/test_npc_intent_api.py`

**Interfaces:**

- Adds only `GET /api/npcs/{npc_id}/intent -> ApiResponse[NpcIntentData]`.
- Reuses existing `get_session`; constructs `IntentRepository` and `NpcIntentService` without Provider/cognition dependencies.
- Maps missing NPC to 404 and `NpcIntentUnavailableError` to safe 503; no other endpoint changes.

- [ ] **Step 1：写 HTTP 契约/只读 RED**

  先测 exact JSON keys、null pair、3–5 Steps、404/503。对禁止参数分别发 query，确认 schema/router 不接受或不改变结果；注入 Planning/Action/Cognition spy 并以零调用断言。GET 前后比较 `world_state`、四 Intent 表、cognition state 和 telemetry 的非空快照。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task12-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_npc_intent_api.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 404 route-not-found 或响应形状缺失；fixture/DB 错误不算 RED。

- [ ] **Step 3：实现单一路由**

  在现有 `npcs.py` 增加静态 `/intent` path，确保不会被 `/{npc_id}` 的其他路径误匹配。只捕获已定义 missing/unavailable 异常；503 message 固定，不串出 SQL、Provider 或 evidence 内容。

- [ ] **Step 4：聚焦 GREEN 与现有 API 回归**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task12-green-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_npc_intent_api.py tests\backend\test_npc_api.py tests\backend\test_npc_chat_api.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 全部 PASS；隐私用例必须报告非空有区分度集合。

- [ ] **Step 5：完整矩阵、R2 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task12-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Standard package，契约/质量两席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add read-only npc intent api`。agent 停机，等待人类提交。

---

### Task 13：建立普通/LLM 模式的前端数据路径
**Review Level:** R1（触发：单层内的有界实现，仅 `frontend/`）
**Binding 条款锚点:** spec:§6 L128-L142、spec:§18.1 L564-L570、spec:§21.4 L651-L660、plan:L925-L989
**证据要求:** DTO 与 adapter 精确携带 mode/fallback；store 默认/Reset=`deterministic` 且每请求显式发送 mode；重复提交、409 refresh 与 canMutate 语义不变；共享 fixture 不把新增响应字段写成 optional

**Files（6）：**

- Modify: `frontend/src/types/worldTick.ts`
- Modify: `frontend/src/api/world.ts`
- Modify: `frontend/src/stores/world.ts`
- Modify: `tests/frontend/fixtures.ts`
- Modify: `tests/frontend/worldTick.spec.ts`
- Modify: `tests/frontend/world.spec.ts`

**Interfaces:**

- Adds `export type WorldAdvanceMode = 'deterministic' | 'auto'`.
- Changes `advanceWorldTick(expectedWorldVersion, mode)` and store `TickAdvancer(expectedWorldVersion, mode)` together in this Task.
- Store exposes `advanceMode`, `setAdvanceMode(mode)` and existing `advanceTick`;本 Task 不改组件或页面。

- [ ] **Step 1：盘点前端替身并写 RED**

  ```powershell
  rg -l "advanceWorldTick|TickAdvancer|advanceTick\(" frontend tests\frontend
  ```

  若新 signature 影响超过八个文件，先保留兼容 adapter（默认 deterministic），不得把第九文件塞进本 Task。RED 覆盖 adapter body exact mode、store 默认/切换/Reset、重复提交、409，以及 response `run.mode/fallback_used` 的必填类型。

- [ ] **Step 2：运行 RED**

  ```powershell
  npm --prefix frontend test -- tests/frontend/worldTick.spec.ts tests/frontend/world.spec.ts
  ```

  Expected: 因 mode 类型/state 不存在而失败；现有 adapter/store 行为测试必须单独保持 GREEN。

- [ ] **Step 3：实现类型、adapter 与 store**

  ```ts
  export type WorldAdvanceMode = 'deterministic' | 'auto'

  export async function advanceWorldTick(
    expectedWorldVersion: number,
    mode: WorldAdvanceMode,
  ): Promise<WorldTickData>
  ```

  Store 每次显式传 `advanceMode`；Reset 设置 `deterministic`。更新 fixture 的 `run.mode/fallback_used`，不得给响应字段写可选类型掩盖后端缺失。

- [ ] **Step 4：聚焦 GREEN 与 store 竞态回归**

  重跑 Step 2。临时让 Reset 保留 `auto`，确认默认/Reset 测试 RED 后还原；重跑 409 与重复请求用例，并运行 `npm --prefix frontend run type-check`。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task13-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  本 Task 改 `TickAdvancer` 测试替身，必须按盘点逐个对齐且全量。生成 Lite package，一席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add world advance mode state`。agent 停机，等待人类提交。

---

### Task 14：交付模式选择与唯一推进按钮的页面接线
**Review Level:** R1（触发：单层内的有界实现，仅 `frontend/`）
**Binding 条款锚点:** spec:§6 L128-L142、spec:§18.1 L564-L570、spec:§21.4 L651-L660、plan:L991-L1039
**证据要求:** 可访问 radio/segmented control + 唯一 mutation button；普通/LLM 标签与 store 双向同步；advancing 时两个控件同时禁用；canMutate/409 交互不倒退；Run mode 与固定 fallback 文案可见且不泄露模型、Provider、NPC 或错误细节

**Files（4）：**

- Modify: `frontend/src/components/TickPanel.vue`
- Modify: `frontend/src/views/TownView.vue`
- Modify: `tests/frontend/TickPanel.spec.ts`
- Modify: `tests/frontend/TownView.spec.ts`

**Interfaces:**

- `TickPanel` receives `mode: WorldAdvanceMode` and `canMutate: boolean`, emits `update:mode` and the existing single `advance` event.
- `TownView` binds `world.advanceMode`, calls `world.setAdvanceMode`, and retains one `world.advanceTick()` mutation path.

- [ ] **Step 1：写组件/页面 RED**

  TickPanel tests 固定 `fieldset/legend/label`、两个 radio、一个且仅一个推进 button、默认普通、切换 emit、advancing 时 radio/button 全禁用、`canMutate=false` 禁止推进，以及 result mode/fallback 固定文案。TownView tests 证明只有一个 `advanceTick` 调用入口，模式选择写入 store，Reset 后 UI 回到普通。

- [ ] **Step 2：运行 RED**

  ```powershell
  npm --prefix frontend test -- tests/frontend/TickPanel.spec.ts tests/frontend/TownView.spec.ts
  ```

  Expected: 因 mode props/emits/control 与 TownView 接线不存在而失败；既有按钮/loading/错误测试必须单独保持 GREEN。

- [ ] **Step 3：实现可访问 UI 与唯一 mutation 接线**

  TickPanel 不直接调 API/store；radio values 只为 `deterministic/auto`。按钮与模式控件共享 disabled 条件 `advancing || !canMutate`。结果根据 `tick.run.mode` 显示“普通推进/LLM 推进”，仅在 `fallback_used` 显示“部分决策已安全降级”。

- [ ] **Step 4：聚焦 GREEN、a11y 与重复提交回归**

  重跑 Step 2。断言按 label 可选中模式、键盘可达、loading 期间事件不发出第二次；运行 `npm --prefix frontend run type-check`。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task14-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Lite package，一席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add world advance mode selector`。agent 停机，等待人类提交。

---

### Task 15：建立独立 npcIntent 类型、API 与 Store
**Review Level:** R1（触发：单层内的有界实现，仅 `frontend/`）
**Binding 条款锚点:** spec:§17.2 L505-L562、spec:§18.2 L572-L584、spec:§21.4 L651-L660、plan:L1041-L1097
**证据要求:** DTO 镜像不增加内部字段；独立 store 具有 selected/data/loading/error/requestVersion；切换 NPC、关闭、Reset 的迟到响应失效；Intent 失败不污染 world/npcDetail/npcMemory/npcChat；adapter 只调用固定路径

**Files（5）：**

- Create: `frontend/src/types/intent.ts`
- Create: `frontend/src/api/intent.ts`
- Create: `frontend/src/stores/npcIntent.ts`
- Create: `tests/frontend/npcIntentApi.spec.ts`
- Create: `tests/frontend/npcIntent.spec.ts`

**Interfaces:**

- Produces `NpcGoalInfo`, `NpcPlanStepInfo`, `NpcPlanInfo`, `NpcIntentData` exact TypeScript mirrors.
- Produces `fetchNpcIntent(npcId: string) -> Promise<NpcIntentData>`.
- Produces `useNpcIntentStore` actions `select(npcId, fetcher?)`, `refresh(fetcher?)`, `clear()`; no dependency on Phaser.

- [ ] **Step 1：写 adapter/store RED**

  Adapter 测 exact GET `/api/npcs/grey/intent` 和 envelope 解包。Store 测 loading/success/null/error；用两个可控 Promise 证明切换 NPC 后旧响应不覆盖；`clear()` 后迟到响应不回填；refresh 仅对当前 selection；失败时其他 store 的非空 fixture 保持严格相等。

  ```ts
  expect(store.data?.npc_id).toBe('shir')
  expect(oldGreyResultWasIgnored).toBe(true)
  expect(worldStore.data).toStrictEqual(worldBefore)
  ```

- [ ] **Step 2：运行 RED**

  ```powershell
  npm --prefix frontend test -- tests/frontend/npcIntentApi.spec.ts tests/frontend/npcIntent.spec.ts
  ```

  Expected: 因新模块/store 不存在而失败；mock URL 不匹配必须显式 throw，禁止 catch-all 假绿。

- [ ] **Step 3：实现 DTO、adapter 与竞态安全 Store**

  Store 的每次 select/refresh/clear 都推进 request version；只有版本与 selected NPC 同时匹配才落 data/error/loading。`clear()` 恢复全空状态。API error 只转为固定 UI error，不解析或展示后端内部 message。

- [ ] **Step 4：聚焦 GREEN 与竞态变异**

  重跑 Step 2。临时移除 request-version 检查，确认迟到响应测试 RED 后还原；运行 `npm --prefix frontend run type-check`。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task15-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Lite package，一席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: add isolated npc intent store`。agent 停机，等待人类提交。

---

### Task 16：交付“当前打算”UI 与 TownView 生命周期接线
**Review Level:** R1（触发：单层内的有界实现，仅 `frontend/`）
**Binding 条款锚点:** spec:§18.2 L572-L584、spec:§21.4 L651-L660、spec:§22 L668-L684、plan:L1099-L1153
**证据要求:** Goal/next Step 默认可见、其余最多五步可展开；null/loading/error 独立；选择时加载、成功 tick 后仅刷新当前 NPC、关闭/Reset 清空；Intent 失败不阻断 Detail/Memory/Chat/地图/推进；Phaser 零 Intent 业务状态

**Files（7）：**

- Create: `frontend/src/components/NpcIntentPanel.vue`
- Modify: `frontend/src/components/NpcDetailPanel.vue`
- Modify: `frontend/src/views/TownView.vue`
- Create: `tests/frontend/NpcIntentPanel.spec.ts`
- Modify: `tests/frontend/NpcDetailPanel.spec.ts`
- Modify: `tests/frontend/TownView.spec.ts`
- Create: `tests/frontend/stage3Acceptance.spec.ts`

**Interfaces:**

- `NpcIntentPanel` is props-only: `intent`, `loading`, `error`; it emits only `retry`.
- `NpcDetailPanel` receives the same intent props and forwards retry; it does not import a store or API.
- `TownView` alone coordinates `useNpcIntentStore` with NPC selection, successful world tick, close, and Demo Reset.

- [ ] **Step 1：写组件/页面 RED**

  Component tests 固定：Goal+next Step 在折叠外；其余 Step 在 `<details>` 内；最多五条；loading/null/error/retry 的 a11y。TownView tests 使用严格 URL-aware mocks，断言 selection fetch、成功 tick refresh 当前 NPC、失败 tick不 refresh、close/reset 使迟到请求失效，以及 Intent 503 时现有非空 Detail/Memory/Chat/地图仍可交互。

  Stage 3 frontend acceptance 从普通模式推进、切 auto、显示 fallback、打开 Grey 当前打算到 Reset，未知 URL 必须 throw。

- [ ] **Step 2：运行 RED**

  ```powershell
  npm --prefix frontend test -- tests/frontend/NpcIntentPanel.spec.ts tests/frontend/NpcDetailPanel.spec.ts tests/frontend/TownView.spec.ts tests/frontend/stage3Acceptance.spec.ts
  ```

  Expected: 因组件/props/接线不存在而失败；既有 Detail/Memory/TownView 用例必须另行保持 GREEN。

- [ ] **Step 3：实现纯展示组件与页面接线**

  `NpcIntentPanel` 仅展示安全 DTO，next ordinal 与 steps 对齐失败时进入固定错误态，不自行猜测。TownView 在选中 NPC 时 `select`，成功 tick 完成后 `refresh`，关闭详情和 Demo Reset 时 `clear`；不向 `TownGameBridge`、scene、projection 或像素坐标传 Goal/Plan。

- [ ] **Step 4：聚焦 GREEN、竞态与既有 UI 回归**

  重跑 Step 2，并运行现有 `npcMemory.spec.ts`、`npcChat.spec.ts`、`TownGameBridge.spec.ts`。临时删除 close 时的 `clear()`，确认迟到响应测试 RED 后还原；运行 type-check。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task16-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Lite package，一席清零 Critical/Important，建立 approved baseline。建议提交信息：`feat: show npc goals and rolling plans`。agent 停机，等待人类提交。

---

### Task 17：同步架构、API 与数据库权威文档
**Review Level:** R1（触发：权威文档改动）
**Binding 条款锚点:** spec:§1 L11-L34、spec:§15–§17 L354-L562、spec:§23–§25 L686-L723、plan:L1155-L1206
**证据要求:** ARCHITECTURE 的 Implemented 与真实代码一致并删除 Stage 3 LangGraph 旧断言；docs/05 写同步显式编排/Session 边界；docs/06 逐字段写两个 Public API；docs/07 写 `0005` 四表/列/约束/forward-only；文档 guard 先 RED 后 GREEN

**Files（5）：**

- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/05_Engineering_Architecture.md`
- Modify: `docs/06_API_Contract.md`
- Modify: `docs/07_Database_Schema.md`
- Create: `tests/backend/test_stage3_documentation.py`

**Interfaces:**

- Documentation only; no production interface changes.
- `docs/ARCHITECTURE.md` moves only verified Stage 3 capabilities into Implemented and leaves Stage 4/Future absent.
- The documentation test checks stable headings/contract tokens, not prose formatting or line numbers.

- [ ] **Step 1：写文档 Guard RED**

  固定检查 `0005_stage3_goals_plans`、四表、`deterministic/auto`、`fallback_used`、Intent endpoint、Provider 外事务、四种 Proposal source、no LangGraph/LangChain。Guard 还必须证明旧 Proposed 行“Stage 3 采用 LangGraph”已删除，而不是只检查新文本存在。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task17-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_stage3_documentation.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因四份文档仍描述 Stage 2/Proposed 状态而失败。

- [ ] **Step 3：按实现逐字段更新文档**

  只记录 Task 1–16 已落地并通过 gate 的真实接口。不得把 Stage 4 queue/SSE/outbox、Agent Lab、LangGraph/LangChain 或 live smoke 未执行写成 Implemented。API 文档列 exact request/response/status；DB 文档列 exact columns/constraints/index 与 legacy null/downgrade。

- [ ] **Step 4：聚焦 GREEN 与事实对照**

  重跑 Step 2；再用 `rg` 对照 migration、ORM、Pydantic schema 与 router 中的每个 token。任何文档与实现不一致，修文档或回到产生实现的 Task，不能在文档 Task 偷改生产代码。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task17-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  生成 Lite package，一席逐字段核对并清零 Critical/Important，建立 approved baseline。建议提交信息：`docs: document stage 3 runtime contracts`。agent 停机，等待人类提交。

---

### Task 18：同步开发验收、README 与 CURRENT_STATE
**Review Level:** R1（触发：权威文档改动）
**Binding 条款锚点:** spec:§21.5 L662-L666、spec:§22 L668-L684、spec:§23–§24 L686-L709、spec:§25 L711-L723、plan:L1208-L1258
**证据要求:** docs/14 提供真实 Fake/live/PostgreSQL 配置与命令；README 展示普通/LLM/Intent/fallback 可复现路径且不夸大；CURRENT_STATE 记录真实 HEAD/工作树/测试数字/Review baseline/未执行 smoke；guard 先 RED 后 GREEN

**Files（4）：**

- Modify: `docs/14_Development_Environment.md`
- Modify: `README.md`
- Modify: `CURRENT_STATE.md`
- Create: `tests/backend/test_stage3_delivery_documentation.py`

**Interfaces:**

- Documentation/state only; no production interface changes.
- Live Planning/Action smoke is documented as conditional manual evidence and never counted as passing without Key.
- CURRENT_STATE records the most recent approved Task baseline; Stage close baseline is written only after the final R3 gate passes.

- [ ] **Step 1：写交付文档 Guard RED**

  测试固定 docs/14 的全部新 env 名、8 秒/30 秒边界、Fake 默认、真实 PostgreSQL命令、无 Key 不宣称 live；README 固定玩家操作闭环与 fallback；CURRENT_STATE 固定 Stage 3 当前状态、真实数字位置和 deferred/risk 段。Guard 不能硬编码一次运行的通过数量。

- [ ] **Step 2：运行 RED**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task18-red-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_stage3_delivery_documentation.py tests\backend\test_story_content.py tests\backend\test_deploy.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  Expected: 因三份文档没有 Stage 3 真实状态而失败；若旧标题顺序测试失败，先确认不是误删既有契约段。

- [ ] **Step 3：只按实测结果更新三份文档**

  README 的演示从默认普通推进开始，显式切 LLM，再查看当前打算和 fallback；不出现模型选择/force。docs/14 区分自动 Fake、显式 live smoke 和 PostgreSQL opt-in。CURRENT_STATE 不预写“Stage 完成”，只记录 Task 18 gate 的真实输出、最新 approved baseline 与最终 Stage Gate 待办。

- [ ] **Step 4：聚焦 GREEN 与陈述审计**

  重跑 Step 2；逐条搜索 `LangGraph|LangChain|Celery|Redis|SSE|202|investigate`，确保只在“未实现/后置”语境出现。未配置 live Key 时必须明确“未执行、未宣称通过”。

- [ ] **Step 5：完整矩阵、R1 Gate 与停机**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-task18-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```

  把真实数字写回 CURRENT_STATE 后重新运行文档 guard 与完整矩阵；若写数字不影响代码，完整矩阵仍不可省。生成 Lite package，一席清零 Critical/Important，建立 approved baseline。建议提交信息：`docs: prepare stage 3 acceptance handoff`。agent 停机，等待人类提交。

---

## 3. Stage 3 最终关闭 Gate

**Review Level:** R3（触发：Stage 关闭）
**Binding 条款锚点:** spec:§21.5 L662-L666、spec:§22 L668-L684、spec:§25 L711-L723、plan:L1260-L1301
**证据要求:** 最近 approved baseline 到当前零表外 drift；Backend/Frontend/type-check/build 全绿且无新增 skip/warning；真实 PostgreSQL migration/约束/并发/rollback/重启零 skip；固定 Fake 完整闭环；有 Key 才报告 live smoke；三席 Critical/Important 清零

最终 Gate 不允许顺手修代码。若发现缺陷，按 finding 风险新建不超过八文件、只命中一类条款的 fix Task，走 RED/GREEN/完整矩阵与独立 gate 后再回来。

- [ ] **Step 1：核对范围与 approved baseline**

  从最新 approved baseline 执行只读 `status/diff/hash-object` 手工漂移检查，输出必须是 `MATCH` 或经内容哈希证明的 `HEAD_MOVED_CONTENT_SAME`；`INDEX_DIRTY` 报告人类，`OUT_OF_SCOPE_DRIFT` 不得继续。

- [ ] **Step 2：运行完整关闭矩阵**

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-close-full-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $stage3Basetemp
  npm --prefix frontend test
  npm --prefix frontend run type-check
  npm --prefix frontend run build
  ```

  记录 passed/skipped/warning、frontend 文件/用例数与两个 exit code；不引用 Task 18 的历史数字。

- [ ] **Step 3：运行真实 PostgreSQL 17 验收**

  在独立测试数据库/schema 设置 `TEST_POSTGRES_URL`，至少运行：

  ```powershell
  $stage3Basetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-stage3-close-postgres-" + [guid]::NewGuid())
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_schema_migrations.py tests\backend\test_postgres_runtime.py tests\backend\test_intent_repository.py tests\backend\test_stage3_world_tick_service.py tests\backend\test_stage3_acceptance.py -q -p no:cacheprovider --basetemp $stage3Basetemp
  ```

  相关 PostgreSQL 用例必须零 skip，覆盖 `0004→0005`、四表/列/约束、竞争 auto、rollback 和重启。若使用 Compose，结束只允许不带 `-v` 的 `docker compose down`。

- [ ] **Step 4：执行 Fake 闭环与条件式 Live Smoke**

  固定 Fake 下实际演示：普通推进→LLM 推进→跨多个 tick 的 Plan→重启→关键 Quest Event/Claim→replan→Provider failure fallback→Intent UI。若 Planning/Action live 配置与 Key 齐全，再各做一次受控 smoke；没有 Key 时明确写“未配置、未执行、未宣称通过”，不得阻塞 Fake/普通路径。

- [ ] **Step 5：R3 Boundary Review 与人类关闭**

  生成不超过目标 120 KB 的 Boundary package：最新通过 R2/R3 baseline→当前 delta、binding 摘录、证据索引、风险/Ruling、不变量断言表和本次实测输出。契约、质量、不变量三席独立 Review；Critical/Important 清零后建立 `stage3-close-approved` baseline，更新 CURRENT_STATE 并再次做 docs guard。agent 提交关闭报告后停机，由人类 Review 并手动提交；不得自动进入 Stage 4。

## 4. 明确不在本 Plan 内

- Stage 4 的异步 submission、202、Outbox、Worker、锁、idempotency、SSE、恢复、backoff、成本/延迟账本。
- LangGraph、LangChain、Celery、Redis 或新基础设施依赖。
- 新 action、NPC-to-NPC 长对话、Relationship、Claim 传播、社会图、Agent Lab、模型/Prompt 控制。
- Forest Embers 扩写、战斗、装备、经济、大地图、新 NPC 或独立向量数据库。

任何上述能力即使出现在 Roadmap 或 `ARCHITECTURE.md` Proposed 段，也不授权本 Plan 实现。
