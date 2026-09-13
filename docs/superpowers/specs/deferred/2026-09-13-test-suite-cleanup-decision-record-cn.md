> **状态：已延期（DEFERRED）— 2026-09-13**
>
> 测试套件清理属于工程治理线，与当前交付窗口内的功能主线并行会分散精力。
> 决定：**在 `stage-3m Agent Loop MVP` 交付完成后再执行**。
>
> 当前执行的主线：`stage-3m Agent Loop MVP`
> - Spec: `docs/superpowers/specs/2026-09-13-stage-3m-agent-loop-mvp-design-cn.md`
>
> 本文档的分析与决策依然有效，仅调整执行时序。

---

# Test Suite Cleanup Decision Record

**状态：** 已批准的清理决策记录；不是产品 Spec，不授权 Stage 3 功能实现。

**日期：** 2026-09-13

## 1. 背景与目标

当前测试基线为后端 `720 passed, 5 skipped, 1 warning`，前端 `30 files / 209 tests passed`。测试套件已经覆盖 Stage 2 的主要行为，但存在四类维护风险：测试之间互相导入、同构 Store 契约重复、历史 acceptance 与当前分层重复、巨型 `TownView.spec.ts` 集中过多 mock 与组合行为。

本清理只调整测试和测试配置，目标是提高失败判别力、减少重复和降低单文件审查体量；不得改变生产代码、Public API、数据库 Schema、权限规则或 Stage 3 范围。

## 2. 已批准的分层

只使用两个测试层级：

```text
tests/
├── backend/
│   ├── unit/
│   ├── component/
│   └── support/
└── frontend/
    ├── unit/
    ├── component/
    └── support/
```

- Backend `unit`：纯模型、schema、配置、policy、registry、确定性 Provider、HTTP Provider adapter 的隔离测试。
- Backend `component`：SQLite/PostgreSQL、Repository、Service、ASGI、Migration、seed/deploy 与跨模块 acceptance。
- Frontend `unit`：纯函数、API adapter、Pinia Store、数据投影。
- Frontend `component`：Vue 组件、TownView 组合、Phaser adapter/scene 与 acceptance。
- `support` 只放 fixture、测试替身、路径与 harness；support 自身不构成第三个测试层。
- Acceptance 不建独立目录：Backend 用 `@pytest.mark.acceptance`，Frontend 用 `*.acceptance.spec.ts` 命名。
- PostgreSQL 不建独立目录：继续 opt-in，并用 `@pytest.mark.postgres` 标记。

## 3. 保留与清理裁定

### 3.1 必须保留

- runtime authority、world version/CAS、事务/rollback、迁移与 PostgreSQL parity。
- cognition retrieval/reflection/privacy、Provider fallback/timeout、quest/reset/deploy。
- 前端 Store 的竞态与失效语义、Vue 可访问性、Phaser input/bridge，以及当前 Stage 2 degradation acceptance。
- 每个删除候选中的独有业务断言；若找不到已存活的等价断言，先迁移再删除。

### 3.2 合并或拆分

- `test_chat_config.py` 与 `test_cognition_config.py` 合并为单一 Settings 单元测试。
- `npcDetail.spec.ts` 与 `npcMemory.spec.ts` 的共同 Store lifecycle 契约参数化到一个共享契约文件；资源特有错误文案与 payload 断言留在各自文件。
- 跨测试文件导入的 cognition fixture/helper 与 shared doubles 移到 `tests/backend/support/`。
- `TownView.spec.ts` 按 world/quest、NPC/chat、movement、reset/memory 组合责任拆分，并共享一个 harness；不以删除跨 Store wiring 为缩文件手段。

### 3.3 删除候选

- 删除 `CURRENT_STATE.md` 的瞬时进度字符串断言。
- 删除 README 标题顺序断言；保留部署、配置与工作流的正向契约。
- 删除精确 stale 文案黑名单；保留 schema/API/commit-boundary 正向契约。
- 删除 `test_phase1e_acceptance.py`：其三 NPC reply、五阶段 quest 与叙事断言已由存活测试覆盖。
- 删除 `test_phase1d_acceptance.py` 前，先把“chat 读取 quest context 且不修改 game state”的独有端到端断言迁入当前 chat acceptance；完整 quest 链由 player quest API 测试保留。
- 删除 `phase2Acceptance.spec.ts`：onboarding、完成态直达、NPC chat 与 movement separation 已分别由 `AppFlow`、`TownView`、Store 和 Phaser component 测试覆盖。

## 4. 可信度护栏

- Reflection 权限测试必须先证明返回集合非空，再证明所有结果仍为 `secret/internal_only`；禁止空集合上的 `all(...)` 恒真。
- 新增测试替身签名守卫，至少覆盖 `EmbeddingProvider.embed`、`ChatProvider.generate_reply`、`CognitionProjectionService.catch_up_owner`，防止接口演进后测试因 `TypeError` 走错分支而假绿。
- Backend acceptance/PostgreSQL marker 必须注册，不能新增未知 marker warning。
- 删除前后都记录 test item 数变化；减少的 item 必须能映射到明确的存活断言。

## 5. 执行边界

- 严格保留生产行为；不修改 `backend/app/`、`frontend/src/`、migration、seed data 或权威文档。
- 不引入依赖，不添加 LangChain/LangGraph/Celery/Redis/独立向量库，也不新增浏览器 E2E 工具。
- 每个 Task 最多八个逻辑文件；断言/mock 变化与纯路径迁移不得放在同一个 Task。
- 每个 Task 完成后运行后端全量、前端全量和 TypeScript type-check；聚焦测试不能替代完整矩阵。
- 不执行 git 写命令；每个 Task 完成后停机，由人类 review 和提交。
- 未跟踪的 Stage 3 Spec/Plan 不属于本清理 scope，不得修改或夹带。

## 6. 明确不做

- 不补写 Stage 3 测试，不实现任何 Stage 3 能力。
- 不新增 contract/integration/e2e/postgres 物理层级。
- 不追求单一 coverage 百分比，不为减少测试数量删除唯一的业务约束。
- 不在本轮修复审计发现的生产能力缺口；健康检查 503、OpenAPI/TypeScript DTO drift 等另行立项。
