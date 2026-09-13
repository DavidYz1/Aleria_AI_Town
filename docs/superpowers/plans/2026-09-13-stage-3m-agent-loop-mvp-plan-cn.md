# Stage 3m Agent Loop MVP 实施计划（aggressive 优化版）

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐 Task 执行本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 5 天内产出**可展示**的 Agent MVP —— NPC 基于身份与记忆自主形成目标、生成计划、通过受校验的工具修改世界，全过程在 UI 上可见。

**定位（重要）：** 这是**演示品**，不是精简版生产 Runtime。当"更严谨"与"更快看到效果"冲突时，**选后者**，并把取舍记在 Task 里。

**Architecture:** LLM 一次 structured output 产出 `thought + goal + steps`；计划存入单表 `agent_plans` 跨 tick 续用；提案经 `ActionRegistry` 校验后由现有纯函数 orchestrator 执行；任何失败降级到确定性 `decide_action`。orchestrator 保持无 IO。

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.x / Alembic / Pydantic v2 / pytest / Vue 3 + TypeScript

**Spec:** `docs/superpowers/specs/2026-09-13-stage-3m-agent-loop-mvp-design-cn.md`

---

## 测试范围裁决（本版最重要的变更）

AGENTS.md 规定 **TDD 是强制流程**，本计划完全遵守：**凡是写了的测试，一律 RED → GREEN → REFACTOR**。

但 TDD 规定的是「写了的测试怎么写」，不规定「哪些行为必须有测试」。本版据此把测试从 38 个收缩到 **10 个**，依据是 spec §15 已声明的「只测关键契约」。

### 保留的 10 个测试（绝不再砍）

| # | 测试 | 为什么必须有 |
| --- | --- | --- |
| 1 | Golden 快照比对 | 唯一能证明 Stage 1/2 零漂移的硬证据 |
| 2-4 | `AgentDecision` 三条 schema 边界 | structured output 是核心机制，边界错了会静默产出垃圾计划 |
| 5 | `agent_plans` partial unique index | **唯一会静默失败**的地方 —— 索引没生效不会报错，只会悄悄允许多条活跃计划 |
| 6-8 | Planner 状态机三条 | 「复用计划不调 LLM」「provider 失败兜底」「过龄重规划」，错一条整个 Agent Loop 行为就错 |
| 9-10 | 降级链路两条 | 「兜底生效且世界推进」是核心卖点，必须有证据；「别名兼容」保护现有 11 处调用 |

### 砍掉的 28 个测试及理由

| 原测试 | 数量 | 砍掉的依据 |
| --- | --- | --- |
| MCP manifest 形状 | 5 | 纯数据转换；位置参数兼容已被现有 `test_agent_orchestrator.py:262` 覆盖；格式错了在第一次 Live 调用就暴露 |
| Repository CRUD | 3 | 薄封装，错了在 Task 3 的手动验证立刻可见（只保留索引那一条） |
| Plan API 端点 | 4 | 端到端 `curl` + 前端渲染即验证，比单测更接近真实 |
| Provider factory 降级 | 3 | 启动时打印 provider 类型即可见 |
| 前端组件 | 4 | UI 肉眼验证更快更准，组件测试对演示品性价比最低 |
| Context 八段组装 | 1 | 内容会直接打印进 trace，看一眼就知道对不对 |
| Fake provider 确定性 | 1 | 被 Planner 状态机测试隐含覆盖 |
| 其余 schema/契约细节 | 7 | 三条边界足够证明校验生效 |

**每个被砍的位置都有对应的手动验证步骤**，写在各 Task 里。不是不验证，是换更便宜的验证方式。

---

## Global Constraints

### 来自 AGENTS.md（项目硬规则，不可协商）

- **Agent 不执行任何 git 写命令**：禁止 `git add` / `commit` / `reset` / `checkout` / `switch` / `clean` / `stash` / `push`。产出保持未暂存、未提交，由人类 review 后手动提交。
- **TDD 强制**：本计划保留的 10 个测试必须走 RED → GREEN。RED 必须是「因目标行为缺失而失败」，import 错误 / fixture 问题导致的失败**不算 RED**，先修掉再重跑。
- **禁止空洞断言**：集合断言必须配非空前提断言。
- **验证基线命令**（Windows，沙箱外运行）：
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
  npm --prefix frontend test
  npm --prefix frontend run type-check
  ```
- **不得引入新的 skip 或新的 warning**。基线：4 skip（`TEST_POSTGRES_URL` 未设置的 opt-in 测试）、1 warning（Starlette/httpx 弃用）。
- **禁止删除 `backend/data/aleria.db`**，测试一律用 `tmp_path`。
- **migration 链 `0001→0002→0003→0004`**，只允许新增 `0005`。
- 每个 Task ≤ 8 个文件，严格遵守文件清单。

### 来自 spec（设计约束）

- **唯一不变量**：LLM 任何失败（超时、非法 schema、提案被拒），世界一定能推进。
- **动作空间锁定 6 个动词**：`move / work / eat / talk / rest / wait`，不得新增。
- **`run_deterministic_advance` 保持向后兼容**，现有 11 处调用零改动。
- **不做**：schema repair 重试、Goal Arbitration、Rolling Plan 防循环、MCP 传输层、SSE 流式推送。

### 演示品定位带来的放松（本版新增）

- **事务边界尽力而为**：Plan 写入与 `persist_run` 尽量同事务，但单机演示无并发，不为此增加复杂度。
- **错误分类从简**：所有 provider 异常归为一类降级处理，不区分超时 / 解析失败 / 限流。
- **每个 Task 结束问一句**：「这一步在 UI 或终端上能看到什么？」看不到任何变化的 Task 说明排错了顺序。

### 回归闸门（Task 0 建立后全程生效）

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_golden_deterministic.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**失败 = Stage 1 行为漂移 = 立即停止定位**，不得通过更新快照"修复"。

---

## 关于代码块的取舍

本计划对**新契约**与**保留的 10 个测试**给出完整代码；对有强既有模式可循的部分（路由、Provider、前端）给出精确参照文件与行号。

依据是 AGENTS.md 的「严格遵循既有模式」：照抄 `npcs.py` 比照抄计划里另写的一版更不容易漂移。执行到这些步骤时**先读参照文件再动手**。参照文件与本计划 Interfaces 块冲突时，**以 Interfaces 块为准**。

---

## File Structure

### 新建（14 个，比上版少 5 个）

| 路径 | 职责 |
| --- | --- |
| `backend/app/agents/planning_contracts.py` | `PlanStep` / `AgentDecision` |
| `backend/app/llm/planning_provider.py` | `PlanningRequest` / Protocol / Fake / Live / `build_planning_provider` |
| `backend/app/agents/planner.py` | Context 组装 + Plan 状态机 |
| `backend/app/database/plan_repository.py` | `agent_plans` 读写 |
| `backend/migrations/versions/0005_stage3m_agent_plans.py` | 建表 |
| `backend/app/schemas/plan.py` | Plan API 响应模型 |
| `backend/app/api/npc_plan.py` | `GET /api/npcs/{npc_id}/plan` |
| `scripts/eval_agent.py` | 离线评估 |
| `frontend/src/api/npcPlan.ts` | API 客户端 + 类型（**合并**，不单独建 types 文件） |
| `frontend/src/components/NpcThoughtTab.vue` | 「思考」Tab（**组件内持有状态，不建 store**） |
| `tests/backend/golden/deterministic_20tick.json` | 快照基线 |
| `tests/backend/test_golden_deterministic.py` | 闸门（1 个测试） |
| `tests/backend/test_planning_core.py` | schema 边界 3 + 状态机 3（**合并两个文件**） |
| `tests/backend/test_agent_loop_fallback.py` | 降级链路 2 + 索引 1 |

### 修改（11 个）

| 路径 | 改动 |
| --- | --- |
| `backend/app/agents/action_registry.py` | `ActionDefinition` 末尾追加 2 个带默认值字段；新增 `to_tool_manifest()`；补齐 6 个动作描述 |
| `backend/app/agents/orchestrator.py` | 新增 `run_advance`；`run_deterministic_advance` 降为别名；fallback 重试 |
| `backend/app/database/models.py` | 新增 `AgentPlan` |
| `backend/app/services/world_clock_service.py` | 接入 planner，切到 `run_advance` |
| `backend/app/schemas/agent_run.py:24` | `TRACE_STAGES` 追加 `planning` |
| `backend/app/schemas/world_clock.py:9` | `WorldTickRequest` 追加可选 `runtime_mode` |
| `backend/app/llm/factory.py` | 追加 `build_planning_provider` |
| `backend/app/core/config.py` | 追加 planning provider 配置 |
| `backend/app/main.py` | 注册 `npc_plan` 路由 |
| `frontend/src/components/NpcDetailPanel.vue` | 挂载「思考」Tab |
| `README.md` | 架构叙事 |

---

## Task 总览

| Task | 内容 | 工时 | 测试数 |
| --- | --- | --- | --- |
| 0 | Golden 快照闸门 | 0.15d | 1 |
| 1 | 规划契约 + MCP 工具清单（**原 T1+T2 合并**） | 0.4d | 3 |
| 2 | `agent_plans` 表 + repository | 0.4d | 1 |
| 3 | Planner | 0.6d | 3 |
| 4 | Orchestrator 注入 + 兜底 | 0.3d | 2 |
| 5 | Service 接线 + Plan API | 0.5d | 0 |
| 6 | Live Provider | 0.5d | 0 |
| 7 | 前端「思考」Tab | 0.6d | 0 |
| 8 | Eval + 演示 + 文档（**原 T9+T10 合并**） | 0.5d | 0 |

**合计 3.95 天**（上版 5.2 天），留足 1 天缓冲应对 Live Provider 调试与演示打磨。

**依赖**：Task 0 最先。之后 Task 1 / 2 / 6 可并行 → Task 3 → Task 4 → Task 5 → Task 7 / 8 可并行。

---

### Task 0: Golden 快照回归闸门

**Files:**
- Create: `tests/backend/test_golden_deterministic.py`
- Create: `tests/backend/golden/deterministic_20tick.json`

**Interfaces:**
- Consumes: `run_deterministic_advance`（`backend/app/agents/orchestrator.py:21`）、`LocationSnapshot` / `NpcSnapshot` / `WorldSnapshot`（`backend/app/world/types.py`）
- Produces: `GOLDEN_PATH`、`build_golden_world()`、`run_twenty_ticks(world) -> list[dict]` — Task 3 / 4 / 8 复用

- [ ] **Step 1: 写闸门测试**

创建 `tests/backend/test_golden_deterministic.py`：

```python
"""Stage 1 确定性行为回归闸门。

失败意味着 run_deterministic_advance 输出发生漂移。
禁止通过重新生成快照"修复" —— 必须定位根因。
"""
import json
from dataclasses import asdict
from pathlib import Path

