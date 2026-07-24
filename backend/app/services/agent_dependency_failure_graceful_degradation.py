from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_dependency_failure_graceful_degradation import (
    DependencyFailureCreate,
    DependencyFailureDisposition,
    DependencyFailureRecord,
    DependencyFailureScores,
    DependencyFailureState,
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


class AgentDependencyFailureGracefulDegradationService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], DependencyFailureRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-dependency-failure-graceful-degradation-governance",
            "version": "21.103",
            "governance_only": True,
            "fault_injection_enabled": False,
            "automatic_failover_enabled": False,
            "automatic_fallback_enabled": False,
            "automatic_recovery_enabled": False,
            "traffic_shift_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: DependencyFailureCreate) -> DependencyFailureRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = DependencyFailureState.BLOCKED if "risk-brain-hard-block" in flags else DependencyFailureState.EVIDENCE_READY
        record = DependencyFailureRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            dispositions=dispositions,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[DependencyFailureRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> DependencyFailureRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> DependencyFailureRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": DependencyFailureState.ASSESSED,
            "submit-review": DependencyFailureState.REVIEW_REQUIRED,
            "approve": DependencyFailureState.APPROVED,
            "activate": DependencyFailureState.ACTIVE,
            "monitor": DependencyFailureState.MONITORING,
            "verify": DependencyFailureState.VERIFIED,
            "suspend": DependencyFailureState.SUSPENDED,
            "revoke": DependencyFailureState.REVOKED,
            "archive": DependencyFailureState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved dependency-failure findings block approval")
        if action in {"activate", "monitor", "verify"} and record.state not in {
            DependencyFailureState.APPROVED,
            DependencyFailureState.ACTIVE,
            DependencyFailureState.MONITORING,
            DependencyFailureState.VERIFIED,
        }:
            raise ValueError("human approval required before governed active state")
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
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _assess(self, payload: DependencyFailureCreate):
        observations = payload.observations
        redundancy = mean(o.redundancy_coverage for o in observations)
        failover = mean((o.failover_readiness + o.fallback_quality) / 2 for o in observations)
        degradation = mean(o.graceful_degradation_quality for o in observations)
        integrity = mean((o.data_integrity_preservation + o.state_consistency) / 2 for o in observations)
        recovery = mean((o.recovery_readiness + o.recovery_point_assurance) / 2 for o in observations)
        observability = mean((o.observability_coverage + o.human_override_readiness) / 2 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)
        aggregate = self._clamp(mean([redundancy, failover, degradation, integrity, recovery, observability]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.redundancy_coverage)*0.10 + (1-o.failover_readiness)*0.12 + (1-o.fallback_quality)*0.08 +
            (1-o.graceful_degradation_quality)*0.12 + (1-o.data_integrity_preservation)*0.12 +
            (1-o.state_consistency)*0.08 + (1-o.recovery_readiness)*0.10 + (1-o.recovery_point_assurance)*0.08 +
            min(o.single_point_failures/2, 1)*0.06 + min(o.failed_failover_checks/2, 1)*0.05 +
            min(o.degradation_violations/2, 1)*0.04 + min(o.integrity_violations/2, 1)*0.03 +
            min(o.failed_recovery_checks/2, 1)*0.02
            for o in observations
        ))
        scores = DependencyFailureScores(
            redundancy_assurance=self._clamp(redundancy),
            failover_assurance=self._clamp(failover),
            degradation_assurance=self._clamp(degradation),
            integrity_assurance=self._clamp(integrity),
            recovery_assurance=self._clamp(recovery),
            observability_assurance=self._clamp(observability),
            aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[DependencyFailureDisposition] = []
        flags: List[str] = []
        for o in observations:
            actions: List[str] = []
            signal = "verified"
            residual = self._clamp(
                (1-o.redundancy_coverage)*0.12 + (1-o.failover_readiness)*0.14 + (1-o.fallback_quality)*0.08 +
                (1-o.graceful_degradation_quality)*0.12 + (1-o.data_integrity_preservation)*0.14 +
                (1-o.state_consistency)*0.08 + (1-o.recovery_readiness)*0.10 + (1-o.recovery_point_assurance)*0.06 +
                min(o.single_point_failures/2,1)*0.06 + min(o.failed_failover_checks/2,1)*0.04 +
                min(o.degradation_violations/2,1)*0.03 + min(o.integrity_violations/2,1)*0.02 +
                min(o.failed_recovery_checks/2,1)*0.01
            )
            if o.redundancy_coverage < payload.min_redundancy or o.single_point_failures > 0:
                signal = "dependency-alert"
                actions.append("dependency-redundancy-review")
                flags.append(f"dependency-alert:{o.agent_id}:{o.dependency_id}")
            if o.failover_readiness < payload.min_failover or o.failed_failover_checks > 0:
                signal = "failover-alert"
                actions.append("failover-and-fallback-review")
                flags.append(f"failover-alert:{o.agent_id}:{o.dependency_id}")
            if o.graceful_degradation_quality < payload.min_degradation_quality or o.degradation_violations > 0:
                signal = "degradation-alert"
                actions.append("graceful-degradation-review")
                flags.append(f"degradation-alert:{o.agent_id}:{o.dependency_id}")
            if o.data_integrity_preservation < payload.min_data_integrity or o.integrity_violations > 0:
                signal = "data-integrity-alert"
                actions.append("data-integrity-and-state-consistency-review")
                flags.append(f"data-integrity-alert:{o.agent_id}:{o.dependency_id}")
            if o.recovery_readiness < payload.min_recovery or o.failed_recovery_checks > 0:
                signal = "recovery-alert"
                actions.append("dependency-recovery-review")
                flags.append(f"recovery-alert:{o.agent_id}:{o.dependency_id}")
            if residual > payload.max_residual_risk:
                actions.append("dependency-failure-risk-committee")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.dependency_id}")
            if o.dependency_criticality >= 0.90 and (
                o.single_point_failures > 0 or o.failed_failover_checks > 0 or o.integrity_violations > 0 or residual >= 0.60
            ):
                signal = "dependency-alert"
                actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
            dispositions.append(DependencyFailureDisposition(
                agent_id=o.agent_id,
                agent_version=o.agent_version,
                dependency_id=o.dependency_id,
                assurance=self._clamp(1-residual),
                residual_risk=residual,
                lifecycle_signal=signal,
                required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: DependencyFailureRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


agent_dependency_failure_graceful_degradation_service = AgentDependencyFailureGracefulDegradationService()
