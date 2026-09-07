from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import AgentRun, ActionProposalRecord, AgentTraceEntry, Event


class AgentRunNotFoundError(RuntimeError):
    pass


class AgentRunPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentRunDetailRecord:
    run: AgentRun
    proposals: tuple[ActionProposalRecord, ...]
    events: tuple[Event, ...]
    trace: tuple[AgentTraceEntry, ...]


class AgentRunRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_detail(self, run_id: str) -> AgentRunDetailRecord:
        try:
            run = self._session.get(AgentRun, run_id)
            if run is None:
                raise AgentRunNotFoundError("agent run not found")
            return AgentRunDetailRecord(
                run=run,
                proposals=tuple(self._session.scalars(select(ActionProposalRecord).where(ActionProposalRecord.run_id == run_id).order_by(ActionProposalRecord.ordinal))),
                events=tuple(self._session.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.event_sequence))),
                trace=tuple(self._session.scalars(select(AgentTraceEntry).where(AgentTraceEntry.run_id == run_id).order_by(AgentTraceEntry.sequence))),
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise AgentRunPersistenceError("agent run is unavailable") from None
