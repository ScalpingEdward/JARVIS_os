"""PHOENIX v21.167 — Reliability Adoption Drift Escalation & Coordinated Reconciliation Readiness Governance."""
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
    drift_reason: str
    expected_baseline_id: str
    expected_baseline_version: int
    expected_baseline_digest: str


@dataclass
class ReliabilityAdoptionDriftRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    affected_consumers: tuple[DriftConsumer, ...]
    healthy_consumers: tuple[str, ...]
    consistency_score: float
    blast_radius: float
    residual_risk: float
    risk_brain_blocked: bool = False
    state: State = "review-required"
    approved_by: str | None = None
    plan_digest: str = field(init=False)
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        self.plan_digest = _digest(self.plan_snapshot())
        self.audit_digest = _digest(self.snapshot())

    def plan_snapshot(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "baseline_digest": self.baseline_digest,
            "affected_consumers": [
                {
                    "consumer_id": c.consumer_id,
                    "drift_reason": c.drift_reason,
                    "expected_baseline_id": c.expected_baseline_id,
                    "expected_baseline_version": c.expected_baseline_version,
                    "expected_baseline_digest": c.expected_baseline_digest,
                }
                for c in self.affected_consumers
            ],
            "healthy_consumers": self.healthy_consumers,
            "consistency_score": round(self.consistency_score, 6),
            "blast_radius": round(self.blast_radius, 6),
            "residual_risk": round(self.residual_risk, 6),
        }

    def snapshot(self) -> dict:
        return {
            "record_id": self.record_id,
            "source_record_id": self.source_record_id,
            "plan_digest": self.plan_digest,
            "state": self.state,
            "approved_by": self.approved_by,
            "risk_brain_blocked": self.risk_brain_blocked,
        }


class ReliabilityAdoptionDriftReconciliationGovernance:
    """Build a bounded, human-reviewed reconciliation-readiness plan from v21.166 drift evidence."""

    def __init__(self, *, max_blast_radius: float = 0.60, max_residual_risk: float = 0.35) -> None:
        self.max_blast_radius = max_blast_radius
        self.max_residual_risk = max_residual_risk
        self.records: dict[str, ReliabilityAdoptionDriftRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: ReliabilityAdoptionDriftRecord, *, source_state: str) -> ReliabilityAdoptionDriftRecord:
        affected_ids = [c.consumer_id for c in record.affected_consumers]
        invalid = (
            source_state != "drift-detected"
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not affected_ids
            or len(set(affected_ids)) != len(affected_ids)
            or bool(set(affected_ids) & set(record.healthy_consumers))
            or record.source_record_id in self.source_ids
            or not 0.0 <= record.consistency_score <= 1.0
            or not 0.0 <= record.blast_radius <= 1.0
            or not 0.0 <= record.residual_risk <= 1.0
            or record.blast_radius > self.max_blast_radius
            or record.residual_risk > self.max_residual_risk
            or record.risk_brain_blocked
        )
        for consumer in record.affected_consumers:
            if (
                not consumer.drift_reason
                or consumer.expected_baseline_id != record.baseline_id
                or consumer.expected_baseline_version != record.baseline_version
                or consumer.expected_baseline_digest != record.baseline_digest
            ):
                invalid = True
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def approve(self, record_id: str, *, actor: str, human_approved: bool) -> ReliabilityAdoptionDriftRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "reconciliation-ready"
            record.approved_by = actor
        self._audit(record, "reconciliation-reviewed")
        return record

    def _audit(self, record: ReliabilityAdoptionDriftRecord, action: str) -> None:
        record.plan_digest = _digest(record.plan_snapshot())
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
