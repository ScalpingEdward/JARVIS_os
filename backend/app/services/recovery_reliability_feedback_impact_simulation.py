"""PHOENIX v21.182 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "approved-preview", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass
class FeedbackImpactPreviewRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    current_value: float
    feedback_adjustment: float
    score_impact: float
    rank_impact: float
    failover_tendency_impact: float
    recovery_readiness_impact: float
    blast_radius: float
    residual_risk: float
    risk_brain_blocked: bool = False
    state: State = "review-required"
    candidate_value: float = field(init=False)
    preview_digest: str = field(init=False)
    approved_by: str | None = None

    def __post_init__(self) -> None:
        self.candidate_value = round(self.current_value + self.feedback_adjustment, 10)
        self.preview_digest = _digest(self.snapshot())

    def snapshot(self) -> dict:
        return {
            "record_id": self.record_id,
            "workspace_id": self.workspace_id,
            "source_record_id": self.source_record_id,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "baseline_digest": self.baseline_digest,
            "current_value": self.current_value,
            "feedback_adjustment": self.feedback_adjustment,
            "candidate_value": self.candidate_value,
            "score_impact": self.score_impact,
            "rank_impact": self.rank_impact,
            "failover_tendency_impact": self.failover_tendency_impact,
            "recovery_readiness_impact": self.recovery_readiness_impact,
            "blast_radius": self.blast_radius,
            "residual_risk": self.residual_risk,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityFeedbackImpactSimulationGovernance:
    """Simulate bounded reliability feedback impact; never mutates baselines or consumers."""

    MAX_ABS_ADJUSTMENT = 0.05
    MAX_BLAST_RADIUS = 0.35
    MAX_RESIDUAL_RISK = 0.30

    def __init__(self) -> None:
        self.records: dict[str, FeedbackImpactPreviewRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create_preview(self, record: FeedbackImpactPreviewRecord, *, source_state: str, source_human_approved: bool) -> FeedbackImpactPreviewRecord:
        normalized = (
            record.current_value,
            record.candidate_value,
            record.score_impact,
            record.rank_impact,
            record.failover_tendency_impact,
            record.recovery_readiness_impact,
            record.blast_radius,
            record.residual_risk,
        )
        invalid = (
            source_state != "approved-feedback"
            or not source_human_approved
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or record.source_record_id in self.source_ids
            or abs(record.feedback_adjustment) > self.MAX_ABS_ADJUSTMENT
            or any(v < -1.0 or v > 1.0 for v in normalized[2:6])
            or record.current_value < 0.0
            or record.current_value > 1.0
            or record.candidate_value < 0.0
            or record.candidate_value > 1.0
            or record.blast_radius < 0.0
            or record.blast_radius > self.MAX_BLAST_RADIUS
            or record.residual_risk < 0.0
            or record.residual_risk > self.MAX_RESIDUAL_RISK
            or record.risk_brain_blocked
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "preview-created")
        return record

    def approve_preview(self, record_id: str, *, actor: str, human_approved: bool) -> FeedbackImpactPreviewRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "approved-preview"
            record.approved_by = actor
        self._audit(record, "preview-reviewed")
        return record

    def _audit(self, record: FeedbackImpactPreviewRecord, action: str) -> None:
        record.preview_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.preview_digest})
