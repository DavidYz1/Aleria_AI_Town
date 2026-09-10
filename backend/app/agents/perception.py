"""Deterministic historical permissions; free text never defines an audience."""
from collections import defaultdict
from types import MappingProxyType
from uuid import UUID

from backend.app.agents.cognition_contracts import ObservationDraft, PerceptionMode, SourceKind


ROLE_CHANNELS = MappingProxyType({
    "Knight": frozenset({"town_guard"}),
    "Guardian": frozenset({"town_guard", "archive_guardian"}),
    "Assassin": frozenset({"scout_network"}),
})
POLICY_VERSION = "perception-v1"
# Only registered structured fields enter facts. Descriptions and arbitrary
# payload extensions are deliberately absent from these projections.
EVENT_FIELDS = {
    "npc_action": ("action_type", "reason_code"),
    "player_travelled": ("player_id", "from_location_id", "to_location_id"),
    "quest_transitioned": ("player_id", "quest_id", "from_status", "to_status", "interaction", "location_id"),
}
EVENT_SUMMARIES = {
    "npc_action": "Observed an NPC action.",
    "player_travelled": "Observed player travel.",
    "quest_transitioned": "Observed quest progress.",
}


class PerceptionPolicyRegistry:
    def project_event(self, event, npc_profiles) -> tuple[ObservationDraft, ...]:
        if event.event_type not in EVENT_FIELDS or event.perception_scope not in {
            "world_public", "location", "participants", "professional", "private"
        }:
            return ()
        audiences = (event.participant_npc_ids_json, event.witness_npc_ids_json,
                     event.professional_channels_json)
        if any(not isinstance(ids, (list, tuple)) or any(not isinstance(id, str) for id in ids)
               for ids in audiences):
            return ()
        if (event.attention_priority is None or not 0 <= event.attention_priority <= 1
            or event.is_critical not in (0, 1) or event.world_version is None
            or event.clock_tick is None or event.world_time is None or event.created_at is None
            or event.id is None or event.event_sequence is None
            or event.secrecy not in {"public", "private", "secret"}
            or event.visibility not in {"public", "private"}
            or not isinstance(event.payload_json, dict)):
            return ()
        if event.perception_scope == "location" and event.location_id is None:
            return ()
        facts = {"event_type": event.event_type, "actor_id": event.actor_id,
                 "location_id": event.location_id}
        facts.update({key: event.payload_json[key] for key in EVENT_FIELDS[event.event_type]
                      if isinstance(event.payload_json.get(key), str)})
        if event.event_type == "npc_action":
            target = event.payload_json.get("target")
            if isinstance(target, dict) and target.get("kind") in {"npc", "location"} and isinstance(target.get("id"), str):
                facts["target"] = {"kind": target["kind"], "id": target["id"]}
        related = tuple(sorted({value for key, value in facts.items()
                                if key.endswith("_id") and isinstance(value, str)}))
        drafts = []
        for npc in sorted(npc_profiles, key=lambda npc: (npc.sort_order, npc.id)):
            mode = None
            if npc.id in event.participant_npc_ids_json:
                mode = PerceptionMode.PARTICIPANT
            elif event.perception_scope not in {"participants", "private"}:
                if (event.secrecy == "public" and event.visibility == "public"
                    and (event.perception_scope == "world_public" or
                         event.perception_scope == "location" and npc.id in event.witness_npc_ids_json)):
                    mode = PerceptionMode.WITNESSED
                elif ROLE_CHANNELS.get(npc.role, frozenset()).intersection(event.professional_channels_json):
                    mode = PerceptionMode.PROFESSIONAL_CHANNEL
            if mode is None:
                continue
            restricted = event.secrecy != "public" or event.visibility != "public" or event.perception_scope == "private"
            drafts.append(ObservationDraft(
                owner_npc_id=npc.id, source_kind=SourceKind.EVENT, source_key=f"event:{event.id}",
                policy_version=POLICY_VERSION, perception_mode=mode, summary=EVENT_SUMMARIES[event.event_type],
                facts=facts, related_entity_ids=related,
                secrecy=event.secrecy if event.secrecy != "public" else ("private" if restricted else "public"),
                disclosure_scope="internal_only" if restricted else "public",
                importance=max(event.attention_priority, 0.9 if event.is_critical else 0.0),
                confidence=1.0, emotional_valence=0.0, is_critical=bool(event.is_critical)))
        return tuple(drafts)

    def project_turn(self, turn, npc_profiles) -> tuple[ObservationDraft, ...]:
        if len(turn.messages) != 2 or {m.role for m in turn.messages} != {"user", "assistant"}:
            return ()
        user = next(m for m in turn.messages if m.role == "user")
        assistant = next(m for m in turn.messages if m.role == "assistant")
        if (turn.conversation.npc_id not in {npc.id for npc in npc_profiles}
            or user.id is None or assistant.id is None or user.id >= assistant.id
            or any(m.conversation_id != turn.conversation.id for m in turn.messages)):
            return ()
        for field in ("turn_id", "world_version", "clock_tick", "world_time"):
            if getattr(user, field) is None or getattr(user, field) != getattr(assistant, field):
                return ()
        try:
            UUID(user.turn_id)
        except (ValueError, TypeError, AttributeError):
            return ()
        if user.created_at is None or assistant.created_at is None:
            return ()
        return (ObservationDraft(
            owner_npc_id=turn.conversation.npc_id, source_kind=SourceKind.CONVERSATION_TURN,
            source_key=f"conversation_turn:{user.turn_id}", policy_version=POLICY_VERSION,
            perception_mode=PerceptionMode.DIRECT_DIALOGUE, summary="Player made a claim in a direct conversation.",
            facts={"speaker_kind": "player", "claim_text": user.content, "npc_reply": assistant.content},
            related_entity_ids=(turn.conversation.npc_id,), secrecy="private", disclosure_scope="player_dialogue",
            importance=0.5, confidence=1.0, emotional_valence=0.0, is_critical=False),)

    def project_batch(self, events, turns, npc_profiles, *, attention_budget=12) -> tuple[ObservationDraft, ...]:
        candidates = []
        for event in events:
            for draft in self.project_event(event, npc_profiles):
                candidates.append((draft, event.attention_priority, event.event_sequence))
        for turn in turns:
            for draft in self.project_turn(turn, npc_profiles):
                candidates.append((draft, 0.5, max(m.id for m in turn.messages)))
        candidates.sort(key=lambda item: (
            item[0].perception_mode != PerceptionMode.PARTICIPANT,
            not item[0].is_critical, -item[1], item[2], item[0].source_key))
        counts = defaultdict(int)
        seen = set()
        selected = []
        for draft, _, _ in candidates:
            key = (draft.owner_npc_id, draft.source_key)
            if key not in seen and counts[draft.owner_npc_id] < attention_budget:
                selected.append(draft)
                seen.add(key)
                counts[draft.owner_npc_id] += 1
        return tuple(selected)
