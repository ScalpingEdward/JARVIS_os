"""PHOENIX v21.178 — Recovery Reliability Reconciliation Authorization & Ordered Consumer Recovery Governance."""
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
class RecoveryStep:
    order: int
    consumer_id: str
    approved: bool = False


@dataclass
class ReconciliationAuthorizationRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    affected_consumers: tuple[str, ...]
    healthy_consumers: tuple[str, ...]
    recovery_steps: list[RecoveryStep]
    blast_radius: float
    residual_risk: float
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
            "recovery_steps": [(s.order, s.consumer_id, s.approved) for s in self.recovery_steps],
            "blast_radius": self.blast_radius,
            "residual_risk": self.residual_risk,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "authorized_by": self.authorized_by,
        }


class RecoveryReliabilityReconciliationAuthorizationGovernance:
    """Authorize ordered consumer recovery plans without mutating runtime consumers."""

    def __init__(self, *, max_blast_radius: float = 0.5, max_residual_risk: float = 0.35) -> None:
        self.max_blast_radius = max_blast_radius
        self.max_residual_risk = max_residual_risk
        self.records: dict[str, ReconciliationAuthorizationRecord] = {}
        self.source_ids: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: ReconciliationAuthorizationRecord, *, source_state: str, source_human_approved: bool) -> ReconciliationAuthorizationRecord:
        affected = set(record.affected_consumers)
        healthy = set(record.healthy_consumers)
        step_consumers = [s.consumer_id for s in record.recovery_steps]
        invalid = (
            source_state != "reconciliation-ready"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not record.affected_consumers
            or record.source_record_id in self.source_ids
            or affected & healthy
            or len(affected) != len(record.affected_consumers)
            or set(step_consumers) != affected
            or len(step_consumers) != len(set(step_consumers))
            or [s.order for s in record.recovery_steps] != list(range(1, len(record.recovery_steps) + 1))
            or not (0.0 <= record.blast_radius <= self.max_blast_radius)
            or not (0.0 <= record.residual_risk <= self.max_residual_risk)
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self._audit(record, "created")
        return record

    def authorize(self, record_id: str, *, actor: str, human_approved: bool) -> ReconciliationAuthorizationRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "authorized"
            record.authorized_by = actor
        self._audit(record, "authorization-reviewed")
        return record

    def approve_step(self, record_id: str, *, order: int, actor: str, human_approved: bool) -> ReconciliationAuthorizationRecord:
        record = self.records[record_id]
        if record.state not in {"authorized", "staged"} or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
            self._audit(record, "step-blocked")
            return record
        index = order - 1
        if index < 0 or index >= len(record.recovery_steps) or any(not s.approved for s in record.recovery_steps[:index]):
            record.state = "blocked"
            self._audit(record, "step-order-blocked")
            return record
        current = record.recovery_steps[index]
        record.recovery_steps[index] = RecoveryStep(current.order, current.consumer_id, True)
        record.state = "recovery-ready" if all(s.approved for s in record.recovery_steps) else "staged"
        self._audit(record, f"step-{order}-approved:{actor}")
        return record

    def _audit(self, record: ReconciliationAuthorizationRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
