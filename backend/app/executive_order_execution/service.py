from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    ExecutionAssessment,
    ExecutionAssessmentCreate,
    ExecutionState,
    ExecutionStatusResponse,
    ReconcileRequest,
)


class ExecutiveOrderExecutionService:
    def __init__(self) -> None:
        self._records: dict[UUID, ExecutionAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._execution_ids: set[tuple[str, UUID]] = set()
        self._idempotency_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._execution_ids.clear()
        self._idempotency_keys.clear()
        self._audit.clear()

    def assess(self, payload: ExecutionAssessmentCreate) -> ExecutionAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        execution_key = (payload.workspace_id, payload.execution_id)
        idempotency_key = (payload.workspace_id, payload.idempotency_key)
        if source_key in self._source_keys:
            raise ValueError("Duplicate order execution source key")
        if execution_key in self._execution_ids:
            raise ValueError("Duplicate execution ID")
        if idempotency_key in self._idempotency_keys:
            raise ValueError("Duplicate execution idempotency key")

        state, reasons, action = self._evaluate(payload)
        o = payload.observation
        fill_ratio = min(o.filled_quantity / o.requested_quantity, 1.0)
        record = ExecutionAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            execution_id=payload.execution_id,
            order_intent_id=payload.order_intent_id,
            adapter=payload.adapter,
            account_reference=payload.account_reference,
            canonical_symbol=payload.canonical_symbol,
            idempotency_key=payload.idempotency_key,
            state=state,
            dispatched=o.dispatch_succeeded,
            broker_acknowledged=o.broker_acknowledged,
            fill_ratio=fill_ratio,
            reconciliation_complete=state == ExecutionState.execution_completed,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._execution_ids.add(execution_key)
        self._idempotency_keys.add(idempotency_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, execution_id=record.execution_id, actor_id=payload.actor_id, action="order-execution-assessed"))
        return record

    def _evaluate(self, payload: ExecutionAssessmentCreate) -> tuple[ExecutionState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return ExecutionState.blocked, ["Risk Brain blocked execution"], "keep-execution-blocked"
        if p.require_ready_intent and o.order_intent_state != "ready-for-dispatch":
            return ExecutionState.intent_required, ["Order intent is not ready for dispatch"], "resolve-order-intent"
        if p.require_human_approval and not o.human_approval_verified:
            return ExecutionState.approval_required, ["Explicit human approval is required"], "request-human-approval"
        if (p.require_registered_adapter and not o.adapter_registered) or (p.require_healthy_adapter and not o.adapter_healthy) or (p.require_credential_binding and not o.credential_binding_valid):
            return ExecutionState.adapter_unavailable, ["Execution adapter or credential binding is unavailable"], "repair-adapter-binding"
        if p.require_idempotency_key and not o.idempotency_key_present:
            return ExecutionState.blocked, ["Execution idempotency key is required"], "provide-idempotency-key"
        if not o.dispatch_attempted or not o.dispatch_succeeded:
            return ExecutionState.dispatch_failed, ["Order dispatch failed or was not attempted"], "retry-through-approved-adapter"
        if o.execution_timeout or (p.require_broker_ack and not o.broker_acknowledged) or (p.require_broker_order_id and not o.broker_order_id_present):
            return ExecutionState.acknowledgement_pending, ["Broker acknowledgement is incomplete"], "query-broker-order-state"
        if p.prohibit_duplicate_fills and o.duplicate_fill_detected:
            return ExecutionState.reconciliation_required, ["Duplicate fill evidence detected"], "quarantine-and-reconcile"
        fill_ratio = o.filled_quantity / o.requested_quantity
        if 0 < fill_ratio < 1:
            return ExecutionState.partial_fill, ["Order is partially filled"], "monitor-or-cancel-remainder"
        if fill_ratio <= 0:
            return ExecutionState.acknowledgement_pending, ["No fill has been reported"], "query-broker-order-state"
        if o.expected_price and o.average_fill_price:
            slippage_bps = abs(o.average_fill_price - o.expected_price) / o.expected_price * 10_000
            if slippage_bps > o.maximum_slippage_bps:
                return ExecutionState.reconciliation_required, ["Fill slippage exceeded the approved limit"], "review-execution-quality"
        reconciliation_ok = o.fill_events_complete and o.commission_reported and o.broker_position_reconciled and (not o.cancel_required or o.cancel_acknowledged)
        if not reconciliation_ok:
            return ExecutionState.reconciliation_required, ["Fill, commission, cancellation or broker-position evidence is incomplete"], "reconcile-broker-state"
        return ExecutionState.execution_completed, ["Execution and fill reconciliation completed"], "publish-position-event"

    def list_executions(self, workspace_id: str) -> list[ExecutionAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> ExecutionAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def reconcile(self, request: ReconcileRequest) -> ExecutionAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.execution_id == request.execution_id), None)
        if record is None:
            raise KeyError("Order execution not found")
        if not request.broker_position_reconciled or not request.fill_events_complete:
            raise ValueError("Complete reconciliation evidence is required")
        record.state = ExecutionState.execution_completed
        record.reconciliation_complete = True
        record.recommended_action = "publish-position-event"
        record.reasons = ["Broker fills and position state reconciled"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, assessment_id=record.id, execution_id=record.execution_id, actor_id=request.actor_id, action="order-execution-reconciled"))
        return record

    def status(self, workspace_id: str) -> ExecutionStatusResponse:
        records = self.list_executions(workspace_id)
        completed = sum(r.state == ExecutionState.execution_completed for r in records)
        return ExecutionStatusResponse(workspace_id=workspace_id, executions=len(records), completed=completed, pending_or_failed=len(records) - completed, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_order_execution_service = ExecutiveOrderExecutionService()
