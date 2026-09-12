"""Read-only public explanation of an NPC's already-permitted memories."""
import logging

from pydantic import ValidationError

from backend.app.agents.memory_retrieval import (
    MemoryRetriever,
    MemoryType,
    RetrievalRequest,
    RetrievalResult,
    RetrievalScope,
    RetrievedMemory,
)
from backend.app.database.action_compat import to_public_action_type
from backend.app.database.npc_repository import (
    NpcDetailRecords,
    NpcDetailUnavailableError,
    NpcRepository,
)
from backend.app.schemas.npc import (
    MemoryExplanationItem,
    MemoryExplanationSource,
    NpcMemoryExplanationsData,
)
from backend.app.services.chat_context import PlayerQuestContextReader
from backend.app.services.cognition_projection import CognitionProjectionService


logger = logging.getLogger(__name__)

UNAVAILABLE_MESSAGE = "NPC memory explanations are unavailable"
# At most five explanations of at most SUMMARY_MAX_LENGTH characters each. The
# budget lives here rather than in Settings so no deployment can widen a public
# surface by configuration.
RETRIEVAL_LIMIT = 5
SUMMARY_MAX_LENGTH = 240
RETRIEVAL_CHAR_BUDGET = RETRIEVAL_LIMIT * SUMMARY_MAX_LENGTH

# The retriever's internal labels are not the public vocabulary. The mapping is
# total: an unrecognised label is a service error, never an invented kind.
SOURCE_KINDS = {
    "observed_event": "world_event",
    "player_claim": "conversation",
    "authored_knowledge": "authored_knowledge",
    "reflection": "reflection",
}
SOURCE_LABELS = {
    "world_event": "亲历事件",
    "conversation": "听到的说法",
    "authored_knowledge": "稳定知识",
    "reflection": "形成的看法",
}
CONVERSATION_SUMMARY = "这位居民记得与你有过一次相关交谈。"

REASON_TEXTS = {
    "semantic": "这段记忆和你此刻关心的事情在含义上最接近。",
    "lexical": "这段记忆里出现了当前情境中的关键信息。",
    "recency": "这件事刚刚发生不久，这位居民印象还很清晰。",
    "importance": "这件事对这位居民本人格外重要。",
    "confidence": "这位居民对这段记忆的来源最有把握。",
}
# The two weight sets MemoryRetriever.retrieve ranks with. Only LEXICAL_WEIGHTS
# may explain a memory that carries no semantic contribution, so a degraded
# retrieval can never print a semantic reason for a score that is structurally 0.
HYBRID_WEIGHTS = (("semantic", 0.40), ("lexical", 0.20), ("recency", 0.20),
                  ("importance", 0.15), ("confidence", 0.05))
LEXICAL_WEIGHTS = (("lexical", 0.45), ("recency", 0.25), ("importance", 0.20),
                   ("confidence", 0.10))


class MemoryExplanationUnavailableError(RuntimeError):
    pass


def dominant_component(memory: RetrievedMemory, mode: str) -> str:
    """Name the public component that contributed most to this memory's rank.

    A memory with no semantic contribution is explained with the lexical
    template set, and an exactly-zero semantic score counts as no contribution.
    This is deliberately stricter than the retriever's own branch, which weights
    a memory by whether it was scored at all: explaining a zero contribution as
    semantic relevance would state something untrue, while explaining it
    lexically only reorders templates that are all true of the same memory.

    Recency is strictly positive for every retrievable memory, so the chosen
    component always names a real contribution rather than an absent one.
    """
    weights = HYBRID_WEIGHTS if mode == "hybrid" and memory.semantic > 0 else LEXICAL_WEIGHTS
    chosen, best = weights[0][0], -1.0
    for component, weight in weights:
        value = weight * getattr(memory, component)
        if value > best:
            chosen, best = component, value
    return chosen