from backend.app.agents.orchestrator import run_deterministic_advance
from backend.app.world.types import LocationSnapshot, NpcSnapshot, WorldSnapshot


GOLDEN_PATH = Path(__file__).parent / "golden" / "deterministic_20tick.json"

LOCATIONS = (
    LocationSnapshot(id="tavern", name="星辉酒馆", sort_order=1),
    LocationSnapshot(id="park", name="中央公园", sort_order=2),
    LocationSnapshot(id="castle", name="晨曦城堡", sort_order=3),
    LocationSnapshot(id="forest", name="低语森林", sort_order=4),
)


def _npc(npc_id, role, location_id, sort_order, energy, mood, social):
    return NpcSnapshot(
        id=npc_id, name=npc_id.title(), role=role, personality=("steady",),
        sort_order=sort_order, location_id=location_id, current_action="rest",
        energy=energy, mood=mood, social=social,
    )


def build_golden_world() -> WorldSnapshot:
    """固定初始世界，纯内存，不依赖数据库。

    NPC id 必须与 Task 2 的测试种子一致（elena / grey / mira），
    否则 Task 3 写 agent_plans 时外键失败。
    """
    return WorldSnapshot(
        id="aleria-town", name="曦谷", day=1, time="08:00",
        clock_tick=0, world_version=1, event_sequence=0,
        locations=LOCATIONS,
        npcs=(
            _npc("elena", "baker", "tavern", 1, 80, 70, 60),
            _npc("grey", "guard", "castle", 2, 55, 45, 30),
            _npc("mira", "scholar", "park", 3, 40, 85, 75),
        ),
    )


def run_twenty_ticks(world: WorldSnapshot) -> list[dict]:
    frames, current = [], world
    for _ in range(20):
        result = run_deterministic_advance(current)
        frames.append(
            {
                "world": asdict(result.world),
                "proposals": [asdict(p) for p in result.proposals],
                "traces": [asdict(t) for t in result.traces],
                "events": [asdict(e) for e in result.events],
            }
        )
        current = result.world
    return frames


def test_deterministic_output_matches_golden_snapshot():
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    actual = run_twenty_ticks(build_golden_world())
    assert len(actual) == 20, "必须产出 20 帧，空集合会让下面的比对恒真"
    assert actual == expected, "Stage 1 行为漂移，禁止更新快照，先定位根因"
```

`asdict` 对 `Mapping` 字段（`TraceDraft.data` / `DomainEventDraft.payload`）会原样保留。若某字段含不可 JSON 序列化的值（如 `StrEnum`），在 `json.dumps` 时用 `default=str` 处理 —— 下一步会暴露这一点。

- [ ] **Step 2: RED —— 运行确认因缺少快照而失败**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_golden_deterministic.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：FAIL，`FileNotFoundError`。这是有效 RED（目标数据缺失）。

- [ ] **Step 3: 生成快照**

```powershell
New-Item -ItemType Directory -Force tests\backend\golden
.\.venv\Scripts\python.exe -c "import json, sys; sys.path.insert(0, '.'); from tests.backend.test_golden_deterministic import build_golden_world, run_twenty_ticks, GOLDEN_PATH; GOLDEN_PATH.write_text(json.dumps(run_twenty_ticks(build_golden_world()), ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding='utf-8')"
```

若报 `TypeError: Object of type X is not JSON serializable`，`default=str` 已覆盖大部分情况；仍失败则在 `run_twenty_ticks` 内把该字段显式转为 `str`。

- [ ] **Step 4: GREEN —— 运行确认通过**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_golden_deterministic.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：1 passed。

- [ ] **Step 5: 人工抽查快照**

打开 `tests/backend/golden/deterministic_20tick.json` 确认：20 个 frame；`world.clock_tick` 从 1 递增到 20；`world.world_version` 从 2 递增到 21；每帧 3 条 proposal。不符则修正生成逻辑后重新生成。

- [ ] **Step 6: 全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：全绿，skip 仍为 4，warning 仍为 1。

**看得到什么**：终端多出一条恒定通过的闸门测试 —— 此后每个 Task 都靠它证明没碰坏旧行为。

- [ ] **Step 7: 停机等待人类 review 与提交**

```
test: add golden snapshot gate for deterministic engine
```

---

### Task 1: 规划契约与 MCP 工具清单

**⚠️ 关键约束**：`ActionDefinition` 现有 7 处构造全是**位置参数**（`action_registry.py` 内 6 处、`tests/backend/test_agent_orchestrator.py:262` 1 处）。新字段**必须追加在末尾且带默认值**。

**Files:**
- Create: `backend/app/agents/planning_contracts.py`
- Create: `backend/app/llm/planning_provider.py`
- Modify: `backend/app/agents/action_registry.py:25-32`、`:41`、`:286-338`
- Test: `tests/backend/test_planning_core.py`（本 Task 写 schema 3 条，Task 3 追加状态机 3 条）

**Interfaces:**
- Produces:
  - `PlanStep(action_type, target_kind, target_id, intent)`
  - `AgentDecision(thought, goal, goal_reason, steps, prompt_version)`
  - `PlanningRequest(npc_id, context_text, tool_manifest, timeout_seconds)`
  - `PlanningProvider` Protocol：`plan(request) -> AgentDecision`
  - `PlanningProviderError(RuntimeError)`、`FakePlanningProvider()`
  - `ActionDefinition.description: str = ""`、`ActionDefinition.input_schema: Mapping = {}`
  - `ActionRegistry.to_tool_manifest() -> list[dict]`

- [ ] **Step 1: 写 schema 边界测试**

创建 `tests/backend/test_planning_core.py`：

```python
import pytest
from pydantic import ValidationError

from backend.app.agents.planning_contracts import AgentDecision, PlanStep


def _kwargs():
    return {
        "thought": "体力偏低，先补充再出门",
        "goal": "补充体力后去广场打听消息",
        "goal_reason": "昨天玩家提到有孩子走失",
        "steps": (
            PlanStep(action_type="eat", target_kind=None, target_id=None, intent="进食"),
            PlanStep(action_type="move", target_kind="location", target_id="park", intent="前往广场"),
        ),
        "prompt_version": "planning-v1",
    }


def test_valid_decision_is_accepted():
    decision = AgentDecision(**_kwargs())
    assert len(decision.steps) == 2
    assert decision.steps[0].action_type == "eat"


