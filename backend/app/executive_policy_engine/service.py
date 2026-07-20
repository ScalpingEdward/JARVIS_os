from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    PolicyDecisionState,
    PolicyEffect,
    PolicyEvaluation,
    PolicyEvaluationCreate,
    PolicyScores,
    PolicyEngineStatusResponse,
)


class ExecutivePolicyEngineService:
    def __init__(self) -> None:
        self._records: dict[UUID, PolicyEvaluation] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._evaluation_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: PolicyEvaluationCreate) -> PolicyEvaluation:
        source_key = (payload.workspace_id, payload.source_key)
        evaluation_key = (payload.workspace_id, payload.evaluation_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate policy evaluation source key")
        if evaluation_key in self._evaluation_ids:
            raise ValueError("Duplicate policy evaluation")

        o, p = payload.observation, payload.policy
        reasons: list[str] = []
        policy_ready = o.policy_set_loaded and o.policy_version_resolved and o.inheritance_resolved
        identity_ready = o.actor_role_resolved and o.action_context_valid
        observability_ready = o.observability_context_linked and o.audit_sink_available
        applicable = [r for r in o.matched_rules if r.enabled and payload.action_kind in r.action_kinds and r.time_window_valid]
        if p.emergency_rules_override_standard and any(r.emergency_rule for r in applicable):
            applicable = [r for r in applicable if r.emergency_rule]
        applicable.sort(key=lambda r: r.priority)
        effects = {r.effect for r in applicable}
        matched_policy_ids = [f"{r.policy_id}:v{r.version}" for r in applicable]

        approval_required = PolicyEffect.require_approval in effects
        dry_run_only = PolicyEffect.dry_run in effects or o.dry_run_requested
        denied = PolicyEffect.deny in effects and (p.deny_overrides_allow or PolicyEffect.allow not in effects)
        allowed_by_rule = PolicyEffect.allow in effects and not denied

        if not payload.risk_brain_clear:
            state, action = PolicyDecisionState.blocked, "block-policy-enforcement"
            reasons.append("Risk Brain blocks the evaluated action")
        elif payload.observability_state not in {"healthy", "observability-ready", "warning"}:
            state, action = PolicyDecisionState.blocked, "complete-observability-governance"
            reasons.append("Observability has not authorized policy evaluation")
        elif p.prohibit_raw_policy_secrets and o.raw_policy_secrets_present:
            state, action = PolicyDecisionState.blocked, "remove-raw-policy-secrets"
            reasons.append("Raw secrets are prohibited in policy context")
        elif p.kill_switch_blocks_all and o.kill_switch_enabled:
            state, action = PolicyDecisionState.blocked, "honor-global-kill-switch"
            reasons.append("Global kill switch is enabled")
        elif p.require_policy_set and not policy_ready:
            state, action = PolicyDecisionState.policy_required, "load-versioned-policy-set"
            reasons.append("Policy set, version or inheritance resolution is incomplete")
        elif (p.require_actor_role or p.require_action_context) and not identity_ready:
            state, action = PolicyDecisionState.policy_required, "resolve-role-and-action-context"
            reasons.append("Actor role or action context is unresolved")
        elif (p.require_observability_link or p.require_audit_sink) and not observability_ready:
            state, action = PolicyDecisionState.policy_required, "link-observability-and-audit"
            reasons.append("Observability or audit linkage is incomplete")
        elif p.maintenance_mode_blocks_mutations and o.maintenance_mode_enabled and payload.mutating_action:
            state, action = PolicyDecisionState.maintenance_mode, "wait-for-maintenance-mode-exit"
            reasons.append("Mutating actions are blocked during maintenance mode")
        elif not applicable:
            state, action = PolicyDecisionState.policy_required, "define-applicable-policy-rule"
            reasons.append("No applicable policy rule matched the action")
        elif denied:
            state, action = PolicyDecisionState.policy_denied, "deny-evaluated-action"
            reasons.append("A matching deny policy overrides permission")
        elif approval_required and not o.human_approval_present:
            state, action = PolicyDecisionState.approval_required, "obtain-explicit-human-approval"
            reasons.append("A matching policy requires explicit human approval")
        elif dry_run_only:
            state, action = PolicyDecisionState.dry_run_only, "execute-in-dry-run-mode-only"
            reasons.append("Policy permits only non-mutating dry-run execution")
        elif allowed_by_rule:
            state, action = PolicyDecisionState.ready_for_dispatch, "dispatch-under-policy-guard"
            reasons.append("Applicable policies authorize controlled dispatch")
        else:
            state, action = PolicyDecisionState.policy_approved, "retain-approved-policy-decision"
            reasons.append("Policy evaluation completed without dispatch authorization")

        allowed = state in {PolicyDecisionState.policy_approved, PolicyDecisionState.ready_for_dispatch, PolicyDecisionState.dry_run_only}
        scores = PolicyScores(
            policy_readiness=100 if policy_ready else 35,
            identity_integrity=100 if identity_ready else 40,
            rule_integrity=100 if applicable else 25,
            enforcement_integrity=100 if state in {PolicyDecisionState.ready_for_dispatch, PolicyDecisionState.policy_denied, PolicyDecisionState.approval_required, PolicyDecisionState.dry_run_only} else 55,
            audit_integrity=100 if observability_ready else 35,
            governance_confidence=round(sum([100 if policy_ready else 35, 100 if identity_ready else 40, 100 if applicable else 25, 100 if observability_ready else 35]) / 4),
        )
        record = PolicyEvaluation(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            evaluation_id=payload.evaluation_id,
            action_kind=payload.action_kind,
            action_target=payload.action_target,
            state=state,
            allowed=allowed,
            approval_required=approval_required and not o.human_approval_present,
            dry_run_only=dry_run_only,
            matched_policy_ids=matched_policy_ids,
            recommended_action=action,
            scores=scores,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._evaluation_ids.add(evaluation_key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, evaluation_record_id=record.id, evaluation_id=record.evaluation_id, actor_id=record.actor_id, action=f"policy-evaluation:{record.state.value}"))
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PolicyEvaluation | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_evaluations(self, workspace_id: str) -> list[PolicyEvaluation]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def policies(self, workspace_id: str) -> list[str]:
        values: set[str] = set()
        for record in self.list_evaluations(workspace_id):
            values.update(record.matched_policy_ids)
        return sorted(values)

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PolicyEngineStatusResponse:
        records = self.list_evaluations(workspace_id)
        denied_states = {PolicyDecisionState.blocked, PolicyDecisionState.policy_denied, PolicyDecisionState.maintenance_mode}
        return PolicyEngineStatusResponse(
            workspace_id=workspace_id,
            evaluations=len(records),
            approved=sum(r.allowed for r in records),
            denied_or_blocked=sum(r.state in denied_states for r in records),
            approval_required=sum(r.state == PolicyDecisionState.approval_required for r in records),
            latest_state=records[-1].state if records else None,
        )


executive_policy_engine_service = ExecutivePolicyEngineService()
