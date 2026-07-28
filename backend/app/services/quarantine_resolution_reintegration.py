"""PHOENIX v21.151 — Quarantine Resolution Authorization & Controlled Consumer Reintegration Governance.

Governance only. Converts human-approved `resolution-ready` evidence into a separately
approved reintegration authorization with exact consumer/baseline binding and staged
re-entry. No routing, policy, permission, credential, or execution mutation occurs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class ReintegrationRecord:
    record_id: str
    workspace_id: str
    consumer_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    readiness_record_id: str
    readiness_digest: str
    quarantine_record_id: str
    status: str
    stage: int = 0
    max_stage: int = 3
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    authorization_digest: str = ""


class QuarantineResolutionReintegrationService:
    """Fail-closed authorization and staged reintegration governance."""

    def __init__(self) -> None:
        self._records: dict[str, ReintegrationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        resolution_readiness: dict[str, Any],
        quarantine_record: dict[str, Any],
        source_key: str,
        max_stage: int = 3,
    ) -> ReintegrationRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if resolution_readiness.get("workspace_id") != workspace_id:
            findings.append("readiness-workspace-mismatch")
        if quarantine_record.get("workspace_id") != workspace_id:
            findings.append("quarantine-workspace-mismatch")
        if resolution_readiness.get("status") != "resolution-ready":
            findings.append("readiness-not-approved")
        if not resolution_readiness.get("human_approved", False):
            findings.append("readiness-human-approval-missing")
        if quarantine_record.get("status") != "quarantined":
            findings.append("consumer-not-quarantined")

        consumer_id = str(quarantine_record.get("consumer_id", ""))
        if resolution_readiness.get("consumer_id") not in (None, consumer_id):
            findings.append("consumer-binding-mismatch")

        baseline_id = str(quarantine_record.get("baseline_id", quarantine_record.get("expected_baseline_id", "")))
        baseline_version = int(quarantine_record.get("baseline_version", quarantine_record.get("expected_baseline_version", 0)) or 0)
        baseline_digest = str(quarantine_record.get("baseline_digest", quarantine_record.get("expected_baseline_digest", "")))
        for field_name, expected in (
            ("baseline_id", baseline_id),
            ("baseline_version", baseline_version),
            ("baseline_digest", baseline_digest),
        ):
            actual = resolution_readiness.get(field_name)
            if actual not in (None, expected):
                findings.append(f"{field_name}-binding-mismatch")

        risk_blocked = bool(resolution_readiness.get("risk_brain_blocked", False) or quarantine_record.get("risk_brain_blocked", False))
        if risk_blocked:
            findings.append("risk-brain-hard-block")

        if max_stage < 1 or max_stage > 5:
            findings.append("invalid-stage-count")

        status = "review-required" if not findings else "blocked"
        record = ReintegrationRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            consumer_id=consumer_id,
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            readiness_record_id=str(resolution_readiness.get("record_id", "")),
            readiness_digest=_digest(resolution_readiness),
            quarantine_record_id=str(quarantine_record.get("record_id", "")),
            status=status,
            max_stage=max_stage,
            risk_brain_blocked=risk_blocked,
            findings=findings,
        )
        record.authorization_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "reintegration-proposed", "id": record_id, "digest": record.authorization_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> ReintegrationRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("reintegration not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "authorized"
        record.authorization_digest = _digest(asdict(record))
        self._audit.append({"event": "reintegration-authorized", "id": record_id, "digest": record.authorization_digest})
        return record

    def advance_stage(self, record_id: str, *, human_approved: bool) -> ReintegrationRecord:
        record = self._records[record_id]
        if record.status not in {"authorized", "staged"}:
            raise ValueError("reintegration is not stage-eligible")
        if not human_approved:
            raise ValueError("human approval required for every stage")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        if record.stage >= record.max_stage:
            raise ValueError("reintegration already complete")
        record.stage += 1
        record.status = "reintegrated" if record.stage == record.max_stage else "staged"
        record.authorization_digest = _digest(asdict(record))
        self._audit.append({"event": "reintegration-stage-advanced", "id": record_id, "stage": record.stage, "digest": record.authorization_digest})
        return record

    def get(self, record_id: str) -> ReintegrationRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[ReintegrationRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
