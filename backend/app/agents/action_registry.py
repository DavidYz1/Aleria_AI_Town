from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Literal, Mapping

from backend.app.agents.contracts import ActionProposal, ActionValidation, JsonValue
from backend.app.world.role_routines import WORK_LOCATION_BY_ROLE
from backend.app.world.types import NpcSnapshot, WorldSnapshot


class ActionValidationError(ValueError):
    pass


ValidationHandler = Callable[
    [ActionProposal, NpcSnapshot, WorldSnapshot],
    ActionValidation,
]
ExecutionHandler = Callable[
    [ActionProposal, NpcSnapshot, WorldSnapshot],
    NpcSnapshot,
]


@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    required_target_kind: Literal["location", "npc"] | None
    validation_handler: ValidationHandler
    execution_handler: ExecutionHandler
    event_type: str
    public_label: str
    description: str = ""
    input_schema: Mapping[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionEventMetadata:
    event_type: str
    public_label: str


class ActionRegistry:
    def __init__(self, definitions: Iterable[ActionDefinition]) -> None:
        by_type: dict[str, ActionDefinition] = {}
        for definition in definitions:
            if definition.action_type in by_type:
                raise ValueError(
                    f"duplicate action definition: {definition.action_type}"
                )
            by_type[definition.action_type] = definition
        self._definitions: Mapping[str, ActionDefinition] = MappingProxyType(
            by_type
        )

    @property
    def action_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def to_tool_manifest(self) -> list[dict]:
        """输出 MCP tools/list 兼容格式。空 description 直接报错，不静默通过。"""
        manifest: list[dict] = []
        for definition in self._definitions.values():
            if not definition.description:
                raise ValueError(
                    f"action '{definition.action_type}' 缺少 description，模型无法理解该工具"
                )
            manifest.append(
                {
                    "name": definition.action_type,
                    "description": definition.description,
                    "inputSchema": dict(definition.input_schema),
                }
            )
        return manifest

    def validate(
        self,
        proposal: ActionProposal,
        actor: NpcSnapshot,
        world: WorldSnapshot,
    ) -> ActionValidation:
        definition = self._definitions.get(proposal.action_type)
        if definition is None:
            return _rejected(
                "unknown_action",
                f"unknown action: {proposal.action_type}",
            )
        if proposal.actor_id != actor.id:
            return _rejected(
                "actor_mismatch",
                "action actor does not match state actor",
            )
        if definition.required_target_kind is None:
            if proposal.target_kind is not None or proposal.target_id is not None:
                return _rejected(
                    "invalid_target",
                    f"{proposal.action_type} does not accept a target",
                )
        elif (
            proposal.target_kind != definition.required_target_kind
            or proposal.target_id is None
        ):
            return _rejected(
                "invalid_target",
                f"{proposal.action_type} requires a valid "
                f"{definition.required_target_kind} target",
            )
        return definition.validation_handler(proposal, actor, world)

    def event_metadata(self, action_type: str) -> ActionEventMetadata:
        definition = self._definitions[action_type]
        return ActionEventMetadata(
            event_type=definition.event_type,
            public_label=definition.public_label,
        )

    def execute(
        self,
        proposal: ActionProposal,
        actor: NpcSnapshot,
        world: WorldSnapshot,
    ) -> NpcSnapshot:
        validation = self.validate(proposal, actor, world)
        if not validation.accepted:
            raise ActionValidationError(validation.message)
        return self._definitions[proposal.action_type].execution_handler(
            proposal,
            actor,
            world,
        )


def clamp_need(value: int) -> int:
    return max(0, min(100, value))


def _accepted(
    _proposal: ActionProposal,
    _actor: NpcSnapshot,
    _world: WorldSnapshot,
) -> ActionValidation:
    return ActionValidation(True, "accepted", "action accepted")


def _rejected(code: str, message: str) -> ActionValidation:
    return ActionValidation(False, code, message)


def _validate_move(
    proposal: ActionProposal,
    _actor: NpcSnapshot,
    world: WorldSnapshot,
) -> ActionValidation:
    if proposal.target_id not in {location.id for location in world.locations}:
        return _rejected(
            "unknown_location",
            "move requires a valid location target",
        )
    return _accepted(proposal, _actor, world)


def _validate_work(
    proposal: ActionProposal,
    actor: NpcSnapshot,
    world: WorldSnapshot,
) -> ActionValidation:
    duty_location = WORK_LOCATION_BY_ROLE.get(actor.role)
    if duty_location is None or actor.location_id != duty_location:
        return _rejected(
            "wrong_duty_location",
            "work requires the actor duty location",
        )
    return _accepted(proposal, actor, world)


def _validate_eat(
    proposal: ActionProposal,
    actor: NpcSnapshot,
    world: WorldSnapshot,
) -> ActionValidation:
    if actor.location_id != "tavern":
        return _rejected(
            "not_at_tavern",
            "eat requires the tavern location",
        )
    return _accepted(proposal, actor, world)


def _validate_talk(
    proposal: ActionProposal,
    actor: NpcSnapshot,
    world: WorldSnapshot,
) -> ActionValidation:
    target = next(
        (npc for npc in world.npcs if npc.id == proposal.target_id),
        None,
    )
    if (
        target is None
        or target.id == actor.id
        or target.location_id != actor.location_id
    ):
        return _rejected(
            "talk_target_unavailable",
            "talk target must be another NPC at the same location",
        )
    return _accepted(proposal, actor, world)


def _update_actor(
    actor: NpcSnapshot,
    *,
    action_type: str,
    location_id: str | None = None,
    energy_delta: int = 0,
    mood_delta: int = 0,
    social_delta: int = 0,
) -> NpcSnapshot:
    return replace(
        actor,
        location_id=actor.location_id if location_id is None else location_id,
        current_action=action_type,
        energy=clamp_need(actor.energy + energy_delta),
        mood=clamp_need(actor.mood + mood_delta),
        social=clamp_need(actor.social + social_delta),
    )


def _execute_move(
    proposal: ActionProposal,
    actor: NpcSnapshot,
    _world: WorldSnapshot,
) -> NpcSnapshot:
    assert proposal.target_id is not None
    return _update_actor(
        actor,
        action_type="move",
        location_id=proposal.target_id,
        energy_delta=-5,
    )


def _execute_rest(
    _proposal: ActionProposal,
    actor: NpcSnapshot,
    _world: WorldSnapshot,
) -> NpcSnapshot:
    return _update_actor(
        actor,
        action_type="rest",
        energy_delta=15,
        mood_delta=2,
    )


def _execute_work(
    _proposal: ActionProposal,
    actor: NpcSnapshot,
    _world: WorldSnapshot,
) -> NpcSnapshot:
    return _update_actor(
        actor,
        action_type="work",
        energy_delta=-8,
        mood_delta=-2,
    )


def _execute_eat(
    _proposal: ActionProposal,
    actor: NpcSnapshot,
    _world: WorldSnapshot,
) -> NpcSnapshot:
    return _update_actor(
        actor,
        action_type="eat",
        energy_delta=5,
        mood_delta=8,
    )


def _execute_talk(
    _proposal: ActionProposal,
    actor: NpcSnapshot,
    _world: WorldSnapshot,
) -> NpcSnapshot:
    return _update_actor(
        actor,
        action_type="talk",
        energy_delta=-2,
        mood_delta=5,
        social_delta=15,
    )


def _execute_wait(
    _proposal: ActionProposal,
    actor: NpcSnapshot,
    _world: WorldSnapshot,
) -> NpcSnapshot:
    return actor


def _schema(*, needs_target: bool, target_desc: str) -> dict:
    properties: dict = {
        "reason_code": {
            "type": "string",
            "description": "本次动作的简短原因编码，小写下划线，如 low_energy",
        }
    }
    required = ["reason_code"]
    if needs_target:
        properties["target_id"] = {"type": "string", "description": target_desc}
        required.append("target_id")
    return {"type": "object", "properties": properties, "required": required}


def build_default_action_registry() -> ActionRegistry:
    return ActionRegistry(
        (
            ActionDefinition(
                "move",
                "location",
                _validate_move,
                _execute_move,
                "npc_action",
                "前往",
                "移动到镇上的另一个地点。目标必须是当前世界中存在的地点 id。",
                _schema(needs_target=True, target_desc="目标地点 id，如 tavern / park / castle / forest"),
            ),
            ActionDefinition(
                "rest",
                None,
                _accepted,
                _execute_rest,
                "npc_action",
                "休息",
                "原地休息以恢复体力。不需要目标。",
                _schema(needs_target=False, target_desc=""),
            ),
            ActionDefinition(
                "work",
                None,
                _validate_work,
                _execute_work,
                "npc_action",
                "工作",
                "从事本职工作，消耗体力并提升心情。不需要目标，但**只能在你的岗位地点执行**（岗位见 [World] 段），否则会被拒绝。",
                _schema(needs_target=False, target_desc=""),
            ),
            ActionDefinition(
                "eat",
                None,
                _validate_eat,
                _execute_eat,
                "npc_action",
                "用餐",
                "进食以恢复体力。不需要目标，但**只能在酒馆（tavern）执行**，否则会被拒绝；不在酒馆时应先 move 过去。",
                _schema(needs_target=False, target_desc=""),
            ),
            ActionDefinition(
                "talk",
                "npc",
                _validate_talk,
                _execute_talk,
                "npc_action",
                "交谈",
                "与同一地点的另一个 NPC 交谈。目标必须是当前与你处于同一地点的 NPC id。",
                _schema(needs_target=True, target_desc="目标 NPC 的 id"),
            ),
            ActionDefinition(
                "wait",
                None,
                _accepted,
                _execute_wait,
                "npc_action",
                "等待",
                "原地等待一个时间单位，不产生显著状态变化。不需要目标。",
                _schema(needs_target=False, target_desc=""),
            ),
        )
    )
