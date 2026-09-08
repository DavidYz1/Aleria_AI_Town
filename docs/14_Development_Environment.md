# Aleria AI Town 开发环境

版本：v2.0 · 更新时间：2026-09-07

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

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm --prefix frontend ci
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.upgrade_schema
.\.venv\Scripts\python.exe -m scripts.ensure_demo_world
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1
```

另一个终端运行 `npm --prefix frontend run dev -- --host 127.0.0.1`。Linux/macOS 使用 `.venv/bin/python` 和对应复制命令。也可以按 README 使用 `start-dev.cmd` / `start-dev.sh`。

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

```powershell
Copy-Item .env.production.example .env.production
# 编辑 .env.production：替换 demo-only POSTGRES_PASSWORD，按需调整 HTTP_PORT。
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps
```

数据库用户名/库名默认 aleria。Compose 由 POSTGRES_USER、POSTGRES_PASSWORD、POSTGRES_DB 生成 `postgresql+psycopg://` URL；密码不应留为示例值。默认拼接需使用 URL-safe 用户名/密码；包含保留字符时显式提供正确 percent-encoded DATABASE_URL，同时保持 POSTGRES_PASSWORD 为数据库真实密码。真实 .env.production 不提交仓库。

基础 Compose 不发布数据库或后端端口，只发布 Web。SQLite 的旧 aleria_data 卷保留，但不会自动导入到 PostgreSQL。升级已有 SQLite 部署前，应明确备份和选择数据迁移方案；本阶段没有跨数据库搬迁工具。

普通 `docker compose --env-file .env.production down` 保留数据卷。不要使用 `down -v` 来重启，它会删除持久数据。已有 PostgreSQL 数据卷不会因修改环境变量而自动更改数据库密码；密码轮换需另外执行数据库管理操作。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/backend -q -rs -p no:cacheprovider --basetemp .test-tmp/final
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build
docker compose --env-file .env.production.example config --quiet
git diff --check
```

确保 .test-tmp 的父目录存在；受限工作区可以改用有写权限的独立临时目录。部署测试解析 YAML、env 和 Dockerfile 指令；这些检查不等于 Docker 实际构建或 PostgreSQL 冒烟。

## PostgreSQL 集成测试（显式可选）

只使用 `TEST_POSTGRES_URL`，必须指向可丢弃的测试数据库。每个测试新建独立的 `aleria_test_<uuid>` schema，表和 alembic_version 从零创建；用 search_path 隔离测试，结束只删除该 schema。测试需要 CREATE SCHEMA、CREATE EXTENSION vector 权限，必须串行执行。已有 public vector 扩展可复用；若迁移在测试 schema 新建扩展，该扩展随自建 schema 清理。

用单独 Compose 项目隔离测试卷，host 端口仅通过 override 发布在 loopback：

```powershell
$env:POSTGRES_PASSWORD = "aleria-test-only"
$env:TEST_POSTGRES_PORT = "55432"
docker compose -p aleria-postgres-test -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example up -d --build db backend
$env:TEST_POSTGRES_URL = "postgresql+psycopg://aleria:aleria-test-only@127.0.0.1:55432/aleria"
.\.venv\Scripts\python.exe -m pytest tests/backend/test_schema_migrations.py tests/backend/test_postgres_runtime.py -q -rs -p no:cacheprovider --basetemp .test-tmp/postgres
docker compose -p aleria-postgres-test -f compose.yaml -f compose.postgres-test.yaml --env-file .env.production.example down
Remove-Item Env:TEST_POSTGRES_URL
Remove-Item Env:TEST_POSTGRES_PORT
Remove-Item Env:POSTGRES_PASSWORD
```

上述密码仅供独立测试环境；真实部署不可使用。down 不带 -v，测试数据卷仍保留。重复运行相同测试项目时保持测试密码一致，或自行管理数据库密码。若环境已有 DATABASE_URL 覆盖值，请使用干净测试 shell 避免 backend 指向其他数据库。

验收检查 pgvector 0.8.6、一次同步 200、一个 completed run、三条 proposal/action/event、有序 trace，以及 world_version=1、clock_tick=1。没有 URL 会明确 skip；没有可用 Docker daemon/Compose 时记录 unavailable，不宣称实际 smoke 通过。

## 手动体验与后续边界

初始世界 Day 1 08:00，四个地点与 Ryan/Shir/Grey。RPG 只有一个“推进 1 小时”入口。旅行和任务更新全局 world_version，但不推进 clock_tick；普通聊天不改变世界版本。Frontend 使用 Backend 的最新 world_version 执行权威变更。

地图已使用 Phaser；不是未来 Pixi 规划。真实 Provider 冒烟需要显式配置，模型只表达角色。Memory/vector 列、关系系统、后台异步任务和 Agent Lab 继续留给后续阶段。
