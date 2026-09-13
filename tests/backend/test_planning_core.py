import json

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
    """动作空间锁定为 6 个动词，模型不得发明新动作。

    走模型的真实路径验证。不能用 PlanStep.model_construct 造非法实例：
    那是 pydantic 显式的「跳过校验」逃生口，且 pydantic v2 默认
    revalidate_instances='never'，父模型不会重新校验已构造的子模型实例，
    那样写的测试无论实现对错都不会抛 ValidationError。
    """
    payload = {
        "thought": "体力偏低，先补充再出门",
        "goal": "补充体力后去广场打听消息",
        "goal_reason": "昨天玩家提到有孩子走失",
        "steps": [
            {"action_type": "craft", "target_kind": None, "target_id": None, "intent": "打造"}
        ],
        "prompt_version": "planning-v1",
    }

    # 路径 1：模型返回的 JSON 文本 —— Task 6 Live provider 的真实入口
    with pytest.raises(ValidationError):
        AgentDecision.model_validate_json(json.dumps(payload))

    # 路径 2：已解析为 dict 后构造
    with pytest.raises(ValidationError):
        AgentDecision(**payload)

    # 非空前提：同一份 payload 只把动词换成合法值必须通过。
    # 否则上面两条可能是别的字段出错才抛的异常，证明不了动作空间约束。
    legal = payload | {"steps": [payload["steps"][0] | {"action_type": "work"}]}
    assert AgentDecision.model_validate_json(json.dumps(legal)).steps[0].action_type == "work"


def test_rejects_empty_thought_and_oversized_plan():
    """两条边界合一：空 thought 与超过 4 步的计划都必须被拒。"""
    empty_thought = _kwargs() | {"thought": ""}
    with pytest.raises(ValidationError):
        AgentDecision(**empty_thought)

    step = PlanStep(action_type="rest", target_kind=None, target_id=None, intent="休息")
    oversized = _kwargs() | {"steps": (step,) * 5}
    with pytest.raises(ValidationError):
        AgentDecision(**oversized)
