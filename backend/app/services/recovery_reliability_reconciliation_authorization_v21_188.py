"""PHOENIX v21.188 — Recovery Reliability Reconciliation Authorization & Ordered Consumer Recovery Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "authorized", "staged", "recovery-ready", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryStep188:
    order: int
    consumer_id: str
    drift_reason: str
    approved: bool = False


@dataclass
class RecoveryAuthorizationRecord188:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    affected_consumers: tuple[str, ...]
    healthy_consumers: tuple[str, ...]
    steps: list[RecoveryStep188]
    blast_radius: float
    residual_risk: float
    max_blast_radius: float = 0.50
    max_residual_risk: float = 0.30
    risk_brain_blocked: bool = False
    state: State = "review-required"
    authorized_by: str | None = None
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
            "affected_consumers": self.affected_consumers,
            "healthy_consumers": self.healthy_consumers,
            "steps": [(s.order, s.consumer_id, s.drift_reason, s.approved) for s in self.steps],
            "blast_radius": self.blast_radius,
            "residual_risk": self.residual_risk,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "authorized_by": self.authorized_by,
        }


class RecoveryReliabilityReconciliationAuthorizationGovernance188:
    """Authorize exact ordered recovery plans; never mutate runtime consumers."""

    def __init__(self) -> None:
        self.records: dict[str, RecoveryAuthorizationRecord188] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: RecoveryAuthorizationRecord188, *, source_state: str, source_human_approved: bool) -> RecoveryAuthorizationRecord188:
        affected = set(record.affected_consumers)
        healthy = set(record.healthy_consumers)
        step_consumers = [s.consumer_id for s in record.steps]
        invalid = (
            source_state != "reconciliation-ready"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not affected
            or record.source_record_id in self.source_ids
            or bool(affected & healthy)
            or len(affected) != len(record.affected_consumers)
            or step_consumers != list(record.affected_consumers)
            or [s.order for s in record.steps] != list(range(1, len(record.steps) + 1))
            or any(not s.drift_reason for s in record.steps)
            or not 0.0 <= record.blast_radius <= record.max_blast_radius <= 1.0
            or not 0.0 <= record.residual_risk <= record.max_residual_risk <= 1.0
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def authorize(self, record_id: str, *, actor: str, human_approved: bool) -> RecoveryAuthorizationRecord188:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "authorized"
            record.authorized_by = actor
        self._audit(record, "authorization-reviewed")
        return record

    def approve_step(self, record_id: str, *, order: int, actor: str, human_approved: bool) -> RecoveryAuthorizationRecord188:
        record = self.records[record_id]
        if record.state not in {"authorized", "staged"} or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
            self._audit(record, "step-blocked")
            return record
        index = order - 1
        if index < 0 or index >= len(record.steps) or any(not s.approved for s in record.steps[:index]):
            record.state = "blocked"
            self._audit(record, "step-order-blocked")
            return record
        current = record.steps[index]
        record.steps[index] = RecoveryStep188(current.order, current.consumer_id, current.drift_reason, True)
        record.state = "recovery-ready" if all(s.approved for s in record.steps) else "staged"
        self._audit(record, f"step-{order}-approved:{actor}")
        return record

    def _audit(self, record: RecoveryAuthorizationRecord188, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