def test_rejects_action_outside_the_six_verbs():
    """动作空间锁定为 6 个动词，模型不得发明新动作。"""
    kwargs = _kwargs()
    kwargs["steps"] = (
        PlanStep.model_construct(action_type="craft", target_kind=None, target_id=None, intent="打造"),
    )
    with pytest.raises(ValidationError):
        AgentDecision(**kwargs)


def test_rejects_empty_thought_and_oversized_plan():
    """两条边界合一：空 thought 与超过 4 步的计划都必须被拒。"""
    empty_thought = _kwargs() | {"thought": ""}
    with pytest.raises(ValidationError):
        AgentDecision(**empty_thought)

    step = PlanStep(action_type="rest", target_kind=None, target_id=None, intent="休息")
    oversized = _kwargs() | {"steps": (step,) * 5}
    with pytest.raises(ValidationError):
        AgentDecision(**oversized)
```

- [ ] **Step 2: RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_planning_core.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：FAIL，`ModuleNotFoundError: backend.app.agents.planning_contracts`。修掉 import 问题后若仍是这个错误，即为有效 RED。

- [ ] **Step 3: 实现契约**

创建 `backend/app/agents/planning_contracts.py`：

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ACTION_TYPES = Literal["move", "work", "eat", "talk", "rest", "wait"]


class PlanStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_type: ACTION_TYPES
    target_kind: Literal["location", "npc"] | None = None
    target_id: str | None = None
    intent: str = Field(min_length=1, max_length=200)


class AgentDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    thought: str = Field(min_length=1, max_length=800)
    goal: str = Field(min_length=1, max_length=200)
    goal_reason: str = Field(min_length=1, max_length=500)
    steps: tuple[PlanStep, ...] = Field(min_length=1, max_length=4)
    prompt_version: Literal["planning-v1"]
```

- [ ] **Step 4: GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_planning_core.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：3 passed。

- [ ] **Step 5: 实现 Provider 骨架与 Fake（无测试，靠 Task 3 使用时暴露）**

创建 `backend/app/llm/planning_provider.py`：

```python
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.app.agents.planning_contracts import AgentDecision, PlanStep


class PlanningRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    npc_id: str = Field(min_length=1, max_length=64)
    context_text: str = Field(min_length=1, max_length=12000)
    tool_manifest: list[dict] = Field(default_factory=list)
    timeout_seconds: float = Field(default=8, gt=0, le=30)


class PlanningProviderError(RuntimeError):
    """规划 provider 不可用或返回不可解析的结果。"""


class PlanningProvider(Protocol):
    def plan(self, request: PlanningRequest) -> AgentDecision: ...


class FakePlanningProvider:
    """确定性替身：不调外部服务，输出只取决于 npc_id。"""

    provider_name = "fake"
    model_name = "fake-planner-1"
    last_tokens_used = None

    def plan(self, request: PlanningRequest) -> AgentDecision:
        return AgentDecision(
            thought=f"{request.npc_id} 正在评估当前状态与近期记忆",
            goal="维持日常节奏并保持体力",
            goal_reason="确定性替身不依赖世界状态，输出恒定",
            steps=(
                PlanStep(action_type="rest", target_kind=None, target_id=None, intent="原地休息恢复体力"),
                PlanStep(action_type="work", target_kind=None, target_id=None, intent="处理本职工作"),
            ),
            prompt_version="planning-v1",
        )
```

`provider_name` / `model_name` / `last_tokens_used` 是 Task 3 通过 `getattr` 读取的约定属性，Live Provider（Task 6）必须提供同名属性。

- [ ] **Step 6: 扩展 `ActionDefinition`（无测试）**

修改 `backend/app/agents/action_registry.py:25-32`，**在末尾**追加：

```python
from dataclasses import dataclass, field
from collections.abc import Mapping

from backend.app.agents.contracts import JsonValue


@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    required_target_kind: Literal["location", "npc"] | None
    validation_handler: ValidationHandler
    execution_handler: ExecutionHandler
    event_type: str
    public_label: str
    description: str = ""
    input_schema: Mapping[str, JsonValue] = field(default_factory=dict)
```

在 `ActionRegistry` 类中追加：

```python
    def to_tool_manifest(self) -> list[dict]:
        """输出 MCP tools/list 兼容格式。空 description 直接报错，不静默通过。"""
        manifest: list[dict] = []
        for definition in self._definitions.values():
            if not definition.description:
                raise ValueError(
                    f"action '{definition.action_type}' 缺少 description，模型无法理解该工具"
                )
            manifest.append(
                {
                    "name": definition.action_type,
                    "description": definition.description,
                    "inputSchema": dict(definition.input_schema),
                }
            )
        return manifest
```

若内部存放定义的属性名不是 `_definitions`，读 `action_registry.py:41-56` 对齐。

- [ ] **Step 7: 补齐 6 个动作的描述与 schema**

修改 `build_default_action_registry()`（`action_registry.py:286` 起）。先加辅助函数：

```python
def _schema(*, needs_target: bool, target_desc: str) -> dict:
    properties: dict = {
        "reason_code": {
            "type": "string",
            "description": "本次动作的简短原因编码，小写下划线，如 low_energy",
        }
    }
    required = ["reason_code"]
    if needs_target:
        properties["target_id"] = {"type": "string", "description": target_desc}
        required.append("target_id")
    return {"type": "object", "properties": properties, "required": required}
```

然后给 6 个 `ActionDefinition` 各追加两个位置参数。完整文案如下，逐条填入：

| 动作 | description | schema 参数 |
| --- | --- | --- |
| `move` | `"移动到镇上的另一个地点。目标必须是当前世界中存在的地点 id。"` | `_schema(needs_target=True, target_desc="目标地点 id，如 tavern / park / castle / forest")` |
| `rest` | `"原地休息以恢复体力。不需要目标。"` | `_schema(needs_target=False, target_desc="")` |
| `work` | `"从事本职工作，消耗体力并提升心情。不需要目标。"` | `_schema(needs_target=False, target_desc="")` |
| `eat` | `"进食以恢复体力。不需要目标。"` | `_schema(needs_target=False, target_desc="")` |
| `talk` | `"与同一地点的另一个 NPC 交谈。目标必须是当前与你处于同一地点的 NPC id。"` | `_schema(needs_target=True, target_desc="目标 NPC 的 id")` |
| `wait` | `"原地等待一个时间单位，不产生显著状态变化。不需要目标。"` | `_schema(needs_target=False, target_desc="")` |

- [ ] **Step 8: 手动验证 manifest（替代被砍的 5 个测试）**

```powershell
.\.venv\Scripts\python.exe -c "import json, sys; sys.path.insert(0, '.'); from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY; print(json.dumps(DEFAULT_ACTION_REGISTRY.to_tool_manifest(), ensure_ascii=False, indent=2))"
```

肉眼确认：6 个工具全在；每个都有非空 description；`move` 与 `talk` 的 `required` 含 `target_id`，其余不含。

- [ ] **Step 9: 全量回归 + golden 闸门**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**特别确认 `test_agent_orchestrator.py` 与 `test_action_registry.py` 全绿** —— 它们依赖位置参数构造。golden 必须 PASS（本 Task 不改变执行行为）。

**看得到什么**：终端能打印出一份 MCP 格式的工具清单 —— 这就是要喂给模型的东西。

- [ ] **Step 10: 停机等待人类 review 与提交**

```
feat: add planning contracts and mcp-compatible tool manifest
```

---

### Task 2: `agent_plans` 表与持久化

**Files:**
- Modify: `backend/app/database/models.py`（追加 `AgentPlan`）
- Create: `backend/migrations/versions/0005_stage3m_agent_plans.py`
- Create: `backend/app/database/plan_repository.py`
- Modify: `tests/backend/conftest.py`（追加 fixture）
- Test: `tests/backend/test_agent_loop_fallback.py`（本 Task 写索引 1 条，Task 4 追加降级 2 条）

**Interfaces:**
- Consumes: `AgentDecision`（Task 1）
- Produces:
  - `AgentPlan` ORM 模型
  - `PlanRepository(session)`：`get_active(world_id, npc_id)` / `create_from_decision(world_id, npc_id, decision, *, clock_tick, run_id, provider, model, latency_ms, tokens_used)` / `advance_step(plan, *, clock_tick)` / `abandon(plan, *, clock_tick)` / `recent(world_id, npc_id, *, limit)`

- [ ] **Step 1: 写唯一索引测试（唯一保留的持久化测试）**

创建 `tests/backend/test_agent_loop_fallback.py`：

