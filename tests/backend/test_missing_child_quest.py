import importlib

import pytest


def _quest_modules():
    try:
        types = importlib.import_module("backend.app.quests.types")
        missing_child = importlib.import_module(
            "backend.app.quests.missing_child"
        )
    except ModuleNotFoundError:
        pytest.fail("missing-child quest domain is missing")
    return types, missing_child


VALID_TRANSITIONS = [
    (
        "available",
        "accept_quest",
        "tavern",
        "accepted",
        "quest_accepted",
    ),
    (
        "accepted",
        "ask_grey",
        "castle",
        "briefed_by_grey",
        "grey_briefed",
    ),
    (
        "briefed_by_grey",
        "inspect_shoe",
        "forest",
        "shoe_found",
        "shoe_inspected",
    ),
    (
        "shoe_found",
        "search_child",
        "forest",
        "child_found",
        "child_found",
    ),
    (
        "child_found",
        "return_child",
        "tavern",
        "completed",
        "child_returned",
    ),
]


@pytest.mark.parametrize(
    (
        "status",
        "interaction",
        "location_id",
        "to_status",
        "event_text_code",
    ),
    VALID_TRANSITIONS,
)
def test_missing_child_policy_applies_each_valid_transition(
    status,
    interaction,
    location_id,
    to_status,
    event_text_code,
):
    types, missing_child = _quest_modules()
    snapshot = types.QuestSnapshot(
        quest_id="missing-child",
        status=status,
        version=3,
        player_location_id=location_id,
        world_tick=7,
        target_npc_location_id=(
            location_id if interaction == "ask_grey" else None
        ),
    )
    command = types.QuestCommand(
        interaction=interaction,
        expected_version=3,
    )

    transition = missing_child.MissingChildQuestPolicy().transition(
        snapshot,
        command,
    )

    assert transition == types.QuestTransition(
        from_status=status,
        to_status=to_status,
        interaction=interaction,
        location_id=location_id,
        event_text_code=event_text_code,
        required_npc_id="grey" if interaction == "ask_grey" else None,
    )


@pytest.mark.parametrize(
    "status,interaction,location_id,to_status,event_text_code",
    VALID_TRANSITIONS,
)
def test_missing_child_policy_rejects_stale_version_before_transition(
    status,
    interaction,
    location_id,
    to_status,
    event_text_code,
):
    types, missing_child = _quest_modules()
    snapshot = types.QuestSnapshot(
        quest_id="missing-child",
        status=status,
        version=4,
        player_location_id=location_id,
        world_tick=7,
        target_npc_location_id=(
            location_id if interaction == "ask_grey" else None
        ),
    )

    with pytest.raises(
        types.QuestStateConflictError,
        match="^Quest state has changed$",
    ):
        missing_child.MissingChildQuestPolicy().transition(
            snapshot,
            types.QuestCommand(
                interaction=interaction,
                expected_version=3,
            ),
        )


@pytest.mark.parametrize(
    "status,interaction,required_location,to_status,event_text_code",
    VALID_TRANSITIONS,
)
def test_missing_child_policy_rejects_valid_interaction_at_wrong_location(
    status,
    interaction,
    required_location,
    to_status,
    event_text_code,
):
    types, missing_child = _quest_modules()
    wrong_location = "park" if required_location != "park" else "forest"
    snapshot = types.QuestSnapshot(
        quest_id="missing-child",
        status=status,
        version=2,
        player_location_id=wrong_location,
        world_tick=7,
        target_npc_location_id=(
            required_location if interaction == "ask_grey" else None
        ),
    )

    with pytest.raises(
        types.QuestInteractionUnavailableError,
        match="^Quest interaction is not available$",
    ):
        missing_child.MissingChildQuestPolicy().transition(
            snapshot,
            types.QuestCommand(
                interaction=interaction,
                expected_version=2,
            ),
        )


@pytest.mark.parametrize(
    "status,interaction,location_id,to_status,event_text_code",
    VALID_TRANSITIONS,
)
def test_missing_child_policy_rejects_interaction_for_wrong_status(
    status,
    interaction,
    location_id,
    to_status,
    event_text_code,
):
    types, missing_child = _quest_modules()
    snapshot = types.QuestSnapshot(
        quest_id="missing-child",
        status="completed",
        version=5,
        player_location_id=location_id,
        world_tick=7,
    )

    with pytest.raises(
        types.QuestInteractionUnavailableError,
        match="^Quest interaction is not available$",
    ):
        missing_child.MissingChildQuestPolicy().transition(
            snapshot,
            types.QuestCommand(
                interaction=interaction,
                expected_version=5,
            ),
        )


@pytest.mark.parametrize(
    (
        "status",
        "location_id",
        "target_npc_location_id",
        "target_npc_location_name",
        "objective",
        "available_interactions",
    ),
    [
        (
            "available",
            "tavern",
            None,
            None,
            "查看星辉酒馆的委托板。",
            (("accept_quest", "接受委托"),),
        ),
        (
            "available",
            "park",
            None,
            None,
            "查看星辉酒馆的委托板。",
            (),
        ),
        (
            "accepted",
            "castle",
            "park",
            "中央公园",
            "前往中央公园询问 Grey。",
            (),
        ),
        (
            "accepted",
            "park",
            "park",
            "中央公园",
            "前往中央公园询问 Grey。",
            (("ask_grey", "询问 Grey"),),
        ),
        (
            "briefed_by_grey",
            "forest",
            None,
            None,
            "前往低语森林寻找线索。",
            (("inspect_shoe", "查看遗落的鞋子"),),
        ),
        (
            "shoe_found",
            "forest",
            None,
            None,
            "沿鞋子附近的痕迹继续寻找。",
            (("search_child", "沿痕迹寻找孩子"),),
        ),
        (
            "child_found",
            "tavern",
            None,
            None,
            "护送孩子返回星辉酒馆。",
            (("return_child", "将孩子带回酒馆"),),
        ),
        ("completed", "tavern", None, None, "任务已完成。", ()),
    ],
)
def test_missing_child_policy_presents_authoritative_objective_and_actions(
    status,
    location_id,
    target_npc_location_id,
    target_npc_location_name,
    objective,
    available_interactions,
):
    types, missing_child = _quest_modules()

    presentation = missing_child.MissingChildQuestPolicy().present(
        status,
        location_id,
        target_npc_location_id=target_npc_location_id,
        target_npc_location_name=target_npc_location_name,
    )

    assert presentation.title == "失踪的孩子"
    assert presentation.objective == objective
    assert tuple(
        (interaction.id, interaction.label)
        for interaction in presentation.available_interactions
    ) == available_interactions
