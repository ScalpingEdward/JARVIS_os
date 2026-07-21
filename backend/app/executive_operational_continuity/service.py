from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    ContinuityAssessment,
    ContinuityAssessmentCreate,
    ContinuityState,
    ContinuityStatusResponse,
    FailoverRequest,
    RecoveryRequest,
)


class ExecutiveOperationalContinuityService:
    def __init__(self) -> None:
        self._records: dict[UUID, ContinuityAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._continuity_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._continuity_ids.clear()
        self._audit.clear()

    def assess(self, payload: ContinuityAssessmentCreate) -> ContinuityAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        continuity_key = (payload.workspace_id, payload.continuity_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate operational continuity source key")
        if continuity_key in self._continuity_ids:
            raise ValueError("Duplicate continuity ID")

        state, reasons, action = self._evaluate(payload)
        o = payload.observation
        failover_required = not all([
            o.source_account_healthy,
            o.follower_accounts_healthy,
            o.broker_sessions_healthy,
            o.market_data_healthy,
            o.executor_healthy,
            o.heartbeat_fresh,
            o.primary_vps_healthy,
        ])
        active_node = payload.standby_node if state == ContinuityState.failed_over else payload.primary_node
        record = ContinuityAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            continuity_id=payload.continuity_id,
            copy_group_id=payload.copy_group_id,
            primary_node=payload.primary_node,
            standby_node=payload.standby_node,
            state=state,
            failover_required=failover_required,
            active_node=active_node,
            reconciled=state in {ContinuityState.continuity_ready, ContinuityState.failed_over, ContinuityState.recovered},
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._continuity_ids.add(continuity_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, record_id=record.id, continuity_id=record.continuity_id, actor_id=payload.actor_id, action="operational-continuity-assessed"))
        return record

    def _evaluate(self, payload: ContinuityAssessmentCreate) -> tuple[ContinuityState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return ContinuityState.blocked, ["Risk Brain blocked continuity processing"], "keep-runtime-blocked"
        if p.require_synchronized_copy and o.copy_execution_state != "synchronized":
            return ContinuityState.copy_sync_required, ["Synchronized copy execution evidence is required"], "reconcile-copy-group"
        runtime_healthy = all([o.source_account_healthy, o.follower_accounts_healthy, o.broker_sessions_healthy, o.market_data_healthy, o.executor_healthy, o.heartbeat_fresh, o.primary_vps_healthy])
        if runtime_healthy:
            return ContinuityState.continuity_ready, ["Primary runtime and copy group are healthy"], "monitor-continuity"
        if p.require_standby and not o.standby_vps_ready:
            return ContinuityState.health_degraded, ["Primary runtime is degraded and standby is unavailable"], "restore-standby-capacity"
        if p.require_current_checkpoint and not o.state_checkpoint_current:
            return ContinuityState.health_degraded, ["Failover checkpoint is stale or incomplete"], "refresh-state-checkpoint"
        if p.require_human_approval_for_failover and not o.human_approval_verified:
            return ContinuityState.failover_approval_required, ["Explicit human approval is required for failover"], "request-failover-approval"
        if not o.failover_dispatched or not o.failover_acknowledged:
            return ContinuityState.failover_pending, ["Failover dispatch is pending or unacknowledged"], "dispatch-or-reconcile-failover"
        final_ok = o.active_node_matches_expected and o.positions_reconciled and o.pending_orders_reconciled and o.copy_group_reconciled
        if p.require_final_reconciliation and not final_ok:
            return ContinuityState.reconciliation_required, ["Post-failover account, order or position reconciliation is incomplete"], "reconcile-failover-state"
        return ContinuityState.failed_over, ["Standby runtime is active and reconciled"], "operate-on-standby"

    def list_assessments(self, workspace_id: str) -> list[ContinuityAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> ContinuityAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def _by_continuity_id(self, workspace_id: str, continuity_id: UUID) -> ContinuityAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == workspace_id and r.continuity_id == continuity_id), None)
        if record is None:
            raise KeyError("Operational continuity record not found")
        return record

    def failover(self, request: FailoverRequest) -> ContinuityAssessment:
        record = self._by_continuity_id(request.workspace_id, request.continuity_id)
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if not request.failover_acknowledged:
            record.state = ContinuityState.failover_pending
            record.reconciled = False
            record.recommended_action = "reconcile-failover-dispatch"
        elif not request.final_reconciliation_complete:
            record.state = ContinuityState.reconciliation_required
            record.reconciled = False
            record.recommended_action = "reconcile-failover-state"
        else:
            record.state = ContinuityState.failed_over
            record.active_node = request.active_node
            record.reconciled = True
            record.recommended_action = "operate-on-standby"
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, continuity_id=record.continuity_id, actor_id=request.actor_id, action="operational-failover-assessed"))
        return record

    def recover(self, request: RecoveryRequest) -> ContinuityAssessment:
        record = self._by_continuity_id(request.workspace_id, request.continuity_id)
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if not request.primary_restored or not request.final_reconciliation_complete:
            raise ValueError("Primary restoration and final reconciliation are required")
        record.state = ContinuityState.recovered
        record.active_node = request.active_node
        record.reconciled = True
        record.failover_required = False
        record.recommended_action = "resume-primary-monitoring"
        record.reasons = ["Primary runtime restored and reconciled"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, continuity_id=record.continuity_id, actor_id=request.actor_id, action="operational-recovery-assessed"))
        return record

    def status(self, workspace_id: str) -> ContinuityStatusResponse:
        records = self.list_assessments(workspace_id)
        healthy = sum(r.state in {ContinuityState.continuity_ready, ContinuityState.recovered} for r in records)
        failed_over = sum(r.state == ContinuityState.failed_over for r in records)
        return ContinuityStatusResponse(workspace_id=workspace_id, assessments=len(records), healthy=healthy, failed_over=failed_over, attention_required=len(records)-healthy-failed_over, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_operational_continuity_service = ExecutiveOperationalContinuityService()
