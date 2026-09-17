from datetime import UTC, datetime
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mode: str
    trigger_type: str
    status: str
    base_world_version: int
    resulting_world_version: int
    base_clock_tick: int
    resulting_clock_tick: int


ACTION_TYPES = frozenset({"eat", "move", "rest", "talk", "wait", "work"})
TARGET_KINDS = frozenset({"location", "npc"})
SOURCES = frozenset({"deterministic", "existing_plan", "llm", "fallback"})
TRACE_STAGES = frozenset({"run_started", "planning", "rule_rejection", "proposal", "validation", "execution", "event", "run_completed"})
QUEST_STATUSES = frozenset({"available", "accepted", "briefed_by_grey", "shoe_found", "child_found", "completed"})
QUEST_INTERACTIONS = frozenset({"accept_quest", "ask_grey", "inspect_shoe", "search_child", "return_child"})


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value))


def _reason_code(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value))


def _integer(value: object) -> bool:
    return type(value) is int and value >= 0


def _uuid_reference(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return value if str(UUID(value)) == value else None
    except ValueError:
        return None


def _target(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"kind", "id"}:
        return None
    if value["kind"] not in TARGET_KINDS or not _identifier(value["id"]):
        return None
    return {"kind": value["kind"], "id": value["id"]}


def _actor_state(value: object) -> dict | None:
    if not isinstance(value, dict) or set(value) != {"location_id", "current_action", "energy", "mood", "social"}:
        return None
    if not _identifier(value["location_id"]) or value["current_action"] not in ACTION_TYPES:
        return None
    if not all(type(value[key]) is int and 0 <= value[key] <= 100 for key in ("energy", "mood", "social")):
        return None
    return {key: value[key] for key in ("location_id", "current_action", "energy", "mood", "social")}


def _event_facts(event_type: str, value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    if event_type == "npc_action":
        if set(value) != {"action_type", "target", "reason_code", "proposal_ordinal"}:
            return {}
        target = _target(value["target"])
        if value["target"] is not None and target is None:
            return {}
        if value["action_type"] not in ACTION_TYPES or not _reason_code(value["reason_code"]) or not _integer(value["proposal_ordinal"]):
            return {}
        return {"action_type": value["action_type"], "target": target, "reason_code": value["reason_code"], "proposal_ordinal": value["proposal_ordinal"]}
    if event_type == "player_travelled":
        if set(value) == {"player_id", "from_location_id", "to_location_id"} and all(_identifier(value[key]) for key in value):
            return dict(value)
    if event_type == "quest_transitioned":
        keys = {"player_id", "quest_id", "from_status", "to_status", "interaction", "location_id"}
        if (
            set(value) == keys
            and _identifier(value["player_id"])
            and _identifier(value["quest_id"])
            and _identifier(value["location_id"])
            and value["from_status"] in QUEST_STATUSES
            and value["to_status"] in QUEST_STATUSES
            and value["interaction"] in QUEST_INTERACTIONS
        ):
            return dict(value)
    return {}


def _trace_facts(stage: str, value: object) -> dict:
    if not isinstance(value, dict) or stage not in TRACE_STAGES:
        return {}
    if stage == "run_started":
        if set(value) == {"world_id", "world_version", "clock_tick"} and _identifier(value["world_id"]) and _integer(value["world_version"]) and _integer(value["clock_tick"]):
            return dict(value)
    if stage == "planning":
        keys = {
            "npc_id", "source", "goal", "thought", "provider", "model",
            "latency_ms", "tokens_used", "failure_stage", "failure_code",
        }
        # goal / thought 是模型自由文本，长度上限与 AgentDecision 契约、DB 列宽一致，
        # 保证公开投影始终有界。
        limits = {"goal": 200, "thought": 800, "provider": 100, "model": 200}
        if (
            set(value) == keys
            and _identifier(value["npc_id"])
            and value["source"] in SOURCES
            and all(isinstance(value[key], str) and 0 < len(value[key]) <= limit for key, limit in limits.items())
            and all(value[key] is None or _integer(value[key]) for key in ("latency_ms", "tokens_used"))
            # 失败分类是**枚举出来的类别名**，不是模型自由文本，也不含响应正文或
            # 凭据，所以可以公开：它让「为什么这个 NPC 忽然按确定性策略行动」有据
            # 可依。规则拒绝的明细不走这里 —— 见文件末尾的说明。
            and value["failure_stage"] in (None, "provider")
            and (
                value["failure_code"] is None
                if value["failure_stage"] is None
                else _reason_code(value["failure_code"])
            )
        ):
            return dict(value)
    if stage == "rule_rejection":
        public = {
            "npc_id", "failure_stage", "failure_code",
            "attempted_action", "attempted_source",
        }
        stored = public | {"attempted_target"}
        # **这个函数必须幂等。** FastAPI 的 `response_model` 会对返回值再验证一次，
        # 于是投影结果会第二次流经这里。其余 stage 恰好满足（它们返回的 key 集合
        # 与输入相同），本分支是唯一做收窄的，所以必须同时认「落盘形状」与
        # 「已收窄形状」—— 否则第二遍会判定不合法并清空成 {}。
        if (
            set(value) in (stored, public)
            and _identifier(value["npc_id"])
            and value["failure_stage"] == "rule"
            and _reason_code(value["failure_code"])
            and value["attempted_action"] in ACTION_TYPES
            and value["attempted_source"] in SOURCES
        ):
            # 落盘完整、对外收窄 —— 与 `npc_plan` 的 evidence 同一条规则。
            # `attempted_target` 的 id 是模型编造的自由文本（`unknown_location`
            # 恰恰意味着它不对应任何真实地点），不进公开响应；排障需要它时读
            # trace 表。其余四项都是枚举出来的类别名，公开它们让「这个 NPC 为什么
            # 忽然按确定性策略行动」对玩家可解释。
            return {key: value[key] for key in sorted(public)}
    if stage == "proposal":
        keys = {"action_type", "target", "reason_code", "proposal_ordinal", "source"}
        target = _target(value.get("target"))
        if set(value) == keys and (value["target"] is None or target is not None) and value["action_type"] in ACTION_TYPES and _reason_code(value["reason_code"]) and _integer(value["proposal_ordinal"]) and value["source"] in SOURCES:
            return {**value, "target": target}
    if stage == "validation":
        if set(value) == {"proposal_ordinal", "accepted", "code"} and _integer(value["proposal_ordinal"]) and type(value["accepted"]) is bool and _reason_code(value["code"]):
            return dict(value)
    if stage == "execution":
        keys = {"proposal_ordinal", "action_type", "before", "after"}
        before, after = _actor_state(value.get("before")), _actor_state(value.get("after"))
        if set(value) == keys and _integer(value["proposal_ordinal"]) and value["action_type"] in ACTION_TYPES and before is not None and after is not None:
            return {"proposal_ordinal": value["proposal_ordinal"], "action_type": value["action_type"], "before": before, "after": after}
    if stage == "event":
        if set(value) == {"proposal_ordinal", "event_type"} and _integer(value["proposal_ordinal"]) and value["event_type"] == "npc_action":
            return dict(value)
    if stage == "run_completed":
        keys = {"world_id", "world_version", "clock_tick", "event_sequence", "accepted_count", "rejected_count"}
        if set(value) == keys and _identifier(value["world_id"]) and all(_integer(value[key]) for key in keys - {"world_id"}):
            return dict(value)
    return {}


def _event_description(event_type: str, actor_id: str | None, payload: dict) -> str:
    if event_type == "npc_action" and _identifier(actor_id) and payload:
        return f"{actor_id} performed {payload['action_type']}"
    if event_type == "player_travelled" and payload:
        return f"Player travelled to {payload['to_location_id']}"
    if event_type == "quest_transitioned" and payload:
        return f"Quest {payload['quest_id']} transitioned to {payload['to_status']}"
    return "Runtime event recorded"


def utc_timestamp(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ActionProposalInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordinal: int
    actor_id: str
    action_type: str
    target_kind: str | None
    target_id: str | None
    reason_code: str
    source: str
    payload: dict = Field(validation_alias="payload_json")
    status: str
    rejection_code: str | None
    rejection_message: str | None

    @field_validator("payload", mode="before")
    @classmethod
    def public_payload(cls, value):
        return {} if value == {} else {}

    @model_validator(mode="after")
    def safe_rejection(self):
        if self.target_kind not in TARGET_KINDS or not _identifier(self.target_id):
            self.target_kind = None
            self.target_id = None
        self.rejection_message = "Proposal rejected" if self.status == "rejected" else None
        return self


class AgentTraceInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    stage: str
    actor_id: str | None
    summary: str
    data: dict = Field(validation_alias="data_json")
    visibility: str
    created_at: datetime

    _utc = field_validator("created_at")(utc_timestamp)

    @model_validator(mode="after")
    def factual_summary(self):
        summaries = {
            "run_started": "Deterministic world advance started",
            "planning": "Planning decision recorded",
            "rule_rejection": "Proposal rejected by rules",
            "proposal": "Action proposed", "validation": "Proposal validated",
            "execution": "Action executed", "event": "Domain event recorded",
            "run_completed": "Deterministic world advance completed",
        }
        self.data = _trace_facts(self.stage, self.data)
        self.summary = summaries.get(self.stage, "Runtime trace recorded")
        return self


class DomainEventInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str | None
    world_version: int
    clock_tick: int = Field(ge=0)
    event_sequence: int
    event_type: str
    actor_id: str | None
    action_id: int | None
    source_event_id: int | None
    description: str
    world_time: str
    payload: dict = Field(validation_alias="payload_json")
    visibility: str
    secrecy: str
    causation_id: str | None
    correlation_id: str
    created_at: datetime

    _utc = field_validator("created_at")(utc_timestamp)

    @model_validator(mode="after")
    def public_facts_and_description(self):
        self.payload = _event_facts(self.event_type, self.payload)
        self.causation_id = _uuid_reference(self.causation_id)
        self.description = _event_description(self.event_type, self.actor_id, self.payload)
        return self


class AgentRunDetail(BaseModel):
    run: AgentRunSummary
    proposals: list[ActionProposalInfo]
    events: list[DomainEventInfo]
    trace: list[AgentTraceInfo]
