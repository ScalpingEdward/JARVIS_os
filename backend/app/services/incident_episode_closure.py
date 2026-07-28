"""PHOENIX v21.143 — Incident Episode Closure & Reliability Baseline Update Governance.

Governance only: converts an approved stable recovery observation into a bounded,
human-approved incident closure and reliability feedback proposal. It never mutates
routing, permissions, policies, credentials, or execution settings.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class IncidentClosureRecord:
    closure_id: str
    workspace_id: str
    incident_id: str
    stability_record_id: str
    stability_digest: str
    primary_adapter_id: str
    primary_worker_id: str
    gateway_id: str
    baseline_before: float
    observed_reliability: float
    proposed_baseline: float
    max_adjustment: float
    residual_risk: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    closure_digest: str = ""


class IncidentEpisodeClosureService:
    """Fail-closed incident closure and bounded reliability feedback governance."""

    def __init__(self) -> None:
        self._records: dict[str, IncidentClosureRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        closure_id: str,
        workspace_id: str,
        incident_id: str,
        stable_observation: dict[str, Any],
        baseline_before: float,
        source_key: str,
        max_adjustment: float = 0.05,
    ) -> IncidentClosureRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if closure_id in self._records:
            raise ValueError("duplicate closure id")

        findings: list[str] = []
        if stable_observation.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if stable_observation.get("status") != "stable":
            findings.append("stability-not-approved")
        if not stable_observation.get("human_approved", False):
            findings.append("stability-human-approval-missing")
        if stable_observation.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        confidence = float(stable_observation.get("aggregate_confidence", 0.0))
        residual_risk = float(stable_observation.get("residual_risk", 1.0))
        observed = max(0.0, min(1.0, confidence * (1.0 - residual_risk)))
        baseline = max(0.0, min(1.0, float(baseline_before)))
        adjustment = max(-max_adjustment, min(max_adjustment, observed - baseline))
        proposed = max(0.0, min(1.0, baseline + adjustment))

        if confidence < 0.75:
            findings.append("confidence-below-closure-floor")
        if residual_risk > 0.25:
            findings.append("residual-risk-above-closure-ceiling")

        risk_blocked = bool(stable_observation.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "blocked"
        record = IncidentClosureRecord(
            closure_id=closure_id,
            workspace_id=workspace_id,
            incident_id=incident_id,
            stability_record_id=str(stable_observation.get("record_id", "")),
            stability_digest=_digest(stable_observation),
            primary_adapter_id=str(stable_observation.get("primary_adapter_id", "")),
            primary_worker_id=str(stable_observation.get("primary_worker_id", "")),
            gateway_id=str(stable_observation.get("gateway_id", "")),
            baseline_before=baseline,
            observed_reliability=round(observed, 6),
            proposed_baseline=round(proposed, 6),
            max_adjustment=max_adjustment,
            residual_risk=residual_risk,
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
        )
        record.closure_digest = _digest(asdict(record))
        self._records[closure_id] = record
        self._audit.append({"event": "closure-created", "id": closure_id, "digest": record.closure_digest})
        return record

    def approve(self, closure_id: str, *, human_approved: bool) -> IncidentClosureRecord:
        record = self._records[closure_id]
        if record.status != "review-required":
            raise ValueError("closure is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "closed"
        record.closure_digest = _digest(asdict(record))
        self._audit.append({"event": "incident-closed", "id": closure_id, "digest": record.closure_digest})
        return record

    def get(self, closure_id: str) -> IncidentClosureRecord:
        return self._records[closure_id]

    def list_records(self, workspace_id: str | None = None) -> list[IncidentClosureRecord]:
        records = list(self._records.values())
        return records if workspace_id is None else [r for r in records if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
