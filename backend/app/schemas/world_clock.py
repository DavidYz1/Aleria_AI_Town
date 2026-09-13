from typing import Literal

from pydantic import BaseModel, Field

from backend.app.agents.contracts import RuntimeMode
from backend.app.schemas.world import ActionId, WorldData
from backend.app.schemas.agent_run import AgentRunSummary, DomainEventInfo


class WorldTickRequest(BaseModel):
    expected_world_version: int = Field(ge=0)
    runtime_mode: RuntimeMode = RuntimeMode.AUTO


class WorldActionInfo(BaseModel):
    id: int
    clock_tick: int = Field(ge=1)
    actor_id: str
    action_type: ActionId
    target_kind: Literal["location", "npc"] | None
    target_id: str | None
    reason: str
    status: Literal["executed"]
    run_id: str
    proposal_id: int
    world_version: int
    world_time: str


class WorldEventInfo(DomainEventInfo):
    pass


class WorldTickData(BaseModel):
    run: AgentRunSummary
    world: WorldData
    actions: list[WorldActionInfo]
    events: list[WorldEventInfo]
