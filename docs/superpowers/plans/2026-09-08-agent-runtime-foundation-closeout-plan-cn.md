# Agent Runtime Foundation 收口实施计划

> **给 agentic workers：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按 Task 执行。每个行为严格执行 RED → GREEN；本计划使用复选框跟踪。用户要求所有修改保持未暂存、未提交，Review 后由用户手动提交。

**目标：** 在不删除或重置用户数据的前提下，让真实历史 SQLite 数据库可靠升级到当前 Agent Runtime Schema，并完成 Windows Git Bash 启动与实际运行验收。

**架构：** 保持 Alembic `0001 → 0002 → 0003` 主链和现有公共 API。SQLite 的 `0002` 通过反射约束语义兼容旧 ORM 创建的未命名约束，PostgreSQL 继续使用显式命名约束；启动器只补足 Windows Git Bash 的 venv 选择，不改变运行时职责。

**技术栈：** Python 3.11+、SQLAlchemy 2、Alembic、SQLite、PostgreSQL/Psycopg 3、pytest、Shell/PowerShell、FastAPI、Vue 3、Phaser、Docker Compose。

**Spec：** `docs/superpowers/specs/2026-09-08-agent-runtime-foundation-closeout-design-cn.md`

## 全局约束

- 基线是用户已提交的 `e78714f`；开始实现前必须确认工作树只有本次获批规划文档，或先由用户处理其他改动。
- 禁止执行 `git add`、`git commit`、`git reset`、`git checkout`、`git switch`。
- 禁止删除、覆盖、移动或直接测试修改 `backend/data/aleria.db`。
- 所有破坏性迁移测试必须使用临时数据库；测试临时目录使用授权工作区。
- 严格 TDD：每项生产行为必须先看到预期失败，再做最小实现并看到通过。
- SQLite 仍是本地默认；PostgreSQL 仍是 Docker 默认。
- 不修改 `POST /api/world/tick` 同步 200、单一推进按钮或任何 Public API Contract。
- 不实现 Memory、Embedding、Reflection、Goal、Plan、LLM Action、LangGraph、Celery、Redis、SSE、Social Runtime 或 Agent Lab。
- 不通过删库、重建库、直接修改 Alembic 版本来解决兼容问题。
- 用户命令优先提供 Git Bash 版本；执行代理内部可以按可靠性使用 PowerShell 或 Git Bash。
- 每个 Task 完成后做范围审计和 Review，未解决 Critical/Important 时不得进入下一 Task。

---

## 文件职责图

| 文件 | 职责 |
| --- | --- |
| `tests/backend/legacy_sqlite_factory.py` | 构造与早期 ORM `create_all()` 等价的未命名约束 SQLite，并写入固定哨兵数据 |
| `tests/backend/test_schema_migrations.py` | 验证无版本/已标记历史库、正式迁移库、空库和 head 幂等升级 |
| `backend/migrations/versions/0002_world_versioning.py` | 在 SQLite 上按约束语义安全重建旧表，在 PostgreSQL 上保留命名约束路径 |
| `scripts/start-dev.sh` | 从 Windows Git Bash、Linux/macOS 选择正确项目 Python 并启动统一 Python Launcher |
| `tests/backend/test_start_dev.py` | 验证启动计划、依赖检查和 Windows venv 优先级 |
| `README.md` | 给用户提供 Git Bash 优先的启动、备份、错误诊断和 Smoke 步骤 |
| `docs/14_Development_Environment.md` | 记录迁移矩阵、数据库安全边界和正式验收命令 |

### Task 1：兼容真实历史 SQLite Schema

**Files：**

- Create: `tests/backend/legacy_sqlite_factory.py`
- Modify: `tests/backend/test_schema_migrations.py`
- Modify: `backend/migrations/versions/0002_world_versioning.py`

**Interfaces：**

