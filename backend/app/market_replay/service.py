from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ReplayReport,
    ReplaySession,
    ReplaySessionCreate,
    ReplayState,
    ReplayStatus,
)


class MarketReplayService:
    def __init__(self) -> None:
        self._sessions: dict[UUID, ReplaySession] = {}

    def status(self) -> ReplayStatus:
        return ReplayStatus()

    def create(self, payload: ReplaySessionCreate) -> ReplaySession:
        session = ReplaySession(
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe.upper(),
            candles=payload.candles,
            speed=payload.speed,
            initial_balance=payload.initial_balance,
            balance=payload.initial_balance,
            equity=payload.initial_balance,
            human_approval_required=payload.human_approval_required,
            automatic_execution=False,
        )
        self._sessions[session.id] = session
        return session

    def list_all(self) -> list[ReplaySession]:
        return list(self._sessions.values())

    def get(self, session_id: UUID) -> ReplaySession | None:
        return self._sessions.get(session_id)

    def step(self, session_id: UUID, bars: int) -> ReplaySession | None:
        session = self.get(session_id)
        if session is None or session.state in {ReplayState.CANCELLED, ReplayState.COMPLETED}:
            return session
        session.state = ReplayState.RUNNING
        session.cursor = min(session.cursor + bars, len(session.candles))
        if session.cursor >= len(session.candles):
            session.state = ReplayState.COMPLETED
        session.updated_at = datetime.now(timezone.utc)
        return session

    def pause(self, session_id: UUID) -> ReplaySession | None:
        session = self.get(session_id)
        if session is not None and session.state not in {ReplayState.CANCELLED, ReplayState.COMPLETED}:
            session.state = ReplayState.PAUSED
            session.updated_at = datetime.now(timezone.utc)
        return session

    def resume(self, session_id: UUID) -> ReplaySession | None:
        session = self.get(session_id)
        if session is not None and session.state == ReplayState.PAUSED:
            session.state = ReplayState.RUNNING
            session.updated_at = datetime.now(timezone.utc)
        return session

    def cancel(self, session_id: UUID) -> ReplaySession | None:
        session = self.get(session_id)
        if session is not None and session.state != ReplayState.COMPLETED:
            session.state = ReplayState.CANCELLED
            session.updated_at = datetime.now(timezone.utc)
        return session

    def report(self, session_id: UUID) -> ReplayReport | None:
        session = self.get(session_id)
        if session is None:
            return None
        current_price = None
        if session.cursor > 0:
            current_price = session.candles[session.cursor - 1].close
        progress = round(session.cursor / len(session.candles) * 100, 2)
        return ReplayReport(
            session_id=session.id,
            symbol=session.symbol,
            timeframe=session.timeframe,
            processed_bars=session.cursor,
            total_bars=len(session.candles),
            progress_pct=progress,
            current_price=current_price,
            balance=session.balance,
            equity=session.equity,
            state=session.state,
            recommendation=(
                "MASTER Brano: review the replay evidence before approving any real-world action."
            ),
        )


market_replay_service = MarketReplayService()
