"""PHOENIX v21.192 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance."""
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
class RecoveryReliabilityImpactPreview:
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
    candidate_value: float = 0.0
    preview_digest: str = field(init=False)
    approved_by: str | None = None

    def __post_init__(self) -> None:
        self.candidate_value = self.current_value + self.feedback_adjustment
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
    """Simulate bounded baseline feedback impact without changing any baseline or runtime state."""

    def __init__(self, *, max_adjustment: float = 0.05, max_blast_radius: float = 0.50, max_residual_risk: float = 0.35) -> None:
        self.max_adjustment = max_adjustment
        self.max_blast_radius = max_blast_radius
        self.max_residual_risk = max_residual_risk
        self.records: dict[str, RecoveryReliabilityImpactPreview] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def simulate(self, record: RecoveryReliabilityImpactPreview, *, source_state: str, source_human_approved: bool) -> RecoveryReliabilityImpactPreview:
        impacts = (
            record.score_impact,
            record.rank_impact,
            record.failover_tendency_impact,
            record.recovery_readiness_impact,
        )
        invalid = (
            source_state != "approved-feedback"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or record.source_record_id in self.source_ids
            or not 0.0 <= record.current_value <= 1.0
            or abs(record.feedback_adjustment) > self.max_adjustment
            or not 0.0 <= record.candidate_value <= 1.0
            or any(not -1.0 <= value <= 1.0 for value in impacts)
            or not 0.0 <= record.blast_radius <= self.max_blast_radius
            or not 0.0 <= record.residual_risk <= self.max_residual_risk
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "simulated")
        return record

    def approve_preview(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryReliabilityImpactPreview:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "approved-preview"
            record.approved_by = actor
        self._audit(record, "preview-reviewed")
        return record

    def _audit(self, record: RecoveryReliabilityImpactPreview, action: str) -> None:
        record.preview_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.preview_digest})
