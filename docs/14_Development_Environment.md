# Aleria AI Town 开发环境

版本：v2.1 · 更新时间：2026-09-09

## 当前运行模式

| 模式 | 数据库 | 入口 |
| --- | --- | --- |
| 本地轻量开发 | SQLite，默认 backend/data/aleria.db | 前端 127.0.0.1:5173，后端 127.0.0.1:8000 |
| Docker Compose | PostgreSQL 17 + pgvector 0.8.6 | Web 的 HTTP_PORT（默认 80） |
| 自动化测试 | 临时 SQLite + Mock | 不需要真实模型密钥 |
| 显式 PostgreSQL 集成测试 | 独立可丢弃 PostgreSQL 数据库 | TEST_POSTGRES_URL，缺失则明确 skip |

当前 Runtime 是同步、确定性的；已有 compatible 模型接入只用于角色聊天。Memory、LLM action cognition、Agent Lab、Celery/Redis/SSE 和异步 202 均未实现。

## 本地准备与启动

需要 Python 3.11+、Node.js 20+ 和项目依赖。Backend Docker 镜像使用 Python 3.12。从仓库根目录：

```bash
cd /d/pythonproject/Aleria_AI_Town
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm --prefix frontend ci
test -e .env || cp .env.example .env
./scripts/start-dev.sh --check
./scripts/start-dev.sh
```

以上以 Windows Git Bash 为主；示例仓库位于 D 盘，其他位置请调整 `cd`。脚本优先选择项目 `.venv/Scripts/python.exe`，其次 `.venv/bin/python`，最后才使用 PATH 中的 Python。Linux/macOS 可使用 `.venv/bin/python` 安装依赖，随后运行相同的 `start-dev.sh`。PowerShell 可运行 `.\scripts\start-dev.cmd --check` 与 `.\scripts\start-dev.cmd`。

`--check` 只检查依赖；实际启动顺序为 **Migration → seed-if-empty → services**。推荐使用 Git Bash/PowerShell 终端读取输出，不把双击窗口是否停留当作成功标准。按 `Ctrl+C` 后检查 8000/5173 均停止监听。

首次升级重要 SQLite 数据前先停止服务，再创建独立时间戳备份。已有文件或复制失败会停止以下命令：

```bash
cd /d/pythonproject/Aleria_AI_Town
backup="backend/data/aleria.before-upgrade-$(date +%Y%m%d-%H%M%S).db"
test ! -e "$backup" || exit 1
cp -- backend/data/aleria.db "$backup" || exit 1
./scripts/start-dev.sh
```

禁止通过手改 `alembic_version`、删除数据库或 Demo Reset 掩盖升级错误。历史数据迁移复现必须使用独立副本，保留原文件；仅输出版本、列名、计数等非敏感证据，不输出聊天正文或密钥。

`upgrade_schema` 使用 Alembic 升级已有数据库，不重置游戏。它能接纳完整受支持的未版本化旧 SQLite 数据库；不完整或不认识的旧表结构会拒绝升级。`ensure_demo_world` 仅在 Demo 世界不存在时播种。`scripts.seed_world` 会重置目标世界及其历史，只在明确需要重置时使用。

## 环境变量

本地 `.env.example` 保持：

```env
APP_ENV=development
DATABASE_URL=sqlite:///./backend/data/aleria.db
FRONTEND_ORIGIN=http://127.0.0.1:5173
CHAT_PROVIDER=mock
```

Mock 不需要 API Key。所有非 Mock 标签共用 OpenAI-compatible adapter：

```env
CHAT_PROVIDER=local
CHAT_LLM_BASE_URL=http://127.0.0.1:8001/v1
CHAT_LLM_MODEL=qwen-local
CHAT_LLM_AUTH_MODE=none
CHAT_LLM_API_KEY=
CHAT_LLM_OUTPUT_MODE=structured_json
CHAT_LLM_TIMEOUT_SECONDS=30
CHAT_HISTORY_LIMIT=10
CHAT_PROMPT_VERSION=v3
```

云服务使用各自地址/模型，bearer 模式的 Key 只放 Backend 私有环境。输出支持 structured_json 或 text；失败可回退 Mock。更完整的模型配置见 README，不能把真实秘密、Authorization Header 或上游错误正文写入测试/文档/日志。

