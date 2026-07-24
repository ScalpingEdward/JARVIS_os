from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_objective_intent_alignment import (
    AgentObjectiveCreate,
    AgentObjectiveDisposition,
    AgentObjectiveRecord,
    AgentObjectiveScores,
    AgentObjectiveState,
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


class AgentObjectiveIntentAlignmentService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentObjectiveRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-objective-intent-alignment-governance",
            "version": "21.91",
            "governance_only": True,
            "objective_mutation_enabled": False,
            "instruction_mutation_enabled": False,
            "automatic_reprioritization_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentObjectiveCreate) -> AgentObjectiveRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = AgentObjectiveState.BLOCKED if "risk-brain-hard-block" in flags else AgentObjectiveState.EVIDENCE_READY
        record = AgentObjectiveRecord(
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

    def list(self, workspace_id: str) -> List[AgentObjectiveRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentObjectiveRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentObjectiveRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentObjectiveState.ASSESSED,
            "submit-review": AgentObjectiveState.REVIEW_REQUIRED,
            "approve": AgentObjectiveState.APPROVED,
            "activate": AgentObjectiveState.ACTIVE,
            "monitor": AgentObjectiveState.MONITORING,
            "suspend": AgentObjectiveState.SUSPENDED,
            "revoke": AgentObjectiveState.REVOKED,
            "archive": AgentObjectiveState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved objective/intent findings block approval")
        if action == "activate" and record.state != AgentObjectiveState.APPROVED:
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

    def _assess(self, payload: AgentObjectiveCreate):
        observations = payload.observations
        objective_alignment = mean(o.declared_objective_alignment for o in observations)
        instruction_integrity = mean(o.instruction_hierarchy_integrity for o in observations)
        constraint_assurance = mean(o.constraint_compliance for o in observations)
        priority_consistency = mean(o.priority_consistency for o in observations)
        human_intent = mean(o.human_intent_alignment for o in observations)
        policy_intent = mean(o.policy_intent_alignment for o in observations)
        cross_agent = mean(o.cross_agent_goal_consistency for o in observations)
        goal_stability = mean(o.goal_stability for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(mean([
            objective_alignment,
            instruction_integrity,
            constraint_assurance,
            priority_consistency,
            human_intent,
            policy_intent,
            cross_agent,
            goal_stability,
        ]) * confidence)

        aggregate_residual_risk = self._clamp(mean(
            (1 - o.declared_objective_alignment) * 0.15
            + (1 - o.instruction_hierarchy_integrity) * 0.10
            + (1 - o.constraint_compliance) * 0.15
            + (1 - o.priority_consistency) * 0.10
            + (1 - o.human_intent_alignment) * 0.15
            + (1 - o.policy_intent_alignment) * 0.10
            + (1 - o.cross_agent_goal_consistency) * 0.10
            + (1 - o.goal_stability) * 0.05
            + min(o.objective_drift_events / 5, 1) * 0.03
            + min(o.conflicting_instruction_events / 5, 1) * 0.02
            + min(o.constraint_breach_events / 5, 1) * 0.02
            + min(o.suspected_goal_hijack_events / 3, 1) * 0.03
            for o in observations
        ))

        scores = AgentObjectiveScores(
            objective_alignment=self._clamp(objective_alignment),
            instruction_integrity=self._clamp(instruction_integrity),
            constraint_assurance=self._clamp(constraint_assurance),
            priority_consistency=self._clamp(priority_consistency),
            human_intent_assurance=self._clamp(human_intent),
            policy_intent_assurance=self._clamp(policy_intent),
            cross_agent_goal_consistency=self._clamp(cross_agent),
            goal_stability=self._clamp(goal_stability),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentObjectiveDisposition] = []
        flags: List[str] = []
        for o in observations:
            required_actions: List[str] = []
            lifecycle = "aligned"
            residual = self._clamp(
                (1 - o.declared_objective_alignment) * 0.18
                + (1 - o.instruction_hierarchy_integrity) * 0.12
                + (1 - o.constraint_compliance) * 0.16
                + (1 - o.priority_consistency) * 0.10
                + (1 - o.human_intent_alignment) * 0.16
                + (1 - o.policy_intent_alignment) * 0.10
                + (1 - o.cross_agent_goal_consistency) * 0.08
                + (1 - o.goal_stability) * 0.05
                + min(o.suspected_goal_hijack_events / 3, 1) * 0.05
            )

            if o.objective_drift_events > 0 or o.declared_objective_alignment < payload.min_objective_alignment or o.goal_stability < payload.min_goal_stability:
                lifecycle = "objective-drift"
                required_actions.append("objective-drift-review")
                flags.append(f"objective-drift:{o.agent_id}:{o.objective_id}")

            if o.conflicting_instruction_events > 0 or o.human_intent_alignment < payload.min_human_intent_alignment:
                lifecycle = "intent-conflict"
                required_actions.append("intent-and-instruction-hierarchy-review")
                flags.append(f"intent-conflict:{o.agent_id}:{o.objective_id}")

            if o.constraint_breach_events > 0 or o.constraint_compliance < payload.min_constraint_compliance:
                lifecycle = "constraint-alert"
                required_actions.append("constraint-compliance-review")
                flags.append(f"constraint-alert:{o.agent_id}:{o.objective_id}")

            if o.priority_inversion_events > 0 or o.priority_consistency < 0.80:
                lifecycle = "priority-conflict"
                required_actions.append("priority-resolution-review")
                flags.append(f"priority-conflict:{o.agent_id}:{o.objective_id}")

            if o.suspected_goal_hijack_events > 0:
                lifecycle = "goal-hijack-alert"
                required_actions.append("goal-hijack-investigation")
                flags.append(f"goal-hijack-alert:{o.agent_id}:{o.objective_id}")

            if residual > payload.max_residual_risk:
                required_actions.append("agent-objective-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.objective_id}")

            if o.business_criticality >= 0.90 and (o.suspected_goal_hijack_events > 0 or o.constraint_breach_events > 0 or residual >= 0.60):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "goal-hijack-alert" if o.suspected_goal_hijack_events > 0 else "constraint-alert"

            dispositions.append(AgentObjectiveDisposition(
                agent_id=o.agent_id,
                objective_id=o.objective_id,
                alignment_score=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentObjectiveRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


agent_objective_intent_alignment_service = AgentObjectiveIntentAlignmentService()
