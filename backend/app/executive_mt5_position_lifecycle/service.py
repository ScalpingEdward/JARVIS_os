from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    MT5PositionLifecycleCreate,
    MT5PositionLifecycleRecord,
    MT5PositionLifecycleState,
    PositionActionRequest,
    PositionLifecycleStatusResponse,
)


class ExecutiveMT5PositionLifecycleService:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._records: dict[UUID, MT5PositionLifecycleRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._lifecycle_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: MT5PositionLifecycleCreate) -> tuple[MT5PositionLifecycleState, list[str]]:
        o = payload.observation
        if not payload.risk_brain_clear:
            return MT5PositionLifecycleState.blocked, ["Risk Brain blocked position lifecycle action"]
        if o.execution_state != "execution-complete":
            return MT5PositionLifecycleState.execution_required, ["Completed MT5 execution is required"]
        if not o.position_exists or o.position_ticket <= 0 or not o.symbol or o.current_volume <= 0:
            return MT5PositionLifecycleState.position_missing, ["Governed MT5 position is unavailable"]
        if o.action not in {"modify", "partial-close", "full-close"}:
            return MT5PositionLifecycleState.request_invalid, ["Unsupported position lifecycle action"]
        if o.action in {"partial-close", "full-close"}:
            if o.requested_volume <= 0 or o.requested_volume > o.current_volume or not o.volume_step_valid:
                return MT5PositionLifecycleState.request_invalid, ["Requested close volume is invalid"]
            if o.action == "partial-close" and o.requested_volume >= o.current_volume:
                return MT5PositionLifecycleState.request_invalid, ["Partial close must leave a remaining position"]
            if o.action == "full-close" and abs(o.requested_volume - o.current_volume) > 1e-9:
                return MT5PositionLifecycleState.request_invalid, ["Full close must request the complete volume"]
        if o.action == "modify" and o.requested_stop_loss is None and o.requested_take_profit is None:
            return MT5PositionLifecycleState.request_invalid, ["Modify action requires stop-loss or take-profit"]
        if not all([o.price_precision_valid, o.stop_level_valid, o.freeze_level_clear]):
            return MT5PositionLifecycleState.protection_invalid, ["Broker protection constraints are not satisfied"]
        if not o.risk_policy_clear or not o.prop_rule_clear:
            return MT5PositionLifecycleState.blocked, ["Risk or prop-rule policy rejected the action"]
        if not o.human_approval_verified:
            return MT5PositionLifecycleState.approval_required, ["Human approval is required"]
        if not o.command_dispatched:
            return MT5PositionLifecycleState.command_pending, ["Position command dispatch is pending"]
        if not o.broker_acknowledged or not o.broker_retcode_success:
            return MT5PositionLifecycleState.broker_ack_pending, ["Broker acknowledgement is pending"]
        if o.terminal_error:
            return MT5PositionLifecycleState.lifecycle_failed, ["MT5 terminal reported an execution error"]
        if o.action in {"partial-close", "full-close"} and not o.deal_event_ingested:
            return MT5PositionLifecycleState.deal_event_pending, ["Close deal event is pending"]
        if o.action == "partial-close" and o.remaining_volume <= 0:
            return MT5PositionLifecycleState.partial_close, ["Partial close result is incomplete"]
        if o.action == "modify" and not all([o.resulting_stop_loss_verified, o.resulting_take_profit_verified]):
            return MT5PositionLifecycleState.reconciliation_required, ["Modified protection values are not verified"]
        if not o.position_reconciled or not o.account_snapshot_reconciled:
            return MT5PositionLifecycleState.reconciliation_required, ["Position or account reconciliation is incomplete"]
        return MT5PositionLifecycleState.lifecycle_complete, []

    def assess(self, payload: MT5PositionLifecycleCreate) -> MT5PositionLifecycleRecord:
        source_key = (payload.workspace_id, payload.source_key)
        lifecycle_key = (payload.workspace_id, payload.lifecycle_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate source key")
        if lifecycle_key in self._lifecycle_ids:
            raise ValueError("Duplicate lifecycle id")
        state, reasons = self._evaluate(payload)
        o = payload.observation
        record = MT5PositionLifecycleRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            lifecycle_id=payload.lifecycle_id,
            position_ticket=o.position_ticket,
            symbol=o.symbol,
            action=o.action,
            state=state,
            reasons=reasons,
            position_actions_enabled=state == MT5PositionLifecycleState.lifecycle_complete,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._lifecycle_ids.add(lifecycle_key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="assessed", actor_id=payload.actor_id, lifecycle_id=record.lifecycle_id, state=record.state))
        return record

    def execute(self, request: PositionActionRequest) -> MT5PositionLifecycleRecord:
        record = next((item for item in self._records.values() if item.workspace_id == request.workspace_id and item.lifecycle_id == request.lifecycle_id), None)
        if record is None:
            raise KeyError("Position lifecycle record not found")
        if not request.human_approval_verified:
            raise ValueError("Human approval required")
        if request.terminal_error:
            record.state = MT5PositionLifecycleState.lifecycle_failed
        elif not request.command_dispatched:
            record.state = MT5PositionLifecycleState.command_pending
        elif not request.broker_acknowledged or not request.broker_retcode_success:
            record.state = MT5PositionLifecycleState.broker_ack_pending
        elif record.action in {"partial-close", "full-close"} and not request.deal_event_ingested:
            record.state = MT5PositionLifecycleState.deal_event_pending
        elif record.action == "partial-close" and request.remaining_volume <= 0:
            record.state = MT5PositionLifecycleState.partial_close
        elif record.action == "modify" and not all([request.resulting_stop_loss_verified, request.resulting_take_profit_verified]):
            record.state = MT5PositionLifecycleState.reconciliation_required
        elif not request.position_reconciled or not request.account_snapshot_reconciled:
            record.state = MT5PositionLifecycleState.reconciliation_required
        else:
            record.state = MT5PositionLifecycleState.lifecycle_complete
        record.position_actions_enabled = record.state == MT5PositionLifecycleState.lifecycle_complete
        record.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, action="executed", actor_id=request.actor_id, lifecycle_id=record.lifecycle_id, state=record.state))
        return record

    def get(self, record_id: UUID, workspace_id: str) -> MT5PositionLifecycleRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[MT5PositionLifecycleRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PositionLifecycleStatusResponse:
        records = self.list_records(workspace_id)
        return PositionLifecycleStatusResponse(
            workspace_id=workspace_id,
            records=len(records),
            lifecycle_complete=sum(r.state == MT5PositionLifecycleState.lifecycle_complete for r in records),
            blocked=sum(r.state == MT5PositionLifecycleState.blocked for r in records),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_mt5_position_lifecycle_service = ExecutiveMT5PositionLifecycleService()