class MemoryExplanationService:
    """Answers one fixed question: why does this NPC currently recall this?

    The caller chooses no query, owner, scope, limit or secrecy. Permission is
    enforced by RetrievalScope.PUBLIC_EXPLANATION in SQL, before any ranking.
    """

    def __init__(
        self,
        npc_repository: NpcRepository,
        retriever: MemoryRetriever,
        *,
        cognition: CognitionProjectionService | None = None,
        quest_context_reader: PlayerQuestContextReader | None = None,
    ) -> None:
        self._npc_repository = npc_repository
        self._retriever = retriever
        self._cognition = cognition
        self._quest_context_reader = quest_context_reader

    def get_explanations(self, npc_id: str) -> NpcMemoryExplanationsData:
        try:
            # NpcNotFoundError is deliberately not caught: a missing NPC keeps the
            # existing 404 contract instead of becoming a cognition failure.
            records = self._npc_repository.get_detail_records(npc_id)
        except NpcDetailUnavailableError:
            raise MemoryExplanationUnavailableError(UNAVAILABLE_MESSAGE) from None

        self._catch_up(records)
        result = self._retrieve(records)
        try:
            return NpcMemoryExplanationsData(
                npc_id=records.profile.id,
                retrieval_mode=result.mode,
                fallback_used=result.mode == "lexical_fallback",
                memories=[self._project(memory, result.mode) for memory in result.memories],
            )
        except ValidationError:
            logger.warning("Memory explanation projection unavailable category=memory_explanation")
            raise MemoryExplanationUnavailableError(UNAVAILABLE_MESSAGE) from None

    def _catch_up(self, records: NpcDetailRecords) -> None:
        """Enrichment, never a precondition: a failure still explains what exists."""
        if self._cognition is None:
            return
        session = self._cognition.repository.session
        try:
            self._cognition.catch_up_owner(records.world.id, records.profile.id)
        except Exception:
            logger.warning("Memory explanation cognition unavailable category=core_projection")
        finally:
            # catch_up_owner and retrieve both refuse a Session that still owns a
            # transaction, and a failed catch-up can abandon its read transaction.
            try:
                if session.in_transaction():
                    session.rollback()
            except Exception:
                logger.warning("Memory explanation cognition unavailable category=core_projection")

    def _retrieve(self, records: NpcDetailRecords) -> RetrievalResult:
        try:
            return self._retriever.retrieve(RetrievalRequest(
                world_id=records.world.id,
                owner_npc_id=records.profile.id,
                current_world_version=records.world.world_version,
                current_clock_tick=records.world.clock_tick,
                query_text=self._query_text(records),
                scope=RetrievalScope.PUBLIC_EXPLANATION,
                allowed_memory_types=frozenset(MemoryType),
                limit=RETRIEVAL_LIMIT,
                char_budget=RETRIEVAL_CHAR_BUDGET,
            ))
        except Exception:
            logger.warning("Memory explanation unavailable category=memory_unavailable")
            raise MemoryExplanationUnavailableError(UNAVAILABLE_MESSAGE) from None

    def _query_text(self, records: NpcDetailRecords) -> str:
        parts = [records.profile.name, records.profile.role, records.location.name,
                 to_public_action_type(records.state.current_action)]
        quest = self._quest_context()
        if quest is not None:
            parts.extend((quest.quest_objective, quest.location_name))
        return " ".join(part for part in parts if part)

    def _quest_context(self):
        if self._quest_context_reader is None:
            return None
        try:
            return self._quest_context_reader.get_chat_context()
        except Exception:
            logger.warning("Memory explanation quest context unavailable category=quest_context")
            return None

    def _project(self, memory: RetrievedMemory, mode: str) -> MemoryExplanationItem:
        kind = SOURCE_KINDS.get(memory.source_label)
        if kind is None:
            logger.warning("Memory explanation source unavailable category=memory_explanation")
            raise MemoryExplanationUnavailableError(UNAVAILABLE_MESSAGE)
        return MemoryExplanationItem(
            id=memory.memory_id,
            type=memory.memory_type,
            summary=self._summary(kind, memory.content),
            occurred_clock_tick=memory.occurred_clock_tick,
            source=MemoryExplanationSource(kind=kind, label=SOURCE_LABELS[kind]),
            reason_text=REASON_TEXTS[dominant_component(memory, mode)],
        )

    @staticmethod
    def _summary(kind: str, content: str) -> str:
        if kind == "conversation":
            # Forward-extension slot. PUBLIC_EXPLANATION's SQL hard filter excludes
            # every player conversation Memory today, because perception fixes those
            # Observations to private/player_dialogue, so this branch is unreachable
            # through this scope. Should such a Memory ever become public/public, its
            # public summary stays this fixed sentence - never `content`, and never
            # the player's own words.
            return CONVERSATION_SUMMARY
        if len(content) > SUMMARY_MAX_LENGTH:
            # memories.safe_summary is unbounded Text. Truncating deterministically
            # keeps a long legitimate memory explainable instead of turning it into
            # a DTO validation failure.
            return content[:SUMMARY_MAX_LENGTH - 1] + "…"
        return content
