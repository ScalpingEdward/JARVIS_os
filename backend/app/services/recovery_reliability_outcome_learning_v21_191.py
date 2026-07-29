"""PHOENIX v21.191 — Recovery Reliability Outcome Learning & Baseline Feedback Governance."""
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
class RecoveryReliabilityLearningRecord:
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
    proposed_adjustment: float
    risk_brain_blocked: bool = False
    state: State = "review-required"
    learning_score: float = 0.0
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
            "proposed_adjustment": self.proposed_adjustment,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "learning_score": self.learning_score,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityOutcomeLearningGovernance:
    """Learn from closed recovery episodes without mutating committed/runtime baselines."""

    def __init__(
        self,
        *,
        max_feedback_adjustment: float = 0.05,
        min_stability_score: float = 0.85,
        min_confidence: float = 0.80,
        min_recovery_quality: float = 0.85,
        max_residual_risk: float = 0.30,
    ) -> None:
        self.max_feedback_adjustment = max_feedback_adjustment
        self.min_stability_score = min_stability_score
        self.min_confidence = min_confidence
        self.min_recovery_quality = min_recovery_quality
        self.max_residual_risk = max_residual_risk
        self.records: dict[str, RecoveryReliabilityLearningRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def learn(
        self,
        record: RecoveryReliabilityLearningRecord,
        *,
        source_state: str,
        source_human_approved: bool,
    ) -> RecoveryReliabilityLearningRecord:
        metrics = (
            record.stability_score,
            record.aggregate_confidence,
            record.recovery_quality,
            record.residual_risk,
        )
        invalid = (
            source_state != "closed"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or record.source_record_id in self.source_ids
            or any(v < 0.0 or v > 1.0 for v in metrics)
            or abs(record.proposed_adjustment) > self.max_feedback_adjustment
        )
        if not invalid:
            quality_ok = (
                record.stability_score >= self.min_stability_score
                and record.aggregate_confidence >= self.min_confidence
                and record.recovery_quality >= self.min_recovery_quality
                and record.residual_risk <= self.max_residual_risk
            )
            if not quality_ok:
                invalid = True

        if invalid:
            record.state = "blocked"
        else:
            safety = 1.0 - record.residual_risk
            record.learning_score = (
                record.stability_score
                + record.aggregate_confidence
                + record.recovery_quality
                + safety
            ) / 4.0

        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "learned")
        return record

    def approve_feedback(
        self,
        record_id: str,
        *,
        actor: str,
        human_approved: bool,
    ) -> RecoveryReliabilityLearningRecord:
        record = self.records[record_id]
        if (
            record.state != "review-required"
            or not human_approved
            or record.risk_brain_blocked
            or record.learning_score <= 0.0
            or abs(record.proposed_adjustment) > self.max_feedback_adjustment
        ):
            record.state = "blocked"
        else:
            record.state = "approved-feedback"
            record.approved_by = actor
        self._audit(record, "feedback-reviewed")
        return record

    def _audit(self, record: RecoveryReliabilityLearningRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
