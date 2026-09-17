# 能力基线

**代码锚点**：`c4d9048ed739516254ef4f65a6401596160c6cd1`（`main`，工作树干净）。
首次记录 2026-09-17（锚点 `a3f15cd`），最后更新 2026-09-18。

> 数字随代码变化。`a3f15cd` 上后端是 779 passed（POSIX），合计 992；`c4d9048`
> 为 Demo Reset 的计划清理补了 2 个回归测试，因此变成 781 / 994。**引用这些数字时
> 请带上锚点** —— 早于本次更新的材料里出现的 992 不是错的，它对应 `a3f15cd`。

本文只回答一个问题：**clone 这个仓库之后，跑哪些命令、会看到什么数字。**

它不提出新结论，只把当前 HEAD 上可复现的验证结果集中记下来，并逐条对上 README 与评测报告中出现的每个数字。与 [Stage 3m 阶段快照](2026-09-16-stage3m-snapshot.md) 的分工：快照负责解释**指标含义与解释边界**，本文只负责**复现步骤与实测输出**。快照里标注的每条限制在这里同样成立，本文没有推翻其中任何一条。

## 运行环境

| 项 | 本次实测值 |
| --- | --- |
| 操作系统 | Windows 10 家庭中文版（10.0.19045） |
| Python | 3.13.9（项目 `.venv`）；`backend/requirements.txt` 要求 3.11+，Docker 镜像用 3.12 |
| Node / npm | v24.18.0 / 11.16.0；README 要求 Node 20+ |
| 数据库 | 临时 SQLite；迁移链 `0001 → 0006` |
| Provider | Chat `mock`、Embedding `fake`、Reflection `fake`、Planning 未配置（走确定性替身） |
| PostgreSQL | **未**设置 `TEST_POSTGRES_URL`，4 项 opt-in 集成测试按设计 skip |
| 外部请求 | 无。后端 conftest 禁用仓库 `.env` 并清空四类 API Key |

## 1. 后端测试

> **必须在沙箱外运行，并显式指定 `--basetemp` 到有写权限的目录。** 沙箱会创建 Windows `0700` 权限的临时目录，导致整轮结果无效——本项目已因此产生过两次无效运行。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=<可写目录>
```

实测输出（exit 0）：

```
780 passed, 5 skipped, 1 warning in 309.49s (0:05:09)
```

同一命令在 Git Bash 下（exit 0）：

```
781 passed, 4 skipped, 1 warning in 262.86s (0:04:22)
```

`--collect-only` 报告 **785 tests collected**，两个环境一致。

### 为什么是 780 和 781 两个数字

差异**只来自 shell 环境，不是测试不稳定**。[`tests/backend/test_start_dev.py:20`](../../tests/backend/test_start_dev.py) 在 PATH 里找不到 POSIX `sh` 时跳过一项：

```python
if shutil.which("sh") is None:
    pytest.skip("Windows shell launcher probe requires a POSIX-compatible sh.")
