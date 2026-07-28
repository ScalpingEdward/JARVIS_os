"""PHOENIX v21.161 — Remediation Outcome Reliability Learning & Baseline Feedback Governance.

Governance only. Converts a human-approved closed remediation episode into bounded
learning evidence and a separately reviewed baseline-feedback proposal. No runtime,
routing, baseline, credential, permission, fund, order, or trading mutation occurs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class LearningRecord:
    record_id: str
    workspace_id: str
    remediation_episode_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    source_digest: str
    observed_stability: float
    aggregate_confidence: float
    residual_risk: float
    recovery_quality: float
    learning_score: float
    baseline_before: float
    proposed_baseline: float
    max_adjustment: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    proposal_digest: str = ""


class RemediationOutcomeReliabilityLearningService:
    """Fail-closed bounded reliability learning and feedback proposal governance."""

    def __init__(self) -> None:
        self._records: dict[str, LearningRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        remediation_episode_id: str,
        closed_episode: dict[str, Any],
        baseline_before: float,
        source_key: str,
        max_adjustment: float = 0.05,
        min_confidence: float = 0.80,
        max_residual_risk: float = 0.20,
    ) -> LearningRecord:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if closed_episode.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if closed_episode.get("status") != "closed":
            findings.append("remediation-episode-not-closed")
        if not closed_episode.get("human_approved", False):
            findings.append("episode-human-approval-missing")

        baseline_id = str(closed_episode.get("baseline_id", ""))
        baseline_version = int(closed_episode.get("baseline_version", 0) or 0)
        baseline_digest = str(closed_episode.get("baseline_digest", ""))
        if not baseline_id or baseline_version <= 0 or not baseline_digest:
            findings.append("baseline-binding-missing")

        stability = max(0.0, min(1.0, float(closed_episode.get("stability_score", 0.0))))
        confidence = max(0.0, min(1.0, float(closed_episode.get("aggregate_confidence", 0.0))))
        residual_risk = max(0.0, min(1.0, float(closed_episode.get("residual_risk", 1.0))))
        reconciliation = max(0.0, min(1.0, float(closed_episode.get("reconciliation_score", 1.0))))

        recovery_quality = (stability * 0.40) + (confidence * 0.35) + (reconciliation * 0.25)
        learning_score = recovery_quality * (1.0 - residual_risk)

        if confidence < min_confidence:
            findings.append("confidence-below-learning-floor")
        if residual_risk > max_residual_risk:
            findings.append("residual-risk-above-learning-ceiling")
        if stability < 0.80:
            findings.append("stability-below-learning-floor")

        risk_blocked = bool(closed_episode.get("risk_brain_blocked", False))
        if risk_blocked:
            findings.append("risk-brain-hard-block")

        baseline = max(0.0, min(1.0, float(baseline_before)))
        max_adjustment = max(0.0, min(0.20, float(max_adjustment)))
        delta = learning_score - baseline
        bounded_delta = max(-max_adjustment, min(max_adjustment, delta))
        proposed = max(0.0, min(1.0, baseline + bounded_delta))

        status = "review-required" if not findings else "blocked"
        record = LearningRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            remediation_episode_id=remediation_episode_id,
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            source_digest=_digest(closed_episode),
            observed_stability=round(stability, 6),
            aggregate_confidence=round(confidence, 6),
            residual_risk=round(residual_risk, 6),
            recovery_quality=round(recovery_quality, 6),
            learning_score=round(learning_score, 6),
            baseline_before=round(baseline, 6),
            proposed_baseline=round(proposed, 6),
            max_adjustment=round(max_adjustment, 6),
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
        )
        record.proposal_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "learning-proposal-created", "id": record_id, "digest": record.proposal_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> LearningRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("learning proposal is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "approved-feedback"
        record.proposal_digest = _digest(asdict(record))
        self._audit.append({"event": "learning-feedback-approved", "id": record_id, "digest": record.proposal_digest})
        return record

    def get(self, record_id: str) -> LearningRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[LearningRecord]:
        records = list(self._records.values())
        return records if workspace_id is None else [r for r in records if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
