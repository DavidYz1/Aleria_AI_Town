"""工具契约必须完整表达引擎强制的前置条件。

背景：2026-09-16 的 Live 探路里动作合法率只有 76.9%。查下来，`work` 与 `eat` 在
`ActionRegistry` 里各有一条位置前置条件（必须在本职岗位 / 必须在酒馆），而工具描述
写的是「不需要目标」，`[World]` 段也从没告诉 NPC 自己的岗位在哪。模型在任意地点调用
它们是合理推断，引擎却必拒 —— 被惩罚的是它无从知晓的规则。

这两条测试守住：凡是引擎按位置拒绝的动作，契约里必须说得出这个条件。
"""

from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY
from backend.app.world.role_routines import WORK_LOCATION_BY_ROLE


def _descriptions() -> dict[str, str]:
    return {t["name"]: t["description"] for t in DEFAULT_ACTION_REGISTRY.to_tool_manifest()}


def test_location_gated_actions_declare_their_precondition():
    """`eat` 的门槛是一个具体地点 id，`work` 的门槛随角色变化。

    断言用的是**引擎里的真实常量**，不是文案里抄来的字符串：`eat` 必须点名
    `_validate_eat` 检查的那个地点，`work` 必须让模型知道存在岗位限制。
    """
    descriptions = _descriptions()

    assert "tavern" in descriptions["eat"], descriptions["eat"]
    assert "岗位" in descriptions["work"], descriptions["work"]


def test_unrestricted_actions_do_not_claim_a_location_precondition():
    """对照组：`rest` 与 `wait` 在引擎里没有位置门槛，描述也不该凭空加一条。

    没有这条，上一条可以靠「给每个动作都写一句位置要求」平凡通过。
    """
    descriptions = _descriptions()

    for name in ("rest", "wait"):
        assert "岗位" not in descriptions[name], descriptions[name]
        assert "tavern" not in descriptions[name], descriptions[name]


def test_planning_context_tells_every_npc_where_its_duty_location_is():
    """模型必须能知道自己的岗位在哪，否则 `work` 的前置条件无法被满足。

    三个 NPC 的岗位各不相同（Knight→park、Assassin→forest、Guardian→castle），
    逐个断言才能证明填进去的是**这个 actor 的**岗位，而不是某个写死的地点。
    """
    from backend.app.agents.planner import AgentPlanner
    from tests.backend.test_golden_deterministic import build_golden_world

    world = build_golden_world()
    planner = AgentPlanner(None, None, None, DEFAULT_ACTION_REGISTRY)

    assert world.npcs, "非空前提：世界里确实有 NPC"
    seen_duties = set()
    for actor in world.npcs:
        duty = WORK_LOCATION_BY_ROLE[actor.role]
        context = planner.build_context(world, actor, None, (), None)
        # 不能只断言 `duty in context` —— 所有岗位地点本来就都列在「可达地点」里，
        # 那样写在改动之前就会平凡通过。必须要求岗位**单独点名**。
        duty_lines = [line for line in context.splitlines() if "岗位" in line]
        assert duty_lines, f"context 里没有任何一行点明岗位：{context}"
        assert any(duty in line for line in duty_lines), (
            f"{actor.id}（{actor.role}）的岗位应为 {duty}，实际那几行是 {duty_lines}"
        )
        seen_duties.add(duty)
    assert len(seen_duties) > 1, "判别力前提：这些 NPC 的岗位不能全都一样"


def test_fake_provider_still_parses_the_current_context_format():
    """`FakePlanningProvider` 用正则读 `[World]` 段，改 context 格式会**静默**破坏它。

    解析失败时它退回 `rest` + `wait` 安全步骤 —— 不抛异常、不降合法率，所有测试
    照样全绿，但评测里的行为多样性会悄悄消失。2026-09-16 给 `[World]` 插入
    「你的岗位」时真实发生过：20 tick 的动作分布从 `eat 3、move 2、rest 28、talk 27`
    塌缩成 `rest 30、wait 30`，行为熵 1.411 → 1.000。

    这条守卫把「context 格式」与「替身的解析」这个隐含耦合显式化。
    """
    from backend.app.agents.planner import AgentPlanner
    from backend.app.llm.planning_provider import FakePlanningProvider, PlanningRequest
    from tests.backend.test_golden_deterministic import build_golden_world

    world = build_golden_world()
    planner = AgentPlanner(None, None, None, DEFAULT_ACTION_REGISTRY)
    provider = FakePlanningProvider()

    produced: set[str] = set()
    for actor in world.npcs:
        context = planner.build_context(world, actor, None, (), None)
        decision = provider.plan(
            PlanningRequest(npc_id=actor.id, context_text=context)
        )
        produced.update(step.action_type for step in decision.steps)

    assert produced, "非空前提：替身确实产出了动作"
    assert produced - {"rest", "wait"}, (
        f"替身只产出了安全退路 {produced}，说明它没能解析当前的 [World] 段格式"
    )


def test_env_example_matches_the_settings_default_for_planning_timeout():
    """`.env.example` 与 `Settings` 默认值不得漂移。

    这两处很容易只改一个：改了代码默认值忘了改示例，新人照示例配置就得到与默认
    不同的行为，而且不会有任何报错。2026-09-17 把超时从 20 调到 30 时就同时涉及
    这两处。

    只读 `.env.example`（被跟踪的模板，不含真实凭据），不碰 `.env`。
    """
    from pathlib import Path

    from backend.app.core.config import Settings

    repo_root = Path(__file__).resolve().parents[2]
    example = (repo_root / ".env.example").read_text(encoding="utf-8")

    declared = [
        line.split("=", 1)[1].strip()
        for line in example.splitlines()
        if line.strip().startswith("PLANNING_PROVIDER_TIMEOUT_SECONDS=")
    ]
    assert len(declared) == 1, f"非空前提：示例里应恰好声明一次，实际 {declared}"

    default = Settings.model_fields["planning_provider_timeout_seconds"].default
    assert float(declared[0]) == float(default), (
        f".env.example 写的是 {declared[0]}，Settings 默认值是 {default}"
    )
