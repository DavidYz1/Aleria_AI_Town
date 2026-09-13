# Test Suite Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for inline execution, or `superpowers:subagent-driven-development` only when the user explicitly requests sub-agents. Steps use checkbox (`- [ ]`) syntax for tracking. 每个 Task 结束即停机，等待独立 Review、用户 Review 与人类手动提交；不得连续执行两个 Task。

**Goal:** 在不改变生产行为的前提下，提高 Aleria AI Town 测试的失败判别力，消除已确认的重复与跨测试耦合，并把套件收敛为 unit/component 两层。

**Architecture:** 先处理测试可信度、共享 support、重复断言和历史 acceptance，再执行纯路径迁移。Backend 的数据库/Repository/Service/ASGI/Migration 测试归 component；Frontend 的 Vue/Phaser/组合测试归 component；其余纯逻辑、API adapter 与 Store 归 unit。Acceptance/PostgreSQL 只用 marker 或命名表达，不增加物理层。

**Tech Stack:** Python 3.11+、pytest、SQLAlchemy、FastAPI/httpx ASGITransport、Vue 3、Pinia、TypeScript 5.7、Vitest 3、Phaser 3.90.0。

**Spec:** `docs/superpowers/specs/2026-09-13-test-suite-cleanup-decision-record-cn.md`（批准的测试清理决策记录，不是产品 Spec）

## 0. 执行前置条件与全局约束

- 本 Plan 与决策记录必须先经用户 Review，并由人类手动提交；未批准不得执行 Task 1。
- Task 1 开始前按 `AGENTS.md`“开发前必读”六项顺序重读。运行 `git log -1 --oneline`、`git status --porcelain -uall` 和 approved baseline 漂移检查；当前未跟踪的 Stage 3 Spec/Plan 以及本清理两份文档必须由人类提交或在 baseline ledger 中显式裁定，任何其他表外漂移均阻塞执行。
- **不改生产代码：** scope 仅限 `tests/` 与 `frontend/vite.config.ts` 的测试解析配置；不得修改 `backend/app/`、`frontend/src/`、migration、seed data、Public API 或权威文档。
- **Task 粒度：** 每个 Task 最多八个逻辑文件，并且只命中 `docs/AI_REVIEW_POLICY.md` §2.3 的一类触发条款。重命名/移动按一个逻辑文件计；若出现第九个文件或第二类触发条款，立即停机拆 Task。
- **严格 TDD：** 新增或强化行为必须先 RED，并确认失败是目标判别能力缺失；import、拼写、fixture 或权限错误不算 RED。纯搬移/提取/合并不创造行为，先记录聚焦测试 item 数与结果，改后要求同一行为集 GREEN。
- **判别性证据：** 所有“不泄露 / 不发生”断言满足 `0 < returned < total`；删除测试必须给出“被删断言 → 存活测试名”的映射；mock 边界调整必须以真实 Store/Repository 或签名扫描证明没有走错分支。
- **不执行 git 写命令：** 禁止 `git add/commit/reset/checkout/switch/clean/stash/push`。每个 Task 只给建议提交信息并停机，由人类 Review、提交。
- **每个 Task 一个 Gate：** Task Gate 最低 R1。Critical/Important 未清零不得进入下一 Task；修复轮可以缩小 reviewer 读取范围，不能缩小 implementer 验证矩阵。
- **完整验证矩阵不可省略：** 每个 Task 的聚焦 GREEN 后都必须在沙箱外运行以下三条命令，记录真实数字与 exit code；不得新增 skip 或 warning。

```powershell
$suiteBasetemp = Join-Path ([System.IO.Path]::GetTempPath()) ("aleria-test-cleanup-" + [guid]::NewGuid())
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp $suiteBasetemp
npm --prefix frontend test
npm --prefix frontend run type-check
```

- 审计实测起点为 Backend `720 passed, 5 skipped, 1 warning`，Frontend `30 files / 209 tests passed`。后续数字必须使用当次本机输出；已批准的测试删除可以降低 passed/item 数，但 `5 skipped / 1 warning` 只能保持或减少，不能增加。
- 改动任何被至少两个测试文件构造过替身的接口时，强制执行完整矩阵；本 Plan 不授权改这些生产接口。
- 不新增依赖、coverage 门槛、浏览器 E2E、LangChain、LangGraph、Celery、Redis 或独立向量库。

## 1. 文件职责与迁移终态

| 路径 | 职责 |
| --- | --- |
| `tests/backend/unit/` | 纯模型/schema/config/policy/registry、隔离 Provider 与测试护栏 |
| `tests/backend/component/` | 数据库、Repository、Service、ASGI、Migration、seed/deploy、acceptance |
| `tests/backend/support/` | cognition fixture/helper、共享 doubles、仓库路径、签名扫描 |
| `tests/frontend/unit/` | 纯函数、API adapter、Pinia Store、数据投影 |
| `tests/frontend/component/` | Vue、TownView、Phaser、acceptance |
| `tests/frontend/support/` | fixture、deferred、TownView harness |

