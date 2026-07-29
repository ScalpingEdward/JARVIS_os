"""PHOENIX v21.176 — Recovery Reliability Cross-Consumer Adoption Consistency & Drift Observation Governance."""
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
    receipt_digest: str
    healthy: bool


@dataclass
class RecoveryReliabilityConsistencyRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: tuple[str, ...]
    observations: tuple[ConsumerAdoptionObservation, ...]
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
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "consistency_score": self.consistency_score,
            "drift_reasons": self.drift_reasons,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityAdoptionConsistencyGovernance:
    """Observe cross-consumer adoption consistency; never mutates consumers or baselines."""

    def __init__(self) -> None:
        self.records: dict[str, RecoveryReliabilityConsistencyRecord] = {}
        self.source_ids: set[str] = set()
        self.receipt_digests: set[str] = set()
        self.audit: list[dict] = []

    def observe(self, record: RecoveryReliabilityConsistencyRecord, *, source_state: str, source_human_approved: bool) -> RecoveryReliabilityConsistencyRecord:
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
            or len(set(record.expected_consumers)) != len(record.expected_consumers)
        )
        consumers = [o.consumer_id for o in record.observations]
        receipts = [o.receipt_digest for o in record.observations]
        if len(consumers) != len(set(consumers)) or len(receipts) != len(set(receipts)):
            invalid = True
        if any(not r or r in self.receipt_digests for r in receipts):
            invalid = True

        reasons: list[str] = []
        exact_count = 0
        by_consumer = {o.consumer_id: o for o in record.observations}
        for consumer_id in record.expected_consumers:
            obs = by_consumer.get(consumer_id)
            if obs is None:
                reasons.append(f"missing:{consumer_id}")
                continue
            exact = (
                obs.workspace_id == record.workspace_id
                and obs.baseline_id == record.baseline_id
                and obs.baseline_version == record.baseline_version
                and obs.baseline_digest == record.baseline_digest
                and bool(obs.receipt_digest)
                and obs.healthy
            )
            if exact:
                exact_count += 1
            else:
                reasons.append(f"drift:{consumer_id}")
        unexpected = sorted(set(consumers) - set(record.expected_consumers))
        reasons.extend(f"unexpected:{c}" for c in unexpected)

        record.consistency_score = exact_count / len(record.expected_consumers)
        record.drift_reasons = tuple(reasons)
        if invalid:
            record.state = "blocked"
        elif record.consistency_score != 1.0 or reasons:
            record.state = "drift-detected"

        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self.receipt_digests.update(receipts)
        self._audit(record, "observed")
        return record

    def approve_consistency(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryReliabilityConsistencyRecord:
        record = self.records[record_id]
        if record.state != "review-required" or record.consistency_score != 1.0 or record.drift_reasons or not human_approved or record.risk_brain_blocked:
            if record.state != "drift-detected":
                record.state = "blocked"
        else:
            record.state = "consistent"
            record.approved_by = actor
        self._audit(record, "consistency-reviewed")
        return record

    def _audit(self, record: RecoveryReliabilityConsistencyRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
