from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_recovery_certification_return_to_service import (
    RecoveryCertificationCreate,
    RecoveryCertificationDisposition,
    RecoveryCertificationRecord,
    RecoveryCertificationScores,
    RecoveryCertificationState,
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


class AgentRecoveryCertificationReturnToServiceService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], RecoveryCertificationRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-recovery-certification-return-to-service-governance",
            "version": "21.106",
            "governance_only": True,
            "return_to_service_execution_enabled": False,
            "traffic_shift_enabled": False,
            "runtime_restart_enabled": False,
            "automatic_recovery_enabled": False,
            "automatic_rollback_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: RecoveryCertificationCreate) -> RecoveryCertificationRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = RecoveryCertificationState.BLOCKED if "risk-brain-hard-block" in flags else RecoveryCertificationState.EVIDENCE_READY
        record = RecoveryCertificationRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[RecoveryCertificationRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> RecoveryCertificationRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> RecoveryCertificationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": RecoveryCertificationState.ASSESSED,
            "submit-review": RecoveryCertificationState.REVIEW_REQUIRED,
            "approve": RecoveryCertificationState.APPROVED,
            "activate": RecoveryCertificationState.ACTIVE,
            "monitor": RecoveryCertificationState.MONITORING,
            "certify": RecoveryCertificationState.CERTIFIED,
            "suspend": RecoveryCertificationState.SUSPENDED,
            "revoke": RecoveryCertificationState.REVOKED,
            "archive": RecoveryCertificationState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved recovery-certification findings block approval")
        if action in {"activate", "monitor", "certify"} and record.state not in {
            RecoveryCertificationState.APPROVED,
            RecoveryCertificationState.ACTIVE,
            RecoveryCertificationState.MONITORING,
            RecoveryCertificationState.CERTIFIED,
        }:
            raise ValueError("human approval required before governed return-to-service state")
        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operations.add(receipt)
        self._audit_event(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [e for e in self._audit if e.workspace_id == workspace_id]

    def _assess(self, payload: RecoveryCertificationCreate):
        obs = payload.observations
        health = mean(o.service_health_score for o in obs)
        integrity = mean((o.state_integrity_score + o.data_integrity_score) / 2 for o in obs)
        dependency = mean(o.dependency_health_score for o in obs)
        observability = mean(o.observability_score for o in obs)
        capacity = mean((o.error_budget_readiness + o.capacity_headroom) / 2 for o in obs)
        business = mean((o.business_validation_score + o.rollback_readiness + o.human_signoff_coverage) / 3 for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([health, integrity, dependency, observability, capacity, business]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.service_health_score)*0.14 + (1-o.state_integrity_score)*0.12 + (1-o.data_integrity_score)*0.12 +
            (1-o.dependency_health_score)*0.08 + (1-o.observability_score)*0.08 + (1-o.error_budget_readiness)*0.08 +
            (1-o.capacity_headroom)*0.08 + (1-o.business_validation_score)*0.10 + (1-o.rollback_readiness)*0.06 +
            (1-o.human_signoff_coverage)*0.08 + min(o.unresolved_recovery_findings/3,1)*0.03 +
            min(o.integrity_failures/2,1)*0.01 + min(o.observability_gaps/2,1)*0.01 + min(o.business_validation_failures/2,1)*0.01
            for o in obs
        ))
        scores = RecoveryCertificationScores(
            health_assurance=self._clamp(health), integrity_assurance=self._clamp(integrity),
            dependency_assurance=self._clamp(dependency), observability_assurance=self._clamp(observability),
            capacity_assurance=self._clamp(capacity), business_assurance=self._clamp(business),
            aggregate_assurance=aggregate, aggregate_residual_risk=aggregate_risk,
            confidence=self._clamp(confidence),
        )
        dispositions: List[RecoveryCertificationDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            signal = "certified"
            residual = self._clamp(
                (1-o.service_health_score)*0.16 + (1-o.state_integrity_score)*0.14 + (1-o.data_integrity_score)*0.14 +
                (1-o.dependency_health_score)*0.08 + (1-o.observability_score)*0.08 + (1-o.error_budget_readiness)*0.07 +
                (1-o.capacity_headroom)*0.07 + (1-o.business_validation_score)*0.10 + (1-o.rollback_readiness)*0.06 +
                (1-o.human_signoff_coverage)*0.10
            )
            if o.service_health_score < payload.min_service_health or o.unresolved_recovery_findings > 0:
                signal = "recovery-alert"; actions.append("service-health-and-recovery-review"); flags.append(f"recovery-alert:{o.agent_id}:{o.recovery_id}")
            if min(o.state_integrity_score, o.data_integrity_score) < payload.min_integrity or o.integrity_failures > 0:
                signal = "integrity-alert"; actions.append("state-and-data-integrity-review"); flags.append(f"integrity-alert:{o.agent_id}:{o.recovery_id}")
            if o.observability_score < payload.min_observability or o.observability_gaps > 0:
                signal = "observability-alert"; actions.append("post-recovery-observability-review"); flags.append(f"observability-alert:{o.agent_id}:{o.recovery_id}")
            if o.business_validation_score < payload.min_business_validation or o.human_signoff_coverage < payload.min_human_signoff or o.business_validation_failures > 0:
                signal = "business-alert"; actions.append("business-validation-and-human-signoff-review"); flags.append(f"business-alert:{o.agent_id}:{o.recovery_id}")
            if residual > payload.max_residual_risk:
                actions.append("recovery-certification-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.recovery_id}")
            if o.criticality >= 0.90 and (o.integrity_failures > 0 or o.business_validation_failures > 0 or o.unresolved_recovery_findings > 0 or residual >= 0.55):
                signal = "recovery-alert"; actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block")
            dispositions.append(RecoveryCertificationDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, recovery_id=o.recovery_id,
                certification_score=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=signal, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: RecoveryCertificationRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_recovery_certification_return_to_service_service = AgentRecoveryCertificationReturnToServiceService()
