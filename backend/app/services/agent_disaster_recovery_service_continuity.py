from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_disaster_recovery_service_continuity import (
    DisasterRecoveryCreate,
    DisasterRecoveryDisposition,
    DisasterRecoveryRecord,
    DisasterRecoveryScores,
    DisasterRecoveryState,
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


class AgentDisasterRecoveryServiceContinuityService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], DisasterRecoveryRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-disaster-recovery-service-continuity-governance",
            "version": "21.104",
            "governance_only": True,
            "automatic_restore_enabled": False,
            "automatic_failover_enabled": False,
            "automatic_recovery_enabled": False,
            "traffic_shift_enabled": False,
            "runtime_restart_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: DisasterRecoveryCreate) -> DisasterRecoveryRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = DisasterRecoveryState.BLOCKED if "risk-brain-hard-block" in flags else DisasterRecoveryState.EVIDENCE_READY
        record = DisasterRecoveryRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[DisasterRecoveryRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> DisasterRecoveryRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> DisasterRecoveryRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": DisasterRecoveryState.ASSESSED,
            "submit-review": DisasterRecoveryState.REVIEW_REQUIRED,
            "approve": DisasterRecoveryState.APPROVED,
            "activate": DisasterRecoveryState.ACTIVE,
            "monitor": DisasterRecoveryState.MONITORING,
            "verify": DisasterRecoveryState.VERIFIED,
            "suspend": DisasterRecoveryState.SUSPENDED,
            "revoke": DisasterRecoveryState.REVOKED,
            "archive": DisasterRecoveryState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved disaster-recovery findings block approval")
        if action in {"activate", "monitor", "verify"} and record.state not in {
            DisasterRecoveryState.APPROVED,
            DisasterRecoveryState.ACTIVE,
            DisasterRecoveryState.MONITORING,
            DisasterRecoveryState.VERIFIED,
        }:
            raise ValueError("human approval required before governed continuity state")
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

    def _assess(self, payload: DisasterRecoveryCreate):
        obs = payload.observations
        rto = mean(o.rto_readiness for o in obs)
        rpo = mean(o.rpo_readiness for o in obs)
        backup_restore = mean((o.backup_integrity + o.restore_readiness + o.state_reconstruction_readiness) / 3 for o in obs)
        continuity = mean((o.regional_redundancy + o.communication_readiness) / 2 for o in obs)
        dependency = mean(o.dependency_recovery_readiness for o in obs)
        operations = mean((o.runbook_coverage + o.recovery_test_coverage) / 2 for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([rto, rpo, backup_restore, continuity, dependency, operations]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.rto_readiness)*0.14 + (1-o.rpo_readiness)*0.14 + (1-o.backup_integrity)*0.12 +
            (1-o.restore_readiness)*0.12 + (1-o.regional_redundancy)*0.08 +
            (1-o.dependency_recovery_readiness)*0.10 + (1-o.state_reconstruction_readiness)*0.08 +
            (1-o.runbook_coverage)*0.06 + (1-o.recovery_test_coverage)*0.06 +
            min(o.failed_restore_tests/2,1)*0.04 + min(o.failed_recovery_tests/2,1)*0.03 +
            min(o.stale_backup_events/3,1)*0.02 + min(o.continuity_gaps/3,1)*0.01
            for o in obs
        ))
        scores = DisasterRecoveryScores(
            rto_assurance=self._clamp(rto), rpo_assurance=self._clamp(rpo),
            backup_restore_assurance=self._clamp(backup_restore), continuity_assurance=self._clamp(continuity),
            dependency_recovery_assurance=self._clamp(dependency), operational_readiness=self._clamp(operations),
            aggregate_assurance=aggregate, aggregate_residual_risk=aggregate_risk,
            confidence=self._clamp(confidence),
        )
        dispositions: List[DisasterRecoveryDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            signal = "verified"
            residual = self._clamp(
                (1-o.rto_readiness)*0.16 + (1-o.rpo_readiness)*0.16 + (1-o.backup_integrity)*0.12 +
                (1-o.restore_readiness)*0.12 + (1-o.regional_redundancy)*0.08 +
                (1-o.dependency_recovery_readiness)*0.10 + (1-o.state_reconstruction_readiness)*0.08 +
                (1-o.runbook_coverage)*0.06 + (1-o.recovery_test_coverage)*0.06 +
                min(o.failed_restore_tests/2,1)*0.03 + min(o.failed_recovery_tests/2,1)*0.02 +
                min(o.continuity_gaps/3,1)*0.01
            )
            if o.rto_readiness < payload.min_rto_readiness:
                signal = "rto-alert"; actions.append("rto-readiness-review"); flags.append(f"rto-alert:{o.agent_id}:{o.service_id}")
            if o.rpo_readiness < payload.min_rpo_readiness:
                signal = "rpo-alert"; actions.append("rpo-readiness-review"); flags.append(f"rpo-alert:{o.agent_id}:{o.service_id}")
            if o.backup_integrity < payload.min_backup_integrity or o.stale_backup_events > 0:
                signal = "backup-alert"; actions.append("backup-integrity-review"); flags.append(f"backup-alert:{o.agent_id}:{o.service_id}")
            if o.restore_readiness < payload.min_recovery_readiness or o.failed_restore_tests > 0 or o.failed_recovery_tests > 0:
                signal = "recovery-alert"; actions.append("restore-and-recovery-review"); flags.append(f"recovery-alert:{o.agent_id}:{o.service_id}")
            if o.regional_redundancy < 0.80 or o.dependency_recovery_readiness < 0.80 or o.continuity_gaps > 0:
                signal = "continuity-alert"; actions.append("service-continuity-review"); flags.append(f"continuity-alert:{o.agent_id}:{o.service_id}")
            if residual > payload.max_residual_risk:
                actions.append("disaster-recovery-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.service_id}")
            if o.criticality >= 0.90 and (o.failed_restore_tests > 0 or o.failed_recovery_tests > 0 or o.continuity_gaps > 1 or residual >= 0.60):
                signal = "recovery-alert"; actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block")
            dispositions.append(DisasterRecoveryDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, service_id=o.service_id,
                assurance=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=signal, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: DisasterRecoveryRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_disaster_recovery_service_continuity_service = AgentDisasterRecoveryServiceContinuityService()
