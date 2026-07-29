"""PHOENIX v21.193 — Versioned Recovery Reliability Baseline Proposal & Controlled Commit Governance."""
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
    proposed_version: int
    previous_value: float
    candidate_value: float
    previous_digest: str
    rollback_version: int
    rollback_value: float
    risk_brain_blocked: bool = False
    state: State = "review-required"
    committed_by: str | None = None
    candidate_digest: str = field(init=False)
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        self.candidate_digest = _digest(self.candidate_snapshot())
        self.audit_digest = _digest(self.snapshot())

    def candidate_snapshot(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "baseline_id": self.baseline_id,
            "version": self.proposed_version,
            "value": self.candidate_value,
            "previous_version": self.previous_version,
            "previous_digest": self.previous_digest,
            "rollback_version": self.rollback_version,
            "rollback_value": self.rollback_value,
        }

    def snapshot(self) -> dict:
        return {
            "record_id": self.record_id,
            "workspace_id": self.workspace_id,
            "source_record_id": self.source_record_id,
            "preview_id": self.preview_id,
            "baseline_id": self.baseline_id,
            "previous_version": self.previous_version,
            "proposed_version": self.proposed_version,
            "previous_value": self.previous_value,
            "candidate_value": self.candidate_value,
            "previous_digest": self.previous_digest,
            "rollback_version": self.rollback_version,
            "rollback_value": self.rollback_value,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "committed_by": self.committed_by,
            "candidate_digest": self.candidate_digest,
        }


class VersionedRecoveryReliabilityBaselineCommitGovernance:
    """Create a versioned baseline proposal and gate commit without activating it."""

    def __init__(self, *, max_candidate_delta: float = 0.05) -> None:
        self.max_candidate_delta = max_candidate_delta
        self.records: dict[str, RecoveryReliabilityBaselineProposal] = {}
        self.source_ids: set[str] = set()
        self.preview_ids: set[str] = set()
        self.audit: list[dict] = []

    def propose(
        self,
        record: RecoveryReliabilityBaselineProposal,
        *,
        source_state: str,
        source_human_approved: bool,
        preview_previous_value: float,
        preview_candidate_value: float,
    ) -> RecoveryReliabilityBaselineProposal:
        invalid = (
            source_state != "approved-preview"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.preview_id
            or not record.baseline_id
            or record.previous_version < 1
            or record.proposed_version != record.previous_version + 1
            or record.rollback_version != record.previous_version
            or record.rollback_value != record.previous_value
            or not record.previous_digest
            or record.source_record_id in self.source_ids
            or record.preview_id in self.preview_ids
            or not (0.0 <= record.previous_value <= 1.0)
            or not (0.0 <= record.candidate_value <= 1.0)
            or abs(record.candidate_value - record.previous_value) > self.max_candidate_delta
            or record.previous_value != preview_previous_value
            or record.candidate_value != preview_candidate_value
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self.preview_ids.add(record.preview_id)
        self._audit(record, "proposed")
        return record

    def commit(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryReliabilityBaselineProposal:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "committed"
            record.committed_by = actor
        self._audit(record, "commit-reviewed")
        return record

    def _audit(self, record: RecoveryReliabilityBaselineProposal, action: str) -> None:
        record.candidate_digest = _digest(record.candidate_snapshot())
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
