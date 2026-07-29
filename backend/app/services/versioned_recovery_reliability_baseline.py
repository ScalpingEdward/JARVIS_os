"""PHOENIX v21.183 — Versioned Recovery Reliability Baseline Proposal & Controlled Commit Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "committed", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass
class RecoveryReliabilityBaselineProposal:
    record_id: str
    workspace_id: str
    source_record_id: str
    preview_id: str
    baseline_id: str
    previous_version: int
    candidate_version: int
    previous_value: float
    candidate_value: float
    previous_digest: str
    rollback_version: int
    rollback_value: float
    risk_brain_blocked: bool = False
    state: State = "review-required"
    approved_by: str | None = None
    candidate_digest: str = field(init=False)
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        self.candidate_digest = _digest({
            "workspace_id": self.workspace_id,
            "baseline_id": self.baseline_id,
            "version": self.candidate_version,
            "value": self.candidate_value,
            "previous_digest": self.previous_digest,
            "preview_id": self.preview_id,
        })
        self.audit_digest = _digest(self.snapshot())

    def snapshot(self) -> dict:
        return {
            "record_id": self.record_id,
            "workspace_id": self.workspace_id,
            "source_record_id": self.source_record_id,
            "preview_id": self.preview_id,
            "baseline_id": self.baseline_id,
            "previous_version": self.previous_version,
            "candidate_version": self.candidate_version,
            "previous_value": self.previous_value,
            "candidate_value": self.candidate_value,
            "previous_digest": self.previous_digest,
            "rollback_version": self.rollback_version,
            "rollback_value": self.rollback_value,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "approved_by": self.approved_by,
            "candidate_digest": self.candidate_digest,
        }


class VersionedRecoveryReliabilityBaselineGovernance:
    """Govern versioned baseline commits without activating or mutating runtime consumers."""

    MAX_DELTA = 0.05

    def __init__(self) -> None:
        self.records: dict[str, RecoveryReliabilityBaselineProposal] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: RecoveryReliabilityBaselineProposal, *, source_state: str, source_human_approved: bool) -> RecoveryReliabilityBaselineProposal:
        invalid = (
            source_state != "approved-preview"
            or not source_human_approved
            or not record.workspace_id
            or not record.preview_id
            or not record.baseline_id
            or not record.previous_digest
            or record.previous_version < 1
            or record.candidate_version != record.previous_version + 1
            or record.rollback_version != record.previous_version
            or abs(record.rollback_value - record.previous_value) > 1e-12
            or not 0.0 <= record.previous_value <= 1.0
            or not 0.0 <= record.candidate_value <= 1.0
            or abs(record.candidate_value - record.previous_value) > self.MAX_DELTA
            or record.source_record_id in self.source_ids
            or record.risk_brain_blocked
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def approve_commit(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryReliabilityBaselineProposal:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "committed"
            record.approved_by = actor
        self._audit(record, "commit-reviewed")
        return record

    def _audit(self, record: RecoveryReliabilityBaselineProposal, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
