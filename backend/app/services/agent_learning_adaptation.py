from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_learning_adaptation import (
    AgentLearningCreate,
    AgentLearningRecord,
    AgentLearningScores,
    AgentLearningState,
    LearningDisposition,
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


class AgentLearningAdaptationService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentLearningRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-learning-adaptation-governance",
            "version": "21.94",
            "governance_only": True,
            "automatic_learning_enabled": False,
            "model_mutation_enabled": False,
            "memory_mutation_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentLearningCreate) -> AgentLearningRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = AgentLearningState.BLOCKED if "risk-brain-hard-block" in flags else AgentLearningState.EVIDENCE_READY
        record = AgentLearningRecord(
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

    def list(self, workspace_id: str) -> List[AgentLearningRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentLearningRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentLearningRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentLearningState.ASSESSED,
            "submit-review": AgentLearningState.REVIEW_REQUIRED,
            "approve": AgentLearningState.APPROVED,
            "activate": AgentLearningState.ACTIVE,
            "monitor": AgentLearningState.MONITORING,
            "suspend": AgentLearningState.SUSPENDED,
            "revoke": AgentLearningState.REVOKED,
            "archive": AgentLearningState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved learning/adaptation findings block approval")
        if action == "activate" and record.state != AgentLearningState.APPROVED:
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

    def _assess(self, payload: AgentLearningCreate):
        observations = payload.observations
        evidence = mean(o.evidence_quality for o in observations)
        outcome = mean(o.outcome_support for o in observations)
        causal = mean(o.causal_confidence for o in observations)
        generalization = mean(o.generalization_score for o in observations)
        safety = mean(o.safety_validation_score for o in observations)
        regression = mean(o.regression_test_coverage for o in observations)
        rollback = mean(o.rollback_readiness for o in observations)
        governance = mean((o.human_review_coverage + o.provenance_coverage) / 2 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(mean([evidence, outcome, causal, generalization, safety, regression, rollback, governance]) * confidence)
        aggregate_residual_risk = self._clamp(mean(
            (1 - o.evidence_quality) * 0.12
            + (1 - o.outcome_support) * 0.10
            + (1 - o.causal_confidence) * 0.10
            + (1 - o.generalization_score) * 0.15
            + (1 - o.safety_validation_score) * 0.18
            + (1 - o.regression_test_coverage) * 0.10
            + (1 - o.rollback_readiness) * 0.10
            + min(o.failed_regressions / 3, 1) * 0.05
            + min(o.safety_failures / 3, 1) * 0.05
            + min(o.overfit_indicators / 3, 1) * 0.05
            for o in observations
        ))

        scores = AgentLearningScores(
            evidence_assurance=self._clamp(evidence),
            outcome_assurance=self._clamp(outcome),
            causal_assurance=self._clamp(causal),
            generalization_assurance=self._clamp(generalization),
            safety_assurance=self._clamp(safety),
            regression_assurance=self._clamp(regression),
            rollback_assurance=self._clamp(rollback),
            governance_assurance=self._clamp(governance),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[LearningDisposition] = []
        flags: List[str] = []
        for o in observations:
            required_actions: List[str] = []
            lifecycle = "adaptation-ready"
            residual = self._clamp(
                (1 - o.evidence_quality) * 0.15
                + (1 - o.generalization_score) * 0.18
                + (1 - o.safety_validation_score) * 0.22
                + (1 - o.regression_test_coverage) * 0.12
                + (1 - o.rollback_readiness) * 0.13
                + min(o.failed_regressions / 3, 1) * 0.07
                + min(o.safety_failures / 3, 1) * 0.08
                + min(o.overfit_indicators / 3, 1) * 0.05
            )

            if o.evidence_quality < payload.min_evidence_quality or o.outcome_support < 0.80:
                lifecycle = "evidence-gap"
                required_actions.append("evidence-and-outcome-review")
                flags.append(f"evidence-gap:{o.agent_id}:{o.adaptation_id}")
            if o.generalization_score < payload.min_generalization_score or o.overfit_indicators > 0:
                lifecycle = "overfit-alert"
                required_actions.append("generalization-and-overfit-review")
                flags.append(f"overfit-alert:{o.agent_id}:{o.adaptation_id}")
            if o.failed_regressions > 0 or o.regression_test_coverage < 0.85:
                lifecycle = "regression-alert"
                required_actions.append("regression-validation-review")
                flags.append(f"regression-alert:{o.agent_id}:{o.adaptation_id}")
            if o.safety_failures > 0 or o.safety_validation_score < payload.min_safety_validation_score:
                lifecycle = "safety-alert"
                required_actions.append("safety-validation-review")
                flags.append(f"safety-alert:{o.agent_id}:{o.adaptation_id}")
            if o.rollback_failures > 0 or o.rollback_readiness < payload.min_rollback_readiness:
                lifecycle = "rollback-alert"
                required_actions.append("rollback-readiness-review")
                flags.append(f"rollback-alert:{o.agent_id}:{o.adaptation_id}")
            if residual > payload.max_residual_risk:
                required_actions.append("agent-learning-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.adaptation_id}")
            if o.business_criticality >= 0.90 and (o.safety_failures > 0 or o.rollback_failures > 0 or residual >= 0.60):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "safety-alert"

            dispositions.append(LearningDisposition(
                agent_id=o.agent_id,
                adaptation_id=o.adaptation_id,
                assurance_score=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentLearningRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


agent_learning_adaptation_service = AgentLearningAdaptationService()
