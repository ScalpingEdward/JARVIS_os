from __future__ import annotations

from statistics import mean
from typing import Dict, Set, Tuple
from uuid import uuid4

from app.schemas.execution_outcome_trust_feedback import (
    OutcomeTrustAction,
    OutcomeTrustCreate,
    OutcomeTrustFeedback,
    OutcomeTrustRecord,
    OutcomeTrustScores,
    OutcomeTrustState,
)


class ExecutionOutcomeTrustFeedbackService:
    PROTECTED_OPERATIONS = {
        "fund-movement",
        "order-submit",
        "trade-execute",
        "credential-mutate",
        "permission-escalate",
        "disable-safety-controls",
    }

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], OutcomeTrustRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: list[dict] = []

    def status(self) -> dict:
        return {
            "module": "execution-outcome-trust-scoring-learning-feedback-governance",
            "version": "21.132",
            "learning_feedback_enabled": True,
            "autonomous_policy_mutation_enabled": False,
            "autonomous_weight_mutation_enabled": False,
            "external_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def create(self, payload: OutcomeTrustCreate) -> OutcomeTrustRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        feedback: list[OutcomeTrustFeedback] = []
        flags: list[str] = []
        trust_values: list[float] = []
        residual_values: list[float] = []

        for observation in payload.observations:
            recommendations: list[str] = []
            if observation.operation.lower() in self.PROTECTED_OPERATIONS:
                flags.append("risk-brain-hard-block")
            if observation.attestation_state not in {"approved", "attested", "verified"}:
                flags.append(f"untrusted-attestation:{observation.attestation_record_id}")
            if not observation.receipt_reconciled:
                flags.append(f"receipt-not-reconciled:{observation.attestation_record_id}")
                recommendations.append("review-reconciliation-quality")
            if not observation.postconditions_passed:
                flags.append(f"postcondition-failure:{observation.attestation_record_id}")
                recommendations.append("review-planner-expectations")
            if not observation.no_prohibited_side_effects:
                flags.append("risk-brain-hard-block")
                recommendations.append("suspend-adapter-and-worker-review")

            trust = self._clamp(
                mean(
                    [
                        1.0 if observation.postconditions_passed else 0.0,
                        1.0 if observation.no_prohibited_side_effects else 0.0,
                        1.0 if observation.receipt_reconciled else 0.0,
                        observation.response_integrity,
                        observation.latency_quality,
                        observation.reliability_signal,
                        observation.evidence_confidence,
                        observation.freshness,
                    ]
                )
            )
            residual = self._clamp((1.0 - trust) * (0.5 + observation.criticality * 0.5))
            trust_values.append(trust)
            residual_values.append(residual)

            if trust < payload.min_trust_score:
                flags.append(f"low-trust:{observation.attestation_record_id}")
                recommendations.extend(
                    [
                        "reduce-adapter-preference",
                        "reduce-worker-preference",
                        "increase-human-review-priority",
                    ]
                )
            if residual > payload.max_residual_risk:
                flags.append(f"residual-risk-breach:{observation.attestation_record_id}")
                recommendations.append("risk-review-required")

            signal = "positive-feedback" if trust >= payload.min_trust_score and residual <= payload.max_residual_risk else "caution-feedback"
            feedback.append(
                OutcomeTrustFeedback(
                    adapter_id=observation.adapter_id,
                    worker_id=observation.worker_id,
                    policy_profile_id=observation.policy_profile_id,
                    planner_context_id=observation.planner_context_id,
                    trust_score=trust,
                    residual_risk=residual,
                    feedback_signal=signal,
                    recommendations=sorted(set(recommendations)),
                )
            )

        aggregate_trust = self._clamp(mean(trust_values))
        aggregate_risk = self._clamp(mean(residual_values))
        scores = OutcomeTrustScores(
            execution_trust=aggregate_trust,
            adapter_reliability=aggregate_trust,
            worker_reliability=aggregate_trust,
            policy_quality=aggregate_trust,
            planner_feedback_quality=aggregate_trust,
            aggregate_residual_risk=aggregate_risk,
        )

        state = OutcomeTrustState.BLOCKED if "risk-brain-hard-block" in flags else OutcomeTrustState.EVIDENCE_READY
        record = OutcomeTrustRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            feedback=feedback,
            risk_flags=sorted(set(flags)),
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit.append({"workspace_id": payload.workspace_id, "record_id": record.record_id, "action": "create", "actor": payload.requested_by})
        return record

    def list(self, workspace_id: str) -> list[OutcomeTrustRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> OutcomeTrustRecord:
        key = (workspace_id, record_id)
        if key not in self._records:
            raise KeyError("record not found")
        return self._records[key]

    def act(self, record_id: str, payload: OutcomeTrustAction) -> OutcomeTrustRecord:
        op_key = (payload.workspace_id, payload.operation_id)
        if op_key in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(payload.workspace_id, record_id)
        transitions = {
            "score": OutcomeTrustState.SCORED,
            "submit-review": OutcomeTrustState.REVIEW_REQUIRED,
            "approve": OutcomeTrustState.APPROVED,
            "activate": OutcomeTrustState.ACTIVE,
            "suspend": OutcomeTrustState.SUSPENDED,
            "revoke": OutcomeTrustState.REVOKED,
            "archive": OutcomeTrustState.ARCHIVED,
        }
        if payload.action not in transitions:
            raise ValueError("unsupported action")
        if payload.action == "approve" and record.risk_flags:
            raise ValueError("unresolved trust findings block approval")
        if payload.action == "activate" and record.state != OutcomeTrustState.APPROVED:
            raise ValueError("human approval required before activation")

        record = record.model_copy(
            update={
                "state": transitions[payload.action],
                "approved_by": payload.actor if payload.action == "approve" else record.approved_by,
                "version": record.version + 1,
            }
        )
        self._records[(payload.workspace_id, record_id)] = record
        self._operations.add(op_key)
        self._audit.append({"workspace_id": payload.workspace_id, "record_id": record_id, "action": payload.action, "actor": payload.actor, "operation_id": payload.operation_id, "reason": payload.reason})
        return record

    def audit(self, workspace_id: str) -> list[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]


execution_outcome_trust_feedback_service = ExecutionOutcomeTrustFeedbackService()
