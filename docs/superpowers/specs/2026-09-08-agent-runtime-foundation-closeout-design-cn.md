# Agent Runtime Foundation 收口设计

**日期：** 2026-09-08
**状态：** 待用户 Review
**基线提交：** `e78714f`（Task 7 已由用户提交）
**上位设计：** `docs/superpowers/specs/2026-09-04-ai-native-agent-rpg-runtime-design.md`

## 1. 背景与当前结论

Agent Runtime Foundation 的 Tasks 1–7 已经建立 Alembic、三类权威计数器、不可变快照、类型化提案、Action Registry、确定性编排、原子运行图、Trace API、前端版本恢复，以及 PostgreSQL/pgvector 部署基线。

自动化验收曾达到后端 463 passed / 2 PostgreSQL skipped、前端 182 passed、类型检查和构建通过，整期代码 Review 为 Approved。

真实本地启动随后暴露了自动化测试没有覆盖的历史兼容问题：

1. 早期版本使用 SQLAlchemy `Base.metadata.create_all()` 创建 SQLite。
2. 该数据库中的 CHECK、UNIQUE、PK、FK 多数没有显式名称。
3. `upgrade_schema()` 将表集合完全匹配的无版本数据库标记为 Alembic `0001`。
4. `0002_world_versioning.py` 按新版 `0001` 中的显式名称删除约束。
5. Alembic 在真实历史数据库中找不到 `ck_world_state_tick`，迁移终止。
6. 启动器在 Schema Upgrade 失败后退出，因此 Backend 和 Frontend 均未启动。

当前实测数据库仍保留旧 `tick` 字段和原有业务数据，不存在 `_alembic_tmp_*` 残留表，但 `alembic_version` 已停在 `0001`。

因此 Foundation 只能认定为“主体完成、真实升级路径未收口”。本设计用于关闭该发布阻塞问题，不进入第二阶段的感知、记忆与反思。

## 2. 目标

本次收口必须同时实现以下目标：

1. 真实历史 SQLite 数据库可以原地升级到 Alembic `head`。
2. 升级保留 World、Location、NPC、Player、Quest、Action、Event、Conversation 和 Message 数据。
3. 同时兼容无 `alembic_version` 的历史数据库，以及已被标记为 `0001` 但仍保留未命名约束的数据库。
4. 新建空 SQLite、由正式 `0001` 创建的 SQLite、已处于 `head` 的 SQLite 均保持可升级或幂等。
5. PostgreSQL 的命名约束迁移路径和 pgvector 初始化行为不被破坏。
6. Windows 用户可以在 Git Bash 中使用项目虚拟环境执行检查和启动。
7. 启动失败时可以在终端看到真实错误；文档不再建议通过资源管理器双击来判断启动是否成功。
8. 完成真实的临时旧库迁移 Smoke、本地启动 Smoke 和完整回归。

## 3. 非目标

本次明确不实现：

- Observation、Memory、Belief、Reflection。
- Embedding 写入、向量检索或任何 vector ORM 字段。
- LLM 行为决策、Goal、Plan、LangGraph。
- Celery、Redis、Outbox、SSE 或异步 `202` Runtime。
- NPC-to-NPC 社交、Relationship、知识传播。
- Agent Lab、新任务章节或新的 RPG 行动类型。
- 战斗、装备、背包、多人世界或账号权限。
- Public API 字段或现有 RPG 行为变更。

## 4. 数据安全原则

1. 自动化测试只操作临时数据库，不直接修改 `backend/data/aleria.db`。
2. 实现和测试过程中不得删除、覆盖或重置用户的真实 SQLite 文件。
3. 对真实数据库执行最终手动升级前，必须先创建可识别的时间戳备份。
4. 迁移不能通过“删库重建”获得成功。
5. 不允许手工把 `alembic_version` 直接改为 `0003` 来绕过真实 Schema Upgrade。
6. 失败必须保留可诊断错误，且不得留下 `_alembic_tmp_*` 表或半完成的新字段。
7. 验收比较业务数据，不输出聊天正文、API Key 或其他潜在敏感内容。

