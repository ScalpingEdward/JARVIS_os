import threading
from datetime import datetime, timezone
from math import isclose
from uuid import UUID, uuid4

from sqlalchemy import update

from app.db import SessionLocal
from app.db_models import LiveOrderAuditRow, LiveOrderExecutorSettingsRow, LiveOrderRecordRow

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
    """The module closest to real money in this codebase.

    Persisted via the same SessionLocal infrastructure the rest of the
    trading chain now uses -- previously records, audit, and (most
    critically) the pause/kill-switch flag itself all lived only in
    process memory, silently reset on every restart. A paused kill
    switch resetting itself to "running" on an unrelated crash or deploy
    would have been the worst possible failure mode for exactly the
    control this session built to prevent duplicate real orders and let
    Brano stop execution instantly -- fail closed applies to the kill
    switch itself, not only to what it guards.
    """

    def __init__(self, executor: NativeOrderExecutor | None = None) -> None:
        self._executor = executor
        #: Still a real, useful fast-path lock for the common case (one
        #: process, multiple threads/requests) -- but the actual
        #: correctness guarantee for the claim in pending_execution() is
        #: now the database-level atomic UPDATE ... WHERE state = ...
        #: below, which stays correct even if more than one backend
        #: process is ever running against the same database.
        self._dispatch_lock = threading.Lock()

    def pause(self) -> None:
        with SessionLocal() as session:
            session.merge(LiveOrderExecutorSettingsRow(key="paused", value="true"))
            session.commit()

    def resume(self) -> None:
        with SessionLocal() as session:
            session.merge(LiveOrderExecutorSettingsRow(key="paused", value="false"))
            session.commit()

    def is_paused(self) -> bool:
        with SessionLocal() as session:
            row = session.get(LiveOrderExecutorSettingsRow, "paused")
        return row is not None and row.value == "true"

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
        with SessionLocal() as session:
            existing = (
                session.query(LiveOrderRecordRow)
                .filter(
                    LiveOrderRecordRow.workspace_id == payload.workspace_id,
                    LiveOrderRecordRow.source_key == payload.source_key,
                )
                .first()
            )
            if existing is not None:
                raise ValueError("duplicate source_key for workspace")
            state, detail = self._state(payload)
            record = LiveOrderRecord(
                workspace_id=payload.workspace_id, source_key=payload.source_key,
                state=state, detail=detail, request=payload,
            )
            session.add(LiveOrderRecordRow(
                id=str(record.id), workspace_id=record.workspace_id, source_key=record.source_key,
                state=state.value, data=record.model_dump_json(),
            ))
            session.add(self._audit_row(record, payload.actor_id, "created"))
            session.commit()
        return record

    def execute(self, record_id: UUID, workspace_id: str, request: LiveOrderExecuteRequest) -> LiveOrderRecord:
        with SessionLocal() as session:
            row = session.get(LiveOrderRecordRow, str(record_id))
            if row is None or row.workspace_id != workspace_id:
                raise KeyError("live order record not found")
            record = LiveOrderRecord.model_validate_json(row.data)

            if request.action == "cancel":
                if record.state in {LiveOrderState.EXECUTED, LiveOrderState.PARTIAL_FILL}:
                    raise ValueError("executed orders cannot be cancelled by preflight service")
                record.state, record.detail = LiveOrderState.CANCELLED, "Order execution cancelled"
                return self._save(session, row, record, request.actor_id, "cancelled")

            if request.human_approved is not None:
                record.request.human_approved = request.human_approved
            state, detail = self._state(record.request)
            record.state, record.detail = state, detail
            if state != LiveOrderState.PREFLIGHT_READY:
                return self._save(session, row, record, request.actor_id, "re-evaluated")

            if self.is_paused():
                # Defense in depth: pending_execution() already hides this
                # record from the remote agent while paused, but a direct
                # execute() call (the native-adapter path, unreachable in
                # this deployment's Linux container but not in every
                # deployment) must be refused too, not just hidden from a
                # different caller.
                record.detail = "Execution is paused -- not submitted."
                return self._save(session, row, record, request.actor_id, "paused")

            executor = self._executor
            if executor is None:
                try:
                    executor = MetaTrader5OrderExecutor()
                except RuntimeError:
                    # No local native adapter -- e.g. AURON running in a
                    # Linux Docker container, which can't load the
                    # Windows-only MetaTrader5 package. Leave the record at
                    # PREFLIGHT_READY rather than failing: a remote
                    # execution agent (real MetaTrader5, running on the
                    # machine with the terminal) picks up orders in this
                    # state via GET .../pending-execution and reports the
                    # real result via POST .../report-execution. This is
                    # not a fallback that fakes success -- nothing is
                    # submitted until the remote agent actually calls
                    # order_send().
                    record.detail = "Preflight passed; awaiting a remote execution agent to submit this order."
                    return self._save(session, row, record, request.actor_id, "awaiting-remote-execution")

            info = executor.symbol_info(record.request.symbol)
            tick = executor.symbol_info_tick(record.request.symbol)
            if info is None or tick is None:
                record.state, record.detail = LiveOrderState.SYMBOL_UNAVAILABLE, "Symbol metadata or tick is unavailable"
                return self._save(session, row, record, request.actor_id, "symbol-unavailable")

            native_request = executor.build_request(record.request) if hasattr(executor, "build_request") else self._generic_request(record.request)
            check = executor.order_check(native_request)
            if check is None or getattr(check, "retcode", 1) not in {0, 10009}:
                record.state = LiveOrderState.BROKER_REJECTED
                record.broker_retcode = getattr(check, "retcode", None)
                record.broker_comment = getattr(check, "comment", "order_check rejected")
                record.detail = "Broker preflight rejected order"
                return self._save(session, row, record, request.actor_id, "broker-check-rejected")

            record.state, record.detail = LiveOrderState.SUBMISSION_PENDING, "Submitting order to MetaTrader5"
            result = executor.order_send(native_request)
            if result is None:
                record.state, record.detail = LiveOrderState.FAILED, "MetaTrader5 returned no order result"
                return self._save(session, row, record, request.actor_id, "submission-failed")

            record.broker_retcode = getattr(result, "retcode", None)
            record.broker_order_id = getattr(result, "order", None)
            record.broker_deal_id = getattr(result, "deal", None)
            record.broker_comment = getattr(result, "comment", None)
            record.filled_volume = float(getattr(result, "volume", 0) or 0)
            record.average_price = getattr(result, "price", None)
            self._classify_broker_result(record)
            return self._save(session, row, record, request.actor_id, "submitted")

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
        SUBMISSION_PENDING via a database-level UPDATE ... WHERE state =
        'preflight-ready' before this method returns. That WHERE clause is
        the actual claim, not the Python lock around it -- an UPDATE whose
        WHERE clause no longer matches (because a concurrent caller, even
        in a different process, already won it) affects zero rows, and
        this method simply does not include that record in what it
        returns. The lock is still held too, as a fast, cheap short-circuit
        for the overwhelmingly common case of one process -- correct
        either way, since the database is the actual source of truth.

        Nothing in this list has been decided by the agent -- every
        decision already happened before a record could reach here.

        Returns nothing at all while paused, regardless of what is
        actually preflight-ready -- see pause()'s own docstring.

        A record that never gets a report_execution() call after being
        claimed here (the agent crashed mid-flight) stays SUBMISSION_PENDING
        forever, on purpose -- it is deliberately NOT re-offered by a later
        call. Nobody can tell from here alone whether the broker actually
        received that order or not; automatically retrying is exactly the
        duplicate-execution risk this fix closes. A human has to check the
        real account and reconcile by hand.
        """
        if self.is_paused():
            return []
        with self._dispatch_lock:
            with SessionLocal() as session:
                candidates = (
                    session.query(LiveOrderRecordRow)
                    .filter(
                        LiveOrderRecordRow.workspace_id == workspace_id,
                        LiveOrderRecordRow.state == LiveOrderState.PREFLIGHT_READY.value,
                    )
                    .all()
                )
                claimed: list[LiveOrderRecord] = []
                for row in candidates:
                    result = session.execute(
                        update(LiveOrderRecordRow)
                        .where(
                            LiveOrderRecordRow.id == row.id,
                            LiveOrderRecordRow.state == LiveOrderState.PREFLIGHT_READY.value,
                        )
                        .values(state=LiveOrderState.SUBMISSION_PENDING.value)
                    )
                    if result.rowcount != 1:
                        continue  # lost the race to a concurrent claim -- not ours
                    record = LiveOrderRecord.model_validate_json(row.data)
                    record.state, record.detail = LiveOrderState.SUBMISSION_PENDING, "Claimed by a remote execution agent"
                    record.updated_at = datetime.now(timezone.utc)
                    row.data = record.model_dump_json()
                    session.add(self._audit_row(record, "system", "claimed-for-dispatch"))
                    claimed.append(record)
                session.commit()
                return claimed

    def report_execution(self, record_id: UUID, workspace_id: str, report: RemoteExecutionReport) -> LiveOrderRecord:
        with SessionLocal() as session:
            row = session.get(LiveOrderRecordRow, str(record_id))
            if row is None or row.workspace_id != workspace_id:
                raise KeyError("live order record not found")
            record = LiveOrderRecord.model_validate_json(row.data)
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
            return self._save(session, row, record, report.actor_id, "remote-execution-reported")

    @staticmethod
    def _generic_request(payload: LiveOrderCreate) -> dict:
        return {"symbol": payload.symbol, "side": payload.side, "order_type": payload.order_type, "volume": payload.volume, "price": payload.requested_price, "sl": payload.stop_loss, "tp": payload.take_profit, "deviation": payload.max_deviation_points, "magic": payload.magic, "comment": payload.comment}

    @staticmethod
    def _audit_row(record: LiveOrderRecord, actor_id: str, action: str) -> LiveOrderAuditRow:
        event = LiveOrderAudit(
            record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id,
            action=action, state=record.state, detail=record.detail,
        )
        return LiveOrderAuditRow(
            workspace_id=event.workspace_id, created_at=event.created_at, data=event.model_dump_json(),
        )

    def _save(self, session, row: LiveOrderRecordRow, record: LiveOrderRecord, actor_id: str, action: str) -> LiveOrderRecord:
        record.updated_at = datetime.now(timezone.utc)
        row.state = record.state.value
        row.data = record.model_dump_json()
        session.add(self._audit_row(record, actor_id, action))
        session.commit()
        return record

    def get(self, record_id: UUID, workspace_id: str) -> LiveOrderRecord | None:
        with SessionLocal() as session:
            row = session.get(LiveOrderRecordRow, str(record_id))
        if row is None or row.workspace_id != workspace_id:
            return None
        return LiveOrderRecord.model_validate_json(row.data)

    def list_records(self, workspace_id: str) -> list[LiveOrderRecord]:
        with SessionLocal() as session:
            rows = session.query(LiveOrderRecordRow).filter(LiveOrderRecordRow.workspace_id == workspace_id).all()
        return [LiveOrderRecord.model_validate_json(r.data) for r in rows]

    def audit_records(self, workspace_id: str) -> list[LiveOrderAudit]:
        with SessionLocal() as session:
            rows = (
                session.query(LiveOrderAuditRow)
                .filter(LiveOrderAuditRow.workspace_id == workspace_id)
                .order_by(LiveOrderAuditRow.created_at)
                .all()
            )
        return [LiveOrderAudit.model_validate_json(r.data) for r in rows]

    def status(self, workspace_id: str) -> LiveOrderStatus:
        items = self.list_records(workspace_id)
        return LiveOrderStatus(
            workspace_id=workspace_id,
            total_records=len(items),
            executed_records=sum(item.state in {LiveOrderState.EXECUTED, LiveOrderState.RECONCILIATION_REQUIRED, LiveOrderState.PARTIAL_FILL} for item in items),
            blocked_records=sum(item.state in {LiveOrderState.BLOCKED, LiveOrderState.RISK_REJECTED, LiveOrderState.BROKER_REJECTED} for item in items),
            paused=self.is_paused(),
        )

    def reset(self) -> None:
        """Needed now that storage is real and shared rather than
        fresh-per-instance in-memory. Also resets the paused flag back to
        its default (unpaused) -- fine for tests/local resets, but never
        called in production, where the whole point is that pausing
        survives exactly this kind of reset."""
        with SessionLocal() as session:
            session.query(LiveOrderRecordRow).delete()
            session.query(LiveOrderAuditRow).delete()
            session.query(LiveOrderExecutorSettingsRow).delete()
            session.commit()


live_order_executor_service = LiveOrderExecutorService()
