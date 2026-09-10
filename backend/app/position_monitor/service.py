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
from app.db import SessionLocal
from app.db_models import MonitorAuditRow, MonitorLastNotifiedStateRow, MonitorOriginalStopLossRow
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
from app.mt5_bridge.models import MT5ConnectionState, MT5Position, MT5SymbolSpec, MT5Tick, MT5TerminalData
from app.mt5_bridge.service import MT5BridgeService, mt5_bridge_service
from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError

from .models import MonitorAuditRecord, MonitorStatus, MonitorTickResult, PositionAssessed, PositionSkipped

log = logging.getLogger(__name__)

#: Actionable end states worth waking a human up for: the trigger was
#: reached and a real stop was computed. Every other state (still waiting,
#: blocked, or a later lifecycle stage this monitor's own
#: human_approved=False/human_approval_verified=False payload can never
#: reach) is not.
ACTIONABLE_BREAK_EVEN_STATES = frozenset({"approval-required", "risk-rejected"})
ACTIONABLE_TRAILING_STATES = frozenset({"approval-required", "blocked"})

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
    MAX_AUDIT_RECORDS = 500

    def __init__(
        self,
        break_even_service: ExecutiveMT5BreakEvenScaleOutService | None = None,
        trailing_service: ExecutiveMT5PositionStreamTrailingStopService | None = None,
        bridge_service: MT5BridgeService | None = None,
        accounts_service: AccountRegistryService | None = None,
        telegram_client: TelegramDeliveryClient | None = None,
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        self._break_even = break_even_service or executive_mt5_break_even_scale_out_service
        self._trailing = trailing_service or executive_mt5_position_stream_trailing_stop_service
        self._bridge = bridge_service or mt5_bridge_service
        self._accounts = accounts_service or account_registry_service
        self._telegram = telegram_client or TelegramDeliveryClient()
        self._clock = clock
        self._status = MonitorStatus(enabled=False, interval_seconds=DEFAULT_INTERVAL_SECONDS)
        self._task: asyncio.Task | None = None
        # Per-ticket state, both keyed by MT5 position ticket (unique and
        # never reused for a new trade) rather than by the ever-changing
        # assessment id a fresh record gets each tick. Persisted via
        # SessionLocal (see MonitorOriginalStopLossRow/
        # MonitorLastNotifiedStateRow's own docstrings) -- previously two
        # in-memory dicts, silently emptied on every restart. Losing
        # _original_stop_loss specifically was a real correctness issue,
        # not just a missing convenience: recomputing it from a
        # since-moved stop would corrupt every future trigger-point
        # calculation for that position.

    def status(self) -> MonitorStatus:
        return self._status

    def _record(self, kind: str, detail: str = "", position_ticket: int | None = None) -> None:
        event = MonitorAuditRecord(kind=kind, detail=detail[:500], position_ticket=position_ticket)
        with SessionLocal() as session:
            session.add(MonitorAuditRow(id=str(event.id), created_at=event.created_at, data=event.model_dump_json()))
            session.flush()
            total = session.query(MonitorAuditRow).count()
            if total > self.MAX_AUDIT_RECORDS:
                excess = total - self.MAX_AUDIT_RECORDS
                stale_ids = [
                    r.id for r in
                    session.query(MonitorAuditRow.id).order_by(MonitorAuditRow.created_at).limit(excess).all()
                ]
                session.query(MonitorAuditRow).filter(MonitorAuditRow.id.in_(stale_ids)).delete(
                    synchronize_session=False
                )
            session.commit()

    def audit_records(self, limit: int = 50) -> list[MonitorAuditRecord]:
        """Most recent first -- notifications actually sent, and any tick
        that raised. Not every routine tick; see MonitorAuditRecord's own
        docstring for why."""
        with SessionLocal() as session:
            rows = session.query(MonitorAuditRow).order_by(MonitorAuditRow.created_at.desc()).limit(limit).all()
        return [MonitorAuditRecord.model_validate_json(r.data) for r in rows]

    @staticmethod
    def _get_original_stop_loss(ticket: int) -> float | None:
        with SessionLocal() as session:
            row = session.get(MonitorOriginalStopLossRow, ticket)
        return row.stop_loss if row else None

    @staticmethod
    def _set_original_stop_loss(ticket: int, stop_loss: float) -> None:
        with SessionLocal() as session:
            session.add(MonitorOriginalStopLossRow(ticket=ticket, stop_loss=stop_loss))
            session.commit()

    @staticmethod
    def _get_last_notified_state(ticket: int, kind: str) -> str | None:
        with SessionLocal() as session:
            row = session.get(MonitorLastNotifiedStateRow, f"{ticket}:{kind}")
        return row.state if row else None

    @staticmethod
    def _set_last_notified_state(ticket: int, kind: str, state: str) -> None:
        with SessionLocal() as session:
            session.merge(MonitorLastNotifiedStateRow(ticket_kind=f"{ticket}:{kind}", state=state))
            session.commit()

    def reset(self) -> None:
        """Needed now that storage is real and shared rather than
        fresh-per-instance in-memory."""
        with SessionLocal() as session:
            session.query(MonitorAuditRow).delete()
            session.query(MonitorOriginalStopLossRow).delete()
            session.query(MonitorLastNotifiedStateRow).delete()
            session.commit()

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

                if position.stop_loss is not None and self._get_original_stop_loss(position.ticket) is None:
                    self._set_original_stop_loss(position.ticket, position.stop_loss)

                result = PositionAssessed(
                    workspace_id=str(account.id), position_ticket=position.ticket, symbol=position.symbol,
                )

                original_stop = self._get_original_stop_loss(position.ticket)
                if original_stop is not None:
                    # Trailing is assessed first because break_even's own
                    # gate requires trailing_state == "trailing-active" as a
                    # precondition -- feeding it the *real* trailing read
                    # means break-even correctly computes off of it rather
                    # than a false precondition.
                    tr = self._assess_trailing(
                        account, risk_clear, position, spec, tick, now, terminal_data,
                        original_stop_loss=original_stop,
                    )
                    result.trailing_stream_id = tr.id
                    result.trailing_state = tr.state.value

                    be = self._assess_break_even(
                        account, risk_clear, position, spec, tick, now,
                        trailing_state=tr.state.value, original_stop_loss=original_stop,
                    )
                    result.break_even_assessment_id = be.id
                    result.break_even_state = be.state.value
                    result.break_even_notified = self._notify_if_newly_actionable(
                        position, be.state.value, kind="break_even")
                    result.trailing_notified = self._notify_if_newly_actionable(
                        position, tr.state.value, kind="trailing")
                else:
                    tr = self._assess_trailing(
                        account, risk_clear, position, spec, tick, now, terminal_data,
                        original_stop_loss=None,
                    )
                    result.trailing_stream_id = tr.id
                    result.trailing_state = tr.state.value
                    result.trailing_notified = self._notify_if_newly_actionable(
                        position, tr.state.value, kind="trailing")
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
        trailing_state: str, original_stop_loss: float,
    ):
        side = "buy" if position.side.lower() in ("buy", "long") else "sell"
        # 1R: the position's ORIGINAL risk distance, pinned the first time
        # this monitor ever saw this ticket (see __init__'s
        # _original_stop_loss note) -- not position.stop_loss directly,
        # which may already have been moved by a real break-even execution
        # or by hand. Measuring 1R against an already-moved stop would
        # shrink the reference distance toward zero and make the trigger
        # fire again on essentially no further favorable movement.
        trigger_points = abs(position.open_price - original_stop_loss) / spec.point
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
            observed_rr=self._observed_rr(position, side, original_stop_loss),
            stop_level_points=0.0,  # mt5_bridge does not report the broker's stop_level; not invented
            freeze_level_points=0.0,
            risk_approved=risk_clear,
            prop_rules_approved=risk_clear,
            risk_brain_blocked=False,
            human_approved=False,  # always -- a human reviews via the module's own execute() step
        )
        return self._break_even.create(payload, actor_id=ACTOR_ID)

    @staticmethod
    def _observed_rr(position: MT5Position, side: str, original_stop_loss: float) -> float:
        risk = abs(position.open_price - original_stop_loss)
        if risk <= 0:
            return 0.0
        favorable = (
            (position.current_price - position.open_price) if side == "buy"
            else (position.open_price - position.current_price)
        )
        return max(0.0, favorable / risk)

    def _notify_if_newly_actionable(self, position: MT5Position, state: str, kind: str = "break_even") -> bool:
        """Sends exactly one Telegram message per transition INTO an
        actionable state -- never a repeat for a state that was already
        the last thing reported for this ticket and this kind. kind
        distinguishes break-even from trailing so the two do not share a
        tracking slot and mask each other's transitions.
        """
        actionable = ACTIONABLE_BREAK_EVEN_STATES if kind == "break_even" else ACTIONABLE_TRAILING_STATES
        previous = self._get_last_notified_state(position.ticket, kind)
        if state not in actionable or state == previous:
            return False
        self._set_last_notified_state(position.ticket, kind, state)
        label = "Break-even" if kind == "break_even" else "Trailing-Stop"
        title = f"{label} bereit" if state == "approval-required" else f"{label} blockiert"
        message = (
            f"Ticket {position.ticket} ({position.symbol}): {state}. "
            f"Aktueller Kurs {position.current_price}, ursprünglicher SL "
            f"{self._get_original_stop_loss(position.ticket)}."
        )
        try:
            self._telegram.send(title, message)
            self._record("notification", f"{kind}: {state}", position.ticket)
        except TelegramDeliveryError as exc:
            log.exception("position_monitor: could not notify about ticket %s (%s)", position.ticket, kind)
            self._record("notification", f"{kind}: {state} -- delivery FAILED: {exc}", position.ticket)
        return True

    # --------------------------------------------------------- trailing stop

    def _assess_trailing(
        self, account: TradingAccountRecord, risk_clear: bool,
        position: MT5Position, spec: MT5SymbolSpec, tick: MT5Tick, now: datetime,
        terminal_data: MT5TerminalData, original_stop_loss: float | None,
    ):
        side = "buy" if position.side.lower() in ("buy", "long") else "sell"
        current_price = tick.bid if side == "sell" else tick.ask

        # Honest, not optimistic, and now real rather than always False:
        # "connected" is the same MT5ConnectionState this terminal already
        # exposes everywhere else (driven by heartbeat/ingest freshness,
        # refreshed on every self._bridge.list() call), and
        # "sequence_contiguous" is the real gap-detection mt5_bridge now
        # tracks per push (see MT5SnapshotIngest.sequence / MT5BridgeService
        # .ingest()). A pusher that has never sent a sequence number at all
        # reports sequence_contiguous=True with no gap ever detected --
        # honest in the "no evidence of a gap" sense, not a claim of
        # verified continuity; see mt5_bridge's own test suite for that
        # exact distinction.
        stream_connected = terminal_data.terminal.state == MT5ConnectionState.connected
        sequence_contiguous = terminal_data.sequence_contiguous

        activation_distance_points = 0
        trailing_distance_points = 0
        proposed_stop_loss: float | None = None
        trailing_enabled = False
        if original_stop_loss is not None:
            # Same 1R convention as break-even's own trigger, and the same
            # reasoning for reusing it here: no per-account/per-strategy
            # trailing policy exists anywhere in this codebase (checked
            # activation_distance_points/trailing_distance_points the same
            # way trigger_points/break_even_offset_points were checked).
            # Trailing activates once price has moved 1R in favor, and
            # trails behind by that same 1R distance -- a common, named,
            # defensible convention ("trail by your own initial risk"),
            # not an invented number. If a real policy layer is ever built
            # per account or strategy, this is the one place to start
            # reading it from instead.
            one_r_points = abs(position.open_price - original_stop_loss) / spec.point
            activation_distance_points = int(round(one_r_points))
            trailing_distance_points = int(round(one_r_points))
            trailing_distance_price = trailing_distance_points * spec.point
            proposed_stop_loss = (
                current_price - trailing_distance_price if side == "buy"
                else current_price + trailing_distance_price
            )
            trailing_enabled = True

        observation = PositionStreamObservation(
            lifecycle_state="lifecycle-complete",
            stream_connected=stream_connected,
            sequence_contiguous=sequence_contiguous,
            snapshot_age_seconds=max(0, int((now - tick.captured_at).total_seconds())),
            position_exists=True,
            symbol=position.symbol,
            side=side,
            current_price=current_price,
            entry_price=position.open_price,
            current_stop_loss=position.stop_loss,
            current_take_profit=position.take_profit,
            trailing_enabled=trailing_enabled,
            activation_distance_points=activation_distance_points,
            trailing_distance_points=trailing_distance_points,
            point_size=spec.point,
            proposed_stop_loss=proposed_stop_loss,
            # mt5_bridge does not report the broker's stop/freeze level
            # (checked: no such field on MT5SymbolSpec); 0 here means
            # "unknown", not "confirmed zero" -- the same honest limitation
            # already documented for break-even's stop_level_points.
            stop_level_points=0,
            freeze_level_points=0,
            human_approval_verified=False,  # always -- a human reviews via execute()
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
        loop -- same task-isolation principle as the trading worker.

        Does not set self._status itself on entry -- start() already did,
        synchronously, before this coroutine got a chance to run at all
        (see start()'s own note on why that matters).
        """
        try:
            while True:
                try:
                    self.tick()
                except Exception as exc:
                    log.exception("position_monitor: tick failed")
                    self._record("tick_failure", str(exc))
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            self._status.enabled = False
            raise

    def start(self, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
        if self._task is not None and not self._task.done():
            return
        # Set synchronously, here, rather than as run_forever's first line:
        # asyncio.create_task() only *schedules* the coroutine -- it does
        # not run any of its body before this function returns. A caller
        # that reads status() immediately after start() (exactly what the
        # /resume endpoint does) would otherwise still see the old,
        # stale enabled=False for at least one event-loop iteration.
        self._status = MonitorStatus(enabled=True, interval_seconds=interval_seconds)
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
