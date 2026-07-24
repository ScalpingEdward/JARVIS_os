from __future__ import annotations

from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_operational_optimization_recommendation import (
    OptimizationCreate,
    OptimizationDisposition,
    OptimizationRecord,
    OptimizationScores,
    OptimizationState,
)


class AgentOperationalOptimizationRecommendationService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], OptimizationRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: list[dict] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-operational-optimization-recommendation-governance",
            "version": "21.110",
            "governance_only": True,
            "automatic_tuning_enabled": False,
            "autoscaling_enabled": False,
            "configuration_mutation_enabled": False,
            "deployment_enabled": False,
            "traffic_shift_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: OptimizationCreate) -> OptimizationRecord:
        source_key = (payload.workspace_id, payload.source_key)
        if source_key in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = OptimizationState.BLOCKED if "risk-brain-hard-block" in flags else OptimizationState.EVIDENCE_READY
        record = OptimizationRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            dispositions=dispositions,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_key)
        self._audit.append({"workspace_id": payload.workspace_id, "record_id": record.record_id, "action": "create", "actor": payload.requested_by})
        return record

    def list(self, workspace_id: str) -> List[OptimizationRecord]:
        return [record for (ws, _), record in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> OptimizationRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> OptimizationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": OptimizationState.ASSESSED,
            "submit-review": OptimizationState.REVIEW_REQUIRED,
            "approve": OptimizationState.APPROVED,
            "publish-advisory": OptimizationState.ADVISORY_READY,
            "monitor": OptimizationState.MONITORING,
            "suspend": OptimizationState.SUSPENDED,
            "revoke": OptimizationState.REVOKED,
            "archive": OptimizationState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved optimization findings block approval")
        if action in {"publish-advisory", "monitor"} and record.state not in {
            OptimizationState.APPROVED,
            OptimizationState.ADVISORY_READY,
            OptimizationState.MONITORING,
        }:
            raise ValueError("human approval required before advisory publication")
        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._audit.append({"workspace_id": workspace_id, "record_id": record_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason})
        return updated

    def audit(self, workspace_id: str) -> list[dict]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _assess(self, payload: OptimizationCreate):
        observations = payload.observations
        value = mean(mean([o.performance_gain_confidence, o.cost_reduction_confidence, o.resource_efficiency_gain]) for o in observations)
        safety = mean(o.reliability_impact for o in observations)
        reversibility = mean(mean([o.reversibility, o.rollback_readiness]) for o in observations)
        validation = mean(mean([o.validation_coverage, o.observability_readiness, o.dependency_impact_clarity, o.human_review_coverage]) for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)
        aggregate = self._clamp(mean([value, safety, reversibility, validation]) * confidence)
        dispositions: List[OptimizationDisposition] = []
        flags: List[str] = []
        risks: List[float] = []

        for o in observations:
            actions: List[str] = []
            signal = "advisory-ready"
            value_score = self._clamp(mean([o.performance_gain_confidence, o.cost_reduction_confidence, o.resource_efficiency_gain]))
            residual = self._clamp(
                (1 - o.reliability_impact) * 0.20
                + (1 - o.reversibility) * 0.15
                + (1 - o.validation_coverage) * 0.15
                + (1 - o.observability_readiness) * 0.10
                + (1 - o.rollback_readiness) * 0.12
                + (1 - o.dependency_impact_clarity) * 0.10
                + (1 - o.human_review_coverage) * 0.08
                + min(o.unresolved_validation_findings / 3, 1) * 0.04
                + min(o.dependency_risk_findings / 3, 1) * 0.03
                + min(o.rollback_failures / 2, 1) * 0.03
            )
            risks.append(residual)
            if o.validation_coverage < payload.min_validation or o.unresolved_validation_findings:
                signal = "validation-alert"
                actions.append("optimization-validation-review")
                flags.append(f"validation-alert:{o.agent_id}:{o.recommendation_id}")
            if o.reversibility < payload.min_reversibility or o.rollback_readiness < payload.min_reversibility or o.rollback_failures:
                signal = "rollback-alert"
                actions.append("reversibility-and-rollback-review")
                flags.append(f"rollback-alert:{o.agent_id}:{o.recommendation_id}")
            if o.dependency_risk_findings or o.dependency_impact_clarity < payload.min_validation:
                signal = "dependency-alert"
                actions.append("dependency-impact-review")
                flags.append(f"dependency-alert:{o.agent_id}:{o.recommendation_id}")
            if o.human_review_coverage < payload.min_human_review:
                signal = "governance-alert"
                actions.append("human-review-coverage-review")
                flags.append(f"governance-alert:{o.agent_id}:{o.recommendation_id}")
            if residual > payload.max_residual_risk:
                actions.append("operational-optimization-risk-committee")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.recommendation_id}")
            if o.criticality >= 0.90 and (o.rollback_failures > 0 or o.unresolved_validation_findings > 1 or residual >= 0.60):
                signal = "blocked"
                actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
            dispositions.append(OptimizationDisposition(
                agent_id=o.agent_id,
                agent_version=o.agent_version,
                recommendation_id=o.recommendation_id,
                value_score=value_score,
                assurance=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=signal,
                required_actions=sorted(set(actions)),
            ))

        scores = OptimizationScores(
            value_assurance=self._clamp(value),
            safety_assurance=self._clamp(safety),
            reversibility_assurance=self._clamp(reversibility),
            validation_assurance=self._clamp(validation),
            aggregate_assurance=aggregate,
            aggregate_residual_risk=self._clamp(mean(risks)),
            confidence=self._clamp(confidence),
        )
        return scores, dispositions, sorted(set(flags))


agent_operational_optimization_recommendation_service = AgentOperationalOptimizationRecommendationService()
