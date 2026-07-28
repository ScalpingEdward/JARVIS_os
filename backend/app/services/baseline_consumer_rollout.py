"""PHOENIX v21.146 — Baseline Consumer Eligibility & Controlled Rollout Governance.

Consumes an approved v21.145 simulation preview and creates a human-approved,
staged allow-list for downstream governance consumers. It does not mutate routing,
policies, permissions, credentials, or execution settings.
"""
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
class ConsumerRolloutRecord:
    rollout_id: str
    workspace_id: str
    preview_id: str
    preview_digest: str
    baseline_id: str
    baseline_version: int
    eligible_consumers: list[str]
    rollout_stage: int
    max_stage: int
    status: str
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    rollout_digest: str = ""


class BaselineConsumerRolloutService:
    def __init__(self) -> None:
        self._records: dict[str, ConsumerRolloutRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        rollout_id: str,
        workspace_id: str,
        approved_preview: dict[str, Any],
        requested_consumers: list[str],
        source_key: str,
        max_stage: int = 3,
    ) -> ConsumerRolloutRecord:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if rollout_id in self._records:
            raise ValueError("duplicate rollout id")

        findings: list[str] = []
        if approved_preview.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if approved_preview.get("status") != "approved-preview":
            findings.append("preview-not-approved")
        if not approved_preview.get("human_approved", False):
            findings.append("preview-human-approval-missing")
        if approved_preview.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")
        if float(approved_preview.get("blast_radius", 1.0)) > 0.35:
            findings.append("blast-radius-above-rollout-ceiling")
        if float(approved_preview.get("residual_risk", 1.0)) > 0.25:
            findings.append("residual-risk-above-rollout-ceiling")
        if max_stage < 1 or max_stage > 5:
            findings.append("invalid-max-stage")

        requested = sorted(set(requested_consumers))
        unsupported = sorted(set(requested) - ALLOWED_CONSUMERS)
        if unsupported:
            findings.extend(f"unsupported-consumer:{name}" for name in unsupported)
        eligible = [name for name in requested if name in ALLOWED_CONSUMERS]
        if not eligible:
            findings.append("no-eligible-consumers")

        record = ConsumerRolloutRecord(
            rollout_id=rollout_id,
            workspace_id=workspace_id,
            preview_id=str(approved_preview.get("record_id", approved_preview.get("preview_id", ""))),
            preview_digest=_digest(approved_preview),
            baseline_id=str(approved_preview.get("baseline_id", "")),
            baseline_version=int(approved_preview.get("baseline_version", 0)),
            eligible_consumers=eligible,
            rollout_stage=0,
            max_stage=max_stage,
            status="review-required" if not findings else "blocked",
            risk_brain_blocked=bool(approved_preview.get("risk_brain_blocked", False)),
            findings=findings,
        )
        record.rollout_digest = _digest(asdict(record))
        self._records[rollout_id] = record
        self._audit.append({"event": "rollout-created", "id": rollout_id, "digest": record.rollout_digest})
        return record

    def approve(self, rollout_id: str, *, human_approved: bool) -> ConsumerRolloutRecord:
        record = self._records[rollout_id]
        if record.status != "review-required":
            raise ValueError("rollout is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "approved"
        record.rollout_digest = _digest(asdict(record))
        self._audit.append({"event": "rollout-approved", "id": rollout_id, "digest": record.rollout_digest})
        return record

    def advance_stage(self, rollout_id: str, *, human_approved: bool) -> ConsumerRolloutRecord:
        record = self._records[rollout_id]
        if record.status not in {"approved", "staged"}:
            raise ValueError("rollout is not stage-eligible")
        if not record.human_approved or not human_approved:
            raise ValueError("human approval required for stage advancement")
        if record.rollout_stage >= record.max_stage:
            raise ValueError("rollout already complete")
        record.rollout_stage += 1
        record.status = "active" if record.rollout_stage == record.max_stage else "staged"
        record.rollout_digest = _digest(asdict(record))
        self._audit.append({"event": "rollout-stage-advanced", "id": rollout_id, "stage": record.rollout_stage, "digest": record.rollout_digest})
        return record

    def get(self, rollout_id: str) -> ConsumerRolloutRecord:
        return self._records[rollout_id]

    def list_records(self, workspace_id: str | None = None) -> list[ConsumerRolloutRecord]:
        records = list(self._records.values())
        return records if workspace_id is None else [r for r in records if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
