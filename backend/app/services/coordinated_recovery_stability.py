"""PHOENIX v21.160 — Coordinated Recovery Stability Observation & Remediation Episode Closure Governance.

Governance only. Observes recovered consumers after v21.159 completion and produces a
human-reviewed episode closure attestation. No runtime mutation is performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from statistics import mean
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True)
class ConsumerObservation:
    consumer_id: str
    health: float
    baseline_match: bool
    dependency_satisfaction: float
    latency_quality: float
    error_quality: float
    confidence: float
    freshness: float


@dataclass
class RecoveryStabilityRecord:
    record_id: str
    workspace_id: str
    completion_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    consumer_ids: list[str]
    aggregate_confidence: float
    residual_risk: float
    stability_score: float
    status: str
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    source_digest: str = ""
    record_digest: str = ""


class CoordinatedRecoveryStabilityService:
    def __init__(self) -> None:
        self._records: dict[str, RecoveryStabilityRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        completion_evidence: dict[str, Any],
        observations: list[ConsumerObservation],
        source_key: str,
        min_stability_score: float = 0.80,
        min_confidence: float = 0.80,
        max_residual_risk: float = 0.20,
    ) -> RecoveryStabilityRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if completion_evidence.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if completion_evidence.get("status") != "completed":
            findings.append("completion-not-approved")
        if not completion_evidence.get("human_approved", False):
            findings.append("completion-human-approval-missing")
        if completion_evidence.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")
        if not observations:
            findings.append("empty-observation-set")

        expected = set(completion_evidence.get("consumer_ids", []))
        observed = [o.consumer_id for o in observations]
        if len(observed) != len(set(observed)):
            findings.append("duplicate-consumer-observation")
        if expected and set(observed) != expected:
            findings.append("consumer-set-mismatch")

        baseline_id = str(completion_evidence.get("baseline_id", ""))
        baseline_version = int(completion_evidence.get("baseline_version", 0) or 0)
        baseline_digest = str(completion_evidence.get("baseline_digest", ""))
        if not baseline_id or baseline_version <= 0 or not baseline_digest:
            findings.append("baseline-binding-missing")

        if observations:
            health = mean(max(0.0, min(1.0, o.health)) for o in observations)
            dependency = mean(max(0.0, min(1.0, o.dependency_satisfaction)) for o in observations)
            latency = mean(max(0.0, min(1.0, o.latency_quality)) for o in observations)
            errors = mean(max(0.0, min(1.0, o.error_quality)) for o in observations)
            confidence = mean(max(0.0, min(1.0, o.confidence)) for o in observations)
            freshness = mean(max(0.0, min(1.0, o.freshness)) for o in observations)
            integrity = mean(1.0 if o.baseline_match else 0.0 for o in observations)
            stability_score = mean([health, dependency, latency, errors, confidence, freshness, integrity])
        else:
            confidence = 0.0
            stability_score = 0.0
            integrity = 0.0

        residual_risk = max(0.0, min(1.0, 1.0 - stability_score))
        if integrity < 1.0:
            findings.append("baseline-drift-detected")
        if confidence < min_confidence:
            findings.append("confidence-below-floor")
        if stability_score < min_stability_score:
            findings.append("stability-below-floor")
        if residual_risk > max_residual_risk:
            findings.append("residual-risk-above-ceiling")

        risk_blocked = bool(completion_evidence.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "degraded"
        record = RecoveryStabilityRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            completion_id=str(completion_evidence.get("record_id") or completion_evidence.get("completion_id") or ""),
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            consumer_ids=sorted(set(observed)),
            aggregate_confidence=round(confidence, 6),
            residual_risk=round(residual_risk, 6),
            stability_score=round(stability_score, 6),
            status=status,
            risk_brain_blocked=risk_blocked,
            findings=findings,
            source_digest=_digest(completion_evidence),
        )
        record.record_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "stability-observed", "id": record_id, "digest": record.record_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> RecoveryStabilityRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record is not eligible for closure")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "closed"
        record.record_digest = _digest(asdict(record))
        self._audit.append({"event": "remediation-episode-closed", "id": record_id, "digest": record.record_digest})
        return record

    def get(self, record_id: str) -> RecoveryStabilityRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[RecoveryStabilityRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
