from backend.app.agents.action_registry import (
    ActionValidationError,
    build_default_action_registry,
    clamp_need,
)
from backend.app.agents.contracts import ActionProposal
from backend.app.world.types import NpcSnapshot, WorldSnapshot


DEFAULT_ACTION_REGISTRY = build_default_action_registry()


def execute_action(
    actor: NpcSnapshot,
    action: ActionProposal,
    world: WorldSnapshot,
) -> NpcSnapshot:
    """Compatibility adapter for the existing synchronous tick engine."""
    return DEFAULT_ACTION_REGISTRY.execute(action, actor, world)
