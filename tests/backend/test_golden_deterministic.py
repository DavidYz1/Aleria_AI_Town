"""Stage 1 确定性行为回归闸门。

失败意味着 run_deterministic_advance 输出发生漂移。
禁止通过重新生成快照"修复" —— 必须定位根因。
"""
import json
from dataclasses import fields, is_dataclass
from collections.abc import Mapping
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


def _to_jsonable(value):
    """把 runtime 结果转成纯 JSON 内建类型。

    不能用 dataclasses.asdict：TraceDraft.data 与 DomainEventDraft.payload
    在 __post_init__ 中被冻结为 MappingProxyType，asdict 会对它走
    copy.deepcopy 并抛 TypeError: cannot pickle 'mappingproxy' object。
    """
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, str):
        # StrEnum（如 ProposalSource）落在这里，显式取字面值避免枚举成员泄漏进快照
        return str(value)
    return value


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

    role 必须是 decide_action 真正分派的三个角色（Knight / Assassin /
    Guardian，见 decision.py:78-131）。用计划原写的 baker / guard / scholar
    会让三个 NPC 全部落入 unknown_role_rest 兜底分支，闸门将测不到任何
    role routine —— 实测覆盖的 reason_code 从 14 个掉到 4 个。

    grey 的 mood 取 20（低于 decide_action 的 35 阈值）是为了覆盖
    low_mood_* 分支。取 45 时覆盖 14 个 reason_code，取 20 时覆盖 15 个
    且是前者的严格超集。这些数值只为拉满分支覆盖，不代表世界设定。
    """
    return WorldSnapshot(
        id="aleria-town", name="曦谷", day=1, time="08:00",
        clock_tick=0, world_version=1, event_sequence=0,
        locations=LOCATIONS,
        npcs=(
            _npc("elena", "Knight", "tavern", 1, 80, 70, 60),
            _npc("grey", "Guardian", "castle", 2, 55, 20, 30),
            _npc("mira", "Assassin", "park", 3, 40, 85, 75),
        ),
    )


def run_twenty_ticks(world: WorldSnapshot) -> list[dict]:
    frames, current = [], world
    for _ in range(20):
        result = run_deterministic_advance(current)
        frames.append(
            {
                "world": _to_jsonable(result.world),
                "proposals": [_to_jsonable(p) for p in result.proposals],
                "traces": [_to_jsonable(t) for t in result.traces],
                "events": [_to_jsonable(e) for e in result.events],
            }
        )
        current = result.world
    return frames


def test_deterministic_output_matches_golden_snapshot():
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    actual = run_twenty_ticks(build_golden_world())
    assert len(actual) == 20, "必须产出 20 帧，空集合会让下面的比对恒真"
    assert actual == expected, "Stage 1 行为漂移，禁止更新快照，先定位根因"
