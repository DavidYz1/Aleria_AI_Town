from backend.app.quests.types import (
    QuestAvailableInteraction,
    QuestCommand,
    QuestInteraction,
    QuestInteractionUnavailableError,
    QuestPresentation,
    QuestSnapshot,
    QuestStateConflictError,
    QuestStatus,
    QuestTransition,
)


class MissingChildQuestPolicy:
    _TRANSITIONS: dict[
        tuple[QuestStatus, QuestInteraction],
        tuple[str, QuestStatus, str],
    ] = {
        ("available", "accept_quest"): (
            "tavern",
            "accepted",
            "quest_accepted",
        ),
        ("accepted", "ask_grey"): (
            "castle",
            "briefed_by_grey",
            "grey_briefed",
        ),
        ("briefed_by_grey", "inspect_shoe"): (
            "forest",
            "shoe_found",
            "shoe_inspected",
        ),
        ("shoe_found", "search_child"): (
            "forest",
            "child_found",
            "child_found",
        ),
        ("child_found", "return_child"): (
            "tavern",
            "completed",
            "child_returned",
        ),
    }
    _OBJECTIVES: dict[QuestStatus, str] = {
        "available": "查看星辉酒馆的委托板。",
        "accepted": "前往晨曦城堡询问 Grey。",
        "briefed_by_grey": "前往低语森林寻找线索。",
        "shoe_found": "沿鞋子附近的痕迹继续寻找。",
        "child_found": "护送孩子返回星辉酒馆。",
        "completed": "任务已完成。",
    }
    _INTERACTION_LABELS: dict[QuestInteraction, str] = {
        "accept_quest": "接受委托",
        "ask_grey": "询问 Grey",
        "inspect_shoe": "查看遗落的鞋子",
        "search_child": "沿痕迹寻找孩子",
        "return_child": "将孩子带回酒馆",
    }

    def transition(
        self,
        snapshot: QuestSnapshot,
        command: QuestCommand,
    ) -> QuestTransition:
        if command.expected_version != snapshot.version:
            raise QuestStateConflictError("Quest state has changed")

        rule = self._TRANSITIONS.get(
            (snapshot.status, command.interaction)
        )
        if rule is None or snapshot.quest_id != "missing-child":
            raise QuestInteractionUnavailableError(
                "Quest interaction is not available"
            )

        required_location, to_status, event_text_code = rule
        required_npc_id = None
        if command.interaction == "ask_grey":
            if (
                snapshot.target_npc_location_id is None
                or snapshot.player_location_id
                != snapshot.target_npc_location_id
            ):
                raise QuestInteractionUnavailableError(
                    "Quest interaction is not available"
                )
            required_location = snapshot.player_location_id
            required_npc_id = "grey"
        elif snapshot.player_location_id != required_location:
            raise QuestInteractionUnavailableError(
                "Quest interaction is not available"
            )

        return QuestTransition(
            from_status=snapshot.status,
            to_status=to_status,
            interaction=command.interaction,
            location_id=required_location,
            event_text_code=event_text_code,
            required_npc_id=required_npc_id,
        )

    def present(
        self,
        status: QuestStatus,
        location_id: str,
        *,
        target_npc_location_id: str | None = None,
        target_npc_location_name: str | None = None,
    ) -> QuestPresentation:
        available_interactions: tuple[QuestAvailableInteraction, ...] = ()
        for (from_status, interaction), rule in self._TRANSITIONS.items():
            required_location, _, _ = rule
            if interaction == "ask_grey":
                interaction_is_available = (
                    target_npc_location_id is not None
                    and target_npc_location_id == location_id
                )
            else:
                interaction_is_available = required_location == location_id
            if from_status == status and interaction_is_available:
                available_interactions = (
                    QuestAvailableInteraction(
                        id=interaction,
                        label=self._INTERACTION_LABELS[interaction],
                    ),
                )
                break

        objective = self._OBJECTIVES[status]
        if status == "accepted" and target_npc_location_name is not None:
            objective = f"前往{target_npc_location_name}询问 Grey。"

        return QuestPresentation(
            title="失踪的孩子",
            objective=objective,
            available_interactions=available_interactions,
        )
