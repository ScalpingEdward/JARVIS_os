"""PHOENIX v21.163 — Versioned Reliability Baseline Proposal & Controlled Commit Governance."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class BaselineProposalRecord:
    record_id: str
    workspace_id: str
    baseline_id: str
    previous_version: int
    candidate_version: int
    previous_value: float
    candidate_value: float
    preview_digest: str
    rollback_version: int
    rollback_value: float
    status: str
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    baseline_digest: str = ""
    record_digest: str = ""


class VersionedReliabilityBaselineService:
    """Fail-closed versioned baseline proposal and commit governance."""

    def __init__(self) -> None:
        self._records: dict[str, BaselineProposalRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        approved_preview: dict[str, Any],
        source_key: str,
        max_delta: float = 0.05,
    ) -> BaselineProposalRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if approved_preview.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if approved_preview.get("status") != "approved-preview":
            findings.append("preview-not-approved")
        if not approved_preview.get("human_approved", False):
            findings.append("preview-human-approval-missing")
        if approved_preview.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        baseline_id = str(approved_preview.get("baseline_id", ""))
        previous_version = int(approved_preview.get("baseline_version", 0) or 0)
        previous_value = float(approved_preview.get("baseline_value", 0.0) or 0.0)
        candidate_value = float(approved_preview.get("candidate_value", previous_value) or previous_value)
        candidate_version = int(approved_preview.get("candidate_version", previous_version + 1) or (previous_version + 1))

        if not baseline_id:
            findings.append("baseline-id-missing")
        if previous_version < 1:
            findings.append("previous-version-invalid")
        if candidate_version <= previous_version:
            findings.append("candidate-version-regression")
        if not 0.0 <= previous_value <= 1.0 or not 0.0 <= candidate_value <= 1.0:
            findings.append("baseline-value-out-of-range")
        if abs(candidate_value - previous_value) > max_delta:
            findings.append("candidate-delta-exceeds-limit")

        risk_blocked = bool(approved_preview.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "blocked"
        baseline_material = {
            "baseline_id": baseline_id,
            "version": candidate_version,
            "value": round(candidate_value, 6),
            "previous_version": previous_version,
            "previous_value": round(previous_value, 6),
        }
        baseline_digest = _digest(baseline_material)
        record = BaselineProposalRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            baseline_id=baseline_id,
            previous_version=previous_version,
            candidate_version=candidate_version,
            previous_value=round(previous_value, 6),
            candidate_value=round(candidate_value, 6),
            preview_digest=_digest(approved_preview),
            rollback_version=previous_version,
            rollback_value=round(previous_value, 6),
            status=status,
            risk_brain_blocked=risk_blocked,
            findings=findings,
            baseline_digest=baseline_digest,
        )
        record.record_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "baseline-proposed", "id": record_id, "digest": record.record_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> BaselineProposalRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("baseline proposal is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "committed"
        record.record_digest = _digest(asdict(record))
        self._audit.append({"event": "baseline-committed", "id": record_id, "digest": record.record_digest})
        return record

    def get(self, record_id: str) -> BaselineProposalRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[BaselineProposalRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