## PostgreSQL Docker 部署

`compose.yaml` 提供 db、backend、web 三个服务。db 固定使用 `pgvector/pgvector:0.8.6-pg17-bookworm`，通过 pg_isready 做健康检查，数据卷为 `aleria_postgres_data`。Backend 等待数据库健康，执行 Alembic、仅空世界播种，然后启动 API；Web 等待 Backend 健康。

```bash
test -e .env.production || cp .env.production.example .env.production
# 编辑 .env.production：替换 demo-only POSTGRES_PASSWORD，按需调整 HTTP_PORT。
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps
```

数据库用户名/库名默认 aleria。Compose 由 POSTGRES_USER、POSTGRES_PASSWORD、POSTGRES_DB 生成 `postgresql+psycopg://` URL；密码不应留为示例值。默认拼接需使用 URL-safe 用户名/密码；包含保留字符时显式提供正确 percent-encoded DATABASE_URL，同时保持 POSTGRES_PASSWORD 为数据库真实密码。真实 .env.production 不提交仓库。

基础 Compose 不发布数据库或后端端口，只发布 Web。SQLite 的旧 aleria_data 卷保留，但不会自动导入到 PostgreSQL。升级已有 SQLite 部署前，应明确备份和选择数据迁移方案；本阶段没有跨数据库搬迁工具。

普通 `docker compose --env-file .env.production down` 保留数据卷。不要使用 `down -v` 来重启，它会删除持久数据。已有 PostgreSQL 数据卷不会因修改环境变量而自动更改数据库密码；密码轮换需另外执行数据库管理操作。

## 验证命令

```bash
mkdir -p .test-tmp
./.venv/Scripts/python.exe -m pytest tests/backend -q -rs -p no:cacheprovider --basetemp .test-tmp/final
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build
docker compose --env-file .env.production.example config --quiet
docker compose -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example config --quiet
git diff --check
```

确保 .test-tmp 的父目录存在；受限工作区可以改用有写权限的独立临时目录。部署测试解析 YAML、env 和 Dockerfile 指令；这些检查不等于 Docker 实际构建或 PostgreSQL 冒烟。

## PostgreSQL 集成测试（显式可选）

只使用 `TEST_POSTGRES_URL`，必须指向独立可丢弃的测试数据库。测试会新建 `aleria_test_<uuid>` schema，结束删除该 schema，且需要 CREATE SCHEMA、CREATE EXTENSION vector 权限，必须串行执行。

**backend 容器 Smoke 与测试数据库必须使用不同的 Compose project/volume。** 测试使用 `search_path=<test schema>,public`，因此 public 不能包含应用表或 `alembic_version`。如果先在同一库启动 backend，它会迁移并播种 public，迁移测试会在空表前置检查失败，Runtime 测试可能访问 public。schema 不能保护已有业务数据，绝不能把 URL 指向现有业务数据库；不要清空业务 public 或改 Alembic 版本来绕过检查。2026-09-09 首次共库流程失败后，用全新的 db-only 项目运行相同测试，13 项全部通过，无需改产品或测试代码。

首先用单独项目验证 backend 构建、迁移和健康状态（基础 Compose 不向主机发布数据库端口）。以下两处启动使用 Compose v5 的 `--wait --wait-timeout 120`，仅在启动成功退出后继续健康请求或测试；超时或失败时先执行对应项目的 down，保留错误信息：

```bash
export POSTGRES_PASSWORD='aleria-test-only'
docker compose -p aleria-backend-smoke --env-file .env.production.example up -d --build --wait --wait-timeout 120 db backend
docker compose -p aleria-backend-smoke --env-file .env.production.example ps
docker compose -p aleria-backend-smoke --env-file .env.production.example exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').status)"
docker compose -p aleria-backend-smoke --env-file .env.production.example down
unset POSTGRES_PASSWORD
```

用单独 Compose 项目隔离测试卷，host 端口仅通过 override 发布在 loopback：

