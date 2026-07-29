"""PHOENIX v21.170 — Reliability Recovery Stability Observation & Episode Closure Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "degraded", "closed", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ConsumerObservation:
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    healthy: bool
    dependency_satisfaction: float
    latency_quality: float
    error_quality: float
    confidence: float
    freshness: float


@dataclass
class RecoveryStabilityRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: tuple[str, ...]
    observations: tuple[ConsumerObservation, ...]
    max_residual_risk: float = 0.25
    risk_brain_blocked: bool = False
    state: State = "review-required"
    stability_score: float = 0.0
    residual_risk: float = 1.0
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
            "expected_consumers": self.expected_consumers,
            "observations": [o.__dict__ for o in self.observations],
            "max_residual_risk": self.max_residual_risk,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "stability_score": self.stability_score,
            "residual_risk": self.residual_risk,
            "approved_by": self.approved_by,
        }


class ReliabilityRecoveryStabilityGovernance:
    """Observe post-recovery stability and govern closure; never mutates runtime consumers."""

    def __init__(self) -> None:
        self.records: dict[str, RecoveryStabilityRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def observe(self, record: RecoveryStabilityRecord, *, source_state: str, source_human_approved: bool) -> RecoveryStabilityRecord:
        invalid = (
            source_state != "completed"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not record.expected_consumers
            or record.source_record_id in self.source_ids
            or len(set(record.expected_consumers)) != len(record.expected_consumers)
            or not (0.0 <= record.max_residual_risk <= 1.0)
        )
        consumers = [o.consumer_id for o in record.observations]
        if len(consumers) != len(set(consumers)) or set(consumers) != set(record.expected_consumers):
            invalid = True

        scores: list[float] = []
        drift = False
        for obs in record.observations:
            exact = (
                obs.workspace_id == record.workspace_id
                and obs.baseline_id == record.baseline_id
                and obs.baseline_version == record.baseline_version
                and obs.baseline_digest == record.baseline_digest
            )
            drift = drift or not exact
            metrics = [obs.dependency_satisfaction, obs.latency_quality, obs.error_quality, obs.confidence, obs.freshness]
            if any(m < 0.0 or m > 1.0 for m in metrics):
                invalid = True
            scores.append((float(obs.healthy) + sum(metrics)) / 6.0 if exact else 0.0)

        record.stability_score = sum(scores) / len(record.expected_consumers) if record.expected_consumers else 0.0
        record.residual_risk = 1.0 - record.stability_score
        if invalid:
            record.state = "blocked"
        elif drift or record.residual_risk > record.max_residual_risk or record.stability_score < 0.75:
            record.state = "degraded"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "observed")
        return record

    def approve_closure(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryStabilityRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            if record.state != "degraded":
                record.state = "blocked"
        else:
            record.state = "closed"
            record.approved_by = actor
        self._audit(record, "closure-reviewed")
        return record

    def _audit(self, record: RecoveryStabilityRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
