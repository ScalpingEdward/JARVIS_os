from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_post_recovery_stabilization import (
    PostRecoveryCreate, PostRecoveryDisposition, PostRecoveryRecord,
    PostRecoveryScores, PostRecoveryState,
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


class AgentPostRecoveryStabilizationService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], PostRecoveryRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-post-recovery-stabilization-hypercare-governance",
            "version": "21.107",
            "governance_only": True,
            "traffic_shift_enabled": False,
            "automatic_rollback_enabled": False,
            "automatic_remediation_enabled": False,
            "runtime_restart_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: PostRecoveryCreate) -> PostRecoveryRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = PostRecoveryState.BLOCKED if "risk-brain-hard-block" in flags else PostRecoveryState.EVIDENCE_READY
        record = PostRecoveryRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[PostRecoveryRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> PostRecoveryRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> PostRecoveryRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": PostRecoveryState.ASSESSED,
            "submit-review": PostRecoveryState.REVIEW_REQUIRED,
            "approve": PostRecoveryState.APPROVED,
            "activate": PostRecoveryState.ACTIVE,
            "monitor": PostRecoveryState.MONITORING,
            "stabilize": PostRecoveryState.STABLE,
            "suspend": PostRecoveryState.SUSPENDED,
            "revoke": PostRecoveryState.REVOKED,
            "archive": PostRecoveryState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved stabilization findings block approval")
        if action in {"activate", "monitor", "stabilize"} and record.state not in {
            PostRecoveryState.APPROVED, PostRecoveryState.ACTIVE,
            PostRecoveryState.MONITORING, PostRecoveryState.STABLE,
        }:
            raise ValueError("human approval required before governed stabilization state")
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

    def _assess(self, payload: PostRecoveryCreate):
        obs = payload.observations
        health = mean((o.service_health + o.latency_stability + o.error_rate_stability) / 3 for o in obs)
        integrity = mean(o.state_integrity for o in obs)
        dependency = mean(o.dependency_health for o in obs)
        observability = mean(o.observability_coverage for o in obs)
        business = mean(o.business_kpi_stability for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([health, integrity, dependency, observability, business]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.service_health)*0.12 + (1-o.latency_stability)*0.08 + (1-o.error_rate_stability)*0.08 +
            (1-o.state_integrity)*0.12 + (1-o.dependency_health)*0.10 + (1-o.observability_coverage)*0.08 +
            (1-o.business_kpi_stability)*0.12 + (1-o.rollback_readiness)*0.08 + (1-o.human_oncall_readiness)*0.05 +
            (1-o.error_budget_remaining)*0.05 + min(o.reopened_incidents/2,1)*0.05 +
            min(o.regression_findings/3,1)*0.03 + min(o.dependency_incidents/3,1)*0.02 +
            min(o.business_impact_events/2,1)*0.02
            for o in obs
        ))
        scores = PostRecoveryScores(
            health_assurance=self._clamp(health), integrity_assurance=self._clamp(integrity),
            dependency_assurance=self._clamp(dependency), observability_assurance=self._clamp(observability),
            business_assurance=self._clamp(business), aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk, confidence=self._clamp(confidence),
        )
        dispositions: List[PostRecoveryDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            signal = "stable"
            residual = self._clamp(
                (1-o.service_health)*0.14 + (1-o.latency_stability)*0.08 + (1-o.error_rate_stability)*0.08 +
                (1-o.state_integrity)*0.14 + (1-o.dependency_health)*0.10 + (1-o.observability_coverage)*0.08 +
                (1-o.business_kpi_stability)*0.12 + (1-o.rollback_readiness)*0.08 +
                (1-o.error_budget_remaining)*0.06 + min(o.reopened_incidents/2,1)*0.05 +
                min(o.regression_findings/3,1)*0.03 + min(o.dependency_incidents/3,1)*0.02 +
                min(o.business_impact_events/2,1)*0.02
            )
            if min(o.service_health, o.latency_stability, o.error_rate_stability) < payload.min_health or o.reopened_incidents > 0:
                signal = "health-alert"; actions.append("post-recovery-health-review"); flags.append(f"health-alert:{o.agent_id}:{o.window_id}")
            if o.error_budget_remaining < payload.min_error_budget:
                signal = "error-budget-alert"; actions.append("error-budget-burn-review"); flags.append(f"error-budget-alert:{o.agent_id}:{o.window_id}")
            if o.regression_findings > 0:
                signal = "regression-alert"; actions.append("post-recovery-regression-review"); flags.append(f"regression-alert:{o.agent_id}:{o.window_id}")
            if o.dependency_health < payload.min_health or o.dependency_incidents > 0:
                signal = "dependency-alert"; actions.append("dependency-stability-review"); flags.append(f"dependency-alert:{o.agent_id}:{o.window_id}")
            if o.business_kpi_stability < payload.min_health or o.business_impact_events > 0:
                signal = "business-alert"; actions.append("business-stability-review"); flags.append(f"business-alert:{o.agent_id}:{o.window_id}")
            if residual > payload.max_residual_risk:
                actions.append("post-recovery-stabilization-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.window_id}")
            if o.criticality >= 0.90 and (o.reopened_incidents > 0 or o.business_impact_events > 0 or o.state_integrity < 0.70 or residual >= 0.60):
                actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block"); signal = "health-alert"
            dispositions.append(PostRecoveryDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, window_id=o.window_id,
                assurance=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=signal, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: PostRecoveryRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_post_recovery_stabilization_service = AgentPostRecoveryStabilizationService()
