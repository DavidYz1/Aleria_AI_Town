from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
import math
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from backend.app.world.types import WorldSnapshot


JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]


def _freeze_json(
    value: object,
    path: str = "$",
    active_collection_ids: frozenset[int] = frozenset(),
) -> JsonValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"JSON number at {path} must be finite")
        return value
    if isinstance(value, (Mapping, list, tuple)):
        collection_id = id(value)
        if collection_id in active_collection_ids:
            raise ValueError(f"JSON collection at {path} must not be cyclic")
        active_collection_ids = active_collection_ids | {collection_id}
    if isinstance(value, Mapping):
        frozen: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON object key at {path} must be a string")
            frozen[key] = _freeze_json(
                item,
                f"{path}.{key}",
                active_collection_ids,
            )
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(
                item,
                f"{path}[{index}]",
                active_collection_ids,
            )
            for index, item in enumerate(value)
        )
    raise TypeError(
        f"JSON value at {path} has unsupported type {type(value).__name__}"
    )


def _freeze_json_object(value: Mapping[str, object]) -> Mapping[str, JsonValue]:
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):
        raise TypeError("JSON payload must be an object")
    return frozen


class RuntimeMode(StrEnum):
    AUTO = "auto"
    DETERMINISTIC = "deterministic"
    FORCE_DELIBERATION = "force_deliberation"


class ProposalSource(StrEnum):
    DETERMINISTIC = "deterministic"
    EXISTING_PLAN = "existing_plan"
    LLM = "llm"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class ActionProposal:
    actor_id: str
    action_type: str
    target_kind: str | None = None
    target_id: str | None = None
    reason_code: str = ""
    source: ProposalSource = ProposalSource.DETERMINISTIC
    payload: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze_json_object(self.payload))


@dataclass(frozen=True)
class ActionValidation:
    accepted: bool
    code: str
    message: str


@dataclass(frozen=True)
class ResolvedProposal:
    proposal: ActionProposal
    validation: ActionValidation


@dataclass(frozen=True)
class DomainEventDraft:
    event_type: str
    actor_id: str | None
    description: str
    payload: Mapping[str, JsonValue] = field(default_factory=dict)
    visibility: str = "public"
    causation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze_json_object(self.payload))


@dataclass(frozen=True)
class TraceDraft:
    sequence: int
    stage: str
    actor_id: str | None
    summary: str
    data: Mapping[str, JsonValue] = field(default_factory=dict)
    visibility: str = "private"

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _freeze_json_object(self.data))


@dataclass(frozen=True)
class AgentRuntimeResult:
    world: "WorldSnapshot"
    proposals: tuple[ActionProposal, ...]
    resolutions: tuple[ResolvedProposal, ...]
    events: tuple[DomainEventDraft, ...]
    traces: tuple[TraceDraft, ...]


def to_json_compatible(
    value: JsonValue,
) -> JsonScalar | list[object] | dict[str, object]:
    """Return mutable built-in containers suitable for a JSON encoder."""
    if isinstance(value, Mapping):
        return {key: to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [to_json_compatible(item) for item in value]
    return value
