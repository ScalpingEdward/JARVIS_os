"""PHOENIX v21.150 — Containment Effectiveness Observation & Quarantine Resolution Readiness Governance.

Governance only. Observes whether an approved containment plan actually preserves
required downstream capabilities and produces a human-reviewed readiness decision
for quarantine resolution. No routing, fallback, policy, permission or execution
mutation is performed here.
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
class ContainmentObservationSample:
    sample_id: str
    capability: str
    available: bool
    fallback_healthy: bool
    dependency_satisfied: bool
    latency_ms: float
    confidence: float
    freshness: float


@dataclass
class ContainmentReadinessRecord:
    record_id: str
    workspace_id: str
    containment_record_id: str
    containment_digest: str
    quarantined_consumer: str
    sample_count: int
    capability_availability: float
    fallback_health: float
    dependency_satisfaction: float
    confidence_score: float
    freshness_score: float
    latency_quality: float
    effectiveness_score: float
    residual_risk: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    readiness_digest: str = ""


class ContainmentEffectivenessObservationService:
    """Fail-closed containment observation and quarantine-resolution readiness."""

    def __init__(self) -> None:
        self._records: dict[str, ContainmentReadinessRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def observe(
        self,
        *,
        record_id: str,
        workspace_id: str,
        containment: dict[str, Any],
        samples: list[ContainmentObservationSample],
        source_key: str,
        max_latency_ms: float = 1500.0,
    ) -> ContainmentReadinessRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if containment.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if containment.get("status") != "fallback-ready":
            findings.append("containment-not-fallback-ready")
        if not containment.get("human_approved", False):
            findings.append("containment-human-approval-missing")
        if containment.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")
        if not samples:
            findings.append("no-observation-samples")

        count = max(len(samples), 1)
        capability_availability = sum(1.0 if s.available else 0.0 for s in samples) / count
        fallback_health = sum(1.0 if s.fallback_healthy else 0.0 for s in samples) / count
        dependency_satisfaction = sum(1.0 if s.dependency_satisfied else 0.0 for s in samples) / count
        confidence_score = sum(max(0.0, min(1.0, s.confidence)) for s in samples) / count
        freshness_score = sum(max(0.0, min(1.0, s.freshness)) for s in samples) / count
        latency_quality = sum(max(0.0, 1.0 - (max(0.0, s.latency_ms) / max(max_latency_ms, 1.0))) for s in samples) / count

        effectiveness = (
            capability_availability * 0.30
            + fallback_health * 0.20
            + dependency_satisfaction * 0.20
            + confidence_score * 0.12
            + freshness_score * 0.08
            + latency_quality * 0.10
        )
        residual_risk = max(0.0, min(1.0, 1.0 - effectiveness))

        if capability_availability < 0.95:
            findings.append("capability-availability-below-floor")
        if fallback_health < 0.90:
            findings.append("fallback-health-below-floor")
        if dependency_satisfaction < 0.95:
            findings.append("dependency-satisfaction-below-floor")
        if confidence_score < 0.80:
            findings.append("confidence-below-floor")
        if freshness_score < 0.75:
            findings.append("freshness-below-floor")
        if residual_risk > 0.20:
            findings.append("residual-risk-above-ceiling")

        risk_blocked = bool(containment.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "degraded"
        record = ContainmentReadinessRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            containment_record_id=str(containment.get("record_id", "")),
            containment_digest=_digest(containment),
            quarantined_consumer=str(containment.get("quarantined_consumer", "")),
            sample_count=len(samples),
            capability_availability=round(capability_availability, 6),
            fallback_health=round(fallback_health, 6),
            dependency_satisfaction=round(dependency_satisfaction, 6),
            confidence_score=round(confidence_score, 6),
            freshness_score=round(freshness_score, 6),
            latency_quality=round(latency_quality, 6),
            effectiveness_score=round(effectiveness, 6),
            residual_risk=round(residual_risk, 6),
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
        )
        record.readiness_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "containment-observed", "id": record_id, "digest": record.readiness_digest})
        return record

    def approve_resolution_readiness(self, record_id: str, *, human_approved: bool) -> ContainmentReadinessRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record is not eligible for resolution readiness approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "resolution-ready"
        record.readiness_digest = _digest(asdict(record))
        self._audit.append({"event": "resolution-ready", "id": record_id, "digest": record.readiness_digest})
        return record

    def get(self, record_id: str) -> ContainmentReadinessRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[ContainmentReadinessRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
