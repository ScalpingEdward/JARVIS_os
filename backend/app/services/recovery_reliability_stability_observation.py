"""PHOENIX v21.180 — Recovery Reliability Stability Observation & Episode Closure Governance."""
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
class ConsumerStabilityObservation:
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    healthy: bool
    baseline_match: bool
    dependency_satisfaction: float
    latency_quality: float
    error_quality: float
    confidence: float
    freshness: float


@dataclass
class RecoveryReliabilityStabilityRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: tuple[str, ...]
    observations: tuple[ConsumerStabilityObservation, ...]
    minimum_stability_score: float = 0.85
    maximum_residual_risk: float = 0.20
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
            "minimum_stability_score": self.minimum_stability_score,
            "maximum_residual_risk": self.maximum_residual_risk,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "stability_score": self.stability_score,
            "residual_risk": self.residual_risk,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityStabilityObservationGovernance:
    """Observe recovered consumers after completion; never mutates runtime state."""

    def __init__(self) -> None:
        self.records: dict[str, RecoveryReliabilityStabilityRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def observe(self, record: RecoveryReliabilityStabilityRecord, *, source_state: str, source_human_approved: bool) -> RecoveryReliabilityStabilityRecord:
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
            or not (0.0 <= record.minimum_stability_score <= 1.0)
            or not (0.0 <= record.maximum_residual_risk <= 1.0)
        )
        obs_consumers = [o.consumer_id for o in record.observations]
        if len(obs_consumers) != len(set(obs_consumers)) or set(obs_consumers) != set(record.expected_consumers):
            invalid = True

        scores: list[float] = []
        for obs in record.observations:
            metrics = [obs.dependency_satisfaction, obs.latency_quality, obs.error_quality, obs.confidence, obs.freshness]
            exact = (
                obs.workspace_id == record.workspace_id
                and obs.baseline_id == record.baseline_id
                and obs.baseline_version == record.baseline_version
                and obs.baseline_digest == record.baseline_digest
            )
            if not all(0.0 <= m <= 1.0 for m in metrics):
                invalid = True
                continue
            consumer_score = sum(metrics) / len(metrics)
            if not obs.healthy or not obs.baseline_match or not exact:
                consumer_score = 0.0
            scores.append(consumer_score)

        record.stability_score = sum(scores) / len(record.expected_consumers) if scores else 0.0
        record.residual_risk = 1.0 - record.stability_score

        if invalid:
            record.state = "blocked"
        elif record.stability_score < record.minimum_stability_score or record.residual_risk > record.maximum_residual_risk:
            record.state = "degraded"

        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "observed")
        return record

    def approve_closure(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryReliabilityStabilityRecord:
        record = self.records[record_id]
        if (
            record.state != "review-required"
            or not human_approved
            or record.risk_brain_blocked
            or record.stability_score < record.minimum_stability_score
            or record.residual_risk > record.maximum_residual_risk
        ):
            if record.state != "degraded":
                record.state = "blocked"
        else:
            record.state = "closed"
            record.approved_by = actor
        self._audit(record, "closure-reviewed")
        return record

    def _audit(self, record: RecoveryReliabilityStabilityRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
