# 能力基线

**代码锚点**：提交 `a53e3d7cef614eaf53acc79bed2c7454fc90b44a`（`main`，
`docs: record deployment verification and refresh baseline`）。
本文数字在该提交的内容上实测，工作树当时除此之外干净。
首次记录 2026-09-17（锚点 `a3f15cd`），最后更新 2026-09-18。

> **锚点必须是 `git cat-file -t` 能解析的对象。** 本文上一版写的
> `c4d9048ed739…` 在仓库历史里不存在 —— 提交被 amend 或 rebase 之后 SHA 变了，
> 而本文没有同步。按那个锚点核对的人会直接卡在第一步。改锚点时请当场验证一次。

本轮数字覆盖的改动落在三个提交里（`d323f1c..a53e3d7`，10 个文件、474 插入 / 44 删除）：
`fdbb53a` Compose 透传、`ccc0726` PostgreSQL 断言与 Reset 覆盖、`a53e3d7` 文档与基线。
**每次改锚点都要当场 `git cat-file -t <SHA>` 验证它能解析** —— 本文上一版就是败在这一步。

> 数字随代码变化。`a3f15cd` 上后端是 779 passed（POSIX），合计 992；随后
> Demo Reset 的计划清理补了 2 个回归测试变成 781 / 994；本轮部署收尾再补 4 条
> Compose 透传守卫与 1 条 opt-in PostgreSQL 用例，POSIX 下变成 785 / 998。
> **引用这些数字时请带上锚点** —— 旧材料里的 992 / 994 不是错的，它们对应更早的锚点。

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
| PostgreSQL | 后端全量跑时**未**设置 `TEST_POSTGRES_URL`，5 项 opt-in 集成测试按设计 skip；另**单独**用独立 db-only Compose 项目实跑了这批用例，见 §5 |
| 外部请求 | 无。后端 conftest 禁用仓库 `.env` 并清空四类 API Key |

## 1. 后端测试

> **必须在沙箱外运行，并显式指定 `--basetemp` 到有写权限的目录。** 沙箱会创建 Windows `0700` 权限的临时目录，导致整轮结果无效——本项目已因此产生过两次无效运行。

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=<可写目录>
```

实测输出（exit 0）：

```
785 passed, 5 skipped, 1 warning in 314.47s (0:05:14)
```

上面是 **Git Bash 实测**。Windows PowerShell 下为 **784 passed, 6 skipped** ——
该差值本轮**没有**整轮复跑，而是单独实测了造成差值的那一个文件（见下）。

`--collect-only` 报告 **790 tests collected**。

### 为什么是 784 和 785 两个数字

差异**只来自 shell 环境，不是测试不稳定**。[`tests/backend/test_start_dev.py:20`](../../tests/backend/test_start_dev.py) 在 PATH 里找不到 POSIX `sh` 时跳过一项：

```python
if shutil.which("sh") is None:
    pytest.skip("Windows shell launcher probe requires a POSIX-compatible sh.")
