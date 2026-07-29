"""PHOENIX v21.166 — Reliability Baseline Cross-Consumer Adoption Consistency & Drift Observation Governance."""
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
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    receipt_digest: str
    healthy: bool = True


@dataclass
class ConsistencyRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: tuple[str, ...]
    observations: tuple[AdoptionObservation, ...]
    risk_brain_blocked: bool = False
    state: State = "review-required"
    consistency_score: float = 0.0
    drift_consumers: tuple[str, ...] = ()
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
            "drift_consumers": self.drift_consumers,
        }


class ReliabilityBaselineConsistencyGovernance:
    """Observe exact adoption consistency across consumers without runtime mutation."""

    def __init__(self) -> None:
        self.records: dict[str, ConsistencyRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: ConsistencyRecord, *, source_state: str, source_human_approved: bool) -> ConsistencyRecord:
        if (
            source_state != "adopted"
            or not source_human_approved
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not record.expected_consumers
            or record.source_record_id in self.source_ids
            or len(set(record.expected_consumers)) != len(record.expected_consumers)
            or record.risk_brain_blocked
        ):
            record.state = "blocked"
            self._save(record, "created-blocked")
            return record

        observed_ids = [o.consumer_id for o in record.observations]
        if len(observed_ids) != len(set(observed_ids)) or set(observed_ids) != set(record.expected_consumers):
            record.state = "drift-detected"
            record.drift_consumers = tuple(sorted(set(record.expected_consumers).symmetric_difference(observed_ids)))
            record.consistency_score = 0.0
            self._save(record, "consumer-set-drift")
            return record

        drift = []
        matches = 0
        for obs in record.observations:
            exact = (
                obs.baseline_id == record.baseline_id
                and obs.baseline_version == record.baseline_version
                and obs.baseline_digest == record.baseline_digest
                and bool(obs.receipt_digest)
                and obs.healthy
            )
            if exact:
                matches += 1
            else:
                drift.append(obs.consumer_id)

        record.consistency_score = round(matches / len(record.expected_consumers), 6)
        record.drift_consumers = tuple(sorted(drift))
        record.state = "review-required" if not drift else "drift-detected"
        self._save(record, "observed")
        return record

    def approve_consistency(self, record_id: str, *, human_approved: bool, actor: str) -> ConsistencyRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked or record.consistency_score != 1.0:
            record.state = "blocked"
            self._save(record, f"approval-blocked:{actor}")
            return record
        record.state = "consistent"
        self._save(record, f"consistent-approved:{actor}")
        return record

    def _save(self, record: ConsistencyRecord, action: str) -> None:
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
