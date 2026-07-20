from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    PositionActionRequest,
    PositionLifecycleAssessment,
    PositionLifecycleAssessmentCreate,
    PositionLifecycleState,
    PositionLifecycleStatusResponse,
)


class ExecutivePositionLifecycleService:
    def __init__(self) -> None:
        self._records: dict[UUID, PositionLifecycleAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._position_ids: set[tuple[str, UUID]] = set()
        self._broker_position_ids: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._position_ids.clear()
        self._broker_position_ids.clear()
        self._audit.clear()

    def assess(self, payload: PositionLifecycleAssessmentCreate) -> PositionLifecycleAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        position_key = (payload.workspace_id, payload.position_id)
        broker_key = (payload.workspace_id, payload.broker_position_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate position lifecycle source key")
        if position_key in self._position_ids:
            raise ValueError("Duplicate position ID")
        if broker_key in self._broker_position_ids:
            raise ValueError("Duplicate broker position ID")

        state, reasons, action = self._evaluate(payload)
        o = payload.observation
        record = PositionLifecycleAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            position_id=payload.position_id,
            execution_id=payload.execution_id,
            broker_position_id=payload.broker_position_id,
            account_reference=payload.account_reference,
            canonical_symbol=payload.canonical_symbol,
            side=payload.side,
            opened_quantity=payload.opened_quantity,
            state=state,
            protected=o.stop_loss_present and o.protection_acknowledged,
            reconciled=state in {PositionLifecycleState.position_open, PositionLifecycleState.position_closed},
            closed=state == PositionLifecycleState.position_closed,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._position_ids.add(position_key)
        self._broker_position_ids.add(broker_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, position_id=record.position_id, actor_id=payload.actor_id, action="position-lifecycle-assessed"))
        return record

    def _evaluate(self, payload: PositionLifecycleAssessmentCreate) -> tuple[PositionLifecycleState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return PositionLifecycleState.blocked, ["Risk Brain blocked position lifecycle action"], "keep-position-blocked"
        if p.require_completed_execution and o.execution_state != "execution-completed":
            return PositionLifecycleState.execution_required, ["Completed and reconciled execution is required"], "resolve-order-execution"
        if p.require_broker_position and not o.broker_position_present:
            return PositionLifecycleState.reconciliation_required, ["Broker position is not present"], "query-broker-position"
        identity_ok = o.broker_position_id_present and o.broker_symbol_matches and o.broker_side_matches and o.broker_quantity_matches
        if p.require_position_identity and not identity_ok:
            return PositionLifecycleState.broker_mismatch, ["Broker position identity or quantity does not match"], "quarantine-and-reconcile"
        if p.require_open_reconciliation and not (o.open_price_reconciled and o.commission_reconciled):
            return PositionLifecycleState.reconciliation_required, ["Opening price or commission evidence is incomplete"], "reconcile-opening-state"
        protection_ok = (not p.require_stop_loss or o.stop_loss_present) and (not p.require_take_profit or o.take_profit_present) and (not p.require_protection_acknowledgement or o.protection_acknowledged)
        if not protection_ok:
            return PositionLifecycleState.protection_required, ["Required stop-loss, take-profit or protection acknowledgement is missing"], "apply-approved-protection"
        if o.modification_requested:
            if p.require_human_approval_for_modification and not o.modification_human_approved:
                return PositionLifecycleState.modification_approval_required, ["Explicit human approval is required for position modification"], "request-modification-approval"
            if not o.modification_acknowledged:
                return PositionLifecycleState.reconciliation_required, ["Broker has not acknowledged the position modification"], "query-modification-state"
        if o.close_requested:
            if p.require_human_approval_for_close and not o.close_human_approved:
                return PositionLifecycleState.modification_approval_required, ["Explicit human approval is required for position close"], "request-close-approval"
            if not o.close_acknowledged or o.remaining_quantity > 0:
                return PositionLifecycleState.close_pending, ["Position close is pending or partially completed"], "monitor-or-reconcile-close"
            final_ok = o.realized_pnl_reported and o.swap_reported and o.final_broker_reconciled
            if p.require_final_reconciliation and not final_ok:
                return PositionLifecycleState.reconciliation_required, ["Final PnL, swap or broker reconciliation is incomplete"], "reconcile-final-position-state"
            return PositionLifecycleState.position_closed, ["Position close and final reconciliation completed"], "publish-position-closed-event"
        return PositionLifecycleState.position_open, ["Position is open, protected and reconciled"], "monitor-position"

    def list_positions(self, workspace_id: str) -> list[PositionLifecycleAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> PositionLifecycleAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def close(self, request: PositionActionRequest) -> PositionLifecycleAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.position_id == request.position_id), None)
        if record is None:
            raise KeyError("Position lifecycle record not found")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if not request.broker_acknowledged or request.remaining_quantity > 0:
            record.state = PositionLifecycleState.close_pending
            record.closed = False
            record.reconciled = False
            record.recommended_action = "monitor-or-reconcile-close"
            record.reasons = ["Broker close acknowledgement or zero remaining quantity is required"]
        elif not request.final_broker_reconciled:
            record.state = PositionLifecycleState.reconciliation_required
            record.closed = False
            record.reconciled = False
            record.recommended_action = "reconcile-final-position-state"
            record.reasons = ["Final broker reconciliation is required"]
        else:
            record.state = PositionLifecycleState.position_closed
            record.closed = True
            record.reconciled = True
            record.recommended_action = "publish-position-closed-event"
            record.reasons = ["Position close and final reconciliation completed"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, assessment_id=record.id, position_id=record.position_id, actor_id=request.actor_id, action="position-close-assessed"))
        return record

    def status(self, workspace_id: str) -> PositionLifecycleStatusResponse:
        records = self.list_positions(workspace_id)
        open_positions = sum(r.state == PositionLifecycleState.position_open for r in records)
        closed_positions = sum(r.state == PositionLifecycleState.position_closed for r in records)
        return PositionLifecycleStatusResponse(workspace_id=workspace_id, positions=len(records), open_positions=open_positions, closed_positions=closed_positions, attention_required=len(records) - open_positions - closed_positions, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_position_lifecycle_service = ExecutivePositionLifecycleService()