```

- **Windows PowerShell**（PATH 无 `sh`）：784 passed, 6 skipped（由下面的单文件实测推出）
- **Git Bash / Linux CI**（`/usr/bin/sh` 存在）：**785 passed, 5 skipped**（整轮实测）

单独验证该文件，两个环境都实跑过：Git Bash 下 `5 passed`，PowerShell 下
`4 passed, 1 skipped in 1.27s`。差值恰好是这一项，因此 PowerShell 的整轮数字可由
Git Bash 的实测值减一推出；但它本身是推出来的，不是本轮实测的。

因此引用后端测试数时必须带环境限定。**POSIX 环境下的 785 是可在 CI 上公开复核的那个数字**；`AGENTS.md` 记录的「5 个 skip」描述的也是 POSIX 环境。

### 5 项 skip 的完整清单（Git Bash 实测）

```
SKIPPED [1] tests\backend\test_chat_repository.py:19:     TEST_POSTGRES_URL is not set
SKIPPED [1] tests\backend\test_memory_retrieval.py:309:   TEST_POSTGRES_URL is not set
SKIPPED [1] tests\backend\test_postgres_runtime.py:91:    TEST_POSTGRES_URL is not set
SKIPPED [1] tests\backend\test_postgres_runtime.py:197:    TEST_POSTGRES_URL is not set
SKIPPED [1] tests\backend\test_schema_migrations.py:443:  TEST_POSTGRES_URL is not set
```

全部是 opt-in PostgreSQL 集成测试。第 5 项（`:197`）是本轮新增的 Demo Reset 对非空 `agent_plans` 的清理覆盖 —— 它让 skip 基线从 4 升到 5，`AGENTS.md` 与 `docs/14` 已同步。**一次 skip 永远不等于一次 PostgreSQL 兼容性验收**——这条规则见 [`docs/07_Database_Schema.md`](../07_Database_Schema.md) 的 acceptance 段。

1 个 warning 是既有的 Starlette/httpx 弃用提示，与 `AGENTS.md` 记录的基线一致，本轮未新增 skip 或 warning。

## 2. 前端测试、类型检查与构建

```bash
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build
```

| 命令 | 实测输出 | exit |
| --- | --- | --- |
| `test` | `Test Files 30 passed (30)` / `Tests 213 passed (213)`，19.13s | 0 |
| `type-check` | 无输出（`vue-tsc -b`） | **0** |
| `build` | `✓ 134 modules transformed` / `✓ built in 5.65s` | **0** |

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

唯一浮动的是墙钟耗时（tick P50 0.218s → 0.241s、P95 0.291s → 0.334s），本来就不该复现。

结果与仓库内已有的 [2026-09-16 Fake 报告](2026-09-16-agent-eval-fake.md)一致。在本文顶部所述的锚点上再次复跑，全部行为指标仍逐位相同 —— `seed_database` 复用 `DemoResetService`，但评测每次新建空的临时库，新增的计划清理删 0 行。本轮的部署改动只涉及 Compose、env 模板、测试与文档，不触及评测路径。

**Fake 数字只证明链路可复现，不能推断真实模型质量或成本**——Provider 是本地确定性替身，token 未上报。

## 4. 与对外声明的逐条对应

| 声明 | 本轮实测 | 证据 |
| --- | --- | --- |
| 前后端测试全部通过 | 785 + 213 = **998**（POSIX 环境，实测）；Windows PowerShell 下为 997 + 1 项环境性 skip（推出，非实测） | 本文 §1、§2 |
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
- **Live tick 延迟未实测。** 当前锚点上的真实模型端到端耗时仍是未知量。§5 的 Docker 实测全部使用 fake/mock Provider。
- **真实 Embedding / Reflection / Planning Provider 的 Docker 冒烟未做。** §5 只证明了配置能到达容器并被 `Settings` 读到（用不可达的探测地址），**没有**证明与真实模型服务的端到端调用成功。
- **云服务器部署未执行。** 本轮只做本地 Docker 验证。

以上四项属于「未执行」，不是「通过」。

## 5. PostgreSQL 与 Docker Compose（本轮实跑）

前两版基线在这两项上都是「未执行」。本轮补上，命令与环境如下。

### 5.1 Docker Compose 端到端

Docker Engine 29.6.1 / Compose v5.3.0。使用**独立 project 名与独立 env 文件**，
不触碰默认 project 的卷；收尾用不带 `-v` 的 `down`。

```bash
docker compose -p aleria-local-verify --env-file <scratch env> up -d --build --wait --wait-timeout 300
```

- db / backend / web 三个容器全部 `healthy`
- 经 nginx 的真实用户路径（`http://127.0.0.1:8080`）：`GET /` 200、`/healthz` 200、
  `/api/health` 返回 `{"status":"ok","database":"ok","chat_provider":"mock"}`
- 一次 `POST /api/world/tick` 在 PostgreSQL 上完成：3 proposals / 3 actions / 3 events，
  **trace sequence 1–17**，前四个 stage 为 `run_started, planning, planning, planning`
- `GET /api/npcs/grey/memory-explanations` 返回 `retrieval_mode: "hybrid"` ——
  pgvector 的 `<=>` 检索真的执行了，不是 lexical fallback
- 浏览器实走完整体验路线：角色创建 → 序章 → 小镇 → 「推进 1 小时」，
  Day 1 08:00 → 09:00，页面显示 3 条 NPC Actions 与 3 条 World Events

**Compose 环境变量透传的差分验证**：把 13 个配置项改成与代码默认值不同的值后重启
backend，容器内 `Settings` 逐项等于 env 文件的值（例如
`cognition_post_commit_budget_seconds` 代码默认 `5.0`、容器实际 `13.0`），
且 `build_planning_provider()` 由 `FakePlanningProvider` 变为
`OpenAICompatiblePlanningProvider`。修复前 Docker 部署路径无法选到 live planner。

### 5.2 PostgreSQL opt-in 集成测试

独立 db-only Compose 项目（全新卷），测试前 `public` 无任何应用表：

```bash
export TEST_POSTGRES_URL='postgresql+psycopg://aleria:<test-only>@127.0.0.1:55432/aleria'
python -m pytest tests/backend/test_schema_migrations.py tests/backend/test_postgres_runtime.py   tests/backend/test_memory_retrieval.py tests/backend/test_chat_repository.py -q -rs
```

实测输出（exit 0）：

```
49 passed in 32.18s
```

**零 skip。** 同时在容器内直接查到：`alembic_version = 0006`、
pgvector `extversion = 0.8.6`、`memories.embedding` 的 `udt_name = vector`。

本轮修掉了该套件里两处过时断言（`alembic_version` 写着 `0004`、trace 写着 1–14），
它们此前必然导致 PG 验收变红；修改前先实跑取得 RED（`assert '0006' == '0004'`）。

新增一条覆盖：Demo Reset 对**非空** `agent_plans` 的清理。容器内实测
reset 前 `agent_plans = 6` / `agent_runs = 3`，reset 后两者均为 0，世界回到
`day 1 08:00 v0 t0`。该用例做过变异验证 —— 把清理改成匹配不到任何行时，
它以 `assert 3 == 0` 变红。
