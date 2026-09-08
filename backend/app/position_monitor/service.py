"""Core tick logic (synchronous, fully testable) plus a thin async loop
wrapper (not the focus of testing -- it only calls tick() on a timer).

Every derived value below is documented at the point it is computed,
because each one is a real, consequential choice about how a stop gets
proposed to move -- not incidental plumbing. None of it is invented from
nothing: it is either read directly from mt5_bridge's own ingested data,
or a named, justified, conservative industry-standard convention (move to
break-even at 1R; buffer the break-even stop by the current spread) used
because no per-account or per-strategy policy for these values exists yet
anywhere in this codebase. If one is ever built, this is the one place
that would need to start reading it instead.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.accounts.models import TradingAccountRecord
from app.accounts.service import AccountRegistryService, account_registry_service
from app.executive_mt5_break_even_scale_out.models import BreakEvenAssessmentCreate
from app.executive_mt5_break_even_scale_out.service import (
    ExecutiveMT5BreakEvenScaleOutService,
    executive_mt5_break_even_scale_out_service,
)
from app.executive_mt5_position_stream_trailing_stop.models import (
    PositionStreamCreate,
    PositionStreamObservation,
)
from app.executive_mt5_position_stream_trailing_stop.service import (
    ExecutiveMT5PositionStreamTrailingStopService,
    executive_mt5_position_stream_trailing_stop_service,
)
from app.mt5_bridge.models import MT5Position, MT5SymbolSpec, MT5Tick, MT5TerminalData
from app.mt5_bridge.service import MT5BridgeService, mt5_bridge_service

from .models import MonitorStatus, MonitorTickResult, PositionAssessed, PositionSkipped

log = logging.getLogger(__name__)

#: mt5_pusher.py defaults to pushing fresh data every 5 seconds (see
#: bridge/mt5_pusher.py's own --interval default) -- that is the real floor
#: on how fresh anything here can ever be, regardless of how often this
#: loop checks. 10s checks twice per pusher cycle, so a proposal is never
#: more than about one pusher-cycle behind real market movement. Checking
#: much faster than the source pushes would not surface fresher data --
#: it would only create more assessment records for the same snapshot
#: (these executive_mt5_* modules keep every record with no eviction; see
#: the "Offen" note in this session's documentation).
DEFAULT_INTERVAL_SECONDS = 10.0
ACTOR_ID = "position-monitor"


class PositionMonitorService:
    def __init__(
        self,
        break_even_service: ExecutiveMT5BreakEvenScaleOutService | None = None,
        trailing_service: ExecutiveMT5PositionStreamTrailingStopService | None = None,
        bridge_service: MT5BridgeService | None = None,
        accounts_service: AccountRegistryService | None = None,
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        self._break_even = break_even_service or executive_mt5_break_even_scale_out_service
        self._trailing = trailing_service or executive_mt5_position_stream_trailing_stop_service
        self._bridge = bridge_service or mt5_bridge_service
        self._accounts = accounts_service or account_registry_service
        self._clock = clock
        self._status = MonitorStatus(enabled=False, interval_seconds=DEFAULT_INTERVAL_SECONDS)
        self._task: asyncio.Task | None = None

    def status(self) -> MonitorStatus:
        return self._status

    # ------------------------------------------------------------------ tick

    def tick(self) -> MonitorTickResult:
        """One pass over every registered terminal's live positions.

        Skips (never guesses) whenever something needed is actually
        missing: no registered AURON account for the terminal's login, no
        fresh tick or symbol spec for the position's symbol. A skip is
        recorded with its reason, never silently dropped.
        """
        now = self._clock()
        assessed: list[PositionAssessed] = []
        skipped: list[PositionSkipped] = []

        accounts_by_login = {int(a.login): a for a in self._accounts.list_accounts() if a.login.isdigit()}

        for terminal_data in self._bridge.list():
            login = terminal_data.terminal.account_login
            account = accounts_by_login.get(login)
            if account is None:
                for position in terminal_data.positions:
                    skipped.append(PositionSkipped(
                        account_login=login, position_ticket=position.ticket, symbol=position.symbol,
                        reason=f"no AURON account registered for MT5 login {login}",
                    ))
                continue

            compliance = self._accounts.compliance(account.id)
            risk_clear = not compliance.breached

            for position in terminal_data.positions:
                spec = self._latest_symbol_spec(terminal_data, position.symbol)
                tick = self._latest_tick(terminal_data, position.symbol)
                if spec is None or tick is None:
                    skipped.append(PositionSkipped(
                        account_login=login, position_ticket=position.ticket, symbol=position.symbol,
                        reason="no symbol spec or tick pushed yet for this symbol",
                    ))
                    continue

                result = PositionAssessed(
                    workspace_id=str(account.id), position_ticket=position.ticket, symbol=position.symbol,
                )

                if position.stop_loss is not None:
                    # Trailing is assessed first because break_even's own
                    # gate requires trailing_state == "trailing-active" as a
                    # precondition -- feeding it the *real* trailing read
                    # (see _assess_trailing's own honesty note: this is
                    # "stream-unavailable" today, never a fabricated
                    # "trailing-active") means break-even correctly and
                    # honestly reports TRAILING_REQUIRED for now rather than
                    # computing a proposed stop off a false precondition.
                    tr = self._assess_trailing(account, risk_clear, position, spec, tick, now)
                    result.trailing_stream_id = tr.id
                    result.trailing_state = tr.state.value

                    be = self._assess_break_even(
                        account, risk_clear, position, spec, tick, now, trailing_state=tr.state.value,
                    )
                    result.break_even_assessment_id = be.id
                    result.break_even_state = be.state.value
                else:
                    tr = self._assess_trailing(account, risk_clear, position, spec, tick, now)
                    result.trailing_stream_id = tr.id
                    result.trailing_state = tr.state.value
                    skipped.append(PositionSkipped(
                        account_login=login, position_ticket=position.ticket, symbol=position.symbol,
                        reason="position has no stop-loss set -- no 1R distance to trigger break-even from",
                    ))

                assessed.append(result)

        self._status.last_tick_at = now
        self._status.last_tick_assessed = len(assessed)
        self._status.last_tick_skipped = len(skipped)
        self._status.ticks_run += 1
        return MonitorTickResult(checked_at=now, assessed=assessed, skipped=skipped)

    # --------------------------------------------------------- break-even

    def _assess_break_even(
        self, account: TradingAccountRecord, risk_clear: bool,
        position: MT5Position, spec: MT5SymbolSpec, tick: MT5Tick, now: datetime,
        trailing_state: str,
    ):
        side = "buy" if position.side.lower() in ("buy", "long") else "sell"
        # 1R: the position's own original risk distance, in points. This is
        # the standard "move to break-even once price has moved as far in
        # your favor as your stop is away" convention -- not a guess, and
        # not something this codebase defines anywhere else per-account or
        # per-strategy yet (checked: no trigger_points/break_even_offset_points
        # config exists anywhere). If one is ever added, read it here instead.
        trigger_points = abs(position.open_price - position.stop_loss) / spec.point
        spread_points = abs(tick.ask - tick.bid) / spec.point

        payload = BreakEvenAssessmentCreate(
            workspace_id=str(account.id),
            source_key=f"mt5-{position.ticket}-{int(now.timestamp())}-{uuid4().hex[:8]}",
            lifecycle_id=f"mt5-position-{position.ticket}",
            trailing_state=trailing_state,
            position_ticket=position.ticket,
            side=side,
            entry_price=position.open_price,
            current_price=tick.bid if side == "sell" else tick.ask,
            current_volume=position.volume,
            point_size=spec.point,
            trigger_points=trigger_points,
            break_even_offset_points=spread_points,  # move to entry + current spread, not exactly entry
            spread_points=spread_points,
            commission_points=0.0,  # mt5_bridge does not report commission; not invented
            scale_out_percent=0,  # no partial-close policy exists yet -- explicitly none requested
            volume_step=spec.volume_step,
            minimum_remaining_volume=spec.volume_min,
            minimum_rr=0.0,  # RR was already the entry strategy's own gate; not re-gated here
            observed_rr=self._observed_rr(position, side),
            stop_level_points=0.0,  # mt5_bridge does not report the broker's stop_level; not invented
            freeze_level_points=0.0,
            risk_approved=risk_clear,
            prop_rules_approved=risk_clear,
            risk_brain_blocked=False,
            human_approved=False,  # always -- a human reviews via the module's own execute() step
        )
        return self._break_even.create(payload, actor_id=ACTOR_ID)

    @staticmethod
    def _observed_rr(position: MT5Position, side: str) -> float:
        risk = abs(position.open_price - position.stop_loss)
        if risk <= 0:
            return 0.0
        favorable = (
            (position.current_price - position.open_price) if side == "buy"
            else (position.open_price - position.current_price)
        )
        return max(0.0, favorable / risk)

    # --------------------------------------------------------- trailing stop

    def _assess_trailing(
        self, account: TradingAccountRecord, risk_clear: bool,
        position: MT5Position, spec: MT5SymbolSpec, tick: MT5Tick, now: datetime,
    ):
        side = "buy" if position.side.lower() in ("buy", "long") else "sell"
        observation = PositionStreamObservation(
            lifecycle_state="lifecycle-complete",
            # Honest, not optimistic: mt5_bridge is a periodic batch pusher,
            # not a sequenced event stream (checked: no such concept exists
            # in app/mt5_bridge/models.py or bridge/mt5_pusher.py). Reporting
            # stream_connected=True here would be a lie this module would
            # then act on. Reporting it honestly as False means this
            # assessment correctly, safely lands in "stream unavailable"
            # rather than "trailing active" -- the day a real streaming
            # transport exists, this is the one line that changes.
            stream_connected=False,
            sequence_contiguous=False,
            snapshot_age_seconds=max(0, int((now - tick.captured_at).total_seconds())),
            position_exists=True,
            symbol=position.symbol,
            side=side,
            current_price=tick.bid if side == "sell" else tick.ask,
            entry_price=position.open_price,
            current_stop_loss=position.stop_loss,
            current_take_profit=position.take_profit,
            trailing_enabled=False,
            point_size=spec.point,
        )
        payload = PositionStreamCreate(
            workspace_id=str(account.id),
            source_key=f"mt5-{position.ticket}-{int(now.timestamp())}-{uuid4().hex[:8]}",
            actor_id=ACTOR_ID,
            position_ticket=position.ticket,
            risk_brain_clear=risk_clear,
            account_risk_clear=risk_clear,
            prop_rules_clear=risk_clear,
            observation=observation,
        )
        return self._trailing.assess(payload)

    @staticmethod
    def _latest_tick(terminal_data: MT5TerminalData, symbol: str) -> MT5Tick | None:
        matching = [t for t in terminal_data.ticks if t.symbol == symbol]
        return max(matching, key=lambda t: t.captured_at) if matching else None

    @staticmethod
    def _latest_symbol_spec(terminal_data: MT5TerminalData, symbol: str) -> MT5SymbolSpec | None:
        matching = [s for s in terminal_data.symbols if s.symbol == symbol]
        return max(matching, key=lambda s: s.captured_at) if matching else None

    # -------------------------------------------------------------- loop

    async def run_forever(self, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
        """Ticks on a timer until cancelled. One bad tick must not kill the
        loop -- same task-isolation principle as the trading worker."""
        self._status = MonitorStatus(enabled=True, interval_seconds=interval_seconds)
        try:
            while True:
                try:
                    self.tick()
                except Exception:
                    log.exception("position_monitor: tick failed")
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            self._status.enabled = False
            raise

    def start(self, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self.run_forever(interval_seconds))

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


position_monitor_service = PositionMonitorService()
