import json
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import (
    AgentCognitionState,
    Belief,
    BeliefEvidence,
    Conversation,
    ConversationMessage,
    Event,
    AgentRun,
    ActionProposalRecord,
    AgentTraceEntry,
    Location,
    Memory,
    MemoryEvidence,
    NpcProfile,
    NpcState,
    Observation,
    PlayerState,
    QuestEvent,
    QuestProgress,
    WorldAction,
    WorldState,
)
from backend.app.schemas.demo import DemoResetData
from backend.app.schemas.seed import SeedData


class DemoResetPersistenceError(RuntimeError):
    pass


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_seed_data(seed_dir: Path) -> SeedData:
    authored_knowledge = _read_json(seed_dir / "agent_knowledge.json")
    return SeedData.model_validate(
        {
            "world": _read_json(seed_dir / "world.json"),
            "locations": _read_json(seed_dir / "locations.json"),
            "npcs": _read_json(seed_dir / "npcs.json"),
            "authored_knowledge_version": authored_knowledge["version"],
            "authored_knowledge": authored_knowledge["items"],
        }
    )


class DemoResetService:
    def __init__(self, session: Session):
        self._session = session

    def reset(self, seed: SeedData) -> DemoResetData:
        try:
            self._reset(seed)
            self._session.commit()
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise DemoResetPersistenceError(
                "Demo reset could not be persisted"
            ) from exc

        return DemoResetData(
            world_id=seed.world.id,
            clock_tick=seed.world.clock_tick,
            player_location_id="tavern",
            quest_status="available",
        )

    def _reset(self, seed: SeedData) -> None:
        memory_ids = select(Memory.id).where(Memory.world_id == seed.world.id)
        belief_ids = select(Belief.id).where(Belief.world_id == seed.world.id)
        self._session.execute(
            delete(BeliefEvidence).where(BeliefEvidence.belief_id.in_(belief_ids))
        )
        self._session.execute(delete(Belief).where(Belief.world_id == seed.world.id))
        self._session.execute(
            delete(MemoryEvidence).where(
                MemoryEvidence.derived_memory_id.in_(memory_ids)
                | MemoryEvidence.evidence_memory_id.in_(memory_ids)
            )
        )
        self._session.execute(delete(Memory).where(Memory.world_id == seed.world.id))
        self._session.execute(
            delete(Observation).where(Observation.world_id == seed.world.id)
        )
        self._session.execute(
            delete(AgentCognitionState).where(
                AgentCognitionState.world_id == seed.world.id
            )
        )

        player_ids = select(PlayerState.id).where(
            PlayerState.world_id == seed.world.id
        )
        self._session.execute(
            delete(QuestEvent).where(QuestEvent.player_id.in_(player_ids))
        )
        self._session.execute(
            delete(QuestProgress).where(
                QuestProgress.player_id.in_(player_ids)
            )
        )
        self._session.execute(
            delete(PlayerState).where(PlayerState.world_id == seed.world.id)
        )

        conversation_ids = select(Conversation.id).where(
            Conversation.world_id == seed.world.id
        )
        self._session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.conversation_id.in_(conversation_ids)
            )
        )
        self._session.execute(
            delete(Conversation).where(Conversation.world_id == seed.world.id)
        )
        run_ids = select(AgentRun.id).where(AgentRun.world_id == seed.world.id)
        self._session.execute(delete(AgentTraceEntry).where(AgentTraceEntry.run_id.in_(run_ids)))
        self._session.execute(delete(Event).where(Event.world_id == seed.world.id))
        self._session.execute(
            delete(WorldAction).where(WorldAction.world_id == seed.world.id)
        )
        self._session.execute(delete(ActionProposalRecord).where(ActionProposalRecord.run_id.in_(run_ids)))
        self._session.execute(delete(AgentRun).where(AgentRun.world_id == seed.world.id))

        self._session.merge(WorldState(**seed.world.model_dump()))
        for location in seed.locations:
            self._session.merge(Location(**location.model_dump()))
        for npc in seed.npcs:
            self._session.merge(
                NpcProfile(
                    id=npc.id,
                    name=npc.name,
                    role=npc.role,
                    personality_json=npc.personality,
                    sort_order=npc.sort_order,
                )
            )
        self._session.flush()
        for npc in seed.npcs:
            self._session.merge(
                NpcState(npc_id=npc.id, **npc.state.model_dump())
            )

        now = datetime.now(UTC)
        for item in seed.authored_knowledge:
            content = item.content.strip()
            self._session.add(Memory(
                id=str(uuid5(
                    NAMESPACE_URL,
                    f"aleria:{seed.world.id}:{item.owner_npc_id}:"
                    f"{seed.authored_knowledge_version}:{item.source_id}",
                )),
                world_id=seed.world.id,
                owner_npc_id=item.owner_npc_id,
                memory_type="knowledge",
                source_observation_id=None,
                authored_source_id=item.source_id,
                authored_source_version=seed.authored_knowledge_version,
                content=content,
                safe_summary=item.safe_summary.strip(),
                normalized_content_hash=hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
                related_entity_ids_json=[],
                occurred_world_version=item.occurred_world_version,
                occurred_clock_tick=item.occurred_clock_tick,
                created_world_version=seed.world.world_version,
                created_clock_tick=seed.world.clock_tick,
                occurred_world_time=item.occurred_world_time,
                source_created_at=item.source_created_at,
                created_at=now,
                importance=item.importance,
                confidence=item.confidence,
                emotional_valence=item.emotional_valence,
                secrecy=item.secrecy,
                disclosure_scope=item.disclosure_scope,
                lifecycle_state="active",
                embedding_provider=None,
                embedding_model=None,
                embedding_version=None,
                embedding_input_hash=None,
                embedding_dimensions=None,
                embedding_status="unavailable",
                embedding=None,
                last_accessed_at=None,
                access_count=0,
            ))

        self._session.merge(
            PlayerState(
                id="default-player",
                world_id=seed.world.id,
                location_id="tavern",
            )
        )
        self._session.flush()
        self._session.merge(
            QuestProgress(
                player_id="default-player",
                quest_id="missing-child",
                status="available",
                version=0,
                updated_clock_tick=seed.world.clock_tick,
            )
        )
