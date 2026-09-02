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
        check and are waiting for a remote execution agent to actually
        submit them. Nothing in this list has been decided by the agent --
        every decision already happened before a record can reach here."""
        return [r for r in self.list_records(workspace_id) if r.state == LiveOrderState.PREFLIGHT_READY]

    def report_execution(self, record_id: UUID, workspace_id: str, report: RemoteExecutionReport) -> LiveOrderRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("live order record not found")
        if record.state != LiveOrderState.PREFLIGHT_READY:
            raise ValueError(f"record is {record.state.value}, not awaiting execution")
        record.state, record.detail = LiveOrderState.SUBMISSION_PENDING, "Remote agent is submitting the order"
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
        return LiveOrderStatus(workspace_id=workspace_id, total_records=len(items), executed_records=sum(item.state in {LiveOrderState.EXECUTED, LiveOrderState.RECONCILIATION_REQUIRED, LiveOrderState.PARTIAL_FILL} for item in items), blocked_records=sum(item.state in {LiveOrderState.BLOCKED, LiveOrderState.RISK_REJECTED, LiveOrderState.BROKER_REJECTED} for item in items))


live_order_executor_service = LiveOrderExecutorService()