```python
import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.agents.planning_contracts import AgentDecision, PlanStep
from backend.app.database.plan_repository import PlanRepository


def _decision() -> AgentDecision:
    return AgentDecision(
        thought="体力不足", goal="恢复体力后回到岗位", goal_reason="能量低于阈值",
        steps=(
            PlanStep(action_type="eat", target_kind=None, target_id=None, intent="进食"),
            PlanStep(action_type="work", target_kind=None, target_id=None, intent="回到工作"),
        ),
        prompt_version="planning-v1",
    )


def test_partial_index_allows_only_one_active_plan_per_npc(plan_session, seeded_ids):
    """这是整个持久化层唯一会静默失败的地方：

    partial unique index 若没生效不会报错，只会悄悄允许一个 NPC 同时有多条活跃计划，
    导致 Planner 的 get_active 随机返回其中一条。必须显式验证索引真的生效。
    """
    world_id, npc_id = seeded_ids
    repo = PlanRepository(plan_session)

    first = repo.create_from_decision(
        world_id, npc_id, _decision(),
        clock_tick=5, run_id=None, provider="fake", model="fake-1", latency_ms=1, tokens_used=1,
    )
    plan_session.commit()
    assert first.status == "active", "非空前提：第一条计划确实处于 active"

    repo.create_from_decision(
        world_id, npc_id, _decision(),
        clock_tick=6, run_id=None, provider="fake", model="fake-1", latency_ms=1, tokens_used=1,
    )
    with pytest.raises(IntegrityError):
        plan_session.commit()
    plan_session.rollback()

    # 反向验证：把第一条置为非活跃后，第二条必须能插入
    repo.abandon(repo.get_active(world_id, npc_id), clock_tick=7)
    plan_session.commit()
    repo.create_from_decision(
        world_id, npc_id, _decision(),
        clock_tick=8, run_id=None, provider="fake", model="fake-1", latency_ms=1, tokens_used=1,
    )
    plan_session.commit()
    assert repo.get_active(world_id, npc_id) is not None
```

- [ ] **Step 2: 添加 fixture**

在 `tests/backend/conftest.py` 末尾追加。**种子 NPC id 必须与 `build_golden_world()` 一致（elena / grey / mira）**，否则 Task 3 外键失败：

```python
@pytest.fixture
def plan_session(database_url):
    """迁移到 head 的临时 SQLite 会话。绝不触碰 backend/data/aleria.db。"""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session as SqlSession

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with SqlSession(engine) as session:
        yield session


@pytest.fixture
def seeded_ids(plan_session) -> tuple[str, str]:
    """返回 (world_id, npc_id)，id 与 build_golden_world() 对齐。"""
    from backend.app.database.models import NpcProfile, WorldState

    world = plan_session.get(WorldState, "aleria-town")
    if world is None:
        raise AssertionError(
            "种子世界缺失。照 tests/backend/test_agent_run_repository.py 的建世界方式"
            "在本 fixture 内插入 id 为 aleria-town 的世界与 elena/grey/mira 三个 NPC"
        )
    npc = plan_session.get(NpcProfile, "elena")
    if npc is None:
        raise AssertionError("种子 NPC elena 缺失，见上条说明")
    return world.id, npc.id
```

若迁移不自带种子数据，读 `tests/backend/test_agent_run_repository.py` 看现有测试如何建世界与 NPC，在 fixture 内照做。

- [ ] **Step 3: RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_agent_loop_fallback.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：FAIL，`ModuleNotFoundError: backend.app.database.plan_repository`。

- [ ] **Step 4: 添加 ORM 模型**

在 `backend/app/database/models.py` 末尾追加：

