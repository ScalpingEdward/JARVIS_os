from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_resilience_capacity_stress import (
    CapacityStressCreate, CapacityStressDisposition, CapacityStressRecord,
    CapacityStressScores, CapacityStressState,
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


class AgentResilienceCapacityStressService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], CapacityStressRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-resilience-capacity-stress-governance",
            "version": "21.102",
            "governance_only": True,
            "stress_execution_enabled": False,
            "load_generation_enabled": False,
            "autoscaling_enabled": False,
            "automatic_remediation_enabled": False,
            "failover_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: CapacityStressCreate) -> CapacityStressRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = CapacityStressState.BLOCKED if "risk-brain-hard-block" in flags else CapacityStressState.EVIDENCE_READY
        record = CapacityStressRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[CapacityStressRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> CapacityStressRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> CapacityStressRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": CapacityStressState.ASSESSED,
            "submit-review": CapacityStressState.REVIEW_REQUIRED,
            "approve": CapacityStressState.APPROVED,
            "activate": CapacityStressState.ACTIVE,
            "monitor": CapacityStressState.MONITORING,
            "verify": CapacityStressState.VERIFIED,
            "suspend": CapacityStressState.SUSPENDED,
            "revoke": CapacityStressState.REVOKED,
            "archive": CapacityStressState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved capacity-stress findings block approval")
        if action in {"activate", "monitor", "verify"} and record.state not in {
            CapacityStressState.APPROVED, CapacityStressState.ACTIVE,
            CapacityStressState.MONITORING, CapacityStressState.VERIFIED,
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
        return [e for e in self._audit if e.workspace_id == workspace_id]

    def _assess(self, payload: CapacityStressCreate):
        obs = payload.observations
        headroom = mean((o.load_headroom + o.concurrency_headroom + o.queue_headroom) / 3 for o in obs)
        stability = mean((o.latency_stability + o.error_stability + o.resource_efficiency + o.degradation_quality) / 4 for o in obs)
        dependency = mean(o.dependency_capacity for o in obs)
        recovery = mean(o.recovery_readiness for o in obs)
        observability = mean(o.observability_coverage for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([headroom, stability, dependency, recovery, observability]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.load_headroom)*0.12 + (1-o.concurrency_headroom)*0.10 + (1-o.queue_headroom)*0.08 +
            (1-o.latency_stability)*0.10 + (1-o.error_stability)*0.10 + (1-o.resource_efficiency)*0.06 +
            (1-o.dependency_capacity)*0.10 + (1-o.degradation_quality)*0.08 + (1-o.recovery_readiness)*0.10 +
            min(o.saturation_events/3,1)*0.06 + min(o.failed_recovery_checks/2,1)*0.06 +
            min(o.dependency_bottlenecks/3,1)*0.04
            for o in obs
        ))
        scores = CapacityStressScores(
            headroom_assurance=self._clamp(headroom), stability_assurance=self._clamp(stability),
            dependency_assurance=self._clamp(dependency), recovery_assurance=self._clamp(recovery),
            observability_assurance=self._clamp(observability), aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk, confidence=self._clamp(confidence),
        )
        dispositions: List[CapacityStressDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            signal = "verified"
            scenario_headroom = mean([o.load_headroom, o.concurrency_headroom, o.queue_headroom])
            residual = self._clamp(
                (1-scenario_headroom)*0.30 + (1-o.latency_stability)*0.10 + (1-o.error_stability)*0.10 +
                (1-o.resource_efficiency)*0.06 + (1-o.dependency_capacity)*0.12 +
                (1-o.degradation_quality)*0.08 + (1-o.recovery_readiness)*0.10 +
                min(o.saturation_events/3,1)*0.06 + min(o.failed_recovery_checks/2,1)*0.05 +
                min(o.dependency_bottlenecks/3,1)*0.03
            )
            if scenario_headroom < payload.min_headroom:
                signal = "capacity-alert"; actions.append("capacity-headroom-review"); flags.append(f"capacity-alert:{o.agent_id}:{o.scenario_id}")
            if o.saturation_events > 0 or o.latency_stability < payload.min_stability or o.error_stability < payload.min_stability:
                signal = "saturation-alert"; actions.append("saturation-and-performance-review"); flags.append(f" saturation-alert:{o.agent_id}:{o.scenario_id}".strip())
            if o.recovery_readiness < payload.min_recovery or o.failed_recovery_checks > 0:
                signal = "recovery-alert"; actions.append("recovery-capacity-review"); flags.append(f"recovery-alert:{o.agent_id}:{o.scenario_id}")
            if o.dependency_capacity < payload.min_headroom or o.dependency_bottlenecks > 0:
                signal = "dependency-alert"; actions.append("dependency-capacity-review"); flags.append(f"dependency-alert:{o.agent_id}:{o.scenario_id}")
            if residual > payload.max_residual_risk:
                actions.append("capacity-stress-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.scenario_id}")
            if o.criticality >= 0.90 and (o.saturation_events > 1 or o.failed_recovery_checks > 0 or o.dependency_bottlenecks > 1 or residual >= 0.60):
                signal = "capacity-alert"; actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block")
            dispositions.append(CapacityStressDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, scenario_id=o.scenario_id,
                assurance=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=signal, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: CapacityStressRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_resilience_capacity_stress_service = AgentResilienceCapacityStressService()
