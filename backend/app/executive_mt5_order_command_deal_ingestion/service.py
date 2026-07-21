from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    DispatchRequest,
    MT5ExecutionCreate,
    MT5ExecutionRecord,
    MT5ExecutionState,
    MT5ExecutionStatusResponse,
)


class ExecutiveMT5OrderCommandDealIngestionService:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._records: dict[UUID, MT5ExecutionRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._execution_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: MT5ExecutionCreate) -> tuple[MT5ExecutionState, list[str]]:
        o = payload.observation
        if not payload.risk_brain_clear:
            return MT5ExecutionState.blocked, ["Risk Brain blocked execution"]
        if o.bridge_state != "bridge-ready":
            return MT5ExecutionState.bridge_required, ["MT5 bridge is not ready"]
        if not all([o.command_schema_valid, o.symbol_mapping_verified, o.side_valid, o.requested_volume > 0, o.normalized_volume > 0, o.stop_loss_valid, o.take_profit_valid, o.price_deviation_within_budget, o.idempotency_key_verified]):
            return MT5ExecutionState.command_invalid, ["Order command validation is incomplete"]
        if not o.account_risk_clear or not o.prop_rules_clear:
            return MT5ExecutionState.risk_rejected, ["Account risk or prop rules rejected execution"]
        if o.terminal_error_present:
            return MT5ExecutionState.execution_failed, ["MT5 terminal reported an execution error"]
        if not o.command_dispatched:
            return MT5ExecutionState.dispatch_required, ["Order command dispatch is required"]
        if not o.broker_acknowledged or not o.broker_order_id or not o.broker_retcode_success:
            return MT5ExecutionState.broker_ack_pending, ["Broker acknowledgement is pending"]
        if o.deal_events_received < 1:
            return MT5ExecutionState.deal_ingestion_pending, ["Broker deal event ingestion is pending"]
        if o.actual_fill_volume < o.requested_fill_volume:
            return MT5ExecutionState.partial_fill, ["Order is only partially filled"]
        if not all([o.average_fill_price_verified, o.position_ticket_verified, o.account_snapshot_reconciled, o.position_reconciled, o.pending_orders_reconciled]):
            return MT5ExecutionState.reconciliation_required, ["Execution reconciliation is incomplete"]
        return MT5ExecutionState.execution_complete, []

    def assess(self, payload: MT5ExecutionCreate) -> MT5ExecutionRecord:
        source_key = (payload.workspace_id, payload.source_key)
        execution_key = (payload.workspace_id, payload.execution_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate source key")
        if execution_key in self._execution_ids:
            raise ValueError("Duplicate execution id")
        state, reasons = self._evaluate(payload)
        record = MT5ExecutionRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            execution_id=payload.execution_id,
            bridge_id=payload.bridge_id,
            account_reference=payload.account_reference,
            symbol=payload.symbol,
            side=payload.side,
            state=state,
            reasons=reasons,
            order_submission_enabled=state == MT5ExecutionState.execution_complete,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._execution_ids.add(execution_key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="assessed", actor_id=payload.actor_id, execution_id=record.execution_id, state=record.state))
        return record

    def dispatch(self, request: DispatchRequest) -> MT5ExecutionRecord:
        record = next((item for item in self._records.values() if item.workspace_id == request.workspace_id and item.execution_id == request.execution_id), None)
        if record is None:
            raise KeyError("Execution not found")
        if request.terminal_error_present:
            record.state = MT5ExecutionState.execution_failed
        elif not request.command_dispatched:
            record.state = MT5ExecutionState.dispatch_required
        elif not request.broker_acknowledged or not request.broker_order_id or not request.broker_retcode_success:
            record.state = MT5ExecutionState.broker_ack_pending
        elif request.deal_events_received < 1:
            record.state = MT5ExecutionState.deal_ingestion_pending
        elif request.actual_fill_volume < request.requested_fill_volume:
            record.state = MT5ExecutionState.partial_fill
        elif not all([request.average_fill_price_verified, request.position_ticket_verified, request.account_snapshot_reconciled, request.position_reconciled, request.pending_orders_reconciled]):
            record.state = MT5ExecutionState.reconciliation_required
        else:
            record.state = MT5ExecutionState.execution_complete
        record.order_submission_enabled = record.state == MT5ExecutionState.execution_complete
        record.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="dispatched", actor_id=request.actor_id, execution_id=record.execution_id, state=record.state))
        return record

    def get(self, record_id: UUID, workspace_id: str) -> MT5ExecutionRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[MT5ExecutionRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> MT5ExecutionStatusResponse:
        records = self.list_records(workspace_id)
        return MT5ExecutionStatusResponse(
            workspace_id=workspace_id,
            records=len(records),
            execution_complete=sum(r.state == MT5ExecutionState.execution_complete for r in records),
            blocked=sum(r.state == MT5ExecutionState.blocked for r in records),
            failed=sum(r.state == MT5ExecutionState.execution_failed for r in records),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_mt5_order_command_deal_ingestion_service = ExecutiveMT5OrderCommandDealIngestionService()