- Consumes: `scripts.upgrade_schema.upgrade_schema(database_url: str, revision: str = "head") -> None`
- Produces: `create_unnamed_legacy_sqlite(database_url: str, *, stamped_revision: str | None) -> LegacySentinels`
- Preserves: `0001 → 0002 → 0003` revision identifiers和 PostgreSQL 命名约束行为

- [ ] **Step 1：建立真实历史数据库生成器**

在 `tests/backend/legacy_sqlite_factory.py` 中定义：

```python
from dataclasses import dataclass

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, text


LEGACY_TABLES = (
    "world_state",
    "locations",
    "npc_profiles",
    "npc_states",
    "player_states",
    "quest_progress",
    "quest_events",
    "actions",
    "events",
    "conversations",
    "conversation_messages",
)


@dataclass(frozen=True)
class LegacySentinels:
    world_id: str = "aleria-town"
    npc_id: str = "grey"
    player_id: str = "default-player"
    quest_id: str = "missing-child"
    conversation_id: str = "legacy-conversation"


def create_unnamed_legacy_sqlite(
    database_url: str,
    *,
    stamped_revision: str | None,
) -> LegacySentinels:
    """Create the committed 0001 shape with ORM-style unnamed constraints."""
```

实现步骤必须是：

1. 在独立临时源库运行 `command.upgrade(config, "0001")`。
2. 只反射 `LEGACY_TABLES`，不复制源库的 `alembic_version`。
3. 把每个反射 Constraint 的 `name` 设置为 `None`，不要清除 Index 名。
4. 在目标临时库执行 `metadata.create_all()`。
5. 依赖顺序写入固定数据：World、`tavern/castle` Location、Grey Profile/State、Player、Quest Progress/Event、`social` Action、对应 Event、Conversation、user/assistant Message。
6. `stamped_revision` 非空时，只对目标库执行 `command.stamp(config, stamped_revision)`。
7. 返回 `LegacySentinels`，测试通过固定 ID 查询，禁止依赖自增 ID 的偶然顺序。

- [ ] **Step 2：写无版本历史库 RED 测试**

在 `tests/backend/test_schema_migrations.py` 新增：

```python
@pytest.mark.parametrize("stamped_revision", [None, "0001"])
def test_real_orm_legacy_sqlite_upgrades_without_data_loss(
    tmp_path: Path,
    stamped_revision: str | None,
) -> None:
    suffix = stamped_revision or "unversioned"
    database_url = f"sqlite:///{(tmp_path / f'legacy-{suffix}.db').as_posix()}"
    sentinels = create_unnamed_legacy_sqlite(
        database_url,
        stamped_revision=stamped_revision,
    )

    upgrade_schema(database_url)

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "tick" not in {column["name"] for column in inspector.get_columns("world_state")}
    assert {"clock_tick", "world_version", "event_sequence"}.issubset(
        column["name"] for column in inspector.get_columns("world_state")
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
        assert connection.execute(
            text("SELECT day, time, clock_tick, world_version, event_sequence FROM world_state WHERE id=:id"),
            {"id": sentinels.world_id},
        ).one() == (7, "16:00", 44, 44, 1)
        assert connection.execute(
            text("SELECT action_type, reason, world_time FROM actions WHERE actor_id=:id"),
            {"id": sentinels.npc_id},
        ).one() == ("talk", "legacy_social", "15:00")
        assert connection.execute(
            text("SELECT status, version, updated_clock_tick FROM quest_progress WHERE player_id=:player AND quest_id=:quest"),
            {"player": sentinels.player_id, "quest": sentinels.quest_id},
        ).one() == ("accepted", 2, 44)
        assert connection.execute(
            text("SELECT created_clock_tick FROM conversations WHERE id=:id"),
            {"id": sentinels.conversation_id},
        ).one() == (42,)
        assert connection.scalar(
            text("SELECT count(*) FROM conversation_messages WHERE conversation_id=:id"),
            {"id": sentinels.conversation_id},
        ) == 2
        assert not connection.execute(
            text("SELECT name FROM sqlite_master WHERE name LIKE '_alembic_tmp_%'")
        ).all()
```

