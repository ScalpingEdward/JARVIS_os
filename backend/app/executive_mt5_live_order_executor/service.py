import threading
from datetime import datetime, timezone
from math import isclose
from uuid import UUID

from .models import (
    LiveOrderAudit,
    LiveOrderCreate,
    LiveOrderExecuteRequest,
    LiveOrderRecord,
    LiveOrderState,
    LiveOrderStatus,
    RemoteExecutionReport,
)
from .native_executor import MetaTrader5OrderExecutor, NativeOrderExecutor


class LiveOrderExecutorService:
    def __init__(self, executor: NativeOrderExecutor | None = None) -> None:
        self._executor = executor
        self._records: dict[UUID, LiveOrderRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[LiveOrderAudit] = []
        #: Protects the read-check-then-transition step in
        #: pending_execution() -- an external test pass reproduced real,
        #: repeated order execution: pending_execution() was a pure read,
        #: so a record stayed PREFLIGHT_READY from the moment it was first
        #: handed to a remote agent all the way until report_execution()
        #: eventually completed. A second poll in that window (a slow
        #: broker round-trip taking longer than the polling interval, a
        #: second agent instance, or the agent crashing and restarting
        #: with its own in-memory dedup state lost) would see the exact
        #: same still-PREFLIGHT_READY record and hand it out again --
        #: which is how a real, live account gets a genuine duplicate
        #: order. See pending_execution()'s own docstring for the fix.
        self._dispatch_lock = threading.Lock()
        #: The single most consequential kill switch in this codebase.
        #: bridge/mt5_execution_agent.py -- the real, Windows-side script
        #: that actually calls order_send() against a live broker --
        #: polls pending_execution() for what to submit next. Pausing here
        #: means that call returns an empty list regardless of what is
        #: actually ready: the agent sees nothing, submits nothing, full
        #: stop, without touching the agent script or restarting anything.
        #: execute() also checks this directly (see below), covering the
        #: rarer case of AURON running somewhere with real native MT5
        #: access instead of the remote-agent path this deployment uses.
        self._paused: bool = False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def is_paused(self) -> bool:
        return self._paused

    def _audit_event(self, record: LiveOrderRecord, actor_id: str, action: str) -> None:
        self._audit.append(LiveOrderAudit(record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id, action=action, state=record.state, detail=record.detail))

    def _state(self, payload: LiveOrderCreate) -> tuple[LiveOrderState, str]:
        if payload.risk_brain_blocked:
            return LiveOrderState.BLOCKED, "Risk Brain blocked order execution"
        if not payload.native_adapter_ready:
            return LiveOrderState.ADAPTER_REQUIRED, "Native MT5 adapter must be ready"
        if payload.account_login not in payload.approved_account_logins:
            return LiveOrderState.BLOCKED, "Connected account is not approved"
        if payload.quote_age_seconds > payload.max_quote_age_seconds:
            return LiveOrderState.QUOTE_STALE, "Quote snapshot is stale"
        if payload.quote_ask < payload.quote_bid:
            return LiveOrderState.ORDER_INVALID, "Quote ask cannot be below bid"
        if not (payload.min_volume <= payload.volume <= payload.max_volume):
            return LiveOrderState.VOLUME_REJECTED, "Order volume is outside symbol limits"
        steps = round((payload.volume - payload.min_volume) / payload.volume_step)
        normalized = payload.min_volume + steps * payload.volume_step
        if not isclose(normalized, payload.volume, rel_tol=0, abs_tol=1e-8):
            return LiveOrderState.VOLUME_REJECTED, "Order volume does not match volume step"
        reference = payload.quote_ask if payload.side == "buy" else payload.quote_bid
        if payload.requested_price is not None:
            deviation = abs(payload.requested_price - reference) / payload.symbol_point
            if payload.order_type == "market" and deviation > payload.max_deviation_points:
                return LiveOrderState.PRICE_DEVIATION_REJECTED, "Requested market price exceeds deviation ceiling"
        min_distance = payload.min_stop_distance_points * payload.symbol_point
        if payload.stop_loss is not None:
            valid_sl = payload.stop_loss < reference - min_distance if payload.side == "buy" else payload.stop_loss > reference + min_distance
            if not valid_sl:
                return LiveOrderState.STOPS_REJECTED, "Stop loss violates direction or minimum distance"
        if payload.take_profit is not None:
            valid_tp = payload.take_profit > reference + min_distance if payload.side == "buy" else payload.take_profit < reference - min_distance
            if not valid_tp:
                return LiveOrderState.STOPS_REJECTED, "Take profit violates direction or minimum distance"
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return LiveOrderState.RISK_REJECTED, "Account-risk and prop-rule approval are mandatory"
        if payload.max_risk_amount and payload.expected_risk_amount > payload.max_risk_amount:
            return LiveOrderState.RISK_REJECTED, "Expected order risk exceeds approved maximum"
        if not payload.human_approved:
            return LiveOrderState.APPROVAL_REQUIRED, "Human approval is required"
        return LiveOrderState.PREFLIGHT_READY, "Order passed deterministic preflight checks"

    def create(self, payload: LiveOrderCreate) -> LiveOrderRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        state, detail = self._state(payload)
        record = LiveOrderRecord(workspace_id=payload.workspace_id, source_key=payload.source_key, state=state, detail=detail, request=payload)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit_event(record, payload.actor_id, "created")
        return record

    def execute(self, record_id: UUID, workspace_id: str, request: LiveOrderExecuteRequest) -> LiveOrderRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("live order record not found")
        if request.action == "cancel":
            if record.state in {LiveOrderState.EXECUTED, LiveOrderState.PARTIAL_FILL}:
                raise ValueError("executed orders cannot be cancelled by preflight service")
            record.state, record.detail = LiveOrderState.CANCELLED, "Order execution cancelled"
            return self._save(record, request.actor_id, "cancelled")
        if request.human_approved is not None:
            record.request.human_approved = request.human_approved
        state, detail = self._state(record.request)
        record.state, record.detail = state, detail
        if state != LiveOrderState.PREFLIGHT_READY:
            return self._save(record, request.actor_id, "re-evaluated")
        if self._paused:
            # Defense in depth: pending_execution() already hides this
            # record from the remote agent while paused, but a direct
            # execute() call (the native-adapter path, unreachable in this
            # deployment's Linux container but not in every deployment)
            # must be refused too, not just hidden from a different caller.
            record.detail = "Execution is paused -- not submitted."
            return self._save(record, request.actor_id, "paused")
        executor = self._executor
        if executor is None:
            try:
                executor = MetaTrader5OrderExecutor()
            except RuntimeError:
                # No local native adapter -- e.g. AURON running in a Linux
                # Docker container, which can't load the Windows-only
                # MetaTrader5 package. Leave the record at PREFLIGHT_READY
                # rather than failing: a remote execution agent (real
                # MetaTrader5, running on the machine with the terminal)
                # picks up orders in this state via GET .../pending-execution
                # and reports the real result via POST .../report-execution.
                # This is not a fallback that fakes success -- nothing is
                # submitted until the remote agent actually calls order_send().
                record.detail = "Preflight passed; awaiting a remote execution agent to submit this order."
                return self._save(record, request.actor_id, "awaiting-remote-execution")
        info = executor.symbol_info(record.request.symbol)
        tick = executor.symbol_info_tick(record.request.symbol)
        if info is None or tick is None:
            record.state, record.detail = LiveOrderState.SYMBOL_UNAVAILABLE, "Symbol metadata or tick is unavailable"
            return self._save(record, request.actor_id, "symbol-unavailable")
        native_request = executor.build_request(record.request) if hasattr(executor, "build_request") else self._generic_request(record.request)
        check = executor.order_check(native_request)
        if check is None or getattr(check, "retcode", 1) not in {0, 10009}:
            record.state = LiveOrderState.BROKER_REJECTED
            record.broker_retcode = getattr(check, "retcode", None)
            record.broker_comment = getattr(check, "comment", "order_check rejected")
            record.detail = "Broker preflight rejected order"
            return self._save(record, request.actor_id, "broker-check-rejected")
        record.state, record.detail = LiveOrderState.SUBMISSION_PENDING, "Submitting order to MetaTrader5"
        result = executor.order_send(native_request)
        if result is None:
            record.state, record.detail = LiveOrderState.FAILED, "MetaTrader5 returned no order result"
            return self._save(record, request.actor_id, "submission-failed")
        record.broker_retcode = getattr(result, "retcode", None)
        record.broker_order_id = getattr(result, "order", None)
        record.broker_deal_id = getattr(result, "deal", None)
        record.broker_comment = getattr(result, "comment", None)
        record.filled_volume = float(getattr(result, "volume", 0) or 0)
        record.average_price = getattr(result, "price", None)
        self._classify_broker_result(record)
        return self._save(record, request.actor_id, "submitted")

    @staticmethod
    def _classify_broker_result(record: LiveOrderRecord) -> None:
        """The one place that turns a raw broker response into a
        LiveOrderState -- used identically whether the response came from
        AURON's own native executor (rare: only when AURON runs somewhere
        with real MT5 access) or from a remote execution agent's report."""
        if record.broker_retcode not in {10008, 10009, 10010}:
            record.state, record.detail = LiveOrderState.BROKER_REJECTED, "Broker rejected order submission"
        elif 0 < record.filled_volume < record.request.volume:
            record.state, record.detail = LiveOrderState.PARTIAL_FILL, "Order received a partial fill"
        elif record.broker_order_id or record.broker_deal_id:
            record.state, record.detail = LiveOrderState.RECONCILIATION_REQUIRED, "Broker accepted order; position/order reconciliation required"
        else:
            record.state, record.detail = LiveOrderState.EXECUTED, "Order execution completed"

    def pending_execution(self, workspace_id: str) -> list[LiveOrderRecord]:
        """Orders that already passed every deterministic + human-approval
        check and are handed to a remote execution agent to actually
        submit -- and, as of this call, ATOMICALLY claimed for that: each
        record returned here is transitioned PREFLIGHT_READY ->
        SUBMISSION_PENDING before this method returns, under a lock, so a
        second call (a slow broker round-trip outlasting the polling
        interval, a second agent instance, or an agent that crashed and
        restarted mid-flight) can never see the same record again. Nothing
        in this list has been decided by the agent -- every decision
        already happened before a record could reach here.

        Returns nothing at all while paused, regardless of what is
        actually preflight-ready -- see the _paused note on __init__.

        A record that never gets a report_execution() call after being
        claimed here (the agent crashed mid-flight) stays SUBMISSION_PENDING
        forever, on purpose -- it is deliberately NOT re-offered by a later
        call. Nobody can tell from here alone whether the broker actually
        received that order or not; automatically retrying is exactly the
        duplicate-execution risk this fix closes. A human has to check the
        real account and reconcile by hand.
        """
        if self._paused:
            return []
        with self._dispatch_lock:
            claimed = [r for r in self.list_records(workspace_id) if r.state == LiveOrderState.PREFLIGHT_READY]
            for record in claimed:
                record.state, record.detail = LiveOrderState.SUBMISSION_PENDING, "Claimed by a remote execution agent"
                self._save(record, "system", "claimed-for-dispatch")
            return claimed

    def report_execution(self, record_id: UUID, workspace_id: str, report: RemoteExecutionReport) -> LiveOrderRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("live order record not found")
        if record.state != LiveOrderState.SUBMISSION_PENDING:
            raise ValueError(
                f"record is {record.state.value}, not awaiting a report -- it must first be claimed via "
                f"pending_execution() (which is also the only path that can put it into submission-pending)"
            )
        record.broker_retcode = report.broker_retcode
        record.broker_order_id = report.broker_order_id
        record.broker_deal_id = report.broker_deal_id
        record.broker_comment = report.broker_comment
        record.filled_volume = report.filled_volume
        record.average_price = report.average_price
        self._classify_broker_result(record)
        return self._save(record, report.actor_id, "remote-execution-reported")

    @staticmethod
    def _generic_request(payload: LiveOrderCreate) -> dict:
        return {"symbol": payload.symbol, "side": payload.side, "order_type": payload.order_type, "volume": payload.volume, "price": payload.requested_price, "sl": payload.stop_loss, "tp": payload.take_profit, "deviation": payload.max_deviation_points, "magic": payload.magic, "comment": payload.comment}

    def _save(self, record: LiveOrderRecord, actor_id: str, action: str) -> LiveOrderRecord:
        record.updated_at = datetime.now(timezone.utc)
        self._records[record.id] = record
        self._audit_event(record, actor_id, action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> LiveOrderRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[LiveOrderRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit_records(self, workspace_id: str) -> list[LiveOrderAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> LiveOrderStatus:
        items = self.list_records(workspace_id)
        return LiveOrderStatus(
            workspace_id=workspace_id,
            total_records=len(items),
            executed_records=sum(item.state in {LiveOrderState.EXECUTED, LiveOrderState.RECONCILIATION_REQUIRED, LiveOrderState.PARTIAL_FILL} for item in items),
            blocked_records=sum(item.state in {LiveOrderState.BLOCKED, LiveOrderState.RISK_REJECTED, LiveOrderState.BROKER_REJECTED} for item in items),
            paused=self._paused,
        )


live_order_executor_service = LiveOrderExecutorService()
