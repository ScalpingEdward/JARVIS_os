"""PHOENIX v21.162 — Reliability Feedback Impact Simulation & Baseline Change Preview Governance."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class ImpactPreviewRecord:
    record_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    current_value: float
    candidate_value: float
    score_delta: float
    rank_delta: float
    failover_tendency_delta: float
    recovery_readiness_delta: float
    blast_radius: float
    residual_risk: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    source_digest: str = ""
    preview_digest: str = ""


class ReliabilityFeedbackImpactPreviewService:
    def __init__(self) -> None:
        self._records: dict[str, ImpactPreviewRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(self, *, record_id: str, workspace_id: str, approved_feedback: dict[str, Any], source_key: str,
               max_score_delta: float = 0.12, max_blast_radius: float = 0.35,
               max_residual_risk: float = 0.25) -> ImpactPreviewRecord:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if approved_feedback.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if approved_feedback.get("status") != "approved-feedback":
            findings.append("feedback-not-approved")
        if not approved_feedback.get("human_approved", False):
            findings.append("feedback-human-approval-missing")

        baseline_id = str(approved_feedback.get("baseline_id", ""))
        baseline_version = int(approved_feedback.get("baseline_version", 0) or 0)
        baseline_digest = str(approved_feedback.get("baseline_digest", ""))
        if not baseline_id or baseline_version <= 0 or not baseline_digest:
            findings.append("baseline-binding-missing")

        current = max(0.0, min(1.0, float(approved_feedback.get("baseline_before", 0.0))))
        candidate = max(0.0, min(1.0, float(approved_feedback.get("proposed_baseline", current))))
        delta = candidate - current
        score_delta = round(delta * 0.82, 6)
        rank_delta = round(delta * 0.55, 6)
        failover_delta = round(-delta * 0.65, 6)
        recovery_delta = round(delta * 0.72, 6)
        blast_radius = round(min(1.0, abs(delta) * 4.0 + abs(rank_delta) * 0.5), 6)
        residual_risk = round(min(1.0, abs(delta) * 1.6 + blast_radius * 0.35), 6)

        if abs(score_delta) > max_score_delta:
            findings.append("score-delta-limit-exceeded")
        if blast_radius > max_blast_radius:
            findings.append("blast-radius-limit-exceeded")
        if residual_risk > max_residual_risk:
            findings.append("residual-risk-limit-exceeded")

        risk_blocked = bool(approved_feedback.get("risk_brain_blocked", False))
        if risk_blocked:
            findings.append("risk-brain-hard-block")

        record = ImpactPreviewRecord(
            record_id=record_id, workspace_id=workspace_id, baseline_id=baseline_id,
            baseline_version=baseline_version, baseline_digest=baseline_digest,
            current_value=current, candidate_value=candidate, score_delta=score_delta,
            rank_delta=rank_delta, failover_tendency_delta=failover_delta,
            recovery_readiness_delta=recovery_delta, blast_radius=blast_radius,
            residual_risk=residual_risk, status="review-required" if not findings else "blocked",
            findings=findings, risk_brain_blocked=risk_blocked,
            source_digest=_digest(approved_feedback),
        )
        record.preview_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "preview-created", "id": record_id, "digest": record.preview_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> ImpactPreviewRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("preview is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "approved-preview"
        record.preview_digest = _digest(asdict(record))
        self._audit.append({"event": "preview-approved", "id": record_id, "digest": record.preview_digest})
        return record

    def get(self, record_id: str) -> ImpactPreviewRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[ImpactPreviewRecord]:
        records = list(self._records.values())
        return records if workspace_id is None else [r for r in records if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