```bash
export POSTGRES_PASSWORD='aleria-test-only'
export TEST_POSTGRES_PORT='55432'
docker compose -p aleria-postgres-test -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example up -d --wait --wait-timeout 120 db
# up 成功退出表示 db healthy；确认 public 中没有应用表，此项目不要启动 backend。
docker compose -p aleria-postgres-test -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example ps
docker compose -p aleria-postgres-test -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example exec -T db psql -U aleria -d aleria -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
export TEST_POSTGRES_URL='postgresql+psycopg://aleria:aleria-test-only@127.0.0.1:55432/aleria'
mkdir -p .test-tmp
./.venv/Scripts/python.exe -m pytest tests/backend/test_schema_migrations.py tests/backend/test_postgres_runtime.py -q -rs -p no:cacheprovider --basetemp .test-tmp/postgres
docker compose -p aleria-postgres-test -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example down
unset TEST_POSTGRES_URL TEST_POSTGRES_PORT POSTGRES_PASSWORD
```

上述密码仅供独立测试环境；真实部署不可使用。即使构建或测试失败，也要执行对应项目的 down。down 不带 -v，测试数据卷仍保留；只有明确确认属于本次可丢弃测试的卷才可另行删除，不能对业务项目使用 down -v。重复运行相同测试项目时保持测试密码一致，或自行管理数据库密码。测试库如已被 backend 播种，应换一个全新的独立测试项目/卷。使用干净测试 shell，避免继承 DATABASE_URL 等覆盖值使 backend 指向其他数据库。

验收检查 pgvector 0.8.6、一次同步 200、一个 completed run、三条 proposal/action/event、有序 trace，以及 world_version=1、clock_tick=1。没有 URL 会明确 skip；没有可用 Docker daemon/Compose 时记录 unavailable，不宣称实际 smoke 通过。

## 2026-09-09 收口验收记录

- 真实历史备份的 C 盘独立副本从 `0001` 升到 `0003`；World ID/day/time 保持，旧 tick 映射为 clock_tick/world_version；4 地点、3 NPC、1 玩家、1 任务、2 会话和 4 消息保留，外键无错，无 `_alembic_tmp_*`。
- 本地 Git Bash `--check` 与实际启动通过；health/world/前端返回 200。先备份真实 SQLite，再执行获批的一次同步 Tick：08:00 → 09:00，world_version/clock_tick 0 → 1，event_sequence 0 → 3；对应 3 proposals、3 actions、3 events、14 traces。按 Ctrl+C 停止后 8000/5173 无监听。
- 协调器随后使用预启动备份的 C 盘临时副本 `foundation-task3-ui-smoke-20260909.db` 完成真实页面验收：点击唯一“推进 1 小时”后 Day 1 08:00 → 09:00，页面显示第 1 回合、3 NPC Actions 与 3 World Events，Ryan 行动和三位 NPC 数值更新，Shir 从星辉酒馆移动到中央公园。临时服务的早期瞬时端口检查曾误判为已关闭；最终核验发现 PID 12448/14940 仍监听，协调器核实命令行为本仓库 Uvicorn/Vite 后精确 Stop-Process，随后最终确认 8000/5173 关闭。这是临时副本服务的显式进程清理，不能作为 start-dev 自动收尾证据；前项真实数据库 Smoke 的 Ctrl+C 清理证据仍成立。真实用户数据库未再推进。
- Git Bash 聚焦 Backend：73 passed、1 个 PostgreSQL skip；完整 Backend：468 passed、2 个明确 PostgreSQL skip。Frontend：182 passed，type-check/build 通过；保留原有 Phaser 大 chunk 提示。
- Docker Compose v5.3.0 两份 config parse 通过；实际 db/backend build/start/health 通过，schema `0003`、pgvector `0.8.6`。首次共库测试为 1 failed、12 passed；分离为全新 db-only 项目后，相同 PostgreSQL 测试为 **13 passed、零 skip**，测试前后 public 均无应用表。两个项目的容器、网络及经确认仅属于本次的可丢弃卷均已清理，8000/5173/55432 无监听。

## 手动体验与后续边界

初始世界 Day 1 08:00，四个地点与 Ryan/Shir/Grey。RPG 只有一个“推进 1 小时”入口。旅行和任务更新全局 world_version，但不推进 clock_tick；普通聊天不改变世界版本。Frontend 使用 Backend 的最新 world_version 执行权威变更。

地图已使用 Phaser；不是未来 Pixi 规划。真实 Provider 冒烟需要显式配置，模型只表达角色。Memory/vector 列、关系系统、后台异步任务和 Agent Lab 继续留给后续阶段。
