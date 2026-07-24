from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_runtime_supervision import (
    AgentRuntimeCreate,
    AgentRuntimeDisposition,
    AgentRuntimeRecord,
    AgentRuntimeScores,
    AgentRuntimeState,
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


class AgentRuntimeSupervisionService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentRuntimeRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-runtime-supervision-intervention-governance",
            "version": "21.88",
            "governance_only": True,
            "agent_execution_enabled": False,
            "automatic_agent_stop_enabled": False,
            "automatic_intervention_enabled": False,
            "tool_execution_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentRuntimeCreate) -> AgentRuntimeRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = AgentRuntimeState.BLOCKED if "risk-brain-hard-block" in flags else AgentRuntimeState.EVIDENCE_READY
        record = AgentRuntimeRecord(
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

    def list(self, workspace_id: str) -> List[AgentRuntimeRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentRuntimeRecord:
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
    ) -> AgentRuntimeRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentRuntimeState.ASSESSED,
            "submit-review": AgentRuntimeState.REVIEW_REQUIRED,
            "approve": AgentRuntimeState.APPROVED,
            "activate": AgentRuntimeState.ACTIVE,
            "monitor": AgentRuntimeState.MONITORING,
            "suspend": AgentRuntimeState.SUSPENDED,
            "revoke": AgentRuntimeState.REVOKED,
            "archive": AgentRuntimeState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved runtime-supervision findings block approval")
        if action == "activate" and record.state != AgentRuntimeState.APPROVED:
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

    def _assess(self, payload: AgentRuntimeCreate):
        observations = payload.observations
        runtime_health = mean(o.heartbeat_health for o in observations)
        behavioral_assurance = mean((o.behavioral_stability + o.policy_conformance) / 2 for o in observations)
        tool_reliability = mean((o.tool_success_rate + o.output_validation_rate) / 2 for o in observations)
        intervention_readiness = mean((o.human_override_readiness + o.stop_control_readiness) / 2 for o in observations)
        resource_resilience = mean((o.resource_efficiency + o.budget_headroom) / 2 for o in observations)
        context_integrity = mean(o.context_integrity for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(
            mean([
                runtime_health,
                behavioral_assurance,
                tool_reliability,
                intervention_readiness,
                resource_resilience,
                context_integrity,
            ]) * confidence
        )

        aggregate_residual_risk = self._clamp(
            mean(
                (1 - o.behavioral_stability) * 0.15
                + (1 - o.policy_conformance) * 0.15
                + (1 - o.tool_success_rate) * 0.10
                + (1 - o.stop_control_readiness) * 0.15
                + (1 - o.budget_headroom) * 0.10
                + (1 - o.context_integrity) * 0.10
                + min(o.repeated_action_count / max(payload.max_repeated_actions, 1), 1) * 0.10
                + min(o.consecutive_tool_failures / 5, 1) * 0.05
                + min(o.policy_violation_count / 5, 1) * 0.05
                + min(o.human_override_failures / 3, 1) * 0.05
                for o in observations
            )
        )

        scores = AgentRuntimeScores(
            runtime_health=self._clamp(runtime_health),
            behavioral_assurance=self._clamp(behavioral_assurance),
            tool_reliability=self._clamp(tool_reliability),
            intervention_readiness=self._clamp(intervention_readiness),
            resource_resilience=self._clamp(resource_resilience),
            context_integrity=self._clamp(context_integrity),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentRuntimeDisposition] = []
        flags: List[str] = []

        for o in observations:
            required_actions: List[str] = []
            lifecycle = "healthy"
            residual = self._clamp(
                (1 - o.behavioral_stability) * 0.15
                + (1 - o.policy_conformance) * 0.15
                + (1 - o.tool_success_rate) * 0.10
                + (1 - o.stop_control_readiness) * 0.15
                + (1 - o.budget_headroom) * 0.10
                + (1 - o.context_integrity) * 0.10
                + min(o.repeated_action_count / max(payload.max_repeated_actions, 1), 1) * 0.10
                + min(o.consecutive_tool_failures / 5, 1) * 0.05
                + min(o.human_override_failures / 3, 1) * 0.10
            )

            if o.behavioral_stability < payload.min_behavioral_stability or o.policy_conformance < payload.min_policy_conformance or o.policy_violation_count > 0:
                lifecycle = "behavior-drift"
                required_actions.append("behavior-and-policy-review")
                flags.append(f"behavior-drift:{o.agent_id}:{o.runtime_id}")

            if o.repeated_action_count > payload.max_repeated_actions:
                lifecycle = "loop-alert"
                required_actions.append("runaway-loop-investigation")
                flags.append(f"loop-alert:{o.agent_id}:{o.runtime_id}")

            if o.tool_success_rate < payload.min_tool_success_rate or o.consecutive_tool_failures >= 3:
                lifecycle = "tool-failure-alert"
                required_actions.append("tool-failure-and-fallback-review")
                flags.append(f"tool-failure-alert:{o.agent_id}:{o.runtime_id}")

            if o.budget_headroom < payload.min_budget_headroom or o.resource_spike_count > 0:
                lifecycle = "budget-alert"
                required_actions.append("resource-and-budget-review")
                flags.append(f"budget-alert:{o.agent_id}:{o.runtime_id}")

            if o.stop_control_readiness < payload.min_stop_control_readiness or o.human_override_failures > 0:
                lifecycle = "intervention-required"
                required_actions.append("human-intervention-control-review")
                flags.append(f"intervention-required:{o.agent_id}:{o.runtime_id}")

            if residual > payload.max_residual_risk:
                required_actions.append("agent-runtime-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.runtime_id}")

            if o.business_criticality >= 0.90 and (
                o.human_override_failures > 0
                or o.policy_violation_count > 0
                or o.repeated_action_count > payload.max_repeated_actions * 2
                or residual >= 0.60
            ):
                lifecycle = "intervention-required"
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(
                AgentRuntimeDisposition(
                    agent_id=o.agent_id,
                    agent_version=o.agent_version,
                    runtime_id=o.runtime_id,
                    assurance_score=self._clamp(1 - residual),
                    residual_risk=residual,
                    lifecycle_signal=lifecycle,
                    required_actions=sorted(set(required_actions)),
                )
            )

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: AgentRuntimeRecord,
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


agent_runtime_supervision_service = AgentRuntimeSupervisionService()
