"""PHOENIX v21.145 — Baseline Impact Simulation & Change-Control Preview Governance.

Simulation only. Evaluates an active reliability baseline against candidate ranking,
failover selection and recovery thresholds without mutating live routing or policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class SimulationScenario:
    scenario_id: str
    candidate_id: str
    current_score: float
    simulated_score: float
    current_rank: int
    simulated_rank: int
    failover_trigger_before: bool
    failover_trigger_after: bool
    recovery_ready_before: bool
    recovery_ready_after: bool


@dataclass
class BaselineImpactRecord:
    record_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    baseline_value: float
    status: str
    scenarios: list[SimulationScenario] = field(default_factory=list)
    rank_change_count: int = 0
    failover_change_count: int = 0
    recovery_change_count: int = 0
    max_score_delta: float = 0.0
    blast_radius_score: float = 0.0
    residual_risk: float = 0.0
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    preview_digest: str = ""


class BaselineImpactSimulationService:
    def __init__(self) -> None:
        self._records: dict[str, BaselineImpactRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def simulate(self, *, record_id: str, workspace_id: str, active_baseline: dict[str, Any], scenarios: list[dict[str, Any]], source_key: str) -> BaselineImpactRecord:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if active_baseline.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if active_baseline.get("status") != "active":
            findings.append("baseline-not-active")
        if not active_baseline.get("human_approved", False):
            findings.append("baseline-human-approval-missing")
        risk_blocked = bool(active_baseline.get("risk_brain_blocked", False))
        if risk_blocked:
            findings.append("risk-brain-hard-block")

        baseline_value = float(active_baseline.get("baseline_value", active_baseline.get("value", 0.0)))
        if not 0.0 <= baseline_value <= 1.0:
            findings.append("baseline-out-of-range")

        sim: list[SimulationScenario] = []
        rank_changes = failover_changes = recovery_changes = 0
        max_delta = 0.0
        for raw in scenarios:
            current = float(raw.get("current_score", 0.0))
            sensitivity = float(raw.get("baseline_sensitivity", 0.0))
            simulated = max(0.0, min(1.0, current + (baseline_value - float(raw.get("reference_baseline", baseline_value))) * sensitivity))
            current_rank = int(raw.get("current_rank", 0))
            simulated_rank = int(raw.get("simulated_rank", current_rank))
            fail_before = bool(raw.get("failover_trigger_before", False))
            fail_after = bool(raw.get("failover_trigger_after", fail_before))
            rec_before = bool(raw.get("recovery_ready_before", False))
            rec_after = bool(raw.get("recovery_ready_after", rec_before))
            rank_changes += int(current_rank != simulated_rank)
            failover_changes += int(fail_before != fail_after)
            recovery_changes += int(rec_before != rec_after)
            max_delta = max(max_delta, abs(simulated - current))
            sim.append(SimulationScenario(str(raw.get("scenario_id", len(sim)+1)), str(raw.get("candidate_id", "unknown")), current, simulated, current_rank, simulated_rank, fail_before, fail_after, rec_before, rec_after))

        count = max(1, len(sim))
        blast = min(1.0, (rank_changes + 2 * failover_changes + 2 * recovery_changes) / (5 * count) + max_delta)
        residual = min(1.0, blast * 0.7 + (0.3 if findings else 0.0))
        if blast > 0.35:
            findings.append("blast-radius-above-preview-threshold")
        status = "review-required" if not findings else "blocked"

        record = BaselineImpactRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            baseline_id=str(active_baseline.get("baseline_id", "")),
            baseline_version=int(active_baseline.get("version", 0)),
            baseline_digest=_digest(active_baseline),
            baseline_value=baseline_value,
            status=status,
            scenarios=sim,
            rank_change_count=rank_changes,
            failover_change_count=failover_changes,
            recovery_change_count=recovery_changes,
            max_score_delta=round(max_delta, 6),
            blast_radius_score=round(blast, 6),
            residual_risk=round(residual, 6),
            risk_brain_blocked=risk_blocked,
            findings=findings,
        )
        record.preview_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "simulation-complete", "id": record_id, "digest": record.preview_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> BaselineImpactRecord:
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

    def get(self, record_id: str) -> BaselineImpactRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[BaselineImpactRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
