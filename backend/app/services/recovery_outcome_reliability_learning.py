"""PHOENIX v21.171 — Recovery Outcome Reliability Learning & Baseline Feedback Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "approved-feedback", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass
class RecoveryOutcomeFeedbackRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    stability_score: float
    aggregate_confidence: float
    recovery_quality: float
    residual_risk: float
    previous_reliability: float
    risk_brain_blocked: bool = False
    state: State = "review-required"
    learning_score: float = 0.0
    proposed_reliability: float = 0.0
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
            "stability_score": self.stability_score,
            "aggregate_confidence": self.aggregate_confidence,
            "recovery_quality": self.recovery_quality,
            "residual_risk": self.residual_risk,
            "previous_reliability": self.previous_reliability,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "learning_score": self.learning_score,
            "proposed_reliability": self.proposed_reliability,
            "approved_by": self.approved_by,
        }


class RecoveryOutcomeReliabilityLearningGovernance:
    """Derive bounded reliability feedback from a closed recovery episode; never mutates baselines."""

    MAX_ADJUSTMENT = 0.05

    def __init__(self) -> None:
        self.records: dict[str, RecoveryOutcomeFeedbackRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: RecoveryOutcomeFeedbackRecord, *, source_state: str, source_human_approved: bool) -> RecoveryOutcomeFeedbackRecord:
        values = [record.stability_score, record.aggregate_confidence, record.recovery_quality, record.residual_risk, record.previous_reliability]
        invalid = (
            source_state != "closed"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or record.source_record_id in self.source_ids
            or any(v < 0.0 or v > 1.0 for v in values)
        )
        if invalid:
            record.state = "blocked"
        else:
            record.learning_score = round((record.stability_score + record.aggregate_confidence + record.recovery_quality + (1.0 - record.residual_risk)) / 4.0, 6)
            raw_delta = (record.learning_score - 0.5) * 0.1
            bounded_delta = max(-self.MAX_ADJUSTMENT, min(self.MAX_ADJUSTMENT, raw_delta))
            record.proposed_reliability = round(max(0.0, min(1.0, record.previous_reliability + bounded_delta)), 6)
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def approve_feedback(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryOutcomeFeedbackRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "approved-feedback"
            record.approved_by = actor
        self._audit(record, "feedback-reviewed")
        return record

    def _audit(self, record: RecoveryOutcomeFeedbackRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
