"""PHOENIX v21.172 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance."""
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
    proposed_adjustment: float
    candidate_value: float
    score_impact: float
    rank_impact: float
    failover_tendency_impact: float
    recovery_readiness_impact: float
    blast_radius: float
    residual_risk: float
    max_abs_adjustment: float = 0.05
    max_blast_radius: float = 0.25
    max_residual_risk: float = 0.25
    risk_brain_blocked: bool = False
    state: State = "review-required"
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
            "current_value": self.current_value,
            "proposed_adjustment": self.proposed_adjustment,
            "candidate_value": self.candidate_value,
            "score_impact": self.score_impact,
            "rank_impact": self.rank_impact,
            "failover_tendency_impact": self.failover_tendency_impact,
            "recovery_readiness_impact": self.recovery_readiness_impact,
            "blast_radius": self.blast_radius,
            "residual_risk": self.residual_risk,
            "state": self.state,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityFeedbackImpactGovernance:
    """Simulate bounded feedback impact only; never mutates the active baseline."""

    def __init__(self) -> None:
        self.records: dict[str, RecoveryReliabilityImpactPreview] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: RecoveryReliabilityImpactPreview, *, source_state: str, source_human_approved: bool) -> RecoveryReliabilityImpactPreview:
        invalid = (
            source_state != "approved-feedback"
            or not source_human_approved
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or record.source_record_id in self.source_ids
            or record.risk_brain_blocked
            or not 0.0 <= record.current_value <= 1.0
            or not 0.0 <= record.candidate_value <= 1.0
            or abs(record.proposed_adjustment) > record.max_abs_adjustment
            or abs((record.current_value + record.proposed_adjustment) - record.candidate_value) > 1e-9
            or not 0.0 <= record.blast_radius <= 1.0
            or not 0.0 <= record.residual_risk <= 1.0
            or record.blast_radius > record.max_blast_radius
            or record.residual_risk > record.max_residual_risk
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
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
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
