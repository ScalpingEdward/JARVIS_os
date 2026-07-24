from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.multi_agent_coordination_delegation import (
    AgentCoordinationDisposition,
    MultiAgentCoordinationCreate,
    MultiAgentCoordinationRecord,
    MultiAgentCoordinationScores,
    MultiAgentCoordinationState,
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


class MultiAgentCoordinationDelegationService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], MultiAgentCoordinationRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "multi-agent-coordination-delegation-governance",
            "version": "21.90",
            "governance_only": True,
            "agent_execution_enabled": False,
            "delegation_mutation_enabled": False,
            "task_assignment_mutation_enabled": False,
            "automatic_consensus_execution_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: MultiAgentCoordinationCreate) -> MultiAgentCoordinationRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = MultiAgentCoordinationState.BLOCKED if "risk-brain-hard-block" in flags else MultiAgentCoordinationState.EVIDENCE_READY
        record = MultiAgentCoordinationRecord(
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

    def list(self, workspace_id: str) -> List[MultiAgentCoordinationRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> MultiAgentCoordinationRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> MultiAgentCoordinationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": MultiAgentCoordinationState.ASSESSED,
            "submit-review": MultiAgentCoordinationState.REVIEW_REQUIRED,
            "approve": MultiAgentCoordinationState.APPROVED,
            "activate": MultiAgentCoordinationState.ACTIVE,
            "monitor": MultiAgentCoordinationState.MONITORING,
            "suspend": MultiAgentCoordinationState.SUSPENDED,
            "revoke": MultiAgentCoordinationState.REVOKED,
            "archive": MultiAgentCoordinationState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved multi-agent coordination findings block approval")
        if action == "activate" and record.state != MultiAgentCoordinationState.APPROVED:
            raise ValueError("human approval required before activation")

        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._append_audit(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _assess(self, payload: MultiAgentCoordinationCreate):
        observations = payload.observations
        role_clarity = mean((o.responsibility_clarity + o.task_ownership_integrity + (1 - min(o.role_conflicts / 3, 1))) / 3 for o in observations)
        delegation = mean((o.delegation_integrity + (1 - min(o.unauthorized_delegations / 3, 1))) / 2 for o in observations)
        handoff = mean((o.handoff_quality + (1 - min(o.failed_handoffs / 3, 1))) / 2 for o in observations)
        consensus = mean((o.consensus_alignment + o.conflict_resolution_readiness + (1 - min(o.unresolved_disagreements / 5, 1))) / 3 for o in observations)
        context = mean(o.shared_context_consistency for o in observations)
        escalation = mean(o.human_escalation_readiness for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(mean([role_clarity, delegation, handoff, consensus, context, escalation]) * confidence)
        aggregate_residual_risk = self._clamp(mean(
            (1 - o.responsibility_clarity) * 0.12
            + (1 - o.delegation_integrity) * 0.15
            + (1 - o.handoff_quality) * 0.12
            + (1 - o.consensus_alignment) * 0.12
            + (1 - o.shared_context_consistency) * 0.12
            + (1 - o.human_escalation_readiness) * 0.12
            + min(o.role_conflicts / 3, 1) * 0.07
            + min(o.unauthorized_delegations / 3, 1) * 0.08
            + min(o.coordination_deadlocks / 3, 1) * 0.10
            for o in observations
        ))

        scores = MultiAgentCoordinationScores(
            role_clarity_assurance=self._clamp(role_clarity),
            delegation_assurance=self._clamp(delegation),
            handoff_assurance=self._clamp(handoff),
            consensus_assurance=self._clamp(consensus),
            context_consistency=self._clamp(context),
            escalation_readiness=self._clamp(escalation),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentCoordinationDisposition] = []
        flags: List[str] = []
        for o in observations:
            actions: List[str] = []
            lifecycle = "coordinated"
            residual = self._clamp(
                (1 - o.responsibility_clarity) * 0.15
                + (1 - o.delegation_integrity) * 0.18
                + (1 - o.handoff_quality) * 0.15
                + (1 - o.consensus_alignment) * 0.15
                + (1 - o.shared_context_consistency) * 0.12
                + (1 - o.human_escalation_readiness) * 0.10
                + min(o.coordination_deadlocks / 3, 1) * 0.15
            )

            if o.role_conflicts > 0 or o.responsibility_clarity < payload.min_responsibility_clarity:
                lifecycle = "role-conflict"
                actions.append("role-and-responsibility-review")
                flags.append(f"role-conflict:{o.agent_id}")
            if o.unauthorized_delegations > 0 or o.delegation_integrity < payload.min_delegation_integrity:
                lifecycle = "delegation-alert"
                actions.append("delegation-chain-and-authority-review")
                flags.append(f"delegation-alert:{o.agent_id}")
            if o.unresolved_disagreements > 0 or o.consensus_alignment < payload.min_consensus_alignment:
                lifecycle = "consensus-alert"
                actions.append("consensus-and-conflict-resolution-review")
                flags.append(f"consensus-alert:{o.agent_id}")
            if o.coordination_deadlocks > 0:
                lifecycle = "deadlock-alert"
                actions.append("coordination-deadlock-investigation")
                flags.append(f"deadlock-alert:{o.agent_id}")
            if o.failed_handoffs > 0 or o.handoff_quality < payload.min_handoff_quality:
                lifecycle = "handoff-alert"
                actions.append("handoff-integrity-review")
                flags.append(f"handoff-alert:{o.agent_id}")
            if residual > payload.max_residual_risk:
                actions.append("multi-agent-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}")
            if o.business_criticality >= 0.90 and (o.unauthorized_delegations > 0 or o.coordination_deadlocks >= 2 or residual >= 0.60):
                actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "deadlock-alert"

            dispositions.append(AgentCoordinationDisposition(
                agent_id=o.agent_id,
                agent_version=o.agent_version,
                role=o.role,
                assurance_score=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: MultiAgentCoordinationRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()),
            workspace_id=record.workspace_id,
            record_id=record.record_id,
            action=action,
            actor=actor,
            operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        ))


multi_agent_coordination_delegation_service = MultiAgentCoordinationDelegationService()
