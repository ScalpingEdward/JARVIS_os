from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class PositionAssessed(BaseModel):
    """One live position, freshly re-assessed this tick."""

    workspace_id: str
    position_ticket: int
    symbol: str
    break_even_assessment_id: UUID | None = None
    break_even_state: str | None = None
    trailing_stream_id: UUID | None = None
    trailing_state: str | None = None
    #: True only on the tick where the corresponding assessment first
    #: *became* actionable for this position -- a Telegram notification was
    #: sent exactly once for that transition. Stays False on every later
    #: tick that still reports the same state, so a position sitting at
    #: approval-required for an hour does not page Brano every 10 seconds.
    break_even_notified: bool = False
    trailing_notified: bool = False


class PositionSkipped(BaseModel):
    """A live position this tick could not assess, and why -- never silent."""

    account_login: int | None = None
    position_ticket: int | None = None
    symbol: str | None = None
    reason: str


class MonitorTickResult(BaseModel):
    """What one pass over every registered terminal's live positions did.
    Nothing in here means a stop was moved or a position was closed --
    only that a fresh proposal was recorded, or why one could not be."""

    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assessed: list[PositionAssessed] = Field(default_factory=list)
    skipped: list[PositionSkipped] = Field(default_factory=list)


class MonitorStatus(BaseModel):
    enabled: bool
    interval_seconds: float
    last_tick_at: datetime | None = None
    last_tick_assessed: int = 0
    last_tick_skipped: int = 0
    ticks_run: int = 0
