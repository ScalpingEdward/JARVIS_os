"""PHOENIX v21.165 — Reliability Baseline Adoption Authorization & Receipt Governance."""
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
    status: str
    receipt_nonce: str


@dataclass
class ReliabilityBaselineAdoptionRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    consumer_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    source_stage: int
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
            "source_stage": self.source_stage,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "authorized_by": self.authorized_by,
            "receipt_digest": self.receipt_digest,
        }


class ReliabilityBaselineAdoptionGovernance:
    """Govern exact consumer adoption authorization and fresh receipt verification."""

    def __init__(self) -> None:
        self.records: dict[str, ReliabilityBaselineAdoptionRecord] = {}
        self.source_consumer_keys: set[tuple[str, str]] = set()
        self.receipt_nonces: set[str] = set()
        self.audit: list[dict] = []

    def create(self, record: ReliabilityBaselineAdoptionRecord, *, source_state: str, source_stage_approved: bool) -> ReliabilityBaselineAdoptionRecord:
        key = (record.source_record_id, record.consumer_id)
        invalid = (
            source_state != "staged"
            or not source_stage_approved
            or not record.workspace_id
            or not record.consumer_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or record.source_stage < 1
            or key in self.source_consumer_keys
            or record.risk_brain_blocked
        )
        if invalid:
            record.state = "blocked"
        self.records[record.record_id] = record
        self.source_consumer_keys.add(key)
        self._audit(record, "created")
        return record

    def authorize(self, record_id: str, *, actor: str, human_approved: bool) -> ReliabilityBaselineAdoptionRecord:
        record = self.records[record_id]
        if record.state != "review-required" or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "authorized"
            record.authorized_by = actor
            record.state = "receipt-required"
        self._audit(record, "authorization-reviewed")
        return record

    def submit_receipt(self, record_id: str, receipt: AdoptionReceipt) -> ReliabilityBaselineAdoptionRecord:
        record = self.records[record_id]
        valid = (
            record.state == "receipt-required"
            and not record.risk_brain_blocked
            and receipt.status == "adopted"
            and receipt.consumer_id == record.consumer_id
            and receipt.workspace_id == record.workspace_id
            and receipt.baseline_id == record.baseline_id
            and receipt.baseline_version == record.baseline_version
            and receipt.baseline_digest == record.baseline_digest
            and bool(receipt.receipt_nonce)
            and receipt.receipt_nonce not in self.receipt_nonces
        )
        if not valid:
            record.state = "blocked"
            self._audit(record, "receipt-blocked")
            return record
        self.receipt_nonces.add(receipt.receipt_nonce)
        record.receipt_digest = _digest(receipt.__dict__)
        record.state = "adopted"
        self._audit(record, "receipt-accepted")
        return record

    def _audit(self, record: ReliabilityBaselineAdoptionRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
