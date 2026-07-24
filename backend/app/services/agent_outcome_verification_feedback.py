from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_outcome_verification_feedback import (
    AgentOutcomeDisposition,
    AgentOutcomeVerificationCreate,
    AgentOutcomeVerificationRecord,
    AgentOutcomeVerificationScores,
    AgentOutcomeVerificationState,
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


class AgentOutcomeVerificationFeedbackService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentOutcomeVerificationRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-outcome-verification-feedback-governance",
            "version": "21.93",
            "governance_only": True,
            "feedback_mutation_enabled": False,
            "automatic_learning_enabled": False,
            "decision_mutation_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentOutcomeVerificationCreate) -> AgentOutcomeVerificationRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = (
            AgentOutcomeVerificationState.BLOCKED
            if "risk-brain-hard-block" in flags
            else AgentOutcomeVerificationState.EVIDENCE_READY
        )
        record = AgentOutcomeVerificationRecord(
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

    def list(self, workspace_id: str) -> List[AgentOutcomeVerificationRecord]:
        return [r for (workspace, _), r in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentOutcomeVerificationRecord:
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
    ) -> AgentOutcomeVerificationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentOutcomeVerificationState.ASSESSED,
            "submit-review": AgentOutcomeVerificationState.REVIEW_REQUIRED,
            "approve": AgentOutcomeVerificationState.APPROVED,
            "activate": AgentOutcomeVerificationState.ACTIVE,
            "monitor": AgentOutcomeVerificationState.MONITORING,
            "suspend": AgentOutcomeVerificationState.SUSPENDED,
            "revoke": AgentOutcomeVerificationState.REVOKED,
            "archive": AgentOutcomeVerificationState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved outcome-verification findings block approval")
        if action == "activate" and record.state != AgentOutcomeVerificationState.APPROVED:
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

    def _assess(self, payload: AgentOutcomeVerificationCreate):
        observations = payload.observations
        outcome_fidelity = mean(1 - abs(o.expected_outcome_score - o.observed_outcome_score) for o in observations)
        kpi_assurance = mean(o.kpi_attainment_score for o in observations)
        evidence_assurance = mean(o.evidence_quality_score for o in observations)
        feedback_assurance = mean(o.feedback_coverage_score for o in observations)
        causal_assurance = mean(o.causal_attribution_score for o in observations)
        regression_assurance = mean(o.regression_detection_score for o in observations)
        learning_assurance = mean((o.learning_traceability_score + o.rollback_readiness_score + o.human_review_coverage) / 3 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(
            mean([
                outcome_fidelity,
                kpi_assurance,
                evidence_assurance,
                feedback_assurance,
                causal_assurance,
                regression_assurance,
                learning_assurance,
            ]) * confidence
        )

        aggregate_residual_risk = self._clamp(
            mean(
                abs(o.expected_outcome_score - o.observed_outcome_score) * 0.20
                + (1 - o.kpi_attainment_score) * 0.15
                + (1 - o.evidence_quality_score) * 0.10
                + (1 - o.feedback_coverage_score) * 0.10
                + (1 - o.causal_attribution_score) * 0.10
                + min(o.adverse_outcomes / 5, 1) * 0.10
                + min(o.missed_kpis / 5, 1) * 0.10
                + min(o.repeated_regressions / 3, 1) * 0.10
                + min(o.unreviewed_feedback_items / 10, 1) * 0.05
                for o in observations
            )
        )

        scores = AgentOutcomeVerificationScores(
            outcome_fidelity=self._clamp(outcome_fidelity),
            kpi_assurance=self._clamp(kpi_assurance),
            evidence_assurance=self._clamp(evidence_assurance),
            feedback_assurance=self._clamp(feedback_assurance),
            causal_assurance=self._clamp(causal_assurance),
            regression_assurance=self._clamp(regression_assurance),
            learning_assurance=self._clamp(learning_assurance),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentOutcomeDisposition] = []
        flags: List[str] = []
        for o in observations:
            required_actions: List[str] = []
            lifecycle = "verified"
            outcome_gap = abs(o.expected_outcome_score - o.observed_outcome_score)
            residual = self._clamp(
                outcome_gap * 0.25
                + (1 - o.kpi_attainment_score) * 0.15
                + (1 - o.evidence_quality_score) * 0.10
                + (1 - o.feedback_coverage_score) * 0.10
                + (1 - o.causal_attribution_score) * 0.10
                + (1 - o.regression_detection_score) * 0.10
                + (1 - o.learning_traceability_score) * 0.10
                + min(o.adverse_outcomes / 5, 1) * 0.05
                + min(o.repeated_regressions / 3, 1) * 0.05
            )

            if outcome_gap > payload.max_outcome_gap:
                lifecycle = "outcome-drift"
                required_actions.append("expected-vs-observed-outcome-review")
                flags.append(f"outcome-drift:{o.agent_id}:{o.decision_id}")
            if o.feedback_coverage_score < payload.min_feedback_coverage or o.unreviewed_feedback_items > 0:
                lifecycle = "feedback-gap"
                required_actions.append("feedback-coverage-and-review")
                flags.append(f"feedback-gap:{o.agent_id}:{o.decision_id}")
            if o.kpi_attainment_score < payload.min_kpi_attainment or o.missed_kpis > 0:
                lifecycle = "kpi-alert"
                required_actions.append("kpi-performance-review")
                flags.append(f"kpi-alert:{o.agent_id}:{o.decision_id}")
            if o.repeated_regressions > 0 or o.regression_detection_score < 0.80:
                lifecycle = "regression-alert"
                required_actions.append("regression-and-rollback-review")
                flags.append(f"regression-alert:{o.agent_id}:{o.decision_id}")
            if o.learning_traceability_score < 0.80 or o.human_review_coverage < 0.90:
                lifecycle = "learning-alert"
                required_actions.append("learning-traceability-human-review")
                flags.append(f"learning-alert:{o.agent_id}:{o.decision_id}")
            if o.evidence_quality_score < payload.min_evidence_quality:
                required_actions.append("outcome-evidence-quality-review")
                flags.append(f"evidence-gap:{o.agent_id}:{o.decision_id}")
            if residual > payload.max_residual_risk:
                required_actions.append("agent-outcome-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.decision_id}")
            if o.business_criticality >= 0.90 and (
                o.adverse_outcomes > 0 or o.repeated_regressions >= 2 or residual >= 0.60
            ):
                lifecycle = "regression-alert"
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(
                AgentOutcomeDisposition(
                    agent_id=o.agent_id,
                    decision_id=o.decision_id,
                    assurance_score=self._clamp(1 - residual),
                    residual_risk=residual,
                    lifecycle_signal=lifecycle,
                    required_actions=sorted(set(required_actions)),
                )
            )

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: AgentOutcomeVerificationRecord,
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


agent_outcome_verification_feedback_service = AgentOutcomeVerificationFeedbackService()