`tests/backend/conftest.py` 保留在 Backend 根目录，以便 pytest 自动作用于两个子层。路径迁移完成后，`tests/frontend/fixtures.ts` 兼容转发文件必须删除。

---

### Task 1：修复 Reflection 权限测试的空集合假绿
**Review Level:** R1（触发：仅测试改动，但改变断言语义）
**Binding 条款锚点:** spec:§4 L62-L67、spec:§5 L69-L76、plan:L51-L97
**证据要求:** 同一测试的临时“删除 reflection 行”mutant 必须 RED 为 `0 < 0`；恢复真实路径后必须证明 `0 < reflections < all memories` 且每条仍为 `secret/internal_only`

**Files（1）：**

- Modify: `tests/backend/test_reflection_engine.py`

- [ ] **Step 1：建立判别性 RED**

  在 `test_permission_change_during_provider_cannot_publish_previously_secret_input` 中、读取 `reflections` 之前临时删除刚生成的 reflection 并提交，然后重新查询并加入目标断言：

  ```python
  session.query(Memory).filter(Memory.memory_type == "reflection").delete()
  session.commit()
  reflections = tuple(
      session.scalars(select(Memory).where(Memory.memory_type == "reflection"))
  )
  all_memories = tuple(session.scalars(select(Memory)))
  assert 0 < len(reflections) < len(all_memories)
  ```

  运行：

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\backend\test_reflection_engine.py::test_permission_change_during_provider_cannot_publish_previously_secret_input -q -p no:cacheprovider --basetemp (Join-Path $env:TEMP ("aleria-reflection-red-" + [guid]::NewGuid()))
  ```

  Expected: FAIL，失败原因是 reflection 集合为空，而不是 fixture/import 错误。

- [ ] **Step 2：移除 mutant，保留真实强化断言**

  删除临时 delete/commit；在读取 `reflections` 后读取所有 `Memory`，保留：

  ```python
  assert 0 < len(reflections) < len(all_memories)
  assert all(
      (row.secrecy, row.disclosure_scope) == ("secret", "internal_only")
      for row in reflections
  )
  ```

- [ ] **Step 3：运行聚焦 GREEN、完整矩阵和 R1 Gate**

  运行同一 node id，Expected: PASS；随后运行 §0 完整矩阵。生成 scoped R1 package，Critical/Important 清零后停机。建议提交信息：`test: make reflection privacy assertion non-vacuous`。

### Task 2：加入测试替身签名漂移守卫
**Review Level:** R1（触发：Task Gate 门位下限；仅新增测试与测试 support，不改变既有断言或 mock）
**Binding 条款锚点:** spec:§4 L62-L67、spec:§5 L69-L76、plan:L98-L135
**证据要求:** 人工缺少 `timeout_seconds` 的 AST fixture 必须 RED；仓库扫描必须枚举并通过 `embed`、`generate_reply`、`catch_up_owner` 三类 test double

**Files（3）：**

- Create: `tests/backend/support/__init__.py`
- Create: `tests/backend/support/signature_guard.py`
- Create: `tests/backend/unit/test_test_double_contracts.py`

- [ ] **Step 1：写会失败的签名比较测试**

  `signature_guard.py` 先只返回空 tuple；测试用以下坏样本要求报告 `embed` 不兼容：

  ```python
  BAD_DOUBLE = """
  class BadEmbedding:
      def embed(self, text):
          return None
  """
  assert incompatible_methods(BAD_DOUBLE, {"embed": embedding_shape}) == ("BadEmbedding.embed",)
  ```

  运行 `test_test_double_contracts.py -q`，Expected: FAIL because returned offenders are empty。

- [ ] **Step 2：实现最小 AST 签名比较器**

  用 `ast.parse` 比较 class method 的 positional/keyword-only 参数名、必填性与 async/sync 形态。生产基准固定从 `inspect.signature(EmbeddingProvider.embed)`、`inspect.signature(ChatProvider.generate_reply)`、`inspect.signature(CognitionProjectionService.catch_up_owner)` 读取，不在测试中复制接口字符串。

- [ ] **Step 3：扫描真实测试树**

  遍历 `tests/backend/**/*.py`，忽略 support 守卫自身的 BAD fixture，断言三类同名 class method 均兼容，并在 assertion message 列出 `path:line Class.method`。运行聚焦测试，Expected: BAD fixture 被检出且真实树零 offender。

- [ ] **Step 4：运行完整矩阵和 R1 Gate**

  运行 §0 完整矩阵并停机。建议提交信息：`test: guard shared test-double signatures`。

### Task 3：集中仓库路径 helper
**Review Level:** R1（触发：Task Gate 门位下限；测试 support 的有界重构）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L136-L169
**证据要求:** 搬移前后五个聚焦文件 item 数相同，且所有文件都从同一个 `REPO_ROOT` 解析 alembic/scripts/docs

**Files（6）：**

- Create: `tests/backend/support/paths.py`
- Modify: `tests/backend/legacy_sqlite_factory.py`
- Modify: `tests/backend/test_deploy.py`
- Modify: `tests/backend/test_schema_migrations.py`
- Modify: `tests/backend/test_seed_world.py`
- Modify: `tests/backend/test_start_dev.py`

- [ ] **Step 1：记录聚焦 characterization**

  对五个 `test_*.py` 运行 `--collect-only -q` 与聚焦测试，记录 item 数和结果。

- [ ] **Step 2：建立单一稳定路径**

  `tests/backend/support/paths.py` 只定义：

  ```python
  from pathlib import Path

  REPO_ROOT = Path(__file__).resolve().parents[3]
  ```

  五个消费文件改为 `from tests.backend.support.paths import REPO_ROOT`；删除自己的 `parents[2]` 计算，Alembic 路径统一写成 `REPO_ROOT / "alembic.ini"`。

- [ ] **Step 3：验证无行为变化并停机**

  重跑相同 collect/聚焦集合，item 数必须一致；再跑 §0 完整矩阵和 R1 Gate。建议提交信息：`test: centralize repository path resolution`。

### Task 4：删除瞬时文档断言与脆弱标题顺序
**Review Level:** R1（触发：仅测试改动，但改变断言语义）
**Binding 条款锚点:** spec:§3.3 L53-L60、spec:§5 L69-L76、plan:L170-L191
**证据要求:** 每条删除断言都映射到保留的正向契约；不得修改 README、CURRENT_STATE 或权威文档来迎合测试

**Files（2）：**

- Modify: `tests/backend/test_stage2_documentation.py`
- Modify: `tests/backend/test_story_content.py`

- [ ] **Step 1：记录存活契约**

  先运行两个文件并记录：migration `0004`、memory endpoint、post-commit、配置变量、Demo reset 与 AI workflow 的正向断言均 PASS。

- [ ] **Step 2：删除低价值断言**

  删除 `test_current_state_records_stage2_task5_incremental_rereview_complete` 和精确 stale 文案 blacklist 测试；`test_readme_is_game_first_deployable_and_documents_ai_workflow` 删除 `ordered_headings/positions`，保留配置、接口、workflow 与过时 claim 的正向/安全断言。两个文件都改用 `tests.backend.support.paths.REPO_ROOT`。

- [ ] **Step 3：验证删除映射并停机**

  重跑两个文件；记录 item 数只按批准的删除减少 2。运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: remove transient documentation assertions`。