哨兵断言必须继续覆盖 NPC location/current_action/energy/mood/social、Player location、Quest Event、Action/Event 关联、Conversation Message role/content/emotion/provider/fallback/prompt/tick。测试不得打印正文。

- [ ] **Step 3：运行测试确认 RED**

Git Bash：

```bash
cd /d/pythonproject/Aleria_AI_Town
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py::test_real_orm_legacy_sqlite_upgrades_without_data_loss \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-red
```

Expected：两个参数场景均失败，核心错误为 `ValueError: No such constraint: 'ck_world_state_tick'`。若失败原因是夹具错误，先修夹具并重新取得干净 RED，不得把夹具错误当作证据。

- [ ] **Step 4：实现 SQLite 语义约束兼容**

在 `0002_world_versioning.py` 增加私有辅助逻辑：

```python
def _normalized_check_sql(constraint: sa.CheckConstraint) -> str:
    rendered = str(constraint.sqltext).lower()
    return "".join(character for character in rendered if character not in " \t\r\n()\"`")


def _sqlite_copy_from_without_obsolete_constraints(
    table_name: str,
    *,
    check_sql: frozenset[str] = frozenset(),
    unique_columns: frozenset[tuple[str, ...]] = frozenset(),
) -> sa.Table:
    bind = op.get_bind()
    table = sa.Table(table_name, sa.MetaData(), autoload_with=bind)
    removed_checks: set[str] = set()
    removed_uniques: set[tuple[str, ...]] = set()
    for constraint in tuple(table.constraints):
        if isinstance(constraint, sa.CheckConstraint):
            normalized = _normalized_check_sql(constraint)
            if normalized in check_sql:
                table.constraints.remove(constraint)
                removed_checks.add(normalized)
        elif isinstance(constraint, sa.UniqueConstraint):
            columns = tuple(column.name for column in constraint.columns)
            if columns in unique_columns:
                table.constraints.remove(constraint)
                removed_uniques.add(columns)
    if removed_checks != set(check_sql) or removed_uniques != set(unique_columns):
        raise RuntimeError(f"unsupported legacy constraints for {table_name}")
    return table
```

实际实现允许做等价的小幅调整，但必须满足：

- SQLite 的每个受影响表通过 `copy_from` 排除且仅排除目标旧约束。
- SQLite 不再调用不存在的旧约束名进行 `drop_constraint`。
- PostgreSQL 继续执行现有显式 `drop_constraint`。
- Index 删除/重建、列重命名、新 CHECK/UNIQUE 创建保持原顺序。
- 不编辑 `0001` Revision，不改 Revision ID。

- [ ] **Step 5：运行历史升级测试确认 GREEN**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py::test_real_orm_legacy_sqlite_upgrades_without_data_loss \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-green
```

Expected：两个参数场景全部 PASS。

- [ ] **Step 6：扩展迁移矩阵回归**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py \
  tests/backend/test_world_clock.py::test_schema_upgrade_adopts_legacy_schema_without_resetting_world_state \
  -q -rs -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-migrations