## 5. 必须兼容的数据库矩阵

| 输入数据库 | 初始特征 | 预期结果 |
| --- | --- | --- |
| 空 SQLite | 无业务表 | 从 `0001` 升级到 `head` 并创建完整 Schema |
| 正式 `0001` SQLite | 约束有显式名称 | 从 `0001` 正常升级到 `head` |
| 历史无版本 SQLite | 11 个旧业务表，约束未命名，无 `alembic_version` | 识别为受支持的 Legacy，标记后完整升级且保留数据 |
| 历史已标记 SQLite | 旧业务表和未命名约束，`alembic_version=0001` | 直接从 `0001` 完整升级且保留数据 |
| 当前 `head` SQLite | `alembic_version=0003` | 重复升级幂等，无数据变化 |
| 部分或未知 Schema | 表集合或关键列与受支持 Legacy 不匹配 | 明确拒绝，不擅自标记版本 |
| 空 PostgreSQL | 独立测试 Schema | 创建 pgvector 扩展并升级到 `head` |

## 6. 历史数据库测试模型

测试不能再使用“执行新版 Alembic `0001` 后删除版本表”作为唯一 Legacy 样本，因为它会保留新版显式约束名，无法代表真实历史数据库。

新的测试夹具应：

1. 在临时源库执行正式 `0001`，获得完整旧表结构。
2. 使用 SQLAlchemy Reflection 读取 11 个 Legacy 业务表。
3. 在复制到目标临时库前清除反射 Constraint 的 `name`，保留显式 Index 名。
4. 使用 `MetaData.create_all()` 生成与旧 ORM `create_all()` 等价的未命名约束结构。
5. 写入覆盖 World、NPC、Player、Quest、Action/Event、Conversation/Message 的哨兵数据。
6. 分别构造无版本和已标记 `0001` 两个输入场景。

这套夹具必须作为长期回归资产保留，不能依赖 Git 历史、用户真实数据库或二进制 `.db` 文件。

## 7. 迁移行为设计

### 7.1 方言边界

- PostgreSQL 保持按现有显式约束名执行迁移。
- SQLite 不能假定反射出来的旧约束具有名称。
- 差异必须封装在 `0002_world_versioning.py` 内部，不扩散到 Domain、Repository 或 API。

### 7.2 SQLite 约束识别

SQLite 路径应根据约束语义识别需要替换的旧约束：

- CHECK：以规范化后的 SQL 表达式匹配，例如 `tick >= 0`、`updated_tick >= 0`、`world_tick >= 0`、`created_tick >= 0`。
- UNIQUE：以有序列集合匹配，例如 `world_id, tick, actor_id`。
- Index：继续使用真实存在的显式 Index 名。

实现不得通过忽略所有约束来完成迁移。与本次列重命名无关的 CHECK、FK、PK、UNIQUE 和 Index 必须保留。

### 7.3 Batch Rebuild

SQLite 使用 Alembic Batch Rebuild 时，应先反射旧表，移除本次确定要替换的旧约束，再把该反射表作为 `copy_from` 输入。随后执行列重命名、添加新列和创建新的显式约束。

每张表必须确认预期旧约束确实存在；若约束语义既不匹配旧结构，也不匹配正式 `0001`，迁移应失败并报告不支持的 Schema，而不是静默继续。

### 7.4 数据转换

继续保持既有语义：

- `world_state.tick → clock_tick`
- `world_version` 初始化为旧 `clock_tick`
- `event_sequence` 初始化为该 World 已有 Event 数量
- Quest、Action、Event、Conversation 和 Message 的旧 Tick 字段迁移到对应 `clock_tick`
- `0003` 继续负责 Runtime Graph 回填以及 `social → talk` 规范化

不得重新生成或覆盖已有对话、任务、NPC 状态和玩家状态。

## 8. Git Bash 启动设计

### 8.1 Windows Git Bash

`scripts/start-dev.sh` 的 Python 选择顺序调整为：