### Task 5：把 cognition fixture/helper 移出测试模块
**Review Level:** R1（触发：仅测试改动，但改变 fixture/mock 边界）
**Binding 条款锚点:** spec:§3.2 L46-L51、spec:§5 L69-L76、plan:L192-L218
**证据要求:** `rg 'tests\.backend\.test_' tests/backend` 不再命中本 Task 的 cognition helper imports；七个文件 item 数不变

**Files（7）：**

- Create: `tests/backend/support/cognition.py`
- Modify: `tests/backend/test_cognition_repository.py`
- Modify: `tests/backend/test_memory_retrieval.py`
- Modify: `tests/backend/test_reflection_engine.py`
- Modify: `tests/backend/test_cognition_projection.py`
- Modify: `tests/backend/test_embedding_provider.py`
- Modify: `tests/backend/test_chat_context.py`

- [ ] **Step 1：记录跨模块依赖与聚焦结果**

  用 `rg -n 'tests\.backend\.test_'` 保存本 Task 相关命中，运行六个消费测试文件的 collect-only 与聚焦测试。

- [ ] **Step 2：提取 fixture/helper**

  将 `source_session`、`memory_session`、`add_memory`、`authority`、`derived_counts`、`add_turn` 原样移入 `tests.backend.support.cognition`。消费文件只从 support 导入；不得改变参数默认值、commit/rollback 或 seed 顺序。

- [ ] **Step 3：验证无跨测试导入并停机**

  重跑相同集合，item 数和结果必须一致；本 Task 的跨测试 import 命中必须为零。运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: centralize cognition fixtures`。

### Task 6：集中被多文件复用的测试替身
**Review Level:** R1（触发：仅测试改动，但改变 mock 边界）
**Binding 条款锚点:** spec:§3.2 L46-L51、spec:§4 L62-L67、plan:L219-L244
**证据要求:** shared doubles 保持生产签名；消费文件不再从其他 test module 导入 `FailingCoreRepository` 或 `_CapturingProvider`

**Files（6）：**

- Create: `tests/backend/support/doubles.py`
- Modify: `tests/backend/test_cognition_projection.py`
- Modify: `tests/backend/test_chat_service.py`
- Modify: `tests/backend/test_chat_context.py`
- Modify: `tests/backend/test_player_quest_service.py`
- Modify: `tests/backend/test_world_clock.py`

- [ ] **Step 1：记录 characterization**

  运行五个消费文件的 collect-only 和聚焦测试，另运行 Task 2 的签名守卫。

- [ ] **Step 2：移动共享 doubles**

  原样移动 `FailingCoreRepository` 与 `_CapturingProvider` 到 `tests.backend.support.doubles`，导出名改为 `FailingCoreRepository`、`CapturingChatProvider`；消费文件更新 import。不得改变异常类型、request capture、reply/fallback 内容或方法签名。

- [ ] **Step 3：验证 mock 边界并停机**

  重跑相同文件与签名守卫，item 数一致、真实扫描零 offender；运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: share cross-suite doubles explicitly`。

