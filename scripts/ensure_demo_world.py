import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import get_settings
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import NpcState, WorldState
from backend.app.services.cognition_projection import CognitionProjectionService
from backend.app.services.demo_reset_service import (
    DemoResetPersistenceError,
    DemoResetService,
    load_seed_data,
)
from scripts.upgrade_schema import upgrade_schema


# 演示开局：让第一个 tick 就有值得看的决策，而不是三个 NPC 各自原地上班。
#
# - shir 体力 34：低于 planner 上下文的「40 亟需处理」阈值，但高于
#   `decide_action` 的 30（`decision.py:51`）—— 于是「模型会去进食」与
#   「确定性策略只会休息」形成可见对比，正是兜底徽章要展示的差别。
#   shir 本就在 tavern，`eat` 当场合法。
# - grey 挪到 park 与 ryan 同处：`talk` 需要同地点有另一个 NPC，
#   不挪就永远触发不了交谈。
#
# 数值只写在这里，不动 `data/npcs.json` —— 那是被跟踪的权威种子，
# 多个测试与 `build_golden_world()` 的注释都以它为基准。
DEMO_NPC_OVERRIDES = {
    "shir": {"energy": 34},
    "grey": {"location_id": "park"},
}


def apply_demo_scenario(session, world_id: str) -> None:
    """在刚播种的世界上叠加演示剧本，并把 authored knowledge 预投影成记忆。

    预投影的意义：`AgentPlanner` 每次规划都会检索记忆填充 `[Episodic]` 段。
    不预投影的话，第一个 tick 的 `goal_reason` 无据可引，要等认知投影在
    第一次 tick 的 post-commit 阶段跑完才有内容。
    """
    for npc_id, fields in DEMO_NPC_OVERRIDES.items():
        state = session.get(NpcState, npc_id)
        if state is None:
            continue
        for name, value in fields.items():
            setattr(state, name, value)
    session.commit()

    # enrichment 与 reflection 一律留空：播种脚本不得调用任何外部 provider。
    CognitionProjectionService(CognitionRepository(session)).catch_up_world(world_id)
    session.commit()


def ensure_demo_world(database_url: str, seed_dir: Path) -> bool:
    seed = load_seed_data(seed_dir)
    engine, session_factory = create_engine_and_session(database_url)
    upgrade_schema(database_url)

    with session_factory() as session:
        if session.get(WorldState, seed.world.id) is not None:
            return False
        DemoResetService(session).reset(seed)

    # 已存在的世界一律原样保留（见 test_ensure_existing_demo_world_preserves_cognition），
    # 演示剧本只作用于刚建出来的空世界，且用独立 Session —— 投影要求所在
    # Session 没有进行中的事务。
    with session_factory() as session:
        apply_demo_scenario(session, seed.world.id)
    return True


def main() -> int:
    try:
        initialized = ensure_demo_world(
            get_settings().database_url,
            REPO_ROOT / "data",
        )
    except (
        OSError,
        json.JSONDecodeError,
        ValidationError,
        SQLAlchemyError,
        DemoResetPersistenceError,
    ) as exc:
        print(f"Failed to ensure the Aleria demo world: {exc}", file=sys.stderr)
        return 1

    if initialized:
        print("Initialized the empty Aleria database with Demo seed data.")
    else:
        print("Existing Aleria world state preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
