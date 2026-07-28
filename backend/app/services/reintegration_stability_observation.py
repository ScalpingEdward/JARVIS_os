"""PHOENIX v21.152 — Reintegration Stability Observation & Post-Quarantine Confidence Governance.

Governance only. Observes a consumer after v21.151 controlled reintegration and
produces bounded confidence evidence before a quarantine episode may be closed.
No routing, policy, credential, permission, baseline, or execution mutation occurs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from statistics import mean
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class StabilitySample:
    consumer_healthy: bool
    baseline_match: bool
    dependency_satisfied: bool
    latency_ms: float
    confidence: float
    freshness: float
    error_rate: float = 0.0


@dataclass
class ReintegrationStabilityRecord:
    record_id: str
    workspace_id: str
    reintegration_record_id: str
    reintegration_digest: str
    consumer_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    sample_count: int
    health_score: float
    baseline_integrity_score: float
    dependency_score: float
    latency_quality: float
    confidence_score: float
    freshness_score: float
    error_quality: float
    aggregate_confidence: float
    residual_risk: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    evidence_digest: str = ""


class ReintegrationStabilityObservationService:
    """Fail-closed post-quarantine observation and confidence governance."""

    def __init__(self) -> None:
        self._records: dict[str, ReintegrationStabilityRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def observe(
        self,
        *,
        record_id: str,
        workspace_id: str,
        reintegration: dict[str, Any],
        samples: list[StabilitySample],
        source_key: str,
        max_latency_ms: float = 1000.0,
        max_error_rate: float = 0.05,
        min_confidence: float = 0.80,
        max_residual_risk: float = 0.25,
    ) -> ReintegrationStabilityRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")
        if not samples:
            raise ValueError("at least one observation sample required")

        findings: list[str] = []
        if reintegration.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if reintegration.get("status") != "reintegrated":
            findings.append("consumer-not-reintegrated")
        if not reintegration.get("human_approved", False):
            findings.append("reintegration-human-approval-missing")

        risk_blocked = bool(reintegration.get("risk_brain_blocked", False))
        if risk_blocked:
            findings.append("risk-brain-hard-block")

        health = mean(1.0 if s.consumer_healthy else 0.0 for s in samples)
        baseline_integrity = mean(1.0 if s.baseline_match else 0.0 for s in samples)
        dependency = mean(1.0 if s.dependency_satisfied else 0.0 for s in samples)
        latency_quality = mean(max(0.0, min(1.0, 1.0 - (s.latency_ms / max_latency_ms))) for s in samples)
        confidence = mean(max(0.0, min(1.0, s.confidence)) for s in samples)
        freshness = mean(max(0.0, min(1.0, s.freshness)) for s in samples)
        error_quality = mean(max(0.0, min(1.0, 1.0 - (s.error_rate / max_error_rate if max_error_rate > 0 else 1.0))) for s in samples)

        aggregate = (
            health * 0.20 + baseline_integrity * 0.20 + dependency * 0.15
            + latency_quality * 0.10 + confidence * 0.15 + freshness * 0.10 + error_quality * 0.10
        )
        residual_risk = max(0.0, min(1.0, 1.0 - aggregate))

        if health < 1.0:
            findings.append("consumer-health-degradation")
        if baseline_integrity < 1.0:
            findings.append("baseline-drift-detected")
        if dependency < 1.0:
            findings.append("dependency-degradation")
        if any(s.latency_ms > max_latency_ms for s in samples):
            findings.append("latency-threshold-breach")
        if any(s.error_rate > max_error_rate for s in samples):
            findings.append("error-rate-threshold-breach")
        if aggregate < min_confidence:
            findings.append("post-quarantine-confidence-below-floor")
        if residual_risk > max_residual_risk:
            findings.append("residual-risk-above-ceiling")

        status = "review-required" if not findings else "degraded"
        record = ReintegrationStabilityRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            reintegration_record_id=str(reintegration.get("record_id", "")),
            reintegration_digest=_digest(reintegration),
            consumer_id=str(reintegration.get("consumer_id", "")),
            baseline_id=str(reintegration.get("baseline_id", "")),
            baseline_version=int(reintegration.get("baseline_version", 0)),
            baseline_digest=str(reintegration.get("baseline_digest", "")),
            sample_count=len(samples),
            health_score=round(health, 6),
            baseline_integrity_score=round(baseline_integrity, 6),
            dependency_score=round(dependency, 6),
            latency_quality=round(latency_quality, 6),
            confidence_score=round(confidence, 6),
            freshness_score=round(freshness, 6),
            error_quality=round(error_quality, 6),
            aggregate_confidence=round(aggregate, 6),
            residual_risk=round(residual_risk, 6),
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
        )
        record.evidence_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "reintegration-observed", "id": record_id, "digest": record.evidence_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> ReintegrationStabilityRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "stable"
        record.evidence_digest = _digest(asdict(record))
        self._audit.append({"event": "post-quarantine-stable", "id": record_id, "digest": record.evidence_digest})
        return record

    def get(self, record_id: str) -> ReintegrationStabilityRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[ReintegrationStabilityRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