### Task 7：合并 Settings 测试
**Review Level:** R1（触发：仅测试改动，但改变断言组织）
**Binding 条款锚点:** spec:§3.2 L46-L51、spec:§5 L69-L76、plan:L245-L267
**证据要求:** 合并前后所有参数 case 数一致；cognition work bounds 与 chat/embedding bounds 均有明确 node id

**Files（3）：**

- Create: `tests/backend/unit/test_settings.py`
- Delete: `tests/backend/test_chat_config.py`
- Delete: `tests/backend/test_cognition_config.py`

- [ ] **Step 1：记录原始参数 case 数**

  对两个源文件运行 `--collect-only -q`，保存完整 node id 列表。

- [ ] **Step 2：无损合并**

  将两个文件的测试原样迁入 `unit/test_settings.py`。只允许统一 import、格式与 describe-by-name；不得合并掉不同 field/value 参数、默认值断言或 safe fallback 配置。

- [ ] **Step 3：比较 node/参数覆盖并停机**

  新文件 collect item 数必须等于两个源文件之和；聚焦 GREEN 后运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: consolidate settings coverage`。

### Task 8：建立 Frontend 测试别名与 support fixture
**Review Level:** R1（触发：单层内的有界实现，仅 frontend 测试配置）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L268-L295
**证据要求:** Phaser alias 与 fixture named exports 均从新 support 文件解析；兼容转发期间 30 个 spec 文件全部通过

**Files（3）：**

- Modify: `frontend/vite.config.ts`
- Create: `tests/frontend/support/fixtures.ts`（从 `tests/frontend/fixtures.ts` 移动实际内容）
- Modify: `tests/frontend/fixtures.ts`（临时兼容转发；最终在 Task 24 删除）

- [ ] **Step 1：记录前端解析基线**

  运行 `npm --prefix frontend test`，记录 `30 files / 209 tests`；运行 type-check。

- [ ] **Step 2：建立稳定别名与兼容转发**

  在 Vite `resolve.alias` 增加 `@app -> frontend/src`、`@test-support -> tests/frontend/support`，把 `phaser` alias 改指向 `support/fixtures.ts`。实际 fixture 内容移入 support，并把其类型 import 改为 `@app/types/...`；根 `fixtures.ts` 仅保留：

  ```ts
  export { default } from './support/fixtures'
  export * from './support/fixtures'
  ```

- [ ] **Step 3：验证兼容层并停机**

  前端全量仍须为 30 files / 209 tests；再运行 §0 其余矩阵与 R1 Gate。建议提交信息：`test: add stable frontend test imports`。

### Task 9：参数化 NPC 资源 Store 的共同生命周期
**Review Level:** R1（触发：仅测试改动，但改变断言语义与 mock 边界）
**Binding 条款锚点:** spec:§3.2 L46-L51、spec:§5 L69-L76、plan:L296-L319
**证据要求:** detail/memory 两个真实 Pinia Store 都通过 loading、not-found、stale response、close invalidation、empty refresh 五项共同契约；资源特有错误和 refresh payload 仍各自保留

**Files（4）：**

- Create: `tests/frontend/support/deferred.ts`
- Create: `tests/frontend/unit/npcResourceStoreContract.spec.ts`
- Modify: `tests/frontend/npcDetail.spec.ts`
- Modify: `tests/frontend/npcMemory.spec.ts`

- [ ] **Step 1：记录两个 Store 的 characterization**

  先对两个源文件运行 verbose，并记录五组共同 lifecycle 测试各自的 10 个实例：loading、not-found、stale response、close invalidation、empty refresh。共同接口只描述 `selectedNpcId/data/loading/error/selectNpc/refresh/close`，不改生产 Store。

- [ ] **Step 2：接入两个真实 Store**

  用 `describe.each` 驱动两个真实 Store，复用 `deferred<T>()`。从原文件删除恰好五组重复 lifecycle tests；API endpoint、ordinary retry/error copy 与 refresh data replacement 继续留在各自文件。

- [ ] **Step 3：验证行为集合没有缩减并停机**

  三个 spec 聚焦 GREEN；输出“旧测试名 → 新 contract case/保留测试名”映射。运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: share npc resource store contract`。

### Task 10：按组合责任拆分 TownView 巨型测试
**Review Level:** R1（触发：仅测试改动，但改变 mock 边界）
**Binding 条款锚点:** spec:§3.2 L46-L51、spec:§5 L69-L76、plan:L320-L354
**证据要求:** 原 35 个 TownView node id 全部映射到五个新文件；共享 harness 不替换 Pinia Store，只集中 mount、API stub、deferred 和查询 helper