```python
class AgentPlan(Base):
    __tablename__ = "agent_plans"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_agent_plans"),
        CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="ck_agent_plans_status"),
        CheckConstraint("current_step_index >= 0", name="ck_agent_plans_current_step_index"),
        Index("ix_agent_plans_owner_status", "world_id", "owner_npc_id", "status", "created_clock_tick"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world_state.id", name="fk_agent_plans_world_id_world_state"))
    owner_npc_id: Mapped[str] = mapped_column(ForeignKey("npc_profiles.id", name="fk_agent_plans_owner_npc_id_npc_profiles"))
    source_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id", name="fk_agent_plans_source_run_id_agent_runs"), nullable=True)

    thought: Mapped[str] = mapped_column(String(800))
    goal: Mapped[str] = mapped_column(String(200))
    goal_reason: Mapped[str] = mapped_column(String(500))
    steps_json: Mapped[list] = mapped_column(JSON)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")

    created_clock_tick: Mapped[int] = mapped_column(Integer)
    updated_clock_tick: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(40))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 5: 写 migration**

创建 `backend/migrations/versions/0005_stage3m_agent_plans.py`：

```python
"""Add Stage 3m agent plans table (procedural memory)."""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_plans",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(), nullable=False),
        sa.Column("owner_npc_id", sa.String(), nullable=False),
        sa.Column("source_run_id", sa.String(36), nullable=True),
        sa.Column("thought", sa.String(800), nullable=False),
        sa.Column("goal", sa.String(200), nullable=False),
        sa.Column("goal_reason", sa.String(500), nullable=False),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_clock_tick", sa.Integer(), nullable=False),
        sa.Column("updated_clock_tick", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_agent_plans"),
        sa.ForeignKeyConstraint(["world_id"], ["world_state.id"], name="fk_agent_plans_world_id_world_state"),
        sa.ForeignKeyConstraint(["owner_npc_id"], ["npc_profiles.id"], name="fk_agent_plans_owner_npc_id_npc_profiles"),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.id"], name="fk_agent_plans_source_run_id_agent_runs"),
        sa.CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="ck_agent_plans_status"),
        sa.CheckConstraint("current_step_index >= 0", name="ck_agent_plans_current_step_index"),
    )
    op.create_index(
        "ix_agent_plans_owner_status",
        "agent_plans",
        ["world_id", "owner_npc_id", "status", "created_clock_tick"],
    )
    # 单 NPC 至多一条活跃计划。SQLite 与 PostgreSQL 均支持 partial unique index。
    op.create_index(
        "uq_agent_plans_active",
        "agent_plans",
        ["world_id", "owner_npc_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_plans_active", table_name="agent_plans")
    op.drop_index("ix_agent_plans_owner_status", table_name="agent_plans")
    op.drop_table("agent_plans")
```

- [ ] **Step 6: 实现 repository**

创建 `backend/app/database/plan_repository.py`：

```python
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.planning_contracts import AgentDecision
from backend.app.database.models import AgentPlan


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active(self, world_id: str, npc_id: str) -> AgentPlan | None:
        statement = select(AgentPlan).where(
            AgentPlan.world_id == world_id,
            AgentPlan.owner_npc_id == npc_id,
            AgentPlan.status == "active",
        )
        return self._session.scalars(statement).one_or_none()

    def create_from_decision(
        self, world_id: str, npc_id: str, decision: AgentDecision, *,
        clock_tick: int, run_id: str | None, provider: str, model: str,
        latency_ms: int | None, tokens_used: int | None,
    ) -> AgentPlan:
        plan = AgentPlan(
            id=str(uuid4()), world_id=world_id, owner_npc_id=npc_id, source_run_id=run_id,
            thought=decision.thought, goal=decision.goal, goal_reason=decision.goal_reason,
            steps_json=[step.model_dump() for step in decision.steps],
            current_step_index=0, status="active",
            created_clock_tick=clock_tick, updated_clock_tick=clock_tick,
            provider=provider, model=model, prompt_version=decision.prompt_version,
            latency_ms=latency_ms, tokens_used=tokens_used,
        )
        self._session.add(plan)
        self._session.flush()
        return plan

    def advance_step(self, plan: AgentPlan, *, clock_tick: int) -> AgentPlan:
        plan.current_step_index += 1
        plan.updated_clock_tick = clock_tick
        if plan.current_step_index >= len(plan.steps_json):
            plan.status = "completed"
        self._session.flush()
        return plan

    def abandon(self, plan: AgentPlan, *, clock_tick: int) -> AgentPlan:
        plan.status = "abandoned"
        plan.updated_clock_tick = clock_tick
        self._session.flush()
        return plan

    def recent(self, world_id: str, npc_id: str, *, limit: int) -> list[AgentPlan]:
        statement = (
            select(AgentPlan)
            .where(AgentPlan.world_id == world_id, AgentPlan.owner_npc_id == npc_id)
            .order_by(AgentPlan.created_clock_tick.desc(), AgentPlan.id.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))
```

- [ ] **Step 7: GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_agent_loop_fallback.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：1 passed。

- [ ] **Step 8: 确认 migration 链无分叉**

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads
```

预期：单一 head `0005`。

- [ ] **Step 9: 全量回归 + golden 闸门**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**看得到什么**：`alembic heads` 输出 0005；数据库多出 `agent_plans` 表。

- [ ] **Step 10: 停机等待人类 review 与提交**

```
feat: add agent_plans table for procedural memory
```

---

### Task 3: Planner

**⚠️ 外键前提**：本 Task 测试同时用 `build_golden_world()`（world.id=`aleria-town`，NPC `elena`/`grey`/`mira`）与真实 DB session。`create_from_decision` 写外键，**DB 中必须存在同名世界与 NPC**。Task 2 的 `seeded_ids` fixture 已按此对齐；若不符，**改 fixture 而不是改 `build_golden_world()`** —— 改后者会让 golden 快照失效。

**Files:**
- Create: `backend/app/agents/planner.py`
- Test: `tests/backend/test_planning_core.py`（追加状态机 3 条）

**Interfaces:**
- Consumes: `AgentDecision`（Task 1）、`PlanningProvider` / `PlanningRequest` / `PlanningProviderError`（Task 1）、`to_tool_manifest()`（Task 1）、`PlanRepository`（Task 2）、`RetrievalRequest` / `RetrievalScope` / `MemoryType`（`backend/app/agents/memory_retrieval.py`）
- Produces:
  - `LastOutcome(action_type: str, accepted: bool, code: str)` — frozen dataclass，Task 5 构造并回传
  - `PlanningOutcome(proposal, source, plan, decision, latency_ms, tokens_used)` — frozen dataclass
  - `AgentPlanner(repository, retriever, provider, registry, *, max_plan_age_ticks=8)`
  - `AgentPlanner.build_context(world, actor, active_plan, memories, last_outcome) -> str`
  - `AgentPlanner.decide(world, actor, *, last_outcome) -> PlanningOutcome`

- [ ] **Step 1: 追加状态机测试**

在 `tests/backend/test_planning_core.py` 追加（覆盖 spec §6 的三条核心规则）：

```python
from dataclasses import replace

from backend.app.agents.contracts import ProposalSource
from backend.app.agents.memory_retrieval import RetrievalResult
from backend.app.agents.planner import AgentPlanner
from backend.app.database.plan_repository import PlanRepository
from backend.app.llm.planning_provider import PlanningProviderError
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY
from tests.backend.test_golden_deterministic import build_golden_world


class StubProvider:
    provider_name = "stub"
    model_name = "stub-1"
    last_tokens_used = 42

    def __init__(self, decision=None, error=None):
        self.decision, self.error, self.calls = decision, error, 0

    def plan(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.decision


class StubRetriever:
    def retrieve(self, request):
        return RetrievalResult(memories=(), mode="stub")


def _plan_decision(*actions: str) -> AgentDecision:
    return AgentDecision(
        thought="测试推理", goal="测试目标", goal_reason="测试理由",
        steps=tuple(
            PlanStep(action_type=a, target_kind=None, target_id=None, intent=f"执行{a}")
            for a in actions
        ),
        prompt_version="planning-v1",
    )


def _planner(plan_session, provider, **kwargs):
    return AgentPlanner(
        PlanRepository(plan_session), StubRetriever(), provider, DEFAULT_ACTION_REGISTRY, **kwargs
    )


def test_active_plan_is_reused_without_calling_the_model(plan_session, seeded_ids):
    """spec §6 规则 2：有 active plan 时不调 LLM —— 这是成本控制的核心。"""
    provider = StubProvider(decision=_plan_decision("rest", "work"))
    planner = _planner(plan_session, provider)
    world = build_golden_world()
    actor = world.npcs[0]

    first = planner.decide(world, actor, last_outcome=None)
    plan_session.commit()
    assert provider.calls == 1
    assert first.source is ProposalSource.LLM
    assert first.proposal.action_type == "rest"

    second = planner.decide(world, actor, last_outcome=None)
    assert provider.calls == 1, "复用计划时不得再次调用模型"
    assert second.source is ProposalSource.EXISTING_PLAN
    assert second.proposal.action_type == "work"


def test_provider_failure_degrades_to_deterministic(plan_session, seeded_ids):
    """spec §13 唯一不变量：provider 失败仍产出可执行提案。"""
    planner = _planner(plan_session, StubProvider(error=PlanningProviderError("timeout")))
    world = build_golden_world()

    outcome = planner.decide(world, world.npcs[0], last_outcome=None)
    assert outcome.source is ProposalSource.FALLBACK
    assert outcome.proposal.action_type in {"move", "work", "eat", "talk", "rest", "wait"}
    assert outcome.plan is None


def test_plan_older_than_max_age_triggers_replanning(plan_session, seeded_ids):
    """spec §6 规则 5：过龄强制完成，防止 NPC 卡在一个计划里。"""
    provider = StubProvider(decision=_plan_decision("rest", "work", "eat"))
    planner = _planner(plan_session, provider, max_plan_age_ticks=2)
    world = build_golden_world()
    actor = world.npcs[0]

    planner.decide(world, actor, last_outcome=None)
    plan_session.commit()
    assert provider.calls == 1

    aged = replace(world, clock_tick=world.clock_tick + 5)
    outcome = planner.decide(aged, actor, last_outcome=None)
    assert provider.calls == 2, "过龄计划应被放弃并触发重新规划"
    assert outcome.source is ProposalSource.LLM
```

- [ ] **Step 2: RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_planning_core.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：新增 3 条 FAIL（`ModuleNotFoundError: backend.app.agents.planner`），原 3 条仍 PASS。若 `RetrievalResult` 构造签名与 stub 不符，读 `memory_retrieval.py:79` 对齐后再确认 RED。

- [ ] **Step 3: 实现 Planner**

创建 `backend/app/agents/planner.py`：

```python
from dataclasses import dataclass
import time

from backend.app.agents.action_registry import ActionRegistry
from backend.app.agents.contracts import ActionProposal, ProposalSource
from backend.app.agents.memory_retrieval import MemoryType, RetrievalRequest, RetrievalScope
from backend.app.agents.planning_contracts import AgentDecision
from backend.app.llm.planning_provider import PlanningRequest
from backend.app.world.decision import decide_action
from backend.app.world.types import NpcSnapshot, WorldSnapshot


@dataclass(frozen=True)
class LastOutcome:
    action_type: str
    accepted: bool
    code: str


@dataclass(frozen=True)
class PlanningOutcome:
    proposal: ActionProposal
    source: ProposalSource
    plan: object | None
    decision: AgentDecision | None
    latency_ms: int | None
    tokens_used: int | None


class AgentPlanner:
    def __init__(self, repository, retriever, provider, registry: ActionRegistry, *, max_plan_age_ticks: int = 8):
        self._repository = repository
        self._retriever = retriever
        self._provider = provider
        self._registry = registry
        self._max_plan_age_ticks = max_plan_age_ticks

    def decide(self, world: WorldSnapshot, actor: NpcSnapshot, *, last_outcome: LastOutcome | None) -> PlanningOutcome:
        plan = self._repository.get_active(world.id, actor.id)

        # 规则 5：过龄强制放弃
        if plan is not None and world.clock_tick - plan.created_clock_tick > self._max_plan_age_ticks:
            self._repository.abandon(plan, clock_tick=world.clock_tick)
            plan = None

        # 规则 2：复用计划，不调模型
        if plan is not None:
            step = plan.steps_json[plan.current_step_index]
            return PlanningOutcome(
                proposal=self._to_proposal(actor, step, ProposalSource.EXISTING_PLAN),
                source=ProposalSource.EXISTING_PLAN,
                plan=plan, decision=None, latency_ms=None, tokens_used=None,
            )

        # 规则 1：调模型生成新计划
        memories = self._retrieve(world, actor)
        context = self.build_context(world, actor, None, memories, last_outcome)
        started = time.monotonic()
        try:
            decision = self._provider.plan(
                PlanningRequest(
                    npc_id=actor.id,
                    context_text=context,
                    tool_manifest=self._registry.to_tool_manifest(),
                )
            )
        except Exception:
            # spec §13 唯一不变量：任何失败都必须产出可执行提案。
            # 捕获宽泛 Exception 是刻意的，不是遗漏 —— PlanningProviderError 之外的
            # 任何意外（网络栈、序列化、第三方库）都不得让世界停摆。
            return PlanningOutcome(
                proposal=decide_action(actor, world), source=ProposalSource.FALLBACK,
                plan=None, decision=None, latency_ms=None, tokens_used=None,
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        created = self._repository.create_from_decision(
            world.id, actor.id, decision,
            clock_tick=world.clock_tick, run_id=None,
            provider=getattr(self._provider, "provider_name", "unknown"),
            model=getattr(self._provider, "model_name", "unknown"),
            latency_ms=latency_ms,
            tokens_used=getattr(self._provider, "last_tokens_used", None),
        )
        return PlanningOutcome(
            proposal=self._to_proposal(actor, created.steps_json[0], ProposalSource.LLM),
            source=ProposalSource.LLM, plan=created, decision=decision,
            latency_ms=latency_ms, tokens_used=created.tokens_used,
        )

    def build_context(self, world, actor, active_plan, memories, last_outcome) -> str:
        """spec §7 八段式。每段以 [SectionName] 开头，便于模型定位与人工排错。"""
        others = [n for n in world.npcs if n.location_id == actor.location_id and n.id != actor.id]
        return "\n".join(
            [
                f"[Identity] {actor.name}（{actor.role}），性格：{'、'.join(actor.personality)}",
                f"[Needs] 体力 {actor.energy} / 心情 {actor.mood} / 社交 {actor.social}（低于 40 视为亟需处理）",
                f"[World] 第 {world.day} 天 {world.time}，当前位于 {actor.location_id}；"
                f"同地点：{'、'.join(n.id for n in others) or '无'}；"
                f"可达地点：{'、'.join(loc.id for loc in world.locations)}",
                "[Episodic] " + ("；".join(m.content for m in memories) if memories else "暂无相关经历"),
                "[Semantic] 暂无已确立的信念",
                "[Procedural] " + (
                    f"当前计划「{active_plan.goal}」进行到第 {active_plan.current_step_index + 1} 步"
                    if active_plan is not None else "当前没有进行中的计划"
                ),
                "[Tools] " + "；".join(
                    f"{t['name']}：{t['description']}" for t in self._registry.to_tool_manifest()
                ),
                "[LastOutcome] " + (
                    f"上一步 {last_outcome.action_type} "
                    f"{'成功' if last_outcome.accepted else '被拒绝'}（{last_outcome.code}）"
                    if last_outcome is not None else "这是本次决策的起点，没有上一步结果"
                ),
            ]
        )

    def _retrieve(self, world: WorldSnapshot, actor: NpcSnapshot):
        try:
            return self._retriever.retrieve(
                RetrievalRequest(
                    world_id=world.id, owner_npc_id=actor.id,
                    current_world_version=world.world_version,
                    current_clock_tick=world.clock_tick,
                    query_text=f"{actor.role} 当前处境与近期经历",
                    scope=RetrievalScope.INTERNAL_REFLECTION,
                    allowed_memory_types=frozenset(MemoryType),
                    limit=6, char_budget=1200,
                )
            ).memories
        except Exception:
            return ()

    def _to_proposal(self, actor: NpcSnapshot, step: dict, source: ProposalSource) -> ActionProposal:
        return ActionProposal(
            actor_id=actor.id, action_type=step["action_type"],
            target_kind=step.get("target_kind"), target_id=step.get("target_id"),
            reason_code="agent_plan", source=source,
        )
```

- [ ] **Step 4: GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_planning_core.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：6 passed（schema 3 + 状态机 3）。

- [ ] **Step 5: 手动检查 Context 内容（替代被砍的八段测试）**

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); from backend.app.agents.planner import AgentPlanner; from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY; from tests.backend.test_golden_deterministic import build_golden_world; w = build_golden_world(); p = AgentPlanner(None, None, None, DEFAULT_ACTION_REGISTRY); print(p.build_context(w, w.npcs[0], None, (), None))"
```

肉眼确认八段齐全、工具清单可读、数值正确。**这段文本就是要喂给模型的东西，读不通顺模型也读不通顺。**

- [ ] **Step 6: 全量回归 + golden 闸门**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**看得到什么**：终端打印出完整的 Agent 上下文。

- [ ] **Step 7: 停机等待人类 review 与提交**

```
feat: add agent planner with context assembly and plan state machine
```

---

### Task 4: Orchestrator 提案注入与兜底

**Files:**
- Modify: `backend/app/agents/orchestrator.py:21`
- Modify: `backend/app/schemas/agent_run.py:24`
- Test: `tests/backend/test_agent_loop_fallback.py`（追加降级 2 条）

**Interfaces:**
- Produces:
  - `run_advance(world, registry=DEFAULT_ACTION_REGISTRY, proposal_override=None) -> AgentRuntimeResult`
  - `run_deterministic_advance = run_advance`（别名）

- [ ] **Step 1: 追加降级链路测试**

在 `tests/backend/test_agent_loop_fallback.py` 追加：

```python
from backend.app.agents.action_registry import ActionRegistry
from backend.app.agents.contracts import ActionProposal, ProposalSource
from backend.app.agents.orchestrator import run_advance, run_deterministic_advance
from tests.backend.test_golden_deterministic import build_golden_world


