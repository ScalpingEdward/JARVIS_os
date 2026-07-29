"""PHOENIX v21.184 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance."""
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
class RecoveryReliabilityRolloutV21184Record:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    rollback_version: int
    rollback_value: float
    candidate_consumers: tuple[str, ...]
    stages: list[RolloutStage]
    max_stage_fraction: float = 0.50
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
            "rollback_version": self.rollback_version,
            "rollback_value": self.rollback_value,
            "candidate_consumers": self.candidate_consumers,
            "stages": [(s.stage, s.consumers, s.approved) for s in self.stages],
            "max_stage_fraction": self.max_stage_fraction,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityBaselineRolloutV21184Governance:
    """Second-cycle rollout eligibility with bounded stage exposure and strict lineage."""

    def __init__(self) -> None:
        self.records: dict[str, RecoveryReliabilityRolloutV21184Record] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: RecoveryReliabilityRolloutV21184Record, *, source_state: str, source_human_approved: bool) -> RecoveryReliabilityRolloutV21184Record:
        invalid = (
            source_state != "committed"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 2
            or not record.baseline_digest
            or record.rollback_version != record.baseline_version - 1
            or not 0.0 <= record.rollback_value <= 1.0
            or not 0.0 < record.max_stage_fraction <= 1.0
            or not record.candidate_consumers
            or record.source_record_id in self.source_ids
            or len(set(record.candidate_consumers)) != len(record.candidate_consumers)
            or not record.stages
        )
        staged_consumers = [c for stage in record.stages for c in stage.consumers]
        if set(staged_consumers) != set(record.candidate_consumers) or len(staged_consumers) != len(set(staged_consumers)):
            invalid = True
        if [stage.stage for stage in record.stages] != list(range(1, len(record.stages) + 1)):
            invalid = True
        total = len(record.candidate_consumers)
        if any((len(stage.consumers) / total) > record.max_stage_fraction for stage in record.stages):
            invalid = True
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def approve_eligibility(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryReliabilityRolloutV21184Record:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "eligible"
            record.approved_by = actor
        self._audit(record, "eligibility-reviewed")
        return record

    def approve_stage(self, record_id: str, *, stage: int, actor: str, human_approved: bool) -> RecoveryReliabilityRolloutV21184Record:
        record = self.records[record_id]
        if record.state not in {"eligible", "staged"} or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
            self._audit(record, "stage-blocked")
            return record
        index = stage - 1
        if index < 0 or index >= len(record.stages) or any(not item.approved for item in record.stages[:index]):
            record.state = "blocked"
            self._audit(record, "stage-order-blocked")
            return record
        current = record.stages[index]
        record.stages[index] = RolloutStage(current.stage, current.consumers, True)
        record.state = "staged"
        self._audit(record, f"stage-{stage}-approved:{actor}")
        return record

    def _audit(self, record: RecoveryReliabilityRolloutV21184Record, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