**Files（7）：**

- Create: `tests/frontend/support/townViewHarness.ts`
- Create: `tests/frontend/component/TownViewWorldQuest.spec.ts`
- Create: `tests/frontend/component/TownViewNpcChat.spec.ts`
- Create: `tests/frontend/component/TownViewMovement.spec.ts`
- Create: `tests/frontend/component/TownViewReset.spec.ts`
- Create: `tests/frontend/component/TownViewMemory.spec.ts`
- Delete: `tests/frontend/TownView.spec.ts`

- [ ] **Step 1：记录 35 项 characterization**

  运行旧文件 `--reporter=verbose` 并保存 35 个名称；按 world/quest、NPC/chat、movement、reset、memory 建立映射表。

- [ ] **Step 2：提取 harness 并搬移测试**

  Harness 只导出 `teleportPlayer`、`deferred`、`createStore`、`mountTownView`、`mockNpcGets`、`callsTo`、`openRyanDetail` 和统一 `afterEach` cleanup。按以下固定分组原样搬移：

  - WorldQuest（9）：mount load、travel、quest advance/conflict、quest load failure、canonical render、loading/retry/incomplete world。
  - NpcChat（9）：detail open/close、independent chat、send、per-NPC restore、tick isolation、late response、detail refresh、map selection、map/DOM ordering。
  - Movement（8）：host stability、background refresh recovery、NPC projection、walk persistence/serialization、stale walk discard、两类 no-teleport failure。
  - Reset（4）：cancel、success/cache clear、pending mutation block、Backend failure。
  - Memory（5）：open、isolated failure/retry、world-version refresh、post-chat refresh、close clear。

  “加载/错误/空数据”等 TownView 组合断言仍保留，不用 Store 单测替代 composition wiring。

- [ ] **Step 3：验证 35 项完整性并停机**

  新目录 verbose 输出必须仍有 35 个 TownView tests，名称集合无丢失；运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: split TownView behavior suites`。

### Task 11：合并 Backend 历史 acceptance
**Review Level:** R1（触发：仅测试改动，但改变断言语义与 mock 边界）
**Binding 条款锚点:** spec:§3.3 L53-L60、spec:§5 L69-L76、plan:L355-L381
**证据要求:** phase1d 的 quest-aware chat/read-only/fallback 独有断言迁入当前 chat acceptance；其余删除项逐条映射到 player quest API/service 与 chat acceptance

**Files（3）：**

- Modify: `tests/backend/test_chat_acceptance.py`
- Delete: `tests/backend/test_phase1d_acceptance.py`
- Delete: `tests/backend/test_phase1e_acceptance.py`

- [ ] **Step 1：建立 survivor 映射并先跑存活测试**

  证明五阶段状态/version/objective/recent events 已由 `test_missing_child_api_completes_all_five_versioned_transitions` 与 `test_service_returns_story_event_descriptions_for_the_full_quest` 覆盖；证明三 NPC distinct replies 已由 `test_same_mock_question_produces_distinct_character_replies` 覆盖。

- [ ] **Step 2：先迁移独有 acceptance 行为**

  在 `test_chat_acceptance.py` 新增 quest-aware chat 场景：accept quest、travel castle、分别在 accepted/briefed 状态聊天，断言 Provider request 的两个 objective、quest snapshot 前后相同、message count 精确 +4；fallback 再断言 provider=`mock`、`fallback_used=True`、quest snapshot 不变。

- [ ] **Step 3：迁移 characterization 与删除**

  先让迁入 `test_chat_acceptance.py` 的场景在原历史文件仍存在时 GREEN，并逐字段对比断言；随后删除两个历史文件。记录 Backend item 净变化和完整 survivor 表，不用 import/fixture 故障伪造 RED。

- [ ] **Step 4：完整矩阵与停机**

  运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: consolidate historical backend acceptance`。

### Task 12：删除重复的 Frontend Phase 2 acceptance
**Review Level:** R1（触发：仅测试改动，但改变断言语义）
**Binding 条款锚点:** spec:§3.3 L53-L60、spec:§5 L69-L76、plan:L382-L403
**证据要求:** 两个删除场景分别映射到 AppFlow、TownView、playerQuest、TownGameHost/TownSceneInput 的存活测试；Stage 2 degradation acceptance 仍通过

**Files（2）：**

- Delete: `tests/frontend/phase2Acceptance.spec.ts`
- Move: `tests/frontend/stage2Acceptance.spec.ts` → `tests/frontend/component/stage2.acceptance.spec.ts`

- [ ] **Step 1：运行 survivor 集合**

  先运行 `AppFlow.spec.ts`、五个 TownView spec、`playerQuest.spec.ts`、`TownGameHost.spec.ts`、`TownSceneInput.spec.ts` 与 `stage2Acceptance.spec.ts`，记录通过项。

