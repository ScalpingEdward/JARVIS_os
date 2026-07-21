from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    CopyExecutionAssessment,
    CopyExecutionAssessmentCreate,
    CopyExecutionState,
    CopyExecutionStatusResponse,
    DriftRepairRequest,
)


class ExecutiveCopyExecutionDriftRepairService:
    def __init__(self) -> None:
        self._records: dict[UUID, CopyExecutionAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._fanout_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._fanout_ids.clear()
        self._audit.clear()

    def assess(self, payload: CopyExecutionAssessmentCreate) -> CopyExecutionAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        fanout_key = (payload.workspace_id, payload.fanout_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate copy execution source key")
        if fanout_key in self._fanout_ids:
            raise ValueError("Duplicate copy fanout ID")

        state, reasons, action = self._evaluate(payload)
        followers = payload.observation.followers
        intended = [f for f in followers if f.intended]
        acknowledged = [f for f in intended if f.broker_acknowledged and f.broker_order_id_present]
        drifted = [f for f in intended if self._has_drift(f, payload)]
        quarantined = [f for f in intended if f.quarantined or f.duplicate_execution_detected]
        synchronized = [f for f in intended if f in acknowledged and f not in drifted and f not in quarantined]

        record = CopyExecutionAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            fanout_id=payload.fanout_id,
            copy_group_id=payload.copy_group_id,
            source_execution_id=payload.source_execution_id,
            source_account_reference=payload.source_account_reference,
            canonical_symbol=payload.canonical_symbol,
            state=state,
            intended_followers=len(intended),
            acknowledged_followers=len(acknowledged),
            synchronized_followers=len(synchronized),
            drifted_followers=len(drifted),
            quarantined_followers=len(quarantined),
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._fanout_ids.add(fanout_key)
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                record_id=record.id,
                fanout_id=record.fanout_id,
                actor_id=payload.actor_id,
                action="copy-execution-fanout-assessed",
            )
        )
        return record

    @staticmethod
    def _has_drift(follower, payload: CopyExecutionAssessmentCreate) -> bool:
        p = payload.policy
        mapping_bad = p.require_symbol_side_volume_mapping and not (
            follower.symbol_matches and follower.side_matches and follower.volume_matches
        )
        protection_bad = p.require_protection_mapping and not (
            follower.stop_loss_matches and follower.take_profit_matches
        )
        return (
            mapping_bad
            or protection_bad
            or not follower.position_present
            or follower.fill_price_drift_bps > p.maximum_fill_price_drift_bps
            or follower.volume_drift_pct > p.maximum_volume_drift_pct
            or follower.latency_ms > p.maximum_latency_ms
            or follower.repair_required
        )

    def _evaluate(self, payload: CopyExecutionAssessmentCreate) -> tuple[CopyExecutionState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return CopyExecutionState.blocked, ["Risk Brain blocked copy fanout"], "keep-copy-execution-blocked"
        if p.require_copy_ready and o.copy_governance_state != "copy-ready":
            return CopyExecutionState.copy_governance_required, ["Copy group is not approved and ready"], "resolve-copy-governance"
        if p.require_source_execution_completed and (o.source_execution_state != "execution-completed" or not o.source_execution_reconciled):
            return CopyExecutionState.source_execution_required, ["Completed and reconciled source execution is required"], "resolve-source-execution"
        if p.require_source_position_open and o.source_position_state != "position-open":
            return CopyExecutionState.source_execution_required, ["Governed source position is not open"], "resolve-source-position"
        if not o.fanout_requested:
            return CopyExecutionState.fanout_pending, ["Follower fanout has not been requested"], "request-approved-fanout"

        intended = [f for f in o.followers if f.intended]
        if p.require_all_intended_followers and not intended:
            return CopyExecutionState.fanout_pending, ["At least one intended follower is required"], "bind-copy-followers"
        if p.prohibit_duplicate_execution and any(f.duplicate_execution_detected for f in intended):
            return CopyExecutionState.quarantined, ["Duplicate follower execution detected"], "quarantine-follower-and-investigate"
        if any(not f.dispatch_attempted for f in intended):
            return CopyExecutionState.fanout_pending, ["Follower dispatch is incomplete"], "dispatch-missing-followers"
        if p.require_broker_acknowledgement and any(not f.broker_acknowledged or not f.broker_order_id_present for f in intended):
            return CopyExecutionState.follower_ack_pending, ["Follower broker acknowledgement is incomplete"], "query-follower-order-state"

        drifted = [f for f in intended if self._has_drift(f, payload)]
        if drifted:
            if p.require_human_approval_for_repair and any(not f.repair_human_approved for f in drifted):
                return CopyExecutionState.repair_approval_required, ["Follower drift requires explicit human-approved repair"], "request-drift-repair-approval"
            if any(not f.repair_dispatched or not f.repair_acknowledged for f in drifted):
                return CopyExecutionState.repair_pending, ["Follower repair dispatch or acknowledgement is incomplete"], "dispatch-or-reconcile-repair"
            return CopyExecutionState.drift_detected, ["Follower drift remains after repair evidence"], "reconcile-follower-positions"

        return CopyExecutionState.synchronized, ["Source execution and all intended followers are synchronized"], "monitor-copy-drift"

    def list_assessments(self, workspace_id: str) -> list[CopyExecutionAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> CopyExecutionAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def repair(self, request: DriftRepairRequest) -> CopyExecutionAssessment:
        record = next(
            (
                item
                for item in self._records.values()
                if item.workspace_id == request.workspace_id and item.fanout_id == request.fanout_id
            ),
            None,
        )
        if record is None:
            raise KeyError("Copy execution fanout record not found")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required for drift repair")
        if not request.repair_dispatch_acknowledged:
            record.state = CopyExecutionState.repair_pending
            record.recommended_action = "query-repair-dispatch-state"
            record.reasons = ["Repair dispatch acknowledgement is required"]
        elif not request.final_positions_reconciled or request.remaining_drifted_followers > 0:
            record.state = CopyExecutionState.drift_detected
            record.drifted_followers = request.remaining_drifted_followers
            record.recommended_action = "reconcile-follower-positions"
            record.reasons = ["Follower positions remain divergent after repair"]
        else:
            record.state = CopyExecutionState.synchronized
            record.synchronized_followers = record.intended_followers
            record.acknowledged_followers = record.intended_followers
            record.drifted_followers = 0
            record.recommended_action = "monitor-copy-drift"
            record.reasons = ["Human-approved drift repair and final reconciliation completed"]
        self._audit.append(
            AuditRecord(
                workspace_id=request.workspace_id,
                record_id=record.id,
                fanout_id=record.fanout_id,
                actor_id=request.actor_id,
                action="copy-execution-drift-repair-assessed",
            )
        )
        return record

    def status(self, workspace_id: str) -> CopyExecutionStatusResponse:
        records = self.list_assessments(workspace_id)
        synchronized = sum(record.state == CopyExecutionState.synchronized for record in records)
        quarantined = sum(record.state == CopyExecutionState.quarantined for record in records)
        return CopyExecutionStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            synchronized=synchronized,
            attention_required=len(records) - synchronized,
            quarantined=quarantined,
            latest_state=records[-1].state if records else None,
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_copy_execution_drift_repair_service = ExecutiveCopyExecutionDriftRepairService()