1. `.venv/Scripts/python.exe`（Windows Git Bash）
2. `.venv/bin/python`（Linux/macOS）
3. PATH 中的 `python3`
4. PATH 中的 `python`

Windows Git Bash 的推荐命令为：

```bash
cd /d/pythonproject/Aleria_AI_Town
./scripts/start-dev.sh --check
./scripts/start-dev.sh
```

`scripts/start-dev.cmd` 和 `scripts/start-dev.ps1` 继续保留，供 CMD/PowerShell 或从 Git Bash 显式调用。

### 8.2 启动顺序

启动顺序保持：

```text
prerequisite check
→ upgrade_schema
→ ensure_demo_world（仅空世界播种）
→ Backend + Frontend
→ 任一子进程退出则统一收尾
```

启动器不得自动 Reset Demo，也不得在迁移失败后继续启动不兼容的 Backend。

## 9. Public Contract 与游戏行为

本次不改变：

- `POST /api/world/tick` 同步返回 HTTP 200。
- RPG 只有一个“推进 1 小时”入口。
- `world_version / clock_tick / event_sequence` 语义。
- Agent Run、Proposal、Action、Event、Trace Schema。
- Quest、Travel、Chat 和 Demo Reset API。
- NPC 的确定性决策结果。
- 本地 `.env` 默认 SQLite，Docker 默认 PostgreSQL。

唯一用户可见变化是：历史本地数据库能够成功升级，项目能从 Git Bash 正常启动。

## 10. 验收标准

### 10.1 迁移验收

- 历史无版本、历史已标记 `0001`、正式 `0001`、空库、当前 `head` 五种 SQLite 路径全部通过。
- 哨兵数据在升级后逐字段验证，不只比较行数。
- 新字段、约束、唯一索引、外键和 Alembic 版本正确。
- 旧 `social` Action 变为 `talk`，且对应 Event/Runtime 回填保持关联。
- 不存在 `_alembic_tmp_*` 残留。
- 部分 Schema 继续明确拒绝。

### 10.2 启动验收

- Git Bash 的 `./scripts/start-dev.sh --check` 使用项目 Windows venv。
- 使用临时复制的真实历史数据库执行 Migration Smoke 成功。
- 启动后 `/api/health`、`/api/world`、一次 `/api/world/tick` 和对应 `/api/agent-runs/{run_id}` 成功。
- 页面可访问，推进一小时后 NPC 状态和行动变化。
- 停止脚本后 Backend/Frontend 子进程均退出。

### 10.3 回归验收

- 完整 Backend 测试通过；未配置 `TEST_POSTGRES_URL` 时只允许计划内两个 PostgreSQL skip。
- Frontend 测试、Type Check、Production Build 通过。
- Compose base 与 PostgreSQL test override 均能被真实 Compose 解析。
- Docker daemon 和 `TEST_POSTGRES_URL` 可用时执行真实 PostgreSQL Smoke；不可用时必须如实记录。
- `git diff --check` 通过，暂存区为空，无自动提交。

## 11. 完成定义

只有同时满足下列条件，Agent Runtime Foundation 才能重新标记为完成：

1. 新增真实历史 SQLite 回归先 RED 后 GREEN。
2. 当前失败栈对应问题被自动化测试覆盖。
3. 临时旧库数据完整升级。
4. Git Bash 启动链可用。
5. 完整测试和可用 Smoke 通过。
6. 独立代码 Review 无未解决 Critical/Important。
7. 用户 Review 后手动提交。

## 12. 后续阶段边界

本次收口并提交后，再创建阶段 2–6 的中文高层路线文档，记录：

1. 感知、记忆与反思。
2. 目标、计划与 LLM 自主行动。
3. 生产级异步 Runtime。
4. 三 NPC 社交与 Forest Embers 章节。
5. Agent Lab、评估与作品化。

该路线文档只锁定阶段目标、依赖关系、交付效果与验收边界，不提前为所有未来阶段编写逐文件实施计划。随后新建干净 Work 聊天，从第二阶段的独立 Spec 开始。
