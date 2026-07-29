"""PHOENIX v21.194 — Recovery Reliability Baseline Controlled Rollout & Adoption Eligibility Governance."""
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
    order: int
    consumers: tuple[str, ...]
    max_exposure: float
    approved: bool = False


@dataclass
class RolloutEligibilityRecord:
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
            "stages": [(s.order, s.consumers, s.max_exposure, s.approved) for s in self.stages],
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityBaselineControlledRolloutGovernance:
    """Govern rollout eligibility/staging without mutating live baselines or consumers."""

    def __init__(self, *, max_stage_exposure: float = 0.50) -> None:
        self.max_stage_exposure = max_stage_exposure
        self.records: dict[str, RolloutEligibilityRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: RolloutEligibilityRecord, *, source_state: str, source_human_approved: bool) -> RolloutEligibilityRecord:
        stage_consumers = [c for s in record.stages for c in s.consumers]
        orders = [s.order for s in record.stages]
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
            or not record.candidate_consumers
            or len(set(record.candidate_consumers)) != len(record.candidate_consumers)
            or not record.stages
            or orders != list(range(1, len(record.stages) + 1))
            or len(stage_consumers) != len(set(stage_consumers))
            or set(stage_consumers) != set(record.candidate_consumers)
            or any(not s.consumers for s in record.stages)
            or any(not 0.0 < s.max_exposure <= self.max_stage_exposure for s in record.stages)
            or record.source_record_id in self.source_ids
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def approve_eligibility(self, record_id: str, *, actor: str, human_approved: bool) -> RolloutEligibilityRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "eligible"
            record.approved_by = actor
        self._audit(record, "eligibility-reviewed")
        return record

    def approve_stage(self, record_id: str, *, order: int, actor: str, human_approved: bool) -> RolloutEligibilityRecord:
        record = self.records[record_id]
        if record.state not in {"eligible", "staged"} or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
            self._audit(record, "stage-blocked")
            return record
        index = order - 1
        if index < 0 or index >= len(record.stages) or any(not s.approved for s in record.stages[:index]):
            record.state = "blocked"
            self._audit(record, "stage-order-blocked")
            return record
        current = record.stages[index]
        record.stages[index] = RolloutStage(current.order, current.consumers, current.max_exposure, True)
        record.state = "staged"
        self._audit(record, f"stage-{order}-approved:{actor}")
        return record

    def _audit(self, record: RolloutEligibilityRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
