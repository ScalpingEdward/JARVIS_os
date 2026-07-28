"""PHOENIX v21.153 — Quarantine Episode Closure & Reintegration Reliability Feedback Governance.

Converts human-approved stable reintegration evidence into an auditable quarantine
closure and bounded reliability feedback proposal. Governance only: no runtime,
routing, baseline, permission, credential, or execution mutation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class QuarantineClosureRecord:
    record_id: str
    workspace_id: str
    quarantine_id: str
    consumer_id: str
    baseline_id: str
    baseline_version: str
    baseline_digest: str
    stability_record_id: str
    stability_digest: str
    aggregate_confidence: float
    residual_risk: float
    observed_reliability: float
    proposed_reliability: float
    max_adjustment: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    closure_digest: str = ""


class QuarantineEpisodeClosureService:
    """Fail-closed episode closure with bounded, non-mutating reliability feedback."""

    def __init__(self) -> None:
        self._records: dict[str, QuarantineClosureRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        quarantine_id: str,
        stable_evidence: dict[str, Any],
        current_reliability: float,
        source_key: str,
        max_adjustment: float = 0.05,
    ) -> QuarantineClosureRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if stable_evidence.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if stable_evidence.get("status") != "stable":
            findings.append("reintegration-not-stable")
        if not stable_evidence.get("human_approved", False):
            findings.append("stable-human-approval-missing")
        if stable_evidence.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        confidence = float(stable_evidence.get("aggregate_confidence", 0.0))
        residual_risk = float(stable_evidence.get("residual_risk", 1.0))
        if confidence < 0.80:
            findings.append("confidence-below-closure-floor")
        if residual_risk > 0.20:
            findings.append("residual-risk-above-closure-ceiling")

        baseline_id = str(stable_evidence.get("baseline_id", ""))
        baseline_version = str(stable_evidence.get("baseline_version", ""))
        baseline_digest = str(stable_evidence.get("baseline_digest", ""))
        consumer_id = str(stable_evidence.get("consumer_id", ""))
        if not all((baseline_id, baseline_version, baseline_digest, consumer_id)):
            findings.append("required-binding-missing")

        observed = max(0.0, min(1.0, confidence * (1.0 - residual_risk)))
        current = max(0.0, min(1.0, float(current_reliability)))
        adjustment = max(-max_adjustment, min(max_adjustment, observed - current))
        proposed = max(0.0, min(1.0, current + adjustment))
        risk_blocked = bool(stable_evidence.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "blocked"

        record = QuarantineClosureRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            quarantine_id=quarantine_id,
            consumer_id=consumer_id,
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            stability_record_id=str(stable_evidence.get("record_id", "")),
            stability_digest=_digest(stable_evidence),
            aggregate_confidence=confidence,
            residual_risk=residual_risk,
            observed_reliability=round(observed, 6),
            proposed_reliability=round(proposed, 6),
            max_adjustment=max_adjustment,
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
        )
        record.closure_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "closure-created", "id": record_id, "digest": record.closure_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> QuarantineClosureRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "closed"
        record.closure_digest = _digest(asdict(record))
        self._audit.append({"event": "quarantine-closed", "id": record_id, "digest": record.closure_digest})
        return record

    def get(self, record_id: str) -> QuarantineClosureRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[QuarantineClosureRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
