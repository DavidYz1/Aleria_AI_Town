from backend.app.agents.orchestrator import run_deterministic_advance
from backend.app.world.types import EventPlan, TickResult, WorldSnapshot


def run_tick(world: WorldSnapshot) -> TickResult:
    result = run_deterministic_advance(world)
    return TickResult(
        world=result.world,
        actions=tuple(
            resolution.proposal
            for resolution in result.resolutions
            if resolution.validation.accepted
        ),
        events=tuple(
            EventPlan(
                actor_id=event.actor_id,
                event_type=event.event_type,
                description=event.description,
            )
            for event in result.events
        ),
    )
