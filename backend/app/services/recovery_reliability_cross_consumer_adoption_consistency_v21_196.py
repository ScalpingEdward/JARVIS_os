"""PHOENIX v21.196 — Recovery Reliability Cross-Consumer Adoption Consistency & Drift Observation Governance."""
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
class AdoptionObservation:
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    receipt_nonce: str
    receipt_age_seconds: int
    healthy: bool
    adopted: bool
    confidence: float


@dataclass
class CrossConsumerAdoptionRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: tuple[str, ...]
    observations: tuple[AdoptionObservation, ...]
    receipt_ttl_seconds: int = 900
    min_consistency_score: float = 0.95
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
            "receipt_ttl_seconds": self.receipt_ttl_seconds,
            "min_consistency_score": self.min_consistency_score,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "consistency_score": self.consistency_score,
            "drift_reasons": self.drift_reasons,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityCrossConsumerAdoptionConsistencyGovernance:
    """Reconcile adoption evidence across consumers without mutating runtime state."""

    def __init__(self) -> None:
        self.records: dict[str, CrossConsumerAdoptionRecord] = {}
        self.source_ids: set[str] = set()
        self.receipt_nonces: set[str] = set()
        self.audit: list[dict] = []

    def observe(
        self,
        record: CrossConsumerAdoptionRecord,
        *,
        source_state: str,
        source_human_approved: bool,
    ) -> CrossConsumerAdoptionRecord:
        consumers = [o.consumer_id for o in record.observations]
        nonces = [o.receipt_nonce for o in record.observations]
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
            or len(record.expected_consumers) != len(set(record.expected_consumers))
            or len(consumers) != len(set(consumers))
            or len(nonces) != len(set(nonces))
            or any(n in self.receipt_nonces or not n for n in nonces)
            or record.receipt_ttl_seconds <= 0
            or not (0.0 <= record.min_consistency_score <= 1.0)
        )

        reasons: list[str] = []
        expected = set(record.expected_consumers)
        observed = set(consumers)
        if not invalid:
            for missing in sorted(expected - observed):
                reasons.append(f"missing-consumer:{missing}")
            for unexpected in sorted(observed - expected):
                reasons.append(f"unexpected-consumer:{unexpected}")

            valid_count = 0
            for o in record.observations:
                exact = (
                    o.workspace_id == record.workspace_id
                    and o.baseline_id == record.baseline_id
                    and o.baseline_version == record.baseline_version
                    and o.baseline_digest == record.baseline_digest
                )
                if not exact:
                    reasons.append(f"baseline-or-workspace-mismatch:{o.consumer_id}")
                if o.receipt_age_seconds < 0 or o.receipt_age_seconds > record.receipt_ttl_seconds:
                    reasons.append(f"stale-receipt:{o.consumer_id}")
                if not o.adopted:
                    reasons.append(f"not-adopted:{o.consumer_id}")
                if not o.healthy:
                    reasons.append(f"unhealthy-consumer:{o.consumer_id}")
                if not (0.0 <= o.confidence <= 1.0):
                    invalid = True
                    break
                if exact and 0 <= o.receipt_age_seconds <= record.receipt_ttl_seconds and o.adopted and o.healthy:
                    valid_count += 1

            if record.expected_consumers:
                record.consistency_score = valid_count / len(record.expected_consumers)
                if record.consistency_score < record.min_consistency_score:
                    reasons.append("consistency-score-below-threshold")

        if invalid:
            record.state = "blocked"
        elif reasons:
            record.state = "drift-detected"
            record.drift_reasons = tuple(sorted(set(reasons)))
        else:
            record.state = "review-required"
            record.drift_reasons = ()

        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self.receipt_nonces.update(nonces)
        self._audit(record, "observed")
        return record

    def approve_consistency(self, record_id: str, *, actor: str, human_approved: bool) -> CrossConsumerAdoptionRecord:
        record = self.records[record_id]
        if (
            record.state != "review-required"
            or not human_approved
            or record.risk_brain_blocked
            or record.consistency_score < record.min_consistency_score
            or record.drift_reasons
        ):
            if record.state != "drift-detected":
                record.state = "blocked"
        else:
            record.state = "consistent"
            record.approved_by = actor
        self._audit(record, "consistency-reviewed")
        return record

    def _audit(self, record: CrossConsumerAdoptionRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
