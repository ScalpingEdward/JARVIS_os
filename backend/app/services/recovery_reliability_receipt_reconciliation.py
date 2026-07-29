"""PHOENIX v21.179 — Recovery Reliability Recovery Receipt Reconciliation & Cross-Consumer Completion Governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

State = Literal["review-required", "incomplete", "completed", "blocked"]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryReliabilityReceipt:
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    recovery_nonce: str
    recovered: bool
    healthy: bool
    recovery_score: float
    evidence_digest: str


@dataclass
class RecoveryReliabilityCompletionRecord:
    record_id: str
    workspace_id: str
    source_record_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: tuple[str, ...]
    receipts: tuple[RecoveryReliabilityReceipt, ...]
    minimum_recovery_score: float = 0.80
    risk_brain_blocked: bool = False
    state: State = "review-required"
    completion_score: float = 0.0
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
            "expected_consumers": self.expected_consumers,
            "receipts": [r.__dict__ for r in self.receipts],
            "minimum_recovery_score": self.minimum_recovery_score,
            "risk_brain_blocked": self.risk_brain_blocked,
            "state": self.state,
            "completion_score": self.completion_score,
            "approved_by": self.approved_by,
        }


class RecoveryReliabilityReceiptReconciliationGovernance:
    """Reconcile fresh recovery receipts; never mutates runtime consumers."""

    def __init__(self) -> None:
        self.records: dict[str, RecoveryReliabilityCompletionRecord] = {}
        self.source_ids: set[str] = set()
        self.nonces: set[str] = set()
        self.audit: list[dict] = []

    def reconcile(
        self,
        record: RecoveryReliabilityCompletionRecord,
        *,
        source_state: str,
        source_human_approved: bool,
    ) -> RecoveryReliabilityCompletionRecord:
        invalid = (
            source_state != "recovery-ready"
            or not source_human_approved
            or record.risk_brain_blocked
            or not record.workspace_id
            or not record.baseline_id
            or record.baseline_version < 1
            or not record.baseline_digest
            or not record.expected_consumers
            or record.source_record_id in self.source_ids
            or len(set(record.expected_consumers)) != len(record.expected_consumers)
            or not 0.0 <= record.minimum_recovery_score <= 1.0
        )

        receipt_consumers = [r.consumer_id for r in record.receipts]
        nonces = [r.recovery_nonce for r in record.receipts]
        if len(receipt_consumers) != len(set(receipt_consumers)):
            invalid = True
        if len(nonces) != len(set(nonces)) or any((not n or n in self.nonces) for n in nonces):
            invalid = True

        exact_matches = 0
        for receipt in record.receipts:
            exact = (
                receipt.consumer_id in record.expected_consumers
                and receipt.workspace_id == record.workspace_id
                and receipt.baseline_id == record.baseline_id
                and receipt.baseline_version == record.baseline_version
                and receipt.baseline_digest == record.baseline_digest
                and receipt.recovered
                and receipt.healthy
                and 0.0 <= receipt.recovery_score <= 1.0
                and receipt.recovery_score >= record.minimum_recovery_score
                and bool(receipt.evidence_digest)
            )
            exact_matches += int(exact)

        record.completion_score = exact_matches / len(record.expected_consumers)
        if invalid:
            record.state = "blocked"
        elif set(receipt_consumers) != set(record.expected_consumers) or record.completion_score != 1.0:
            record.state = "incomplete"

        self.records[record.record_id] = record
        self.source_ids.add(record.source_record_id)
        self.nonces.update(nonces)
        self._audit(record, "reconciled")
        return record

    def approve_completion(
        self,
        record_id: str,
        *,
        actor: str,
        human_approved: bool,
    ) -> RecoveryReliabilityCompletionRecord:
        record = self.records[record_id]
        if record.state == "incomplete":
            self._audit(record, "completion-incomplete")
            return record
        if record.state != "review-required" or record.completion_score != 1.0 or not human_approved or record.risk_brain_blocked:
            record.state = "blocked"
        else:
            record.state = "completed"
            record.approved_by = actor
        self._audit(record, "completion-reviewed")
        return record

    def _audit(self, record: RecoveryReliabilityCompletionRecord, action: str) -> None:
        record.audit_digest = _digest(record.snapshot())
        self.audit.append({"record_id": record.record_id, "action": action, "digest": record.audit_digest})
