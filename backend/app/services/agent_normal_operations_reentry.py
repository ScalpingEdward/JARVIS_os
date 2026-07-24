from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_normal_operations_reentry import (
    NormalOperationsReentryCreate,
    NormalOperationsReentryDisposition,
    NormalOperationsReentryRecord,
    NormalOperationsReentryScores,
    NormalOperationsReentryState,
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


class AgentNormalOperationsReentryService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], NormalOperationsReentryRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-normal-operations-reentry-hypercare-exit-governance",
            "version": "21.108",
            "governance_only": True,
            "hypercare_exit_execution_enabled": False,
            "traffic_shift_enabled": False,
            "runtime_restart_enabled": False,
            "automatic_remediation_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: NormalOperationsReentryCreate) -> NormalOperationsReentryRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = NormalOperationsReentryState.BLOCKED if "risk-brain-hard-block" in flags else NormalOperationsReentryState.EVIDENCE_READY
        record = NormalOperationsReentryRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[NormalOperationsReentryRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> NormalOperationsReentryRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> NormalOperationsReentryRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": NormalOperationsReentryState.ASSESSED,
            "submit-review": NormalOperationsReentryState.REVIEW_REQUIRED,
            "approve": NormalOperationsReentryState.APPROVED,
            "activate": NormalOperationsReentryState.ACTIVE,
            "monitor": NormalOperationsReentryState.MONITORING,
            "enter-normal-operations": NormalOperationsReentryState.NORMAL_OPERATIONS,
            "suspend": NormalOperationsReentryState.SUSPENDED,
            "revoke": NormalOperationsReentryState.REVOKED,
            "archive": NormalOperationsReentryState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved re-entry findings block approval")
        if action in {"activate", "monitor", "enter-normal-operations"} and record.state not in {
            NormalOperationsReentryState.APPROVED,
            NormalOperationsReentryState.ACTIVE,
            NormalOperationsReentryState.MONITORING,
            NormalOperationsReentryState.NORMAL_OPERATIONS,
        }:
            raise ValueError("human approval required before governed re-entry state")
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

    def _assess(self, payload: NormalOperationsReentryCreate):
        obs = payload.observations
        stability = mean((o.service_health_stability + o.latency_stability + o.error_rate_stability) / 3 for o in obs)
        integrity = mean((o.state_integrity + o.dependency_health) / 2 for o in obs)
        business = mean((o.business_kpi_stability + o.error_budget_posture) / 2 for o in obs)
        governance = mean((o.alert_noise_quality + o.runbook_currency + o.residual_risk_acceptance) / 3 for o in obs)
        ownership = mean(o.operational_owner_readiness for o in obs)
        handoff = mean(o.handoff_completeness for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([stability, integrity, business, governance, ownership, handoff]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.service_health_stability)*0.10 + (1-o.latency_stability)*0.07 + (1-o.error_rate_stability)*0.09 +
            (1-o.state_integrity)*0.10 + (1-o.dependency_health)*0.08 + (1-o.business_kpi_stability)*0.08 +
            (1-o.error_budget_posture)*0.07 + (1-o.operational_owner_readiness)*0.08 +
            (1-o.handoff_completeness)*0.10 + (1-o.residual_risk_acceptance)*0.07 +
            min(o.reopened_incidents/2,1)*0.06 + min(o.unresolved_high_findings/3,1)*0.06 +
            min(o.failed_handoffs/2,1)*0.04
            for o in obs
        ))
        scores = NormalOperationsReentryScores(
            stability_assurance=self._clamp(stability), integrity_assurance=self._clamp(integrity),
            business_assurance=self._clamp(business), governance_assurance=self._clamp(governance),
            ownership_assurance=self._clamp(ownership), handoff_assurance=self._clamp(handoff),
            aggregate_assurance=aggregate, aggregate_residual_risk=aggregate_risk,
            confidence=self._clamp(confidence),
        )
        dispositions: List[NormalOperationsReentryDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            signal = "normal-operations"
            local_stability = mean([o.service_health_stability, o.latency_stability, o.error_rate_stability])
            residual = self._clamp(
                (1-local_stability)*0.28 + (1-o.state_integrity)*0.10 + (1-o.dependency_health)*0.08 +
                (1-o.business_kpi_stability)*0.08 + (1-o.error_budget_posture)*0.08 +
                (1-o.operational_owner_readiness)*0.10 + (1-o.handoff_completeness)*0.10 +
                (1-o.residual_risk_acceptance)*0.06 + min(o.reopened_incidents/2,1)*0.05 +
                min(o.unresolved_high_findings/3,1)*0.04 + min(o.failed_handoffs/2,1)*0.03
            )
            if o.stabilization_window_hours < payload.min_stabilization_hours or local_stability < payload.min_stability or o.reopened_incidents > 0:
                signal = "stability-alert"; actions.append("extend-hypercare-and-stability-review"); flags.append(f"stability-alert:{o.agent_id}")
            if o.runbook_currency < payload.min_stability or o.alert_noise_quality < payload.min_stability or o.unresolved_high_findings > 0:
                signal = "governance-alert"; actions.append("operational-governance-readiness-review"); flags.append(f"governance-alert:{o.agent_id}")
            if o.operational_owner_readiness < payload.min_owner_readiness or o.handoff_completeness < payload.min_handoff_completeness or o.failed_handoffs > 0:
                signal = "ownership-alert"; actions.append("owner-and-handoff-readiness-review"); flags.append(f"ownership-alert:{o.agent_id}")
            if residual > payload.max_residual_risk:
                signal = "residual-risk-alert"; actions.append("normal-operations-reentry-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}")
            if o.criticality >= 0.90 and (o.reopened_incidents > 0 or o.unresolved_high_findings > 0 or o.failed_handoffs > 0 or residual >= 0.55):
                actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block"); signal = "residual-risk-alert"
            dispositions.append(NormalOperationsReentryDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version,
                assurance=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=signal, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: NormalOperationsReentryRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_normal_operations_reentry_service = AgentNormalOperationsReentryService()