def test_alias_keeps_backward_compatible_signature():
    """保护现有 11 处调用：不传 override 时行为必须与改造前完全一致。"""
    world = build_golden_world()
    assert run_deterministic_advance(world) == run_advance(world)
    assert run_deterministic_advance(world, registry=ActionRegistry(())) == run_advance(
        world, registry=ActionRegistry(())
    )


def test_rejected_llm_proposal_falls_back_and_world_still_advances():
    """spec §13 唯一不变量 —— 这是本项目最核心的卖点，必须有证据。"""
    world = build_golden_world()
    actor = world.npcs[0]
    unreachable = ActionProposal(
        actor_id=actor.id, action_type="move", target_kind="location",
        target_id="nowhere", reason_code="agent_plan", source=ProposalSource.LLM,
    )

    result = run_advance(world, proposal_override={actor.id: unreachable})

    assert result.world.world_version == world.world_version + 1, "世界必须推进"
    assert result.world.clock_tick == world.clock_tick + 1

    fallback = next(p for p in result.proposals if p.actor_id == actor.id)
    assert fallback.source is ProposalSource.FALLBACK

    accepted = [
        r for r in result.resolutions
        if r.proposal.actor_id == actor.id and r.validation.accepted
    ]
    assert accepted, "兜底提案必须通过校验并被执行"

    sources = [t.data.get("source") for t in result.traces if t.stage == "proposal"]
    assert sources, "非空前提：必须有 proposal 阶段的 trace"
    assert "fallback" in sources, "降级必须在 trace 中可见，否则 UI 无法显示徽章"
```

- [ ] **Step 2: RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_agent_loop_fallback.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：新增 2 条 FAIL（`ImportError: cannot import name 'run_advance'`），索引那条仍 PASS。

- [ ] **Step 3: 改造 orchestrator**

修改 `backend/app/agents/orchestrator.py`：把 `run_deterministic_advance` 更名为 `run_advance` 并追加第三参数；把原第 35-37 行的提案生成替换为：

```python
    override = proposal_override or {}
    initial = tuple(
        override.get(actor.id) or decide_action(actor, decision_world)
        for actor in decision_world.npcs
    )
    proposals = tuple(
        _with_fallback(proposal, actor, decision_world, registry)
        for proposal, actor in zip(initial, decision_world.npcs, strict=True)
    )
    resolutions = resolve_proposals(decision_world, proposals, registry)
```

模块内追加：

```python
def _with_fallback(
    proposal: ActionProposal,
    actor: NpcSnapshot,
    world: WorldSnapshot,
    registry: ActionRegistry,
) -> ActionProposal:
    """外部提案被拒绝时替换为确定性兜底。spec §13 唯一不变量。"""
    if proposal.source is ProposalSource.DETERMINISTIC:
        return proposal
    try:
        accepted = registry.validate(proposal, actor, world).accepted
    except Exception:
        accepted = False
    if accepted:
        return proposal
    return replace(decide_action(actor, world), source=ProposalSource.FALLBACK)
