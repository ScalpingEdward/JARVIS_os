"""PHOENIX v21.186 — Recovery Reliability Cross-Consumer Adoption Consistency & Drift Observation Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "consistent", "drift-detected", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ConsumerAdoptionObservation:
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    receipt_nonce: str
    receipt_age_seconds: int
    healthy: bool


@dataclass
class CrossConsumerConsistencyRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: tuple[str, ...]
    observations: tuple[ConsumerAdoptionObservation, ...]
    max_receipt_age_seconds: int = 900
    risk_brain_blocked: bool = False
    state: State = "review-required"
    consistency_score: float = 0.0
    drift_reasons: tuple[str, ...] = ()
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
            "max_receipt_age_seconds": self.max_receipt_age_seconds,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "consistency_score": self.consistency_score,
            "drift_reasons": self.drift_reasons,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityCrossConsumerConsistencyGovernance:
    """Observe cross-consumer adoption state without mutating runtime consumers."""

    def __init__(self) -> None:
        self.records: dict[str, CrossConsumerConsistencyRecord] = {}
        self.source_ids: set[str] = set()
        self.receipt_nonces: set[str] = set()
        self.audit: list[dict] = []

    def observe(self, record: CrossConsumerConsistencyRecord, *, source_state: str, source_human_approved: bool) -> CrossConsumerConsistencyRecord:
        invalid = (
            source_state != "adopted"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not record.expected_consumers
            or record.source_record_id in self.source_ids
            or record.max_receipt_age_seconds <= 0
            or len(set(record.expected_consumers)) != len(record.expected_consumers)
        )
        consumers = [o.consumer_id for o in record.observations]
        nonces = [o.receipt_nonce for o in record.observations]
        if len(consumers) != len(set(consumers)) or len(nonces) != len(set(nonces)):
            invalid = True
        if any((not n) or n in self.receipt_nonces for n in nonces):
            invalid = True

        reasons: list[str] = []
        expected = set(record.expected_consumers)
        observed = set(consumers)
        for consumer_id in sorted(expected - observed):
            reasons.append(f"missing-consumer:{consumer_id}")
        for consumer_id in sorted(observed - expected):
            reasons.append(f"unexpected-consumer:{consumer_id}")

        valid_count = 0
        for obs in record.observations:
            issues: list[str] = []
            if obs.consumer_id not in expected:
                issues.append("unexpected")
            if obs.workspace_id != record.workspace_id:
                issues.append("workspace-mismatch")
            if obs.baseline_id != record.baseline_id or obs.baseline_version != record.baseline_version or obs.baseline_digest != record.baseline_digest:
                issues.append("baseline-mismatch")
            if obs.receipt_age_seconds < 0 or obs.receipt_age_seconds > record.max_receipt_age_seconds:
                issues.append("stale-receipt")
            if not obs.healthy:
                issues.append("unhealthy")
            if issues:
                reasons.append(f"{obs.consumer_id}:" + ",".join(issues))
            else:
                valid_count += 1

        record.consistency_score = valid_count / len(record.expected_consumers)
        record.drift_reasons = tuple(sorted(set(reasons)))
        if invalid:
            record.state = "blocked"
        elif record.drift_reasons or record.consistency_score != 1.0:
            record.state = "drift-detected"

        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self.receipt_nonces.update(nonces)
        self._audit(record, "observed")
        return record

    def approve_consistency(self, record_id: str, *, actor: str, human_approved: bool) -> CrossConsumerConsistencyRecord:
        record = self.records[record_id]
        if record.state != "review-required" or record.consistency_score != 1.0 or record.drift_reasons or not human_approved or record.risk_brain_blocked:
            if record.state != "drift-detected":
                record.state = "blocked"
        else:
            record.state = "consistent"
            record.approved_by = actor
        self._audit(record, "consistency-reviewed")
        return record

    def _audit(self, record: CrossConsumerConsistencyRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