```

Expected：SQLite 全部 PASS；未设置 `TEST_POSTGRES_URL` 时 PostgreSQL Migration 测试明确 skip。确认正式 `0001`、历史未命名约束和空库都通过。

- [ ] **Step 7：Task 1 Review Gate**

检查：

- `git diff --check`
- 只修改本 Task 列出的 Migration/Test Support 文件。
- 测试未访问真实 `backend/data/aleria.db`。
- 独立 Reviewer 无 Critical/Important 后才进入 Task 2。

### Task 2：让 Windows Git Bash 原生使用项目虚拟环境

**Files：**

- Modify: `scripts/start-dev.sh`
- Modify: `tests/backend/test_start_dev.py`

**Interfaces：**

- Consumes: `python -m scripts.start_dev [--check]`
- Produces: Git Bash 优先选择 `<repo>/.venv/Scripts/python.exe`
- Preserves: PowerShell/CMD Wrapper 和统一 Python Launcher 行为

- [ ] **Step 1：写 Windows venv 选择 RED 测试**

在 `tests/backend/test_start_dev.py` 新增隔离 Shell Probe：

```python
def test_shell_launcher_prefers_windows_project_venv(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    windows_python = repo / ".venv" / "Scripts" / "python.exe"
    scripts.mkdir(parents=True)
    windows_python.parent.mkdir(parents=True)
    shutil.copy(PROJECT_ROOT / "scripts" / "start-dev.sh", scripts / "start-dev.sh")
    windows_python.write_text(
        "#!/usr/bin/env sh\nprintf '%s\\n' \"$@\"\n",
        encoding="utf-8",
    )
    windows_python.chmod(0o755)

    result = subprocess.run(
        ["sh", str(scripts / "start-dev.sh"), "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["-m", "scripts.start_dev", "--check"]
```

测试必须在找不到 `sh` 的环境中给出清晰的项目测试约束，而不是误报产品失败；当前 Windows 开发环境有 Git Bash，最终还必须执行真实 Git Bash Smoke。

- [ ] **Step 2：运行确认 RED**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_start_dev.py::test_shell_launcher_prefers_windows_project_venv \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/start-dev-sh-red
```

Expected：旧脚本忽略 `.venv/Scripts/python.exe`，测试失败。

- [ ] **Step 3：实现最小 Shell 修复**

把 `scripts/start-dev.sh` 的 Python 选择顺序调整为：

```sh
if [ -x "$repo_root/.venv/Scripts/python.exe" ]; then
    python_command="$repo_root/.venv/Scripts/python.exe"
elif [ -x "$repo_root/.venv/bin/python" ]; then
    python_command="$repo_root/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    python_command=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
    python_command=$(command -v python)
else
    echo "Python was not found. Install Python 3.11+ or create .venv first." >&2
    exit 1
fi
```

不在 Shell 中复制 Python Launcher 的依赖检查、迁移或进程管理逻辑。

- [ ] **Step 4：运行确认 GREEN 并回归启动逻辑**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_start_dev.py \
  -q -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/start-dev-sh-green
```

Expected：全部 PASS。

- [ ] **Step 5：真实 Git Bash Check Smoke**

```bash
cd /d/pythonproject/Aleria_AI_Town
./scripts/start-dev.sh --check
```

Expected：输出的 Python 为 `D:/pythonproject/Aleria_AI_Town/.venv/Scripts/python.exe`，并确认 Backend/Frontend URL。该命令不得迁移或启动服务。

- [ ] **Step 6：Task 2 Review Gate**

确认 Shell 只负责选择 Python 和转交参数；Linux/macOS `.venv/bin/python` 路径未回归；无未解决 Critical/Important。

### Task 3：真实启动验收、文档和阶段关闭

**Files：**

- Modify: `README.md`
- Modify: `docs/14_Development_Environment.md`
- Modify: `.superpowers/sdd/2026-09-04-agent-runtime-foundation/progress.md`
- Modify: `.superpowers/sdd/2026-09-04-agent-runtime-foundation/task-7-report.md`

**Interfaces：**

- Consumes: 完成后的 `upgrade_schema`、`start-dev.sh`、现有同步 World Tick/Run API
- Produces: 可复现 Git Bash 启动步骤、备份策略、最终验收证据
- Preserves: 用户手动 Review/Commit 工作流

- [ ] **Step 1：用临时副本复现真实数据库升级**

不得直接迁移用户数据库。先建立临时目录和副本：

```bash
cd /d/pythonproject/Aleria_AI_Town
mkdir -p /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-smoke
cp backend/data/aleria.db \
  /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-smoke/aleria.db

DATABASE_URL='sqlite:///C:/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-smoke/aleria.db' \
  ./.venv/Scripts/python.exe -m scripts.upgrade_schema
```

Expected：退出码 0，版本到 `0003`。只输出版本、列名、关系计数和非敏感状态，不输出聊天正文。

- [ ] **Step 2：验证临时副本的数据与结构**

使用只读查询核对：

- World 仍为同一 ID/day/time，旧 tick 正确迁移为 clock_tick/world_version。
- 4 个 Location、3 个 NPC、1 个 Player、1 个 Quest 仍存在。
- Conversation/Message 行数与迁移前一致。
- 外键检查无错误。
- `alembic_version=0003`。
- 无 `_alembic_tmp_*`。

如果真实副本揭示测试未覆盖的另一种历史结构，停止 Task 3，回到 Task 1 增加 RED 测试；不得在 Smoke 中临时修改数据库绕过。

- [ ] **Step 3：更新用户文档**

README 和开发环境文档必须给出：

```bash
cd /d/pythonproject/Aleria_AI_Town
./scripts/start-dev.sh --check
./scripts/start-dev.sh
```

并说明：

- 推荐从 Git Bash/PowerShell 终端启动，不把双击窗口是否停留当作成功标准。
- 启动顺序是 Migration → Seed-if-empty → Backend/Frontend。
- 首次升级重要本地数据前先备份 SQLite。
- 禁止手工修改 `alembic_version` 或删除数据库来伪造升级成功。
- Docker/PostgreSQL 的命令和限制保持不变。

- [ ] **Step 4：实际本地服务 Smoke**

在用户确认允许真实数据库升级并完成备份后，从 Git Bash 启动：

```bash
cd /d/pythonproject/Aleria_AI_Town
cp backend/data/aleria.db \
  "backend/data/aleria.before-foundation-closeout-$(date +%Y%m%d-%H%M%S).db"
./scripts/start-dev.sh
```

另一个 Git Bash 终端执行：

```bash
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/world
```

在 Swagger 或游戏页面完成：一次同步 Tick、读取返回的 Run ID、查询 Agent Run Detail、确认 3 proposals / 3 actions / 3 events / 14 traces。按 `Ctrl+C` 后确认 8000/5173 不再监听。

- [ ] **Step 5：运行聚焦与完整 Backend**

```bash
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py \
  tests/backend/test_start_dev.py \
  tests/backend/test_agent_run_repository.py \
  tests/backend/test_agent_run_api.py \
  -q -rs -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-focused

./.venv/Scripts/python.exe -m pytest tests/backend \
  -q -rs -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-backend
```

Expected：零失败；未设置 `TEST_POSTGRES_URL` 时只允许两个有明确原因的 PostgreSQL skip。

- [ ] **Step 6：运行 Frontend 与 Compose Gates**

```bash
npm --prefix frontend test
npm --prefix frontend run type-check
npm --prefix frontend run build

docker-compose.exe --env-file .env.production.example config --quiet
docker-compose.exe -f compose.yaml -f compose.postgres-test.yaml \
  --env-file .env.production.example config --quiet
```

Expected：Frontend 测试、Type Check、Build 和两份 Compose Parse 均成功。已有 Phaser 大 Chunk 警告可记录，但不是本次阻塞项。

- [ ] **Step 7：条件式 PostgreSQL Smoke**

只有 Docker daemon 可用时执行以下 PostgreSQL 集成步骤。2026-09-09 收口复验修正：backend 启动会在 public 迁移并播种，不能与迁移/Runtime 测试共用数据库。使用不同的独立 Compose project/volume；测试项目只启动 db，public 必须无应用表或 alembic_version。禁止把 TEST_POSTGRES_URL 指向已有业务数据库，不得清空业务 public 或伪造版本号绕过检查。

先用第一个项目验证 backend 构建、迁移和健康状态：

```bash
export POSTGRES_PASSWORD='aleria-test-only'
docker compose -p aleria-backend-smoke --env-file .env.production.example \
  up -d --build --wait --wait-timeout 120 db backend
docker compose -p aleria-backend-smoke --env-file .env.production.example ps
docker compose -p aleria-backend-smoke --env-file .env.production.example \
  exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').status)"
docker compose -p aleria-backend-smoke --env-file .env.production.example down
unset POSTGRES_PASSWORD
```

再用第二个全新 db-only 项目及其独立卷执行测试（使用干净测试 shell，避免继承 DATABASE_URL 覆盖值）：

```bash
export POSTGRES_PASSWORD='aleria-test-only'
export TEST_POSTGRES_PORT='55432'
docker compose -p aleria-postgres-test \
  -f compose.yaml -f compose.postgres-test.yaml \
  --env-file .env.production.example up -d --wait --wait-timeout 120 db
docker compose -p aleria-postgres-test \
  -f compose.yaml -f compose.postgres-test.yaml \
  --env-file .env.production.example exec -T db psql -U aleria -d aleria \
  -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
# 以上查询应无应用表；此测试项目不要启动 backend。

export TEST_POSTGRES_URL='postgresql+psycopg://aleria:aleria-test-only@127.0.0.1:55432/aleria'
./.venv/Scripts/python.exe -m pytest \
  tests/backend/test_schema_migrations.py \
  tests/backend/test_postgres_runtime.py \
  -q -rs -p no:cacheprovider \
  --basetemp /c/Users/yangzhaoting/Documents/ChatGPT/ai小镇全栈/foundation-closeout-postgres

docker compose -p aleria-postgres-test \
  -f compose.yaml -f compose.postgres-test.yaml \
  --env-file .env.production.example down
unset TEST_POSTGRES_URL TEST_POSTGRES_PORT POSTGRES_PASSWORD
```

两处 up 都等待健康，只有成功退出后才继续后续请求/测试。构建、等待或测试失败时仍需执行该项目的 down 并保留诊断；不要继续到依赖失败步骤的命令。down 默认保留卷；只在确认卷属于本次可丢弃测试且获准后清理，不能对业务项目执行 down -v。Daemon 不可用时记录真实错误并保留两项 skip，不得宣称 PostgreSQL Runtime Smoke 通过。这里使用已验证的 docker compose v5；不要复用已被 backend 播种的测试卷。

- [ ] **Step 8：最终范围与 Git Gate**

```bash
git diff --check
git status --short
git diff --cached --quiet
git rev-parse HEAD
```

Expected：

- 暂存区为空。
- HEAD 在实现期间不变。
- 产品变更只涉及本计划文件职责图中的范围。
- 没有 Memory/LLM/Async/Social/Agent Lab 越界。

- [ ] **Step 9：独立 Review 与用户交付**

独立 Reviewer 检查：

- 两种真实历史 SQLite 输入均从 RED 到 GREEN。
- 没有以删库、重建或伪造 Alembic 版本解决问题。
- 所有哨兵数据逐字段保留。
- PostgreSQL 路径没有回归。
- Git Bash 使用项目 Windows venv。
- Public API 和 RPG 行为未变化。

Critical/Important 清零后，更新 Task 7 报告和进度账本，停止等待用户 Review。用户自行提交；建议提交信息：

```text
fix: close historical sqlite migration and git bash startup gaps
```

## 第一阶段完成后的下一步

用户 Review 并手动提交本计划实现后：

1. 新建 `docs/superpowers/roadmaps/2026-09-xx-ai-native-agent-rpg-stages-2-to-6-cn.md`。
2. 只记录阶段 2–6 的目标、依赖、用户效果、技术交付和验收边界。
3. 不提前写阶段 2 的逐文件计划，也不提前实现 Memory Schema。
4. 用户 Review 路线文档并提交。
5. 新建一个干净 Work 聊天，从阶段 2“感知、记忆与反思”的独立中文 Spec 开始。
