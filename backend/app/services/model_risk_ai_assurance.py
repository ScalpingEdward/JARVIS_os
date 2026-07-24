from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.model_risk_ai_assurance import (
    ModelAssuranceState,
    ModelDisposition,
    ModelRiskAssuranceCreate,
    ModelRiskAssuranceRecord,
    ModelRiskAssuranceScores,
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


class ModelRiskAIAssuranceService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ModelRiskAssuranceRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "model-risk-ai-assurance",
            "version": "21.80",
            "governance_only": True,
            "model_mutation_enabled": False,
            "deployment_mutation_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ModelRiskAssuranceCreate) -> ModelRiskAssuranceRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = ModelAssuranceState.BLOCKED if "risk-brain-hard-block" in flags else ModelAssuranceState.EVIDENCE_READY
        record = ModelRiskAssuranceRecord(
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

    def list(self, workspace_id: str) -> List[ModelRiskAssuranceRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ModelRiskAssuranceRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> ModelRiskAssuranceRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": ModelAssuranceState.ASSESSED,
            "submit-review": ModelAssuranceState.REVIEW_REQUIRED,
            "approve": ModelAssuranceState.APPROVED,
            "activate": ModelAssuranceState.ACTIVE,
            "monitor": ModelAssuranceState.MONITORING,
            "suspend": ModelAssuranceState.SUSPENDED,
            "revoke": ModelAssuranceState.REVOKED,
            "archive": ModelAssuranceState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved model-risk flags block approval")
        if action == "activate" and record.state != ModelAssuranceState.APPROVED:
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

    def _assess(self, payload: ModelRiskAssuranceCreate):
        observations = payload.observations
        validation_strength = mean(o.validation_coverage for o in observations)
        performance_resilience = mean((o.performance_stability + o.calibration_quality + o.robustness_score) / 3 for o in observations)
        explainability_strength = mean((o.explainability_coverage + o.human_oversight_coverage) / 2 for o in observations)
        fairness_integrity = mean(o.fairness_score for o in observations)
        data_governance_quality = mean(o.data_quality_score for o in observations)
        operational_resilience = mean((o.fallback_readiness + (1 - min(o.incident_count / 10, 1))) / 2 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(mean([
            validation_strength,
            performance_resilience,
            explainability_strength,
            fairness_integrity,
            data_governance_quality,
            operational_resilience,
        ]) * confidence)
        aggregate_residual_risk = self._clamp(mean(
            (1 - o.validation_coverage) * 0.20
            + (1 - o.performance_stability) * 0.15
            + o.drift_score * 0.20
            + (1 - o.explainability_coverage) * 0.15
            + (1 - o.fairness_score) * 0.10
            + (1 - o.data_quality_score) * 0.10
            + (1 - o.fallback_readiness) * 0.10
            for o in observations
        ))

        scores = ModelRiskAssuranceScores(
            validation_strength=self._clamp(validation_strength),
            performance_resilience=self._clamp(performance_resilience),
            explainability_strength=self._clamp(explainability_strength),
            fairness_integrity=self._clamp(fairness_integrity),
            data_governance_quality=self._clamp(data_governance_quality),
            operational_resilience=self._clamp(operational_resilience),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[ModelDisposition] = []
        flags: List[str] = []
        for observation in observations:
            required_actions: List[str] = []
            lifecycle = "assured"
            residual = self._clamp(
                (1 - observation.validation_coverage) * 0.25
                + observation.drift_score * 0.25
                + (1 - observation.explainability_coverage) * 0.15
                + (1 - observation.fairness_score) * 0.10
                + (1 - observation.data_quality_score) * 0.15
                + min(observation.open_validation_findings / 10, 1) * 0.10
            )
            assurance = self._clamp(1 - residual)

            if observation.validation_coverage < payload.required_validation_coverage or observation.open_validation_findings > 0:
                lifecycle = "validation-required"
                required_actions.append("independent-model-validation")
                flags.append(f"validation-gap:{observation.model_id}")
            if observation.drift_score >= 0.35:
                lifecycle = "drift-alert"
                required_actions.append("drift-investigation")
                flags.append(f"drift-alert:{observation.model_id}")
            if observation.fairness_score < 0.70:
                lifecycle = "bias-alert"
                required_actions.append("fairness-review")
                flags.append(f"bias-alert:{observation.model_id}")
            if observation.explainability_coverage < 0.65:
                lifecycle = "explainability-gap"
                required_actions.append("explainability-remediation")
                flags.append(f"explainability-gap:{observation.model_id}")
            if observation.data_quality_score < 0.70:
                lifecycle = "data-quality-alert"
                required_actions.append("data-lineage-and-quality-review")
                flags.append(f"data-quality-alert:{observation.model_id}")
            if residual > payload.max_acceptable_risk:
                required_actions.append("model-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{observation.model_id}")
            if observation.business_criticality >= 0.90 and residual >= 0.60:
                lifecycle = "validation-failure"
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(ModelDisposition(
                model_id=observation.model_id,
                model_version=observation.model_version,
                assurance_score=assurance,
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: ModelRiskAssuranceRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


model_risk_ai_assurance_service = ModelRiskAIAssuranceService()