- [ ] **Step 2：删除/改名并修正 import**

  删除 Phase 2 两个重复场景；Stage 2 文件移动后使用 `@app` 与 `@test-support/fixtures`，测试正文不改。

- [ ] **Step 3：验证净减少恰好 2 项并停机**

  重跑 survivor 集合，Stage 2 两项仍 PASS，Frontend item 数恰好减少 2。运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: retire duplicate phase2 acceptance`。

### Task 13：注册 acceptance 与 PostgreSQL marker
**Review Level:** R1（触发：仅测试改动，但改变测试选择边界）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§4 L62-L67、plan:L404-L433
**证据要求:** `pytest --markers` 显示两个 marker；`-m acceptance` 与 `-m postgres` 收集集合可解释；默认矩阵 skip/warning 不增加

**Files（5）：**

- Modify: `tests/backend/conftest.py`
- Modify: `tests/backend/test_chat_acceptance.py`
- Modify: `tests/backend/test_stage2_acceptance.py`
- Modify: `tests/backend/test_postgres_runtime.py`
- Modify: `tests/backend/test_chat_repository.py`

- [ ] **Step 1：写 marker 注册 RED**

  先给 acceptance 文件加 `pytestmark = pytest.mark.acceptance`，给 PostgreSQL 文件和 `postgres_database_url` 参数加 `postgres` mark；以 `--strict-markers --collect-only` 运行，Expected: FAIL because markers are not registered。

- [ ] **Step 2：在 conftest 注册 marker**

  通过 `pytest_configure` 增加：

  ```python
  config.addinivalue_line("markers", "acceptance: cross-module user journey")
  config.addinivalue_line("markers", "postgres: requires TEST_POSTGRES_URL")
  ```

- [ ] **Step 3：验证选择边界并停机**

  `--strict-markers --collect-only` 必须通过；分别记录 `-m acceptance` 与 `-m postgres` 的收集数。运行 §0 完整矩阵与 R1 Gate。建议提交信息：`test: mark acceptance and postgres suites`。

### Task 14：迁移 Backend unit（批次 A）
**Review Level:** R1（触发：Task Gate 门位下限；八个测试文件的纯路径迁移）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L434-L448
**证据要求:** 八个文件移动前后 node id 尾部与 item 数一致；无断言、fixture 或 mock 变化

**Files（8 个逻辑移动）：**

- `test_action_explanation.py`、`test_action_registry.py`、`test_chat_models.py`、`test_chat_provider_factory.py`
- `test_chat_schemas.py`、`test_cognition_models.py`、`test_database_connection.py`、`test_missing_child_quest.py`
- Destination: `tests/backend/unit/`

- [ ] **Step 1：记录 collect-only 清单。** 对八个源文件保存 node id 与 item 数。
- [ ] **Step 2：使用普通文件移动完成八个 rename。** 不使用 `git mv`；不改测试正文。
- [ ] **Step 3：重跑相同清单与 §0 完整矩阵。** 路径前缀之外的 node id、item 数与结果一致；R1 Gate 后停机。建议提交信息：`test: group backend unit suite batch one`。

### Task 15：迁移 Backend unit（批次 B）
**Review Level:** R1（触发：Task Gate 门位下限；七个测试文件的纯路径迁移）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L449-L463
**证据要求:** 七个文件移动前后 item 数一致；文档测试继续通过 shared REPO_ROOT

**Files（7 个逻辑移动）：**

- `test_mock_chat_provider.py`、`test_openai_compatible_provider.py`、`test_perception_policy.py`
- `test_player_quest_models.py`、`test_reflection_provider.py`、`test_story_content.py`、`test_stage2_documentation.py`
- Destination: `tests/backend/unit/`

- [ ] **Step 1：记录 collect-only 与聚焦基线。**
- [ ] **Step 2：普通移动七个文件；不改断言。**
- [ ] **Step 3：重跑相同集合、Task 2 签名守卫和 §0 完整矩阵。** item 数一致后 R1 Gate 停机。建议提交信息：`test: group backend unit suite batch two`。

### Task 16：迁移 Backend component（批次 A）
**Review Level:** R1（触发：Task Gate 门位下限；八个测试文件的纯路径迁移）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L464-L478
**证据要求:** 八个文件移动前后 item 数一致；support imports 不回退成 test-module imports

**Files（8 个逻辑移动）：**

- `test_agent_orchestrator.py`、`test_agent_run_api.py`、`test_agent_run_repository.py`、`test_chat_acceptance.py`
- `test_chat_context.py`、`test_chat_repository.py`、`test_chat_service.py`、`test_cognition_projection.py`
- Destination: `tests/backend/component/`

- [ ] **Step 1：记录 collect-only 与聚焦基线。**
- [ ] **Step 2：普通移动八个文件；只在必要时更新 support import，不改行为。**
- [ ] **Step 3：重跑、执行跨测试 import 扫描及 §0 完整矩阵。** R1 Gate 后停机。建议提交信息：`test: group backend component suite batch one`。

### Task 17：迁移 Backend component（批次 B）
**Review Level:** R1（触发：Task Gate 门位下限；八个测试文件的纯路径迁移）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L479-L493
**证据要求:** 八个文件移动前后 item 数一致；cognition fixture 与 embedding doubles 仍通过签名守卫

**Files（8 个逻辑移动）：**

- `test_cognition_repository.py`、`test_demo_reset_api.py`、`test_deploy.py`、`test_embedding_provider.py`
- `test_health_api.py`、`test_memory_explanation_service.py`、`test_memory_retrieval.py`、`test_npc_api.py`
- Destination: `tests/backend/component/`

- [ ] **Step 1：记录 collect-only 与聚焦基线。**
- [ ] **Step 2：普通移动八个文件；不改断言/mock。**
- [ ] **Step 3：重跑、执行签名守卫及 §0 完整矩阵。** R1 Gate 后停机。建议提交信息：`test: group backend component suite batch two`。

### Task 18：迁移 Backend component（批次 C）
**Review Level:** R1（触发：Task Gate 门位下限；八个测试文件的纯路径迁移）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L494-L508
**证据要求:** 八个文件移动前后 item 数一致；PostgreSQL marker 收集数不变

**Files（8 个逻辑移动）：**

- `test_npc_chat_api.py`、`test_npc_repository.py`、`test_npc_service.py`、`test_player_quest_api.py`
- `test_player_quest_repository.py`、`test_player_quest_service.py`、`test_postgres_runtime.py`、`test_reflection_engine.py`
- Destination: `tests/backend/component/`

- [ ] **Step 1：记录 collect-only、acceptance/postgres marker 清单。**
- [ ] **Step 2：普通移动八个文件；不改 marker/断言。**
- [ ] **Step 3：重跑相同集合与 §0 完整矩阵。** R1 Gate 后停机。建议提交信息：`test: group backend component suite batch three`。

### Task 19：迁移 Backend component（批次 D）
**Review Level:** R1（触发：Task Gate 门位下限；八个测试文件的纯路径迁移）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L509-L523
**证据要求:** 八个文件移动前后 item 数一致；migration/seed/start-dev 使用 shared REPO_ROOT

**Files（8 个逻辑移动）：**

- `test_schema_migrations.py`、`test_seed_world.py`、`test_stage2_acceptance.py`、`test_stage2_chat_memory.py`
- `test_start_dev.py`、`test_world_api.py`、`test_world_clock.py`、`test_world_engine.py`
- Destination: `tests/backend/component/`

- [ ] **Step 1：记录 collect-only 与聚焦基线。**
- [ ] **Step 2：普通移动八个文件；不改测试正文。**
- [ ] **Step 3：重跑相同集合、marker 选择与 §0 完整矩阵。** R1 Gate 后停机。建议提交信息：`test: group backend component suite batch four`。

### Task 20：完成 Backend 路径迁移
**Review Level:** R1（触发：Task Gate 门位下限；两个测试文件的纯路径迁移）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L524-L538
**证据要求:** Backend 根目录只剩 conftest 与三个目录；全量收集无 duplicate/import error

**Files（3）：**

- Move: `tests/backend/test_world_versioning.py` → `tests/backend/component/test_world_versioning.py`
- Move: `tests/backend/legacy_sqlite_factory.py` → `tests/backend/support/legacy_sqlite_factory.py`
- Modify: `tests/backend/component/test_schema_migrations.py`

- [ ] **Step 1：记录两个文件的消费者与 item 数。**
- [ ] **Step 2：普通移动并把 schema migration 的 import 更新为 `tests.backend.support.legacy_sqlite_factory`。** 只允许这一个 import 变化；不得改变 legacy fixture 或 migration 断言。
- [ ] **Step 3：运行 Backend collect-only、§0 完整矩阵和 R1 Gate。** 建议提交信息：`test: complete backend test layering`。

### Task 21：迁移 Frontend unit（批次 A）
**Review Level:** R1（触发：单层内的有界实现，仅 frontend）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L539-L553
**证据要求:** 八个文件移动前后 test 名与数量一致；import 统一使用 `@app` / `@test-support`

**Files（8 个逻辑移动）：**

- `apiClient.spec.ts`、`chatApi.spec.ts`、`demoApi.spec.ts`、`gameFlow.spec.ts`
- `movement.spec.ts`、`npcChat.spec.ts`、`npcDetail.spec.ts`、`npcMemory.spec.ts`
- Destination: `tests/frontend/unit/`

- [ ] **Step 1：记录八个文件 verbose test 名。**
- [ ] **Step 2：普通移动并仅机械替换 import 为 `@app/...` 与 `@test-support/fixtures`。**
- [ ] **Step 3：重跑相同集合、type-check 与 §0 完整矩阵。** 名称/数量一致后 R1 Gate 停机。建议提交信息：`test: group frontend unit suite batch one`。

### Task 22：迁移 Frontend unit（批次 B）
**Review Level:** R1（触发：单层内的有界实现，仅 frontend）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L554-L568
**证据要求:** 八个文件移动前后 test 名与数量一致；静态 asset 路径仍指向真实 frontend/public

**Files（8 个逻辑移动）：**

- `npcProjection.spec.ts`、`playerProfile.spec.ts`、`playerQuest.spec.ts`、`playerQuestApi.spec.ts`
- `spriteAssets.spec.ts`、`townMap.spec.ts`、`world.spec.ts`、`worldTick.spec.ts`
- Destination: `tests/frontend/unit/`

- [ ] **Step 1：记录八个文件 verbose test 名。**
- [ ] **Step 2：普通移动并改用别名；`spriteAssets/townMap` 的磁盘路径必须由稳定 helper 或新深度精确解析，不能指向测试目录。**
- [ ] **Step 3：重跑相同集合、type-check 与 §0 完整矩阵。** R1 Gate 后停机。建议提交信息：`test: group frontend unit suite batch two`。

### Task 23：迁移 Frontend component（批次 A）
**Review Level:** R1（触发：单层内的有界实现，仅 frontend）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L569-L583
**证据要求:** 八个 Vue component 文件移动前后 test 名与数量一致；无 production component 被 stub 替换以迎合迁移

**Files（8 个逻辑移动）：**

- `AppFlow.spec.ts`、`LocationCard.spec.ts`、`NpcCard.spec.ts`、`NpcChatPanel.spec.ts`
- `NpcDetailPanel.spec.ts`、`PlayerLocationPanel.spec.ts`、`QuestPanel.spec.ts`、`TickPanel.spec.ts`
- Destination: `tests/frontend/component/`

- [ ] **Step 1：记录八个文件 verbose test 名。**
- [ ] **Step 2：普通移动并机械改用 `@app` / `@test-support`。**
- [ ] **Step 3：重跑相同集合、type-check 与 §0 完整矩阵。** R1 Gate 后停机。建议提交信息：`test: group frontend component suite batch one`。

### Task 24：完成 Frontend component 与兼容层迁移
**Review Level:** R1（触发：单层内的有界实现，仅 frontend）
**Binding 条款锚点:** spec:§2 L13-L35、spec:§5 L69-L76、plan:L584-L600
**证据要求:** Frontend 根目录不再有 spec/兼容 fixture；所有测试从 unit/component 递归收集，Phaser alias 直接指 support

**Files（4）：**

- Move: `tests/frontend/TownGameBridge.spec.ts` → `tests/frontend/component/TownGameBridge.spec.ts`
- Move: `tests/frontend/TownGameHost.spec.ts` → `tests/frontend/component/TownGameHost.spec.ts`
- Move: `tests/frontend/TownSceneInput.spec.ts` → `tests/frontend/component/TownSceneInput.spec.ts`
- Delete: `tests/frontend/fixtures.ts`

- [ ] **Step 1：记录三个文件 verbose test 名及根 fixture 消费者。** `rg "from './fixtures'|tests/frontend/fixtures"` 除待删 shim 外必须为零；Vite phaser alias 已直接指 support。
- [ ] **Step 2：移动三个文件、改用别名并删除兼容 shim。** 不修改 test body 或 mock 行为。
- [ ] **Step 3：验证终态。** `tests/frontend/` 根目录只剩 `unit/`、`component/`、`support/`；Vitest 收集数只反映 Task 12 批准删除的 2 项，TownView 仍为 35 项。
- [ ] **Step 4：运行 §0 完整矩阵与 R1 Gate并停机。** 建议提交信息：`test: complete frontend test layering`。

## 2. 每个 Task 的固定交付证据

每个 Task 的停机报告必须包含：

1. `git status --porcelain -uall` 原文与本 Task 文件计数；
2. RED 或搬移前 characterization 的命令、关键输出和失败/通过原因；
3. 聚焦 GREEN 的真实 item 数；
4. Backend 全量、Frontend 全量、type-check 的真实数字与 exit code；
5. skip/warning 与上一个 approved baseline 的变化；
6. Review Level、唯一触发条款、binding 摘录、scoped package 路径与 verdict；
7. 删除 Task 的 survivor mapping，移动 Task 的 before/after node-id mapping；
8. 建议提交信息，以及“未执行任何 git 写命令”的声明。

## 3. Plan 自检

- **决策覆盖：** 两层物理目录、support、acceptance/PostgreSQL marker、非空 privacy 断言、test-double 签名守卫、Settings/Store 合并、TownView 拆分、历史 acceptance 与瞬时文档测试清理均有对应 Task。
- **范围隔离：** 所有 Task ≤8 个逻辑文件；断言/mock 变化集中在 Task 1/4/5/6/7/9/10/11/12/13，纯目录迁移从 Task 14 开始，不与生产改动混合。
- **不变量：** 无生产代码、Schema、Public API、权限、Provider 接口或 Stage 3 实现；完整矩阵和人类提交停机点对每个 Task 生效。
- **占位符扫描：** 最终版已用实际行号替换全部 Task binding，不保留待填内容。
