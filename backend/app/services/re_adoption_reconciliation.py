"""PHOENIX v21.159 — Re-Adoption Receipt Reconciliation & Coordinated Recovery Completion Governance.

Governance only. Reconciles each approved v21.158 recovery step against a fresh
consumer adoption receipt before a coordinated remediation episode may be closed.
No consumer, baseline, routing, policy, credential, permission, fund, order, or
execution mutation is performed here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class AdoptionReceipt:
    receipt_id: str
    consumer_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    status: str
    source_digest: str


@dataclass
class RecoveryCompletionRecord:
    record_id: str
    workspace_id: str
    sequence_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    expected_consumers: list[str]
    reconciled_consumers: list[str]
    missing_consumers: list[str]
    mismatched_consumers: list[str]
    duplicate_consumers: list[str]
    reconciliation_score: float
    status: str
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    source_digest: str = ""
    completion_digest: str = ""


class ReAdoptionReconciliationService:
    """Fail-closed reconciliation of fresh re-adoption receipts."""

    def __init__(self) -> None:
        self._records: dict[str, RecoveryCompletionRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        recovery_sequence: dict[str, Any],
        receipts: list[AdoptionReceipt],
        source_key: str,
    ) -> RecoveryCompletionRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if recovery_sequence.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if recovery_sequence.get("status") != "recovery-ready":
            findings.append("sequence-not-recovery-ready")
        if not recovery_sequence.get("human_approved", False):
            findings.append("sequence-human-approval-missing")

        baseline_id = str(recovery_sequence.get("baseline_id", ""))
        baseline_version = int(recovery_sequence.get("baseline_version", 0) or 0)
        baseline_digest = str(recovery_sequence.get("baseline_digest", ""))
        if not baseline_id or baseline_version <= 0 or not baseline_digest:
            findings.append("baseline-binding-missing")

        expected = [str(x) for x in recovery_sequence.get("affected_consumers", [])]
        if not expected:
            findings.append("expected-consumer-set-empty")

        seen: set[str] = set()
        reconciled: list[str] = []
        mismatched: list[str] = []
        duplicates: list[str] = []

        for receipt in receipts:
            if receipt.consumer_id in seen:
                duplicates.append(receipt.consumer_id)
                continue
            seen.add(receipt.consumer_id)

            mismatch = False
            if receipt.consumer_id not in expected:
                mismatch = True
            if receipt.workspace_id != workspace_id:
                mismatch = True
            if receipt.baseline_id != baseline_id:
                mismatch = True
            if receipt.baseline_version != baseline_version:
                mismatch = True
            if receipt.baseline_digest != baseline_digest:
                mismatch = True
            if receipt.status != "adopted":
                mismatch = True
            if not receipt.source_digest:
                mismatch = True

            if mismatch:
                mismatched.append(receipt.consumer_id)
            else:
                reconciled.append(receipt.consumer_id)

        missing = sorted(set(expected) - seen)
        duplicate_consumers = sorted(set(duplicates))
        mismatched_consumers = sorted(set(mismatched))
        reconciled_consumers = sorted(set(reconciled))

        if missing:
            findings.append("missing-re-adoption-receipts")
        if duplicate_consumers:
            findings.append("duplicate-consumer-receipts")
        if mismatched_consumers:
            findings.append("receipt-binding-mismatch")

        risk_blocked = bool(recovery_sequence.get("risk_brain_blocked", False))
        if risk_blocked:
            findings.append("risk-brain-hard-block")

        denominator = max(len(set(expected)), 1)
        score = round(len(reconciled_consumers) / denominator, 6)
        status = "review-required" if not findings and score == 1.0 else "incomplete"

        source_digest = _digest(
            {
                "recovery_sequence": recovery_sequence,
                "receipts": [asdict(r) for r in receipts],
            }
        )
        record = RecoveryCompletionRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            sequence_id=str(recovery_sequence.get("record_id", recovery_sequence.get("sequence_id", ""))),
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            expected_consumers=sorted(set(expected)),
            reconciled_consumers=reconciled_consumers,
            missing_consumers=missing,
            mismatched_consumers=mismatched_consumers,
            duplicate_consumers=duplicate_consumers,
            reconciliation_score=score,
            status=status,
            risk_brain_blocked=risk_blocked,
            findings=findings,
            source_digest=source_digest,
        )
        record.completion_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "reconciliation-created", "id": record_id, "digest": record.completion_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> RecoveryCompletionRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record is not eligible for completion approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        if record.reconciliation_score != 1.0:
            raise ValueError("all expected consumers must reconcile")
        record.human_approved = True
        record.status = "completed"
        record.completion_digest = _digest(asdict(record))
        self._audit.append({"event": "recovery-completed", "id": record_id, "digest": record.completion_digest})
        return record

    def get(self, record_id: str) -> RecoveryCompletionRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[RecoveryCompletionRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
