from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import WorldAction, WorldState
from backend.app.database.npc_repository import NpcRepository
from backend.app.services.npc_service import NpcService
from scripts.seed_world import seed_database


def test_service_maps_authoritative_detail_and_empty_history(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        detail = NpcService(NpcRepository(session)).get_detail("ryan")

    assert detail.model_dump() == {
        "profile": {
            "id": "ryan",
            "name": "Ryan",
            "role": "Knight",
            "personality": ["optimistic", "brave", "kind"],
        },
        "state": {
            "location_id": "park",
            "location_name": "中央公园",
            "current_action": "rest",
            "status": {
                "energy": 80,
                "mood": 78,
                "social": 70,
            },
        },
        "world_context": {
            "day": 1,
            "time": "08:00",
            "tick": 0,
            "time_phase": "morning",
        },
        "recent_actions": [],
    }


def test_service_maps_resolved_action_targets_and_explanations(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        world = session.get(WorldState, "aleria-town")
        assert world is not None
        world.time = "10:00"
        world.tick = 2
        session.add_all(
            [
                WorldAction(
                    world_id="aleria-town",
                    tick=1,
                    actor_id="ryan",
                    action_type="move",
                    target_kind="location",
                    target_id="park",
                    reason="knight_duty_travel",
                    status="recorded",
                    world_time="09:00",
                ),
                WorldAction(
                    world_id="aleria-town",
                    tick=2,
                    actor_id="ryan",
                    action_type="social",
                    target_kind="npc",
                    target_id="grey",
                    reason="knight_evening_social",
                    status="recorded",
                    world_time="10:00",
                ),
            ]
        )
        session.commit()

        detail = NpcService(NpcRepository(session)).get_detail("ryan")

    assert [action.model_dump() for action in detail.recent_actions] == [
        {
            "id": 2,
            "tick": 2,
            "world_time": "10:00",
            "action_type": "social",
            "target_kind": "npc",
            "target_id": "grey",
            "target_name": "Grey",
            "reason_code": "knight_evening_social",
            "reason_text": "傍晚职责结束，因此选择与 Grey 交流。",
        },
        {
            "id": 1,
            "tick": 1,
            "world_time": "09:00",
            "action_type": "move",
            "target_kind": "location",
            "target_id": "park",
            "target_name": "中央公园",
            "reason_code": "knight_duty_travel",
            "reason_text": "当前处于骑士履行职责的时间，因此前往中央公园。",
        },
    ]
    assert detail.world_context.time_phase == "morning"


def test_service_preserves_unresolved_target_id_as_display_name(
    database_url,
    seed_dir,
):
    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)

    with session_factory() as session:
        session.add(
            WorldAction(
                world_id="aleria-town",
                tick=1,
                actor_id="ryan",
                action_type="move",
                target_kind="location",
                target_id="missing-place",
                reason="low_mood_find_food",
                status="recorded",
                world_time="09:00",
            )
        )
        session.commit()

        detail = NpcService(NpcRepository(session)).get_detail("ryan")

    assert detail.recent_actions[0].model_dump() == {
        "id": 1,
        "tick": 1,
        "world_time": "09:00",
        "action_type": "move",
        "target_kind": "location",
        "target_id": "missing-place",
        "target_name": "missing-place",
        "reason_code": "low_mood_find_food",
        "reason_text": "心情较低，因此前往missing-place用餐。",
    }
