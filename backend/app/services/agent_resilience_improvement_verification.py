from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_resilience_improvement_verification import (
    AgentResilienceImprovementCreate,
    AgentResilienceImprovementDisposition,
    AgentResilienceImprovementRecord,
    AgentResilienceImprovementScores,
    AgentResilienceImprovementState,
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


class AgentResilienceImprovementVerificationService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentResilienceImprovementRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-resilience-improvement-verification-governance",
            "version": "21.100",
            "governance_only": True,
            "automatic_remediation_enabled": False,
            "automatic_chaos_execution_enabled": False,
            "automatic_failover_enabled": False,
            "automatic_recovery_enabled": False,
            "deployment_execution_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentResilienceImprovementCreate) -> AgentResilienceImprovementRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = AgentResilienceImprovementState.BLOCKED if "risk-brain-hard-block" in flags else AgentResilienceImprovementState.EVIDENCE_READY
        record = AgentResilienceImprovementRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AgentResilienceImprovementRecord]:
        return [r for (workspace, _), r in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentResilienceImprovementRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentResilienceImprovementRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentResilienceImprovementState.ASSESSED,
            "submit-review": AgentResilienceImprovementState.REVIEW_REQUIRED,
            "approve": AgentResilienceImprovementState.APPROVED,
            "activate": AgentResilienceImprovementState.ACTIVE,
            "monitor": AgentResilienceImprovementState.MONITORING,
            "verify": AgentResilienceImprovementState.VERIFIED,
            "suspend": AgentResilienceImprovementState.SUSPENDED,
            "revoke": AgentResilienceImprovementState.REVOKED,
            "archive": AgentResilienceImprovementState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved resilience-improvement findings block approval")
        if action in {"activate", "monitor", "verify"} and record.state not in {
            AgentResilienceImprovementState.APPROVED,
            AgentResilienceImprovementState.ACTIVE,
            AgentResilienceImprovementState.MONITORING,
            AgentResilienceImprovementState.VERIFIED,
        }:
            raise ValueError("human approval required before governed verification state")
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
        return [e for e in self._audit if e.workspace_id == workspace_id]

    def _assess(self, payload: AgentResilienceImprovementCreate):
        observations = payload.observations
        control = mean(o.control_implementation_score for o in observations)
        resilience = mean((o.resilience_test_coverage + o.chaos_test_readiness) / 2 for o in observations)
        failover_recovery = mean((o.failover_validation_score + o.recovery_validation_score) / 2 for o in observations)
        observability = mean(o.observability_validation_score for o in observations)
        dependency = mean(o.dependency_resilience_score for o in observations)
        regression = mean(o.regression_coverage for o in observations)
        recurrence = mean(o.recurrence_prevention_confidence for o in observations)
        confidence = mean(o.confidence * o.freshness * o.evidence_quality for o in observations)
        aggregate = self._clamp(mean([control, resilience, failover_recovery, observability, dependency, regression, recurrence]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.control_implementation_score)*0.14 + (1-o.resilience_test_coverage)*0.10 +
            (1-o.failover_validation_score)*0.10 + (1-o.recovery_validation_score)*0.10 +
            (1-o.observability_validation_score)*0.06 + (1-o.dependency_resilience_score)*0.08 +
            (1-o.regression_coverage)*0.10 + (1-o.recurrence_prevention_confidence)*0.12 +
            min(o.unresolved_control_gaps/3,1)*0.08 + min(o.failed_resilience_tests/3,1)*0.04 +
            min(o.regression_failures/3,1)*0.04 + min(o.repeat_incident_count/3,1)*0.04
            for o in observations
        ))
        scores = AgentResilienceImprovementScores(
            control_assurance=self._clamp(control), resilience_assurance=self._clamp(resilience),
            failover_recovery_assurance=self._clamp(failover_recovery), observability_assurance=self._clamp(observability),
            dependency_assurance=self._clamp(dependency), regression_assurance=self._clamp(regression),
            recurrence_assurance=self._clamp(recurrence), aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk, confidence=self._clamp(confidence),
        )
        dispositions: List[AgentResilienceImprovementDisposition] = []
        flags: List[str] = []
        for o in observations:
            actions: List[str] = []
            lifecycle = "verified"
            residual = self._clamp(
                (1-o.control_implementation_score)*0.16 + (1-o.resilience_test_coverage)*0.10 +
                (1-o.chaos_test_readiness)*0.06 + (1-o.failover_validation_score)*0.10 +
                (1-o.recovery_validation_score)*0.10 + (1-o.observability_validation_score)*0.06 +
                (1-o.dependency_resilience_score)*0.08 + (1-o.regression_coverage)*0.10 +
                (1-o.recurrence_prevention_confidence)*0.12 + min(o.unresolved_control_gaps/3,1)*0.06 +
                min(o.repeat_incident_count/3,1)*0.06
            )
            if o.control_implementation_score < payload.min_control_implementation or o.unresolved_control_gaps > 0:
                lifecycle = "control-alert"; actions.append("control-implementation-review"); flags.append(f"control-alert:{o.agent_id}:{o.improvement_id}")
            if o.resilience_test_coverage < payload.min_resilience_validation or o.failed_resilience_tests > 0:
                lifecycle = "resilience-alert"; actions.append("resilience-and-chaos-test-review"); flags.append(f"resilience-alert:{o.agent_id}:{o.improvement_id}")
            if min(o.failover_validation_score, o.recovery_validation_score) < payload.min_resilience_validation or o.failed_failover_tests > 0 or o.failed_recovery_tests > 0:
                lifecycle = "validation-alert"; actions.append("failover-and-recovery-validation-review"); flags.append(f"validation-alert:{o.agent_id}:{o.improvement_id}")
            if o.regression_coverage < payload.min_regression_coverage or o.regression_failures > 0:
                lifecycle = "regression-alert"; actions.append("regression-validation-review"); flags.append(f"regression-alert:{o.agent_id}:{o.improvement_id}")
            if o.recurrence_prevention_confidence < payload.min_recurrence_prevention or o.repeat_incident_count > 0:
                lifecycle = "recurrence-alert"; actions.append("recurrence-prevention-review"); flags.append(f"recurrence-alert:{o.agent_id}:{o.improvement_id}")
            if residual > payload.max_residual_risk:
                actions.append("agent-resilience-improvement-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.improvement_id}")
            if o.business_criticality >= 0.90 and (o.unresolved_control_gaps > 0 or o.failed_failover_tests > 0 or o.failed_recovery_tests > 0 or o.repeat_incident_count > 0 or residual >= 0.60):
                actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block"); lifecycle = "resilience-alert"
            dispositions.append(AgentResilienceImprovementDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, improvement_id=o.improvement_id,
                verification_score=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=lifecycle, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentResilienceImprovementRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_resilience_improvement_verification_service = AgentResilienceImprovementVerificationService()
