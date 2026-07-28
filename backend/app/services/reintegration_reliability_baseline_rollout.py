"""PHOENIX v21.155 — Reintegration Reliability Baseline Commit & Controlled Consumer Rollout Governance."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any

ALLOWED_CONSUMERS = {
    "adapter-selection",
    "worker-selection",
    "dispatch-planning",
    "failover-health",
    "recovery-readiness",
}


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class BaselineRolloutRecord:
    record_id: str
    workspace_id: str
    preview_id: str
    preview_digest: str
    baseline_id: str
    baseline_version: int
    baseline_value: float
    baseline_digest: str
    consumers: list[str]
    rollout_stage: int
    max_stage: int
    status: str
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    record_digest: str = ""


class ReintegrationReliabilityBaselineRolloutService:
    """Versioned baseline commit plus staged consumer eligibility; no runtime mutation."""

    def __init__(self) -> None:
        self._records: dict[str, BaselineRolloutRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []
        self._versions: dict[tuple[str, str], int] = {}

    def create(self, *, record_id: str, workspace_id: str, approved_preview: dict[str, Any], consumers: list[str], source_key: str, max_stage: int = 3) -> BaselineRolloutRecord:
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

        unsupported = sorted(set(consumers) - ALLOWED_CONSUMERS)
        if unsupported:
            findings.append("unsupported-consumer:" + ",".join(unsupported))
        if not consumers:
            findings.append("no-consumers")

        value = float(approved_preview.get("candidate_baseline", approved_preview.get("proposed_reliability", 0.0)))
        if not 0.0 <= value <= 1.0:
            findings.append("baseline-out-of-range")

        baseline_id = str(approved_preview.get("baseline_id") or f"reintegration:{approved_preview.get('consumer_id','unknown')}")
        version_key = (workspace_id, baseline_id)
        version = self._versions.get(version_key, 0) + 1
        baseline_digest = _digest({"workspace_id": workspace_id, "baseline_id": baseline_id, "version": version, "value": round(value, 6)})
        status = "review-required" if not findings else "blocked"

        record = BaselineRolloutRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            preview_id=str(approved_preview.get("record_id", approved_preview.get("preview_id", ""))),
            preview_digest=_digest(approved_preview),
            baseline_id=baseline_id,
            baseline_version=version,
            baseline_value=round(value, 6),
            baseline_digest=baseline_digest,
            consumers=sorted(set(consumers)),
            rollout_stage=0,
            max_stage=max(1, int(max_stage)),
            status=status,
            risk_brain_blocked=bool(approved_preview.get("risk_brain_blocked", False)),
            findings=findings,
        )
        record.record_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "rollout-created", "id": record_id, "digest": record.record_digest})
        return record

    def approve_commit(self, record_id: str, *, human_approved: bool) -> BaselineRolloutRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record not eligible for commit approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "committed"
        self._versions[(record.workspace_id, record.baseline_id)] = record.baseline_version
        record.record_digest = _digest(asdict(record))
        self._audit.append({"event": "baseline-committed", "id": record_id, "digest": record.record_digest})
        return record

    def advance_stage(self, record_id: str, *, human_approved: bool) -> BaselineRolloutRecord:
        record = self._records[record_id]
        if record.status not in {"committed", "staged"}:
            raise ValueError("record not eligible for stage advance")
        if not human_approved:
            raise ValueError("human approval required for every stage")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.rollout_stage += 1
        record.status = "active" if record.rollout_stage >= record.max_stage else "staged"
        record.record_digest = _digest(asdict(record))
        self._audit.append({"event": "stage-advanced", "id": record_id, "stage": record.rollout_stage, "digest": record.record_digest})
        return record

    def get(self, record_id: str) -> BaselineRolloutRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[BaselineRolloutRecord]:
        records = list(self._records.values())
        return records if workspace_id is None else [r for r in records if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