```

文件末尾追加别名：

```python
# 向后兼容：现有 11 处调用继续使用此名称
run_deterministic_advance = run_advance
```

新增 import：`from collections.abc import Mapping`、`from backend.app.agents.contracts import ProposalSource`。函数签名追加 `proposal_override: Mapping[str, ActionProposal] | None = None`。

- [ ] **Step 4: 扩展 TRACE_STAGES**

修改 `backend/app/schemas/agent_run.py:24`：

```python
TRACE_STAGES = frozenset({"run_started", "planning", "proposal", "validation", "execution", "event", "run_completed"})
```

`agent_trace_entries.stage` 是裸 `String` 列、无 CHECK 约束，**无需 migration**。

- [ ] **Step 5: GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend\test_agent_loop_fallback.py -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

预期：3 passed。

- [ ] **Step 6: 全量回归 + golden 闸门（本 Task 最关键）**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**golden 必须 PASS** —— 不传 `proposal_override` 时行为必须逐字节不变。若失败，检查 `_with_fallback` 的 `DETERMINISTIC` 短路分支是否生效。

**看得到什么**：一条测试证明"LLM 给了非法动作，世界照样往前走"。

- [ ] **Step 7: 停机等待人类 review 与提交**

```
feat: accept external proposals in orchestrator with deterministic fallback
```

---

### Task 5: Service 接线与 Plan API（无新测试）

**Files:**
- Modify: `backend/app/services/world_clock_service.py`
- Modify: `backend/app/schemas/world_clock.py:9`
- Modify: `backend/app/api/dependencies.py`
- Create: `backend/app/schemas/plan.py`
- Create: `backend/app/api/npc_plan.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `AgentPlanner` / `PlanningOutcome` / `LastOutcome`（Task 3）、`run_advance`（Task 4）、`PlanRepository`（Task 2）
- Produces: `GET /api/npcs/{npc_id}/plan` → `ApiResponse[NpcPlanData]`；`NpcPlanData(current: PlanInfo | None, recent: list[PlanInfo])`

**本 Task 不写自动化测试** —— 端到端 `curl` 与前端渲染是更接近真实的验证，写在 Step 5。

- [ ] **Step 1: 定义响应模型**

创建 `backend/app/schemas/plan.py`：

```python
from pydantic import BaseModel, ConfigDict


class PlanStepInfo(BaseModel):
    action_type: str
    target_kind: str | None = None
    target_id: str | None = None
    intent: str


class PlanInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal: str
    goal_reason: str
    thought: str
    steps: list[PlanStepInfo]
    current_step_index: int
    status: str
    created_clock_tick: int
    provider: str
    model: str
    latency_ms: int | None = None
    tokens_used: int | None = None


class NpcPlanData(BaseModel):
    current: PlanInfo | None = None
    recent: list[PlanInfo] = []
```

- [ ] **Step 2: 实现路由**

创建 `backend/app/api/npc_plan.py`，**照 `backend/app/api/npcs.py:32` 的既有写法**（`ApiResponse` 包装、`responses={404, 503}`、`Depends(get_session)`）实现 `GET /api/npcs/{npc_id}/plan`：

- NPC 不存在 → 404
- 否则 `PlanRepository.get_active(...)` 取当前、`recent(limit=5)` 取历史
- `steps_json` 逐项映射为 `PlanStepInfo`

在 `backend/app/main.py` 按现有方式注册 `npc_plan.router`。

- [ ] **Step 3: `WorldTickRequest` 追加可选字段**

修改 `backend/app/schemas/world_clock.py:9`：

```python
from backend.app.agents.contracts import RuntimeMode


class WorldTickRequest(BaseModel):
    expected_world_version: int = Field(ge=0)
    runtime_mode: RuntimeMode = RuntimeMode.AUTO
```

带默认值，老请求体保持有效。

- [ ] **Step 4: Service 接线**

修改 `backend/app/services/world_clock_service.py`：

- `WorldTickService.__init__` 追加可选参数 `planner: AgentPlanner | None = None`
- `advance(expected_world_version, runtime_mode=RuntimeMode.AUTO)`：
  - `runtime_mode is RuntimeMode.DETERMINISTIC` 或 `planner is None` → `override = None`
  - 否则逐个 NPC 调 `planner.decide(snapshot, actor, last_outcome=None)`，收集 `{npc_id: outcome.proposal}`
- 第 79 行 `run_deterministic_advance(snapshot)` 换成 `run_advance(snapshot, proposal_override=override)`
- 为每个 `PlanningOutcome` 追加一条 `planning` stage trace，data 含 `{"npc_id", "source", "goal", "thought", "provider", "model", "latency_ms", "tokens_used"}`
- 推进成功后：`source is EXISTING_PLAN` 的调 `advance_step`；被兜底替换的（比对 `result.proposals` 中该 NPC 的 `source is FALLBACK`）调 `abandon`

在 `backend/app/api/dependencies.py` 照现有 `get_cognition_service` 的写法追加 `get_planner(session)`，内部用 `build_planning_provider(settings)`。

**演示品取舍**：Plan 写入与 `persist_run` 尽量同 session 事务；若既有代码结构不便，允许先提交 run 再更新 plan 并在 review 中记录 —— 单机演示无并发，不为此重构 repository。

`LastOutcome` 本轮固定传 `None`（上一步结果的跨 tick 回传属于 ReAct 的完整形态，Task 8 若有余量再补；trace 里已记录足够信息）。

- [ ] **Step 5: 端到端验证（替代被砍的 4 个 API 测试）**

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

另开终端依次执行，逐条确认：

```powershell
curl.exe -X POST http://localhost:8000/api/world/tick -H "Content-Type: application/json" -d '{\"expected_world_version\":1}'
```
→ 200，且不带 `runtime_mode` 仍然工作（向后兼容）

```powershell
curl.exe http://localhost:8000/api/npcs/elena/plan
```
→ 返回含非空 `goal` / `thought` / `steps` 的 `current`

```powershell
curl.exe http://localhost:8000/api/npcs/does-not-exist/plan
```
→ 404

再取上一步 tick 返回的 `run.id`：

```powershell
curl.exe http://localhost:8000/api/agent-runs/<run_id>
```
→ trace 中出现 `planning` stage，含 goal 与 thought

- [ ] **Step 6: 全量回归 + golden 闸门**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**看得到什么**：`curl` 能拿到 NPC 的目标和计划 —— Agent Loop 第一次端到端跑通。

- [ ] **Step 7: 停机等待人类 review 与提交**

```
feat: wire agent planner into world tick and expose plan api
```

---

### Task 6: Live Planning Provider（无新测试）

**Files:**
- Modify: `backend/app/llm/planning_provider.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/llm/factory.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `OpenAICompatiblePlanningProvider`（属性 `provider_name` / `model_name` / `last_tokens_used`）、`build_planning_provider(settings) -> PlanningProvider`

**本 Task 不写自动化测试** —— provider 装配结果在启动日志中直接可见，Live 行为只有真实调用能验证。

- [ ] **Step 1: 追加配置项**

`backend/app/core/config.py` 照现有 chat / reflection provider 的命名风格追加：`planning_provider_base_url` / `planning_provider_api_key` / `planning_provider_model` / `planning_provider_auth_mode` / `planning_provider_timeout_seconds`。同步更新 `.env.example`。

- [ ] **Step 2: 实现 Live Provider**

在 `backend/app/llm/planning_provider.py` 追加 `OpenAICompatiblePlanningProvider`，**结构对齐 `backend/app/llm/reflection_provider.py:61`**：

- 请求体带 `tools`（直接传 `request.tool_manifest`）与 `tool_choice="required"`
- 从响应 `tool_calls` 读取模型选择的动作组装 `AgentDecision`；若模型走普通 content 通道，退回解析 JSON
- 记录 `usage.total_tokens` 到 `self.last_tokens_used`
- 任何解析失败 / 超时 / 非 2xx 一律抛 `PlanningProviderError`，**不做 repair 重试**（spec §18）
- `provider_name = "openai_compatible"`，`model_name = self._model`

- [ ] **Step 3: 实现 `build_planning_provider`**

照 `backend/app/llm/reflection_provider.py:106` 的写法：`base_url` / `api_key` / `model` 缺任一 → 返回 `FakePlanningProvider()`；齐全 → 返回 Live。在 `backend/app/llm/factory.py` 导出。

在装配处加一行启动日志，打印实际选中的 provider 类型 —— 这替代了被砍的 3 个 factory 测试。

- [ ] **Step 4: 验证降级装配**

不配置任何 planning 环境变量，启动应用：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

确认日志打印 `FakePlanningProvider`。再配置完整的三项环境变量重启，确认打印 `OpenAICompatiblePlanningProvider`。

- [ ] **Step 5: Live 冒烟（需真实 API key）**

配置 `.env` 后推进 3 tick，检查数据库：

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); from sqlalchemy import create_engine, text; e = create_engine('sqlite:///backend/data/aleria.db'); print(list(e.connect().execute(text('SELECT owner_npc_id, goal, provider, latency_ms, tokens_used FROM agent_plans ORDER BY created_clock_tick DESC LIMIT 5'))))"
```

确认 `provider` 为 `openai_compatible`、`latency_ms` 与 `tokens_used` 有真实值、`goal` 是有意义的中文目标。

