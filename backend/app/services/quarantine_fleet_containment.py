"""PHOENIX v21.149 — Quarantine Fleet Impact & Dependency Containment Governance.

Governance only. Evaluates downstream dependency impact from a quarantined
consumer and produces a human-approved containment/fallback plan. No route,
policy, credential, permission or execution mutation occurs here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class Dependency:
    consumer_id: str
    capability: str
    critical: bool = False
    fallback_consumer_id: str | None = None
    fallback_ready: bool = False


@dataclass
class ContainmentRecord:
    record_id: str
    workspace_id: str
    quarantined_consumer_id: str
    quarantine_record_id: str
    quarantine_digest: str
    affected_consumers: list[str]
    affected_capabilities: list[str]
    critical_gap_count: int
    fallback_ready_count: int
    blast_radius_score: float
    containment_severity: str
    residual_risk: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    fallback_activation_approved: bool = False
    risk_brain_blocked: bool = False
    containment_digest: str = ""


class QuarantineFleetContainmentService:
    def __init__(self) -> None:
        self._records: dict[str, ContainmentRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        quarantine: dict[str, Any],
        dependencies: list[Dependency],
        source_key: str,
    ) -> ContainmentRecord:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if quarantine.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if quarantine.get("status") != "quarantined":
            findings.append("consumer-not-quarantined")
        consumer_id = str(quarantine.get("consumer_id", ""))
        if not consumer_id:
            findings.append("consumer-identity-missing")
        if quarantine.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        affected_consumers = sorted({d.consumer_id for d in dependencies})
        affected_capabilities = sorted({d.capability for d in dependencies})
        critical = [d for d in dependencies if d.critical]
        missing_fallback = [d for d in critical if not (d.fallback_consumer_id and d.fallback_ready)]
        fallback_ready_count = sum(1 for d in dependencies if d.fallback_consumer_id and d.fallback_ready)

        total = max(1, len(dependencies))
        critical_ratio = len(critical) / total
        missing_ratio = len(missing_fallback) / total
        blast_radius = min(1.0, 0.45 * min(1.0, len(affected_consumers) / 5.0) + 0.35 * critical_ratio + 0.20 * missing_ratio)
        residual_risk = min(1.0, 0.60 * missing_ratio + 0.40 * critical_ratio)
        severity = "critical" if missing_fallback else "high" if blast_radius >= 0.65 else "medium" if blast_radius >= 0.35 else "low"

        if missing_fallback:
            findings.append("critical-dependency-without-fallback")
        risk_blocked = bool(quarantine.get("risk_brain_blocked", False))
        status = "blocked" if findings else "review-required"

        rec = ContainmentRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            quarantined_consumer_id=consumer_id,
            quarantine_record_id=str(quarantine.get("record_id", "")),
            quarantine_digest=_digest(quarantine),
            affected_consumers=affected_consumers,
            affected_capabilities=affected_capabilities,
            critical_gap_count=len(missing_fallback),
            fallback_ready_count=fallback_ready_count,
            blast_radius_score=round(blast_radius, 6),
            containment_severity=severity,
            residual_risk=round(residual_risk, 6),
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
        )
        rec.containment_digest = _digest(asdict(rec))
        self._records[record_id] = rec
        self._audit.append({"event": "containment-created", "id": record_id, "digest": rec.containment_digest})
        return rec

    def approve(self, record_id: str, *, human_approved: bool) -> ContainmentRecord:
        rec = self._records[record_id]
        if rec.status != "review-required":
            raise ValueError("containment is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if rec.risk_brain_blocked or rec.critical_gap_count:
            raise ValueError("containment blocked")
        rec.human_approved = True
        rec.status = "approved"
        rec.containment_digest = _digest(asdict(rec))
        self._audit.append({"event": "containment-approved", "id": record_id, "digest": rec.containment_digest})
        return rec

    def approve_fallback_activation(self, record_id: str, *, human_approved: bool) -> ContainmentRecord:
        rec = self._records[record_id]
        if rec.status != "approved":
            raise ValueError("containment must be approved first")
        if not human_approved:
            raise ValueError("human approval required")
        rec.fallback_activation_approved = True
        rec.status = "fallback-ready"
        rec.containment_digest = _digest(asdict(rec))
        self._audit.append({"event": "fallback-ready", "id": record_id, "digest": rec.containment_digest})
        return rec

    def get(self, record_id: str) -> ContainmentRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[ContainmentRecord]:
        records = list(self._records.values())
        return records if workspace_id is None else [r for r in records if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
