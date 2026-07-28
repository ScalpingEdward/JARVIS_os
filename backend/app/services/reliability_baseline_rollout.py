"""PHOENIX v21.164 — Reliability Baseline Controlled Rollout & Adoption Eligibility Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "eligible", "staged", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RolloutStage:
    stage: int
    consumers: tuple[str, ...]
    approved: bool = False


@dataclass
class ReliabilityBaselineRolloutRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    candidate_consumers: tuple[str, ...]
    stages: list[RolloutStage]
    risk_brain_blocked: bool = False
    state: State = "review-required"
    approved_by: str | None = None
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        self.audit_digest = _digest(self.snapshot())

    def snapshot(self) -> dict:
        return {
            "record_id": self.record_id,
            "workspace_id": self.workspace_id,
            "source_record_id": self.source_record_id,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "baseline_digest": self.baseline_digest,
            "candidate_consumers": self.candidate_consumers,
            "stages": [(s.stage, s.consumers, s.approved) for s in self.stages],
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "approved_by": self.approved_by,
        }


class ReliabilityBaselineRolloutGovernance:
    """Govern eligibility and staged rollout intent; never mutates runtime consumers."""

    def __init__(self) -> None:
        self.records: dict[str, ReliabilityBaselineRolloutRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: ReliabilityBaselineRolloutRecord, *, source_state: str, source_human_approved: bool) -> ReliabilityBaselineRolloutRecord:
        invalid = (
            source_state != "committed"
            or not source_human_approved
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not record.candidate_consumers
            or record.source_record_id in self.source_ids
            or len(set(record.candidate_consumers)) != len(record.candidate_consumers)
            or record.risk_brain_blocked
        )
        staged = [c for s in record.stages for c in s.consumers]
        if set(staged) != set(record.candidate_consumers) or len(staged) != len(set(staged)):
            invalid = True
        if [s.stage for s in record.stages] != list(range(1, len(record.stages) + 1)):
            invalid = True
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def approve_eligibility(self, record_id: str, *, actor: str, human_approved: bool) -> ReliabilityBaselineRolloutRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "eligible"
            record.approved_by = actor
        self._audit(record, "eligibility-reviewed")
        return record

    def approve_stage(self, record_id: str, *, stage: int, actor: str, human_approved: bool) -> ReliabilityBaselineRolloutRecord:
        record = self.records[record_id]
        if record.state not in {"eligible", "staged"} or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
            self._audit(record, "stage-blocked")
            return record
        index = stage - 1
        if index < 0 or index >= len(record.stages) or any(not s.approved for s in record.stages[:index]):
            record.state = "blocked"
            self._audit(record, "stage-order-blocked")
            return record
        current = record.stages[index]
        record.stages[index] = RolloutStage(current.stage, current.consumers, True)
        record.state = "staged"
        self._audit(record, f"stage-{stage}-approved:{actor}")
        return record

    def _audit(self, record: ReliabilityBaselineRolloutRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
