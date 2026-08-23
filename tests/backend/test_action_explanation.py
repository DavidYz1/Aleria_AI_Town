import pytest

from backend.app.services.action_explanation import explain_action


@pytest.mark.parametrize(
    ("reason_code", "target_name", "expected"),
    [
        ("night_rest", None, "夜晚已经到来，因此选择休息。"),
        ("low_energy", None, "体力较低，因此选择休息恢复。"),
        (
            "low_social_with_companion",
            "Grey",
            "社交需求较高，因此选择与 Grey 交谈。",
        ),
        (
            "low_social_find_companion",
            "中央公园",
            "社交需求较高，因此前往中央公园寻找同伴。",
        ),
        ("low_mood_eat", None, "心情较低，因此选择用餐调整状态。"),
        (
            "low_mood_find_food",
            "星辰酒馆",
            "心情较低，因此前往星辰酒馆用餐。",
        ),
        (
            "knight_duty_travel",
            "中央公园",
            "当前处于骑士履行职责的时间，因此前往中央公园。",
        ),
        ("knight_duty", None, "当前处于骑士履行训练职责的时间。"),
        (
            "knight_evening_social",
            "Grey",
            "傍晚职责结束，因此选择与 Grey 交流。",
        ),
        (
            "knight_evening_rest",
            None,
            "傍晚没有同伴在附近，因此选择休息。",
        ),
        (
            "assassin_meal_travel",
            "星辰酒馆",
            "当前符合刺客的用餐安排，因此前往星辰酒馆。",
        ),
        (
            "assassin_meal",
            None,
            "当前符合刺客的用餐安排，因此选择用餐。",
        ),
        (
            "guardian_patrol_travel",
            "中央公园",
            "当前处于守护者巡查时间，因此前往中央公园。",
        ),
        (
            "guardian_patrol",
            None,
            "当前处于守护者巡查时间，因此执行工作。",
        ),
        (
            "unknown_role_rest",
            None,
            "当前没有匹配的角色例程，因此选择休息。",
        ),
    ],
)
def test_explain_action_maps_every_current_reason_code(
    reason_code: str,
    target_name: str | None,
    expected: str,
):
    assert explain_action(reason_code, target_name) == expected


def test_explain_action_uses_safe_fallback_for_unknown_history():
    assert explain_action("legacy_reason") == "按照当时的世界规则执行了该行动。"
