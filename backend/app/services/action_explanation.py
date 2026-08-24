FALLBACK_EXPLANATION = "按照当时的世界规则执行了该行动。"

TARGET_REASON_TEXT = {
    "low_social_with_companion": "社交需求较高，因此选择与 {target} 交谈。",
    "low_social_find_companion": "社交需求较高，因此前往{target}寻找同伴。",
    "low_mood_find_food": "心情较低，因此前往{target}用餐。",
    "knight_duty_travel": "当前处于骑士履行职责的时间，因此前往{target}。",
    "knight_training_travel": "当前是训练时间，因此前往{target}。",
    "knight_evening_social": "傍晚职责结束，因此选择与 {target} 交流。",
    "assassin_meal_travel": "当前符合刺客的用餐安排，因此前往{target}。",
    "assassin_scout_travel": "当前是侦察时间，因此前往{target}。",
    "guardian_patrol_travel": "当前是巡逻时间，因此前往{target}。",
}

STATIC_REASON_TEXT = {
    "night_rest": "夜晚已经到来，因此选择休息。",
    "low_energy": "体力较低，因此选择休息恢复。",
    "low_mood_eat": "心情较低，因此选择用餐调整状态。",
    "knight_duty": "当前处于骑士履行训练职责的时间。",
    "knight_training": "当前处于骑士训练时间，因此执行训练。",
    "knight_evening_rest": "傍晚没有同伴在附近，因此选择休息。",
    "assassin_meal": "当前符合刺客的用餐安排，因此选择用餐。",
    "assassin_scout": "当前处于刺客侦察时间，因此执行侦察。",
    "guardian_patrol": "当前处于守护者巡逻时间，因此执行巡逻。",
    "unknown_role_rest": "当前没有匹配的角色例程，因此选择休息。",
}


def explain_action(reason_code: str, target_name: str | None = None) -> str:
    target_template = TARGET_REASON_TEXT.get(reason_code)
    if target_template is not None:
        return target_template.format(target=target_name or "目标")

    return STATIC_REASON_TEXT.get(reason_code, FALLBACK_EXPLANATION)
