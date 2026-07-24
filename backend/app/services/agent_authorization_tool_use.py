from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_authorization_tool_use import (
    AgentAuthorizationCreate,
    AgentAuthorizationRecord,
    AgentAuthorizationScores,
    AgentAuthorizationState,
    AgentToolDisposition,
)


@dataclass
class AuditEntry:
    audit_id: str
    workspace_id: str
    record_id: str
    action: str
    actor: str
    operation_id: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


class AgentAuthorizationToolUseService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentAuthorizationRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-authorization-tool-use-governance",
            "version": "21.87",
            "governance_only": True,
            "agent_execution_enabled": False,
            "tool_permission_mutation_enabled": False,
            "credential_mutation_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentAuthorizationCreate) -> AgentAuthorizationRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = (
            AgentAuthorizationState.BLOCKED
            if "risk-brain-hard-block" in flags
            else AgentAuthorizationState.EVIDENCE_READY
        )
        record = AgentAuthorizationRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            dispositions=dispositions,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AgentAuthorizationRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentAuthorizationRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(
        self,
        workspace_id: str,
        record_id: str,
        action: str,
        actor: str,
        operation_id: str,
        reason: str | None = None,
    ) -> AgentAuthorizationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentAuthorizationState.ASSESSED,
            "submit-review": AgentAuthorizationState.REVIEW_REQUIRED,
            "approve": AgentAuthorizationState.APPROVED,
            "activate": AgentAuthorizationState.ACTIVE,
            "monitor": AgentAuthorizationState.MONITORING,
            "suspend": AgentAuthorizationState.SUSPENDED,
            "revoke": AgentAuthorizationState.REVOKED,
            "archive": AgentAuthorizationState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved agent-authorization findings block approval")
        if action == "activate" and record.state != AgentAuthorizationState.APPROVED:
            raise ValueError("human approval required before activation")

        updated = record.model_copy(
            update={
                "state": transitions[action],
                "approved_by": actor if action == "approve" else record.approved_by,
                "version": record.version + 1,
            }
        )
        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._append_audit(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _assess(self, payload: AgentAuthorizationCreate):
        observations = payload.observations
        identity_and_scope = mean(
            (o.least_privilege_score + o.authorization_coverage + (1 - max(0.0, o.requested_scope - o.approved_scope))) / 3
            for o in observations
        )
        tool_control = mean(o.tool_allowlist_coverage for o in observations)
        delegation = mean(o.delegation_control_score for o in observations)
        injection = mean(o.prompt_injection_resilience for o in observations)
        data_access = mean(o.data_access_control_score for o in observations)
        human_control = mean(o.human_approval_coverage for o in observations)
        audit_reversibility = mean((o.auditability_score + o.reversibility_score + o.output_validation_score) / 3 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(
            mean([
                identity_and_scope,
                tool_control,
                delegation,
                injection,
                data_access,
                human_control,
                audit_reversibility,
            ])
            * confidence
        )

        aggregate_residual_risk = self._clamp(
            mean(
                max(0.0, o.requested_scope - o.approved_scope) * 0.15
                + (1 - o.least_privilege_score) * 0.10
                + (1 - o.authorization_coverage) * 0.10
                + (1 - o.tool_allowlist_coverage) * 0.10
                + (1 - o.delegation_control_score) * 0.10
                + (1 - o.prompt_injection_resilience) * 0.15
                + (1 - o.data_access_control_score) * 0.10
                + min(o.unauthorized_tool_attempts / 5, 1) * 0.05
                + min(o.unapproved_delegations / 5, 1) * 0.05
                + min(o.prompt_injection_events / 5, 1) * 0.05
                + min(o.autonomous_high_impact_actions / 3, 1) * 0.05
                for o in observations
            )
        )

        scores = AgentAuthorizationScores(
            identity_and_scope_assurance=self._clamp(identity_and_scope),
            tool_control_assurance=self._clamp(tool_control),
            delegation_assurance=self._clamp(delegation),
            injection_resilience=self._clamp(injection),
            data_access_assurance=self._clamp(data_access),
            human_control_assurance=self._clamp(human_control),
            audit_and_reversibility=self._clamp(audit_reversibility),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentToolDisposition] = []
        flags: List[str] = []

        for o in observations:
            required_actions: List[str] = []
            lifecycle = "authorized"
            scope_excess = max(0.0, o.requested_scope - o.approved_scope)
            residual = self._clamp(
                scope_excess * 0.18
                + (1 - o.least_privilege_score) * 0.12
                + (1 - o.authorization_coverage) * 0.10
                + (1 - o.tool_allowlist_coverage) * 0.10
                + (1 - o.delegation_control_score) * 0.10
                + (1 - o.prompt_injection_resilience) * 0.15
                + (1 - o.data_access_control_score) * 0.10
                + (1 - o.human_approval_coverage) * 0.10
                + min(o.autonomous_high_impact_actions / 3, 1) * 0.05
            )

            if scope_excess > payload.max_scope_excess or o.least_privilege_score < payload.min_least_privilege_score:
                lifecycle = "scope-alert"
                required_actions.append("least-privilege-and-scope-review")
                flags.append(f"scope-alert:{o.agent_id}:{o.tool_name}")

            if o.authorization_coverage < payload.min_authorization_coverage or o.unauthorized_tool_attempts > 0:
                lifecycle = "tool-alert"
                required_actions.append("tool-authorization-review")
                flags.append(f"tool-alert:{o.agent_id}:{o.tool_name}")

            if o.unapproved_delegations > 0 or o.delegation_control_score < 0.80:
                lifecycle = "delegation-alert"
                required_actions.append("delegation-chain-review")
                flags.append(f"delegation-alert:{o.agent_id}")

            if o.prompt_injection_events > 0 or o.prompt_injection_resilience < payload.min_prompt_injection_resilience:
                lifecycle = "injection-alert"
                required_actions.append("prompt-injection-containment-review")
                flags.append(f"injection-alert:{o.agent_id}")

            if o.sensitive_data_access_events > 0 or o.data_access_control_score < 0.80:
                lifecycle = "data-access-alert"
                required_actions.append("sensitive-data-access-review")
                flags.append(f"data-access-alert:{o.agent_id}")

            if o.human_approval_coverage < payload.min_human_approval_coverage or o.autonomous_high_impact_actions > 0:
                lifecycle = "autonomy-alert"
                required_actions.append("human-control-and-autonomy-review")
                flags.append(f"autonomy-alert:{o.agent_id}")

            if residual > payload.max_residual_risk:
                required_actions.append("agent-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.tool_name}")

            if o.business_criticality >= 0.90 and (
                o.autonomous_high_impact_actions > 0
                or o.unauthorized_tool_attempts > 0
                or residual >= 0.60
            ):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "autonomy-alert"

            dispositions.append(
                AgentToolDisposition(
                    agent_id=o.agent_id,
                    agent_version=o.agent_version,
                    tool_name=o.tool_name,
                    assurance_score=self._clamp(1 - residual),
                    residual_risk=residual,
                    lifecycle_signal=lifecycle,
                    required_actions=sorted(set(required_actions)),
                )
            )

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: AgentAuthorizationRecord,
        action: str,
        actor: str,
        operation_id: str,
        metadata: dict | None = None,
    ) -> None:
        self._audit.append(
            AuditEntry(
                audit_id=str(uuid4()),
                workspace_id=record.workspace_id,
                record_id=record.record_id,
                action=action,
                actor=actor,
                operation_id=operation_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata=metadata or {},
            )
        )


agent_authorization_tool_use_service = AgentAuthorizationToolUseService()
