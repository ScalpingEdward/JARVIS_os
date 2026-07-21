from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    ContainmentActionRequest,
    ContainmentReleaseRequest,
    EmergencyContainmentAssessment,
    EmergencyContainmentAssessmentCreate,
    EmergencyContainmentState,
    EmergencyContainmentStatusResponse,
)


BREACH_STATES = {
    "daily-loss-breached",
    "drawdown-breached",
    "margin-stressed",
    "exposure-concentrated",
    "correlation-breached",
    "risk-reduction-required",
}


class ExecutiveEmergencyRiskContainmentService:
    def __init__(self) -> None:
        self._records: dict[UUID, EmergencyContainmentAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._containment_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._containment_ids.clear()
        self._audit.clear()

    def assess(self, payload: EmergencyContainmentAssessmentCreate) -> EmergencyContainmentAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        containment_key = (payload.workspace_id, payload.containment_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate emergency containment source key")
        if containment_key in self._containment_ids:
            raise ValueError("Duplicate containment ID")

        state, reasons, action = self._evaluate(payload)
        o = payload.observation
        record = EmergencyContainmentAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            containment_id=payload.containment_id,
            account_reference=payload.account_reference,
            broker_reference=payload.broker_reference,
            trigger=payload.trigger,
            state=state,
            kill_switch_active=o.kill_switch_active,
            new_orders_blocked=o.new_order_block_active,
            pending_orders_cancelled=(not o.pending_orders_present) or o.pending_orders_cancelled,
            positions_liquidated=o.remaining_open_positions == 0 and o.liquidation_acknowledged,
            reconciled=state in {EmergencyContainmentState.contained, EmergencyContainmentState.released},
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._containment_ids.add(containment_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, record_id=record.id, containment_id=record.containment_id, actor_id=payload.actor_id, action="emergency-containment-assessed"))
        return record

    def _evaluate(self, payload: EmergencyContainmentAssessmentCreate) -> tuple[EmergencyContainmentState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return EmergencyContainmentState.blocked, ["Risk Brain blocked containment processing"], "keep-containment-blocked"
        if p.require_account_risk_breach and o.account_risk_state not in BREACH_STATES:
            return EmergencyContainmentState.account_risk_required, ["Governed account-risk breach is required"], "verify-account-risk-state"
        if p.require_confirmed_trigger and not o.trigger_confirmed:
            return EmergencyContainmentState.trigger_not_confirmed, ["Emergency trigger is not confirmed"], "confirm-emergency-trigger"
        if (p.require_kill_switch and not o.kill_switch_active) or (p.require_new_order_block and not o.new_order_block_active):
            return EmergencyContainmentState.blocked, ["Kill switch and new-order block must be active"], "activate-risk-containment-controls"
        if p.cancel_pending_orders and o.pending_orders_present and (not o.pending_orders_cancelled or o.remaining_pending_orders > 0):
            return EmergencyContainmentState.cancellation_pending, ["Pending orders are not fully cancelled"], "cancel-and-reconcile-pending-orders"
        if o.open_positions_present:
            if p.require_human_approval_for_liquidation and not o.human_approval_verified:
                return EmergencyContainmentState.approval_required, ["Explicit human approval is required for emergency liquidation"], "request-liquidation-approval"
            if not o.liquidation_dispatched or not o.liquidation_acknowledged or (p.require_zero_remaining_positions and o.remaining_open_positions > 0):
                return EmergencyContainmentState.liquidation_pending, ["Emergency liquidation is pending or incomplete"], "dispatch-or-reconcile-liquidation"
        final_ok = o.broker_equity_reconciled and o.broker_balance_reconciled and o.position_state_reconciled
        if p.require_final_reconciliation and not final_ok:
            return EmergencyContainmentState.reconciliation_required, ["Final broker and position reconciliation is incomplete"], "reconcile-final-account-state"
        if p.require_zero_remaining_orders and o.remaining_pending_orders > 0:
            return EmergencyContainmentState.reconciliation_required, ["Pending broker orders remain after containment"], "reconcile-pending-orders"
        if p.require_incident_record and not o.incident_recorded:
            return EmergencyContainmentState.reconciliation_required, ["Trading incident record is required"], "record-trading-incident"
        if o.release_requested:
            if p.require_human_approval_for_release and not o.release_human_approved:
                return EmergencyContainmentState.approval_required, ["Explicit human approval is required to release containment"], "request-release-approval"
            if not o.controls_reset_acknowledged or o.account_risk_state != "account-risk-clear":
                return EmergencyContainmentState.reconciliation_required, ["Account risk must be clear and controls reset before release"], "verify-release-readiness"
            return EmergencyContainmentState.released, ["Emergency containment released after approved recovery"], "resume-advisory-monitoring"
        return EmergencyContainmentState.contained, ["Account risk is contained and reconciled"], "keep-kill-switch-active"

    def list_assessments(self, workspace_id: str) -> list[EmergencyContainmentAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> EmergencyContainmentAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def contain(self, request: ContainmentActionRequest) -> EmergencyContainmentAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.containment_id == request.containment_id), None)
        if record is None:
            raise KeyError("Emergency containment record not found")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if not request.pending_orders_cancelled or request.remaining_pending_orders > 0:
            record.state = EmergencyContainmentState.cancellation_pending
            record.recommended_action = "cancel-and-reconcile-pending-orders"
            record.reasons = ["Pending orders remain"]
        elif not request.liquidation_acknowledged or request.remaining_open_positions > 0:
            record.state = EmergencyContainmentState.liquidation_pending
            record.recommended_action = "dispatch-or-reconcile-liquidation"
            record.reasons = ["Open positions remain"]
        elif not request.final_reconciliation_complete:
            record.state = EmergencyContainmentState.reconciliation_required
            record.recommended_action = "reconcile-final-account-state"
            record.reasons = ["Final reconciliation is required"]
        else:
            record.state = EmergencyContainmentState.contained
            record.pending_orders_cancelled = True
            record.positions_liquidated = True
            record.reconciled = True
            record.recommended_action = "keep-kill-switch-active"
            record.reasons = ["Emergency containment completed"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, containment_id=record.containment_id, actor_id=request.actor_id, action="emergency-containment-action-assessed"))
        return record

    def release(self, request: ContainmentReleaseRequest) -> EmergencyContainmentAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.containment_id == request.containment_id), None)
        if record is None:
            raise KeyError("Emergency containment record not found")
        if record.state != EmergencyContainmentState.contained:
            raise ValueError("Containment must be completed before release")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if request.account_risk_state != "account-risk-clear" or not request.controls_reset_acknowledged:
            raise ValueError("Account risk must be clear and controls reset must be acknowledged")
        record.state = EmergencyContainmentState.released
        record.kill_switch_active = False
        record.new_orders_blocked = False
        record.recommended_action = "resume-advisory-monitoring"
        record.reasons = ["Containment released after approved recovery"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, containment_id=record.containment_id, actor_id=request.actor_id, action="emergency-containment-released"))
        return record

    def status(self, workspace_id: str) -> EmergencyContainmentStatusResponse:
        records = self.list_assessments(workspace_id)
        contained = sum(r.state == EmergencyContainmentState.contained for r in records)
        released = sum(r.state == EmergencyContainmentState.released for r in records)
        return EmergencyContainmentStatusResponse(workspace_id=workspace_id, assessments=len(records), active=len(records) - released, contained=contained, released=released, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_emergency_risk_containment_service = ExecutiveEmergencyRiskContainmentService()
