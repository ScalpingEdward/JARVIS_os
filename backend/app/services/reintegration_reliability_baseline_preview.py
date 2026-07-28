"""PHOENIX v21.154 — Reintegration Reliability Baseline Proposal & Impact Preview Governance.

Governance only. Converts a closed quarantine episode with bounded reliability feedback
into a separately reviewed baseline candidate and simulation-only impact preview.
No active baseline, routing, policy or execution state is mutated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass
class BaselinePreviewRecord:
    record_id: str
    workspace_id: str
    consumer_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    current_reliability: float
    proposed_reliability: float
    score_delta: float
    simulated_rank_delta: float
    simulated_failover_delta: float
    simulated_recovery_delta: float
    blast_radius: float
    residual_risk: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    source_digest: str = ""
    preview_digest: str = ""


class ReintegrationReliabilityBaselinePreviewService:
    """Fail-closed proposal + simulation-only impact preview governance."""

    def __init__(self) -> None:
        self._records: dict[str, BaselinePreviewRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        closed_episode: dict[str, Any],
        current_reliability: float,
        source_key: str,
        max_score_delta: float = 0.10,
        max_blast_radius: float = 0.30,
        max_residual_risk: float = 0.25,
    ) -> BaselinePreviewRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if closed_episode.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if closed_episode.get("status") != "closed":
            findings.append("episode-not-closed")
        if not closed_episode.get("human_approved", False):
            findings.append("episode-human-approval-missing")
        if closed_episode.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        consumer_id = str(closed_episode.get("consumer_id", ""))
        baseline_id = str(closed_episode.get("baseline_id", ""))
        baseline_version = int(closed_episode.get("baseline_version", 0) or 0)
        baseline_digest = str(closed_episode.get("baseline_digest", ""))
        if not consumer_id or not baseline_id or baseline_version <= 0 or not baseline_digest:
            findings.append("required-binding-missing")

        current = max(0.0, min(1.0, float(current_reliability)))
        proposed = max(0.0, min(1.0, float(closed_episode.get("proposed_reliability", current))))
        score_delta = round(proposed - current, 6)

        # Deterministic simulation-only proxies; consumers can later replace these with richer models.
        rank_delta = round(score_delta * 0.75, 6)
        failover_delta = round(-score_delta * 0.50, 6)
        recovery_delta = round(score_delta * 0.60, 6)
        blast_radius = round(min(1.0, abs(score_delta) * 2.5), 6)
        confidence = float(closed_episode.get("aggregate_confidence", 0.0))
        source_residual = float(closed_episode.get("residual_risk", 1.0))
        residual_risk = round(min(1.0, max(source_residual, blast_radius * (1.0 - confidence))), 6)

        if abs(score_delta) > max_score_delta:
            findings.append("score-delta-above-limit")
        if blast_radius > max_blast_radius:
            findings.append("blast-radius-above-limit")
        if residual_risk > max_residual_risk:
            findings.append("residual-risk-above-limit")

        risk_blocked = bool(closed_episode.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "blocked"
        record = BaselinePreviewRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            consumer_id=consumer_id,
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            current_reliability=current,
            proposed_reliability=proposed,
            score_delta=score_delta,
            simulated_rank_delta=rank_delta,
            simulated_failover_delta=failover_delta,
            simulated_recovery_delta=recovery_delta,
            blast_radius=blast_radius,
            residual_risk=residual_risk,
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
            source_digest=_digest(closed_episode),
        )
        record.preview_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "preview-created", "id": record_id, "digest": record.preview_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> BaselinePreviewRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("preview not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "approved-preview"
        record.preview_digest = _digest(asdict(record))
        self._audit.append({"event": "preview-approved", "id": record_id, "digest": record.preview_digest})
        return record

    def get(self, record_id: str) -> BaselinePreviewRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[BaselinePreviewRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
