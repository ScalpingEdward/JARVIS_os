from __future__ import annotations

from uuid import UUID

from .models import (
    AccountRole,
    AuditRecord,
    CopyControlRequest,
    CopyGovernanceAssessment,
    CopyGovernanceAssessmentCreate,
    CopyGovernanceState,
    CopyGovernanceStatusResponse,
)


class ExecutiveMultiAccountCopyGovernanceService:
    def __init__(self) -> None:
        self._records: dict[UUID, CopyGovernanceAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._group_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._group_ids.clear()
        self._audit.clear()

    def assess(self, payload: CopyGovernanceAssessmentCreate) -> CopyGovernanceAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        group_key = (payload.workspace_id, payload.copy_group_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate copy-governance source key")
        if group_key in self._group_ids:
            raise ValueError("Duplicate copy group ID")

        state, reasons, action = self._evaluate(payload)
        sources = [a for a in payload.accounts if a.role == AccountRole.source and a.enabled]
        followers = [a for a in payload.accounts if a.role == AccountRole.follower and a.enabled]
        aggregate_risk = sum(a.current_open_risk_pct for a in payload.accounts if a.enabled)
        record = CopyGovernanceAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            copy_group_id=payload.copy_group_id,
            copy_mode=payload.copy_mode,
            source_account_reference=sources[0].account_reference if len(sources) == 1 else None,
            follower_count=len(followers),
            aggregate_open_risk_pct=aggregate_risk,
            state=state,
            synchronized=state == CopyGovernanceState.copy_ready,
            approved=payload.observation.human_approval_verified,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._group_ids.add(group_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, record_id=record.id, copy_group_id=record.copy_group_id, actor_id=payload.actor_id, action="copy-governance-assessed"))
        return record

    def _evaluate(self, payload: CopyGovernanceAssessmentCreate) -> tuple[CopyGovernanceState, list[str], str]:
        o, p = payload.observation, payload.policy
        enabled = [a for a in payload.accounts if a.enabled]
        sources = [a for a in enabled if a.role == AccountRole.source]
        followers = [a for a in enabled if a.role == AccountRole.follower]
        if not payload.risk_brain_clear:
            return CopyGovernanceState.blocked, ["Risk Brain blocked multi-account copy governance"], "keep-copy-group-blocked"
        if p.require_single_source and len(sources) != 1:
            return CopyGovernanceState.topology_invalid, ["Exactly one enabled source account is required"], "repair-copy-topology"
        if not (p.minimum_followers <= len(followers) <= p.maximum_followers):
            return CopyGovernanceState.topology_invalid, ["Follower count is outside the governed range"], "repair-copy-topology"
        if p.require_trading_reenabled and any(a.controlled_reentry_state != "trading-reenabled" for a in enabled):
            return CopyGovernanceState.reentry_required, ["Every enabled account must be fully trading-reenabled"], "complete-controlled-reentry"
        if any(not a.session_ready for a in enabled) or not o.follower_sessions_ready:
            return CopyGovernanceState.account_unavailable, ["One or more account sessions are unavailable"], "restore-account-sessions"
        if p.require_account_risk_clear and any(a.account_risk_state != "account-risk-clear" for a in enabled):
            return CopyGovernanceState.risk_mismatch, ["Every enabled account must be account-risk-clear"], "resolve-account-risk"
        if any(a.emergency_containment_state != "released" for a in enabled):
            return CopyGovernanceState.blocked, ["Emergency containment remains active on an account"], "release-account-containment"
        if not (o.source_signal_present and o.source_order_intent_approved and o.source_execution_reconciled and o.source_position_reconciled):
            return CopyGovernanceState.synchronization_degraded, ["Source signal, intent, execution or position evidence is incomplete"], "reconcile-source-state"
        if not (o.symbol_mapping_complete and o.volume_mapping_complete and o.stop_mapping_complete and o.direction_consistent):
            return CopyGovernanceState.synchronization_degraded, ["Follower symbol, volume, stop or direction mapping is incomplete"], "repair-copy-mapping"
        if o.latency_ms > o.maximum_latency_ms or o.divergence_pct > o.maximum_divergence_pct:
            return CopyGovernanceState.synchronization_degraded, ["Copy latency or account divergence exceeded policy"], "suspend-and-reconcile-copying"
        if p.prohibit_duplicate_dispatch and o.duplicate_dispatch_detected:
            return CopyGovernanceState.policy_rejected, ["Duplicate cross-account dispatch was detected"], "quarantine-duplicate-dispatch"
        if p.prohibit_cross_account_hedging and o.cross_account_hedge_detected:
            return CopyGovernanceState.policy_rejected, ["Cross-account hedging is prohibited"], "remove-cross-account-hedge"
        if p.require_prop_rule_compatibility and o.prop_rule_conflict_detected:
            return CopyGovernanceState.policy_rejected, ["A prop-firm rule conflict was detected"], "resolve-prop-rule-conflict"
        aggregate_risk = sum(a.current_open_risk_pct for a in enabled)
        if aggregate_risk > p.maximum_total_open_risk_pct or any(a.current_open_risk_pct > a.maximum_open_risk_pct for a in enabled):
            return CopyGovernanceState.risk_mismatch, ["Aggregate or account-level open risk exceeded policy"], "reduce-copy-group-risk"
        if o.suspension_requested:
            return CopyGovernanceState.copy_suspended, ["Copy group suspension was requested"], "keep-copy-group-suspended"
        if p.require_human_approval and not o.human_approval_verified:
            return CopyGovernanceState.approval_required, ["Explicit human approval is required before copying"], "request-copy-approval"
        return CopyGovernanceState.copy_ready, ["Multi-account copy group is approved, synchronized and risk-compatible"], "monitor-copy-group"

    def list_groups(self, workspace_id: str) -> list[CopyGovernanceAssessment]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> CopyGovernanceAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def control(self, request: CopyControlRequest, suspend: bool) -> CopyGovernanceAssessment:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.copy_group_id == request.copy_group_id), None)
        if record is None:
            raise KeyError("Copy governance record not found")
        if not request.human_approval_verified:
            raise ValueError("Explicit human approval is required")
        if suspend:
            record.state = CopyGovernanceState.copy_suspended
            record.synchronized = False
            record.recommended_action = "keep-copy-group-suspended"
            record.reasons = ["Copy group suspended by approved human action"]
            action = "copy-group-suspended"
        else:
            if not request.synchronization_verified or not request.account_risk_clear:
                raise ValueError("Synchronization and account-risk-clear evidence are required")
            record.state = CopyGovernanceState.copy_ready
            record.synchronized = True
            record.approved = True
            record.recommended_action = "monitor-copy-group"
            record.reasons = ["Copy group resumed after approved verification"]
            action = "copy-group-resumed"
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, record_id=record.id, copy_group_id=record.copy_group_id, actor_id=request.actor_id, action=action))
        return record

    def status(self, workspace_id: str) -> CopyGovernanceStatusResponse:
        records = self.list_groups(workspace_id)
        ready = sum(r.state == CopyGovernanceState.copy_ready for r in records)
        suspended = sum(r.state == CopyGovernanceState.copy_suspended for r in records)
        return CopyGovernanceStatusResponse(workspace_id=workspace_id, groups=len(records), ready=ready, suspended=suspended, attention_required=len(records) - ready - suspended, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_multi_account_copy_governance_service = ExecutiveMultiAccountCopyGovernanceService()