```

- **Windows PowerShell**（PATH 无 `sh`）：780 passed, 5 skipped
- **Git Bash / Linux CI**（`/usr/bin/sh` 存在）：**781 passed, 4 skipped**

单独验证该文件：Git Bash 下 `5 passed`，PowerShell 下 4 passed + 1 skipped。

因此引用后端测试数时必须带环境限定。**POSIX 环境下的 781 是可在 CI 上公开复核的那个数字**；`AGENTS.md` 记录的「4 个 skip」描述的也是 POSIX 环境。

### 4 项 skip 的完整清单（Git Bash 实测）

```
SKIPPED [1] tests\backend\test_chat_repository.py:19:     TEST_POSTGRES_URL is not set
SKIPPED [1] tests\backend\test_memory_retrieval.py:309:   TEST_POSTGRES_URL is not set
SKIPPED [1] tests\backend\test_postgres_runtime.py:90:    TEST_POSTGRES_URL is not set
SKIPPED [1] tests\backend\test_schema_migrations.py:443:  TEST_POSTGRES_URL is not set
```

全部是 opt-in PostgreSQL 集成测试。**一次 skip 永远不等于一次 PostgreSQL 兼容性验收**——这条规则见 [`docs/07_Database_Schema.md`](../07_Database_Schema.md) 的 acceptance 段。

1 个 warning 是既有的 Starlette/httpx 弃用提示，与 `AGENTS.md` 记录的基线一致，本轮未新增 skip 或 warning。

## 2. 前端测试、类型检查与构建

```bash
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build
```

| 命令 | 实测输出 | exit |
| --- | --- | --- |
| `test` | `Test Files 30 passed (30)` / `Tests 213 passed (213)`，19.25s | 0 |
| `type-check` | 无输出（`vue-tsc -b`） | **0** |
| `build` | `✓ 134 modules transformed` / `✓ built in 5.28s` | **0** |

构建有一条既有提示：`createTownGame` chunk 1,492.94 kB 超过 500 kB 警告线。这是 Phaser 被动态加载进独立 chunk 的预期结果（见 [`docs/12_Game_Experience_Design.md`](../12_Game_Experience_Design.md) 对 bundle 代价的记录），不是本轮引入的回归。

## 3. Fake 评测的可复现性

```bash
python scripts/eval_agent.py --ticks 20 --provider fake
```

不带 `--out` 连跑两次，两次的**行为指标逐位一致**：

| 指标 | 第 1 次 | 第 2 次 |
| --- | --- | --- |
| 动作合法率 | 100.0%（60/60） | 100.0%（60/60） |
| 可用决策率 | 100.0%（30/30） | 100.0%（30/30） |
| 兜底率 | 0.0%（0/60） | 0.0%（0/60） |
| 计划完成率（状态） | 90.0%（27/30） | 90.0%（27/30） |
| 行为熵 | 1.411 / 2.585 | 1.411 / 2.585 |
| 计划复用率 | 50.0%（30/60） | 50.0%（30/60） |
| 模型调用 / NPC-tick | 30/60 = 0.500 | 30/60 = 0.500 |
| 动作分布 | eat 3、move 2、rest 28、talk 27 | 同左 |

唯一浮动的是墙钟耗时（tick P50 0.427s → 0.371s），本来就不该复现。

结果与仓库内已有的 [2026-09-16 Fake 报告](2026-09-16-agent-eval-fake.md)一致。在 `c4d9048` 上再次复跑，全部行为指标仍逐位相同 —— `seed_database` 复用 `DemoResetService`，但评测每次新建空的临时库，新增的计划清理删 0 行。

**Fake 数字只证明链路可复现，不能推断真实模型质量或成本**——Provider 是本地确定性替身，token 未上报。

## 4. 与对外声明的逐条对应

| 声明 | 本轮实测 | 证据 |
| --- | --- | --- |
| 前后端测试全部通过 | 781 + 213 = **994**（POSIX 环境）；Windows PowerShell 下为 993 + 1 项环境性 skip | 本文 §1、§2 |
| Live 20 tick 动作合法率 100%（43/43） | **100.0%（43/43）** | [20-tick Live 报告](2026-09-17-agent-eval-live-20tick.md) |
| 计划复用率 51.7% | **51.7%（31/60）** | 同上 |
| 模型调用 0.483 次/NPC-tick | **29/60 = 0.483** | 同上 |
| 行为熵 2.126 / 2.585 | 历次最高 | 同上 |
| Plan-and-Execute，多步计划跨回合复用 | `agent_plans` 表 + `source=existing_plan` 提案 | [`docs/07`](../07_Database_Schema.md)、[`docs/06` §4.4](../06_API_Contract.md) |
| 模型仅产出类型化提案，经注册表二次校验 | `ActionRegistry.to_tool_manifest()` 输出 MCP `tools/list` 形状 | [`docs/05`](../05_Engineering_Architecture.md) |
| 超时或非法结构降级至确定性策略 | `provider:timeout` / `provider:parse_error` 等分层归因落盘 | [Live 20-tick 报告](2026-09-17-agent-eval-live-20tick.md) |
| 记忆访问权限在 SQL 层硬过滤 | `SCOPE_RULES` 三档 scope，排序前过滤 | [`docs/05`](../05_Engineering_Architecture.md) 的 Cognition pipeline 段 |
| 前端 Vue 3 + TS + Pinia，Phaser 承载地图，单向事件桥 | `TownGameBridge` + 独立 Pinia store | [`docs/05`](../05_Engineering_Architecture.md) 的 Frontend 段 |

### 本轮**没有**复核的项

- **真实模型（Live）评测未重跑。** §4 中的 Live 数字全部引用 2026-09-17 已有报告，不是本轮新测。
- **PostgreSQL / pgvector 端到端未验收。** 4 项 opt-in 测试在本轮全部 skip。
- **Live tick 延迟未实测。** 当前 HEAD 的真实模型端到端耗时仍是未知量。
- **Docker Compose 未启动。** 本轮只验证源码级测试与构建。

以上四项属于「未执行」，不是「通过」。
