"""PHOENIX v21.195 — Recovery Reliability Baseline Adoption Authorization & Receipt Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "authorized", "receipt-required", "adopted", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class AdoptionReceipt:
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    adoption_nonce: str
    evidence_age_seconds: int
    adopted: bool


@dataclass
class BaselineAdoptionRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    consumer_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    rollback_version: int
    rollback_value: float
    risk_brain_blocked: bool = False
    state: State = "review-required"
    authorized_by: str | None = None
    receipt_digest: str | None = None
    audit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        self.audit_digest = _digest(self.snapshot())

    def snapshot(self) -> dict:
        return {
            "record_id": self.record_id,
            "workspace_id": self.workspace_id,
            "source_record_id": self.source_record_id,
            "consumer_id": self.consumer_id,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "baseline_digest": self.baseline_digest,
            "rollback_version": self.rollback_version,
            "rollback_value": self.rollback_value,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "authorized_by": self.authorized_by,
            "receipt_digest": self.receipt_digest,
        }


class RecoveryReliabilityBaselineAdoptionGovernance:
    """Authorize adoption and reconcile fresh receipts without mutating runtime consumers."""

    def __init__(self, *, max_receipt_age_seconds: int = 300) -> None:
        self.max_receipt_age_seconds = max_receipt_age_seconds
        self.records: dict[str, BaselineAdoptionRecord] = {}
        self.source_consumer_keys: set[tuple[str, str]] = set()
        self.nonces: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: BaselineAdoptionRecord, *, source_state: str, source_human_approved: bool) -> BaselineAdoptionRecord:
        key = (record.source_record_id, record.consumer_id)
        invalid = (
            source_state != "staged"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.consumer_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or record.rollback_version < 1
            or record.rollback_version >= record.baseline_version
            or not (0.0 <= record.rollback_value <= 1.0)
            or key in self.source_consumer_keys
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_consumer_keys.add(key)
        self._audit(record, "created")
        return record

    def authorize(self, record_id: str, *, actor: str, human_approved: bool) -> BaselineAdoptionRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "authorized"
            record.authorized_by = actor
        self._audit(record, "authorization-reviewed")
        return record

    def require_receipt(self, record_id: str) -> BaselineAdoptionRecord:
        record = self.records[record_id]
        if record.state != "authorized" or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "receipt-required"
        self._audit(record, "receipt-requested")
        return record

    def reconcile_receipt(self, record_id: str, receipt: AdoptionReceipt) -> BaselineAdoptionRecord:
        record = self.records[record_id]
        valid = (
            record.state == "receipt-required"
            and not record.risk_brain_blocked
            and receipt.consumer_id == record.consumer_id
            and receipt.workspace_id == record.workspace_id
            and receipt.baseline_id == record.baseline_id
            and receipt.baseline_version == record.baseline_version
            and receipt.baseline_digest == record.baseline_digest
            and receipt.adopted
            and 0 <= receipt.evidence_age_seconds <= self.max_receipt_age_seconds
            and bool(receipt.adoption_nonce)
            and receipt.adoption_nonce not in self.nonces
        )
        if not valid:
            record.state = "blocked"
        else:
            self.nonces.add(receipt.adoption_nonce)
            record.receipt_digest = _digest(receipt.__dict__)
            record.state = "adopted"
        self._audit(record, "receipt-reconciled")
        return record

    def _audit(self, record: BaselineAdoptionRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
