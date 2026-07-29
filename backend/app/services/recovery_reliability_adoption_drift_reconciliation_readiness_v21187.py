"""PHOENIX v21.187 — Recovery Reliability Adoption Drift Escalation & Coordinated Reconciliation Readiness Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "reconciliation-ready", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class DriftConsumer:
    consumer_id: str
    reason: str
    severity: float


@dataclass
class ReconciliationReadinessRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    affected_consumers: tuple[DriftConsumer, ...]
    healthy_consumers: tuple[str, ...]
    blast_radius: float
    residual_risk: float
    max_blast_radius: float = 0.50
    max_residual_risk: float = 0.35
    risk_brain_blocked: bool = False
    state: State = "review-required"
    readiness_score: float = 0.0
    approved_by: str | None = None
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        self.audit_digest = _digest(self.snapshot())

    def snapshot(self) -> dict:
        return {
            "record_id": self.record_id,
            "workspace_id": self.workspace_id,
            "source_record_id": self.source_record_id,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "baseline_digest": self.baseline_digest,
            "affected_consumers": [(c.consumer_id, c.reason, c.severity) for c in self.affected_consumers],
            "healthy_consumers": self.healthy_consumers,
            "blast_radius": self.blast_radius,
            "residual_risk": self.residual_risk,
            "max_blast_radius": self.max_blast_radius,
            "max_residual_risk": self.max_residual_risk,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "readiness_score": self.readiness_score,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityAdoptionDriftReconciliationReadinessGovernance:
    """Escalate drift into a bounded reconciliation plan without runtime mutation."""

    def __init__(self) -> None:
        self.records: dict[str, ReconciliationReadinessRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def evaluate(self, record: ReconciliationReadinessRecord, *, source_state: str, source_human_approved: bool) -> ReconciliationReadinessRecord:
        affected_ids = [c.consumer_id for c in record.affected_consumers]
        invalid = (
            source_state != "drift-detected"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not record.affected_consumers
            or record.source_record_id in self.source_ids
            or len(set(affected_ids)) != len(affected_ids)
            or len(set(record.healthy_consumers)) != len(record.healthy_consumers)
            or bool(set(affected_ids) & set(record.healthy_consumers))
            or any(not c.reason or not 0.0 <= c.severity <= 1.0 for c in record.affected_consumers)
            or not 0.0 <= record.blast_radius <= 1.0
            or not 0.0 <= record.residual_risk <= 1.0
            or not 0.0 <= record.max_blast_radius <= 1.0
            or not 0.0 <= record.max_residual_risk <= 1.0
        )
        avg_severity = sum(c.severity for c in record.affected_consumers) / len(record.affected_consumers)
        record.readiness_score = round(max(0.0, 1.0 - (0.45 * avg_severity + 0.30 * record.blast_radius + 0.25 * record.residual_risk)), 6)
        if invalid or record.blast_radius > record.max_blast_radius or record.residual_risk > record.max_residual_risk:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "evaluated")
        return record

    def approve(self, record_id: str, *, actor: str, human_approved: bool, minimum_readiness: float = 0.55) -> ReconciliationReadinessRecord:
        record = self.records[record_id]
        if (
            record.state != "review-required"
            or not human_approved
            or record.risk_brain_blocked
            or record.readiness_score < minimum_readiness
        ):
            record.state = "blocked"
        else:
            record.state = "reconciliation-ready"
            record.approved_by = actor
        self._audit(record, "reviewed")
        return record

    def _audit(self, record: ReconciliationReadinessRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
