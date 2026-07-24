from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.operational_resilience_incident import (
    OperationalResilienceCreate,
    OperationalResilienceRecord,
    OperationalResilienceScores,
    OperationalResilienceState,
    ServiceResilienceDisposition,
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


class OperationalResilienceIncidentService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], OperationalResilienceRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "operational-resilience-incident",
            "version": "21.81",
            "governance_only": True,
            "infrastructure_mutation_enabled": False,
            "failover_execution_enabled": False,
            "service_restart_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: OperationalResilienceCreate) -> OperationalResilienceRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = OperationalResilienceState.BLOCKED if "risk-brain-hard-block" in flags else OperationalResilienceState.EVIDENCE_READY
        record = OperationalResilienceRecord(
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

    def list(self, workspace_id: str) -> List[OperationalResilienceRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> OperationalResilienceRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> OperationalResilienceRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": OperationalResilienceState.ASSESSED,
            "submit-review": OperationalResilienceState.REVIEW_REQUIRED,
            "approve": OperationalResilienceState.APPROVED,
            "activate": OperationalResilienceState.ACTIVE,
            "monitor": OperationalResilienceState.MONITORING,
            "escalate": OperationalResilienceState.ESCALATED,
            "suspend": OperationalResilienceState.SUSPENDED,
            "revoke": OperationalResilienceState.REVOKED,
            "archive": OperationalResilienceState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved operational-resilience flags block approval")
        if action == "activate" and record.state != OperationalResilienceState.APPROVED:
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

    def _assess(self, payload: OperationalResilienceCreate):
        observations = payload.observations
        service_availability = mean(o.availability_score for o in observations)
        recovery_strength = mean((o.recovery_readiness + o.recovery_test_coverage + (1 - o.rto_breach_risk) + (1 - o.rpo_breach_risk)) / 4 for o in observations)
        continuity_strength = mean((o.continuity_readiness + o.runbook_coverage) / 2 for o in observations)
        dependency_resilience = mean(o.dependency_resilience for o in observations)
        capacity_resilience = mean(o.capacity_headroom for o in observations)
        cyber_resilience = mean(o.cyber_resilience for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_resilience = self._clamp(mean([
            service_availability,
            recovery_strength,
            continuity_strength,
            dependency_resilience,
            capacity_resilience,
            cyber_resilience,
        ]) * confidence)
        aggregate_residual_risk = self._clamp(mean(
            (1 - o.availability_score) * 0.15
            + (1 - o.recovery_readiness) * 0.20
            + (1 - o.continuity_readiness) * 0.15
            + (1 - o.dependency_resilience) * 0.10
            + (1 - o.capacity_headroom) * 0.10
            + (1 - o.cyber_resilience) * 0.10
            + o.rto_breach_risk * 0.10
            + o.rpo_breach_risk * 0.05
            + min(o.incident_count_30d / 20, 1) * 0.05
            for o in observations
        ))

        scores = OperationalResilienceScores(
            service_availability=self._clamp(service_availability),
            recovery_strength=self._clamp(recovery_strength),
            continuity_strength=self._clamp(continuity_strength),
            dependency_resilience=self._clamp(dependency_resilience),
            capacity_resilience=self._clamp(capacity_resilience),
            cyber_resilience=self._clamp(cyber_resilience),
            aggregate_resilience=aggregate_resilience,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[ServiceResilienceDisposition] = []
        flags: List[str] = []
        for observation in observations:
            required_actions: List[str] = []
            lifecycle = "resilient"
            residual = self._clamp(
                (1 - observation.availability_score) * 0.15
                + (1 - observation.recovery_readiness) * 0.20
                + (1 - observation.continuity_readiness) * 0.15
                + (1 - observation.dependency_resilience) * 0.10
                + (1 - observation.capacity_headroom) * 0.10
                + (1 - observation.cyber_resilience) * 0.10
                + observation.rto_breach_risk * 0.10
                + observation.rpo_breach_risk * 0.05
                + min(observation.incident_count_30d / 20, 1) * 0.05
            )
            resilience = self._clamp(1 - residual)

            if observation.recovery_readiness < payload.minimum_recovery_readiness or observation.rto_breach_risk >= 0.35 or observation.rpo_breach_risk >= 0.35:
                lifecycle = "recovery-risk"
                required_actions.append("recovery-objective-review")
                flags.append(f"recovery-risk:{observation.service_id}")
            if observation.continuity_readiness < payload.minimum_continuity_readiness or observation.runbook_coverage < 0.70:
                lifecycle = "continuity-gap"
                required_actions.append("continuity-runbook-remediation")
                flags.append(f"continuity-gap:{observation.service_id}")
            if observation.dependency_resilience < 0.65:
                lifecycle = "dependency-alert"
                required_actions.append("dependency-concentration-review")
                flags.append(f"dependency-alert:{observation.service_id}")
            if observation.capacity_headroom < 0.25:
                lifecycle = "capacity-alert"
                required_actions.append("capacity-and-throttling-review")
                flags.append(f"capacity-alert:{observation.service_id}")
            if observation.open_sev1_incidents > 0 or observation.incident_count_30d >= 8:
                lifecycle = "incident-alert"
                required_actions.append("incident-command-review")
                flags.append(f"incident-alert:{observation.service_id}")
            if observation.recovery_test_coverage < 0.60:
                required_actions.append("recovery-test-program")
                flags.append(f"recovery-test-gap:{observation.service_id}")
            if residual > payload.maximum_acceptable_residual_risk:
                required_actions.append("operational-resilience-committee-escalation")
                flags.append(f"residual-risk-breach:{observation.service_id}")
            if observation.criticality >= 0.90 and observation.open_sev1_incidents > 0 and residual >= 0.60:
                lifecycle = "incident-alert"
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(ServiceResilienceDisposition(
                service_id=observation.service_id,
                resilience_score=resilience,
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: OperationalResilienceRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


operational_resilience_incident_service = OperationalResilienceIncidentService()
