from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_decision_explainability_accountability import (
    AgentDecisionAccountabilityCreate,
    AgentDecisionAccountabilityRecord,
    AgentDecisionAccountabilityScores,
    AgentDecisionAccountabilityState,
    AgentDecisionDisposition,
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


class AgentDecisionExplainabilityAccountabilityService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentDecisionAccountabilityRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-decision-explainability-accountability-governance",
            "version": "21.92",
            "governance_only": True,
            "decision_mutation_enabled": False,
            "automatic_override_enabled": False,
            "agent_execution_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentDecisionAccountabilityCreate) -> AgentDecisionAccountabilityRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = AgentDecisionAccountabilityState.BLOCKED if "risk-brain-hard-block" in flags else AgentDecisionAccountabilityState.EVIDENCE_READY
        record = AgentDecisionAccountabilityRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AgentDecisionAccountabilityRecord]:
        return [r for (workspace, _), r in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentDecisionAccountabilityRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentDecisionAccountabilityRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentDecisionAccountabilityState.ASSESSED,
            "submit-review": AgentDecisionAccountabilityState.REVIEW_REQUIRED,
            "approve": AgentDecisionAccountabilityState.APPROVED,
            "activate": AgentDecisionAccountabilityState.ACTIVE,
            "monitor": AgentDecisionAccountabilityState.MONITORING,
            "suspend": AgentDecisionAccountabilityState.SUSPENDED,
            "revoke": AgentDecisionAccountabilityState.REVOKED,
            "archive": AgentDecisionAccountabilityState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved explainability/accountability findings block approval")
        if action == "activate" and record.state != AgentDecisionAccountabilityState.APPROVED:
            raise ValueError("human approval required before activation")
        updated = record.model_copy(update={"state": transitions[action], "approved_by": actor if action == "approve" else record.approved_by, "version": record.version + 1})
        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._append_audit(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _assess(self, payload: AgentDecisionAccountabilityCreate):
        obs = payload.observations
        rationale = mean(o.rationale_completeness for o in obs)
        evidence = mean(o.evidence_coverage for o in obs)
        traceability = mean(o.source_traceability for o in obs)
        uncertainty = mean((o.counterfactual_quality + o.uncertainty_disclosure) / 2 for o in obs)
        policy = mean(o.policy_reference_coverage for o in obs)
        human = mean(o.human_owner_coverage for o in obs)
        reviewability = mean((o.reviewability_score + o.override_traceability + o.reproducibility_score) / 3 for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([rationale, evidence, traceability, uncertainty, policy, human, reviewability]) * confidence)
        residual = self._clamp(mean(
            (1-o.rationale_completeness)*0.15 + (1-o.evidence_coverage)*0.15 + (1-o.source_traceability)*0.15 +
            (1-o.uncertainty_disclosure)*0.10 + (1-o.policy_reference_coverage)*0.10 + (1-o.human_owner_coverage)*0.10 +
            (1-o.reviewability_score)*0.10 + min(o.missing_evidence_count/5,1)*0.05 + min(o.untraceable_sources/5,1)*0.05 +
            min(o.undocumented_overrides/3,1)*0.05 for o in obs
        ))
        scores = AgentDecisionAccountabilityScores(
            rationale_assurance=self._clamp(rationale), evidence_assurance=self._clamp(evidence), traceability_assurance=self._clamp(traceability),
            uncertainty_assurance=self._clamp(uncertainty), policy_accountability=self._clamp(policy), human_accountability=self._clamp(human),
            reviewability_assurance=self._clamp(reviewability), aggregate_assurance=aggregate, aggregate_residual_risk=residual, confidence=self._clamp(confidence),
        )
        dispositions: List[AgentDecisionDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            lifecycle = "explainable"
            item_residual = self._clamp(
                (1-o.rationale_completeness)*0.18 + (1-o.evidence_coverage)*0.16 + (1-o.source_traceability)*0.16 +
                (1-o.uncertainty_disclosure)*0.10 + (1-o.policy_reference_coverage)*0.10 + (1-o.human_owner_coverage)*0.10 +
                (1-o.reviewability_score)*0.10 + min(o.undocumented_overrides/3,1)*0.10
            )
            if o.rationale_completeness < payload.min_rationale_completeness:
                lifecycle = "rationale-gap"; actions.append("decision-rationale-review"); flags.append(f"rationale-gap:{o.agent_id}:{o.decision_id}")
            if o.evidence_coverage < payload.min_evidence_coverage or o.missing_evidence_count > 0:
                lifecycle = "evidence-gap"; actions.append("decision-evidence-review"); flags.append(f"evidence-gap:{o.agent_id}:{o.decision_id}")
            if o.source_traceability < payload.min_traceability or o.untraceable_sources > 0:
                lifecycle = "traceability-alert"; actions.append("source-traceability-review"); flags.append(f"traceability-alert:{o.agent_id}:{o.decision_id}")
            if o.human_owner_coverage < payload.min_human_owner_coverage or o.unresolved_challenges > 0:
                lifecycle = "accountability-alert"; actions.append("human-accountability-review"); flags.append(f"accountability-alert:{o.agent_id}:{o.decision_id}")
            if o.undocumented_overrides > 0 or o.override_traceability < 0.85:
                lifecycle = "override-alert"; actions.append("override-traceability-review"); flags.append(f"override-alert:{o.agent_id}:{o.decision_id}")
            if item_residual > payload.max_residual_risk:
                actions.append("agent-decision-risk-committee-escalation"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.decision_id}")
            if o.business_criticality >= 0.90 and (o.undocumented_overrides > 0 or o.untraceable_sources > 0 or item_residual >= 0.60):
                actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block")
            dispositions.append(AgentDecisionDisposition(agent_id=o.agent_id, decision_id=o.decision_id, assurance_score=self._clamp(1-item_residual), residual_risk=item_residual, lifecycle_signal=lifecycle, required_actions=sorted(set(actions))))
        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentDecisionAccountabilityRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id, action=action, actor=actor, operation_id=operation_id, timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {}))


agent_decision_explainability_accountability_service = AgentDecisionExplainabilityAccountabilityService()