**未配置 key 则明确记录「未执行」，不得宣称通过。**

- [ ] **Step 6: 全量回归 + golden 闸门**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**看得到什么**：数据库里出现真实模型生成的中文目标。

- [ ] **Step 7: 停机等待人类 review 与提交**

```
feat: add live planning provider with native tool calling
```

---

### Task 7: 前端「思考」Tab（无新测试）

**本 Task 是整个演示的门面**，值得多花时间在观感上。

**Files:**
- Create: `frontend/src/api/npcPlan.ts`（类型与客户端合并在此，不单建 types 文件）
- Create: `frontend/src/components/NpcThoughtTab.vue`（状态用组件内 `ref` 持有，不建 store）
- Modify: `frontend/src/components/NpcDetailPanel.vue`

**Interfaces:**
- Consumes: `GET /api/npcs/{npc_id}/plan`（Task 5）
- Produces: `fetchNpcPlan(npcId: string): Promise<NpcPlanData>`

**本 Task 不写组件测试** —— UI 正确性靠肉眼验证更快更准，写在 Step 4。

- [ ] **Step 1: 类型与 API 客户端**

创建 `frontend/src/api/npcPlan.ts`，按 `backend/app/schemas/plan.py` 一一对应定义 `PlanStepInfo` / `PlanInfo` / `NpcPlanData`，并**照 `frontend/src/api/npc.ts` 的既有写法**实现 `fetchNpcPlan(npcId)`。

- [ ] **Step 2: 实现组件**

创建 `frontend/src/components/NpcThoughtTab.vue`，展示四块：

1. **当前 Goal** + goal_reason
2. **Thought** 文本（本 tick 的推理）
3. **Plan 步骤列表**：`index < current_step_index` 标「已完成」、`=== current_step_index` 标「进行中」、`>` 标「待执行」
4. **决策来源徽章**：`llm` → 「LLM 规划」、`existing_plan` → 「沿用计划」、`fallback` → 「确定性兜底」（来源取自 `current.provider` 与 plan 状态；`fallback` 情况下当前无 active plan，显示空态加兜底提示）

无计划时显示空态文案。样式沿用 `NpcDetailPanel.vue` 现有 class 与设计语言，**不引入新 UI 库**。

- [ ] **Step 3: 挂载到 NpcDetailPanel**

在 `NpcDetailPanel.vue` 现有 Tab 结构中追加「思考」Tab，切换到该 Tab 时调用 `fetchNpcPlan`。不改动其他 Tab 行为。

- [ ] **Step 4: 前端验证**

```powershell
npm --prefix frontend test
npm --prefix frontend run type-check
```

预期：既有测试全绿，无新增类型错误。

- [ ] **Step 5: 端到端视觉验证（替代被砍的 4 个组件测试）**

启动前后端，推进 5 tick，逐条肉眼确认：

1. 打开任一 NPC 详情 →「思考」Tab 显示目标、推理、步骤进度
2. 再推进 1 tick → 步骤进度前进一格，徽章变为「沿用计划」
3. 把 `.env` 里的 planning provider 配置注释掉重启 → 再推进 → 徽章变为「确定性兜底」
4. 切换到其他 Tab 再切回 → 数据正常刷新，无报错

- [ ] **Step 6: 后端全量回归**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
```

**看得到什么**：这就是演示时要展示的那块屏幕。

- [ ] **Step 7: 停机等待人类 review 与提交**

```
feat(frontend): add agent thought tab to npc detail panel
```

---

### Task 8: Eval、演示种子与文档

**Files:**
- Create: `scripts/eval_agent.py`
- Modify: `scripts/ensure_demo_world.py`
- Modify: `README.md`
- Modify: `CURRENT_STATE.md`

**Interfaces:**
- Consumes: `build_golden_world`（Task 0）、`AgentPlanner`（Task 3）、`run_advance`（Task 4）、`build_planning_provider`（Task 6）

- [ ] **Step 1: 实现 eval 脚本（四项指标，从六项精简）**

创建 `scripts/eval_agent.py`，参数：`--ticks`（默认 20）、`--provider`（`fake` | `live`，默认 `fake`）、`--out`（可选）。

用临时 SQLite + 迁移到 head 构造隔离环境，**绝不写入 `backend/data/aleria.db`**。

| 指标 | 计算方式 |
| --- | --- |
| 动作合法率 | `source=llm` 的提案中通过 `registry.validate` 的比例 |
| 兜底率 | `source=fallback` 提案数 / 总提案数 |
| 目标达成率 | `status=completed` 的 plan 数 / 总 plan 数 |
| 行为熵 | 动作类型分布的香农熵 `-Σ p·log2(p)`，6 个动作满熵 `log2(6)≈2.585`；低于 1.0 标注「存在行为坍缩风险」 |

附带输出平均规划延迟与累计 token（直接取 `agent_plans` 的 `latency_ms` / `tokens_used` 均值与总和，**不做 p50/p95 分位数统计**）。

输出 markdown 表格到 stdout，`--out` 指定时同时写文件。

- [ ] **Step 2: Fake provider 验证脚本可用**

```powershell
.\.venv\Scripts\python.exe scripts\eval_agent.py --ticks 20 --provider fake
```

预期：输出四行指标表加延迟/token 两行，无异常。Fake 下动作合法率应为 100%。

- [ ] **Step 3: Live provider 评估（需真实 key）**

```powershell
.\.venv\Scripts\python.exe scripts\eval_agent.py --ticks 20 --provider live --out docs\eval\2026-09-13-agent-eval.md
```

验收线：**Live 下动作合法率 ≥ 90%**。未配置 key 则明确记录「未执行」。

- [ ] **Step 4: 演示剧本种子**

修改 `scripts/ensure_demo_world.py`，确保演示世界能触发有趣决策：至少一个 NPC 体力低于 40（触发进食目标）、至少两个 NPC 同处一地（触发交谈）、若干条预置记忆（让 `goal_reason` 能引用具体事件）。

验证：

```powershell
.\.venv\Scripts\python.exe scripts\ensure_demo_world.py
```

然后启动前后端连续推进 20 tick，确认全程无异常、NPC 行为有可读的目标脉络。

- [ ] **Step 5: 更新 README**

追加一节覆盖 spec §19 的包装点：Agent Loop 架构图、Memory 四层表、MCP 工具清单说明、Plan-and-Execute × ReAct 的设计立场、评估指标表（贴 Step 2/3 的真实输出）、韧性设计（fallback 链路）。

- [ ] **Step 6: 更新 CURRENT_STATE.md**

更新「Active Track」章节：标记 Stage 3m 完成、记录实际工时、列出遗留 P2（确定性回放、LLM-as-judge、真 MCP 传输层、Token 预算治理、`LastOutcome` 跨 tick 回传）。

- [ ] **Step 7: 最终全量验证**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q -p no:cacheprovider --basetemp=C:\Temp\aleria-pytest
npm --prefix frontend test
npm --prefix frontend run type-check
```

预期：全绿，skip 仍为 4，warning 仍为 1，golden 闸门 PASS，新增 10 个测试全部通过。

- [ ] **Step 8: 对照 spec §17 逐条核验收**

1. 连续 20 tick 零异常，行为可追溯到 goal 与 thought
2. 关闭 LLM 后世界仍推进，UI 显示兜底徽章
3. `GET /api/npcs/{id}/plan` 返回目标、步骤与进度
4. 「思考」Tab 完整展示决策链路
5. eval 指标产出，Live 下动作合法率 ≥ 90%
6. 关键契约测试通过（本版为 10 个）
7. Golden 快照比对通过
8. 全量测试通过，无新增 skip / warning

逐条记录实际结果。**未执行的项明确标注「未执行」，不得宣称通过。**

- [ ] **Step 9: 停机等待人类 review 与提交**

```
docs: add stage 3m evaluation, demo seed and architecture narrative
```

---

## 与上一版的差异摘要

| 项 | 上一版 | 本版 |
| --- | --- | --- |
| 测试数量 | 38 | **10** |
| 测试文件 | 9 | **3** |
| Task 数量 | 11 | **9**（T1+T2 合并、T9+T10 合并） |
| 前端新建文件 | 4 | **2**（types 并入 api，取消 store） |
| Eval 指标 | 6 项含 p50/p95 | **4 项 + 两个均值** |
| 工时 | 5.2d | **3.95d** |
| TDD 流程 | 强制 | **仍然强制**（只收缩范围，不放松流程） |

被砍的验证没有消失，而是换成了更便宜的形式：**28 个自动化测试 → 8 处手动验证步骤**，每一处都写明了「看什么、什么算对」。
