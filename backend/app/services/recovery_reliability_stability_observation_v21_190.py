"""PHOENIX v21.190 — Recovery Reliability Stability Observation & Episode Closure Governance."""
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
class StabilityObservation:
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    healthy: bool
    dependency_satisfied: bool
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
    observations: tuple[StabilityObservation, ...]
    max_residual_risk: float = 0.30
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


class RecoveryReliabilityStabilityObservationGovernance:
    """Observe post-recovery stability and gate episode closure without runtime mutation."""

    def __init__(self, *, min_stability_score: float = 0.85) -> None:
        self.min_stability_score = min_stability_score
        self.records: dict[str, RecoveryStabilityRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def observe(self, record: RecoveryStabilityRecord, *, source_state: str, source_human_approved: bool) -> RecoveryStabilityRecord:
        consumers = [o.consumer_id for o in record.observations]
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
            or len(consumers) != len(set(consumers))
            or set(consumers) != set(record.expected_consumers)
        )
        scores: list[float] = []
        consumer_degraded = False
        if not invalid:
            for o in record.observations:
                normalized = [o.latency_quality, o.error_quality, o.confidence, o.freshness]
                exact = (
                    o.workspace_id == record.workspace_id
                    and o.baseline_id == record.baseline_id
                    and o.baseline_version == record.baseline_version
                    and o.baseline_digest == record.baseline_digest
                )
                if not exact or any(v < 0.0 or v > 1.0 for v in normalized):
                    invalid = True
                    break
                if not o.healthy or not o.dependency_satisfied:
                    consumer_degraded = True
                health = 1.0 if o.healthy else 0.0
                deps = 1.0 if o.dependency_satisfied else 0.0
                scores.append((health + deps + sum(normalized)) / 6.0)

        if invalid:
            record.state = "blocked"
        else:
            record.stability_score = sum(scores) / len(scores)
            record.residual_risk = 1.0 - record.stability_score
            if (
                consumer_degraded
                or record.stability_score < self.min_stability_score
                or record.residual_risk > record.max_residual_risk
            ):
                record.state = "degraded"

        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "observed")
        return record

    def close(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryStabilityRecord:
        record = self.records[record_id]
        if (
            record.state != "review-required"
            or not human_approved
            or record.risk_brain_blocked
            or record.stability_score < self.min_stability_score
            or record.residual_risk > record.max_residual_risk
        ):
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
