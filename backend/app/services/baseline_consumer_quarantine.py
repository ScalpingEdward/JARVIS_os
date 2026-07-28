"""PHOENIX v21.148 — Drift Escalation, Consumer Quarantine & Re-Adoption Governance.

Governance only. Human-reviewed drift can quarantine an affected baseline consumer.
Re-adoption requires a fresh exact baseline receipt and explicit human approval.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class QuarantineRecord:
    record_id: str
    workspace_id: str
    consumer_id: str
    drift_receipt_id: str
    drift_receipt_digest: str
    expected_baseline_id: str
    expected_baseline_version: int
    expected_baseline_digest: str
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    readoption_receipt_id: str | None = None
    readoption_digest: str | None = None
    record_digest: str = ""


class BaselineConsumerQuarantineService:
    """Fail-closed quarantine and controlled re-adoption governance."""

    def __init__(self) -> None:
        self._records: dict[str, QuarantineRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create_from_drift(self, *, record_id: str, workspace_id: str, drift_receipt: dict[str, Any], source_key: str) -> QuarantineRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate quarantine record")

        findings: list[str] = []
        if drift_receipt.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if drift_receipt.get("status") != "drift-reviewed":
            findings.append("drift-not-human-reviewed")
        if drift_receipt.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        status = "review-required" if not findings else "blocked"
        rec = QuarantineRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            consumer_id=str(drift_receipt.get("consumer_id", "")),
            drift_receipt_id=str(drift_receipt.get("receipt_id", "")),
            drift_receipt_digest=_digest(drift_receipt),
            expected_baseline_id=str(drift_receipt.get("expected_baseline_id", drift_receipt.get("baseline_id", ""))),
            expected_baseline_version=int(drift_receipt.get("expected_baseline_version", drift_receipt.get("baseline_version", 0))),
            expected_baseline_digest=str(drift_receipt.get("expected_baseline_digest", drift_receipt.get("baseline_digest", ""))),
            status=status,
            findings=findings,
            risk_brain_blocked=bool(drift_receipt.get("risk_brain_blocked", False)),
        )
        rec.record_digest = _digest(asdict(rec))
        self._records[record_id] = rec
        self._audit.append({"event": "quarantine-proposed", "id": record_id, "digest": rec.record_digest})
        return rec

    def quarantine(self, record_id: str, *, human_approved: bool) -> QuarantineRecord:
        rec = self._records[record_id]
        if rec.status != "review-required":
            raise ValueError("record not eligible for quarantine approval")
        if not human_approved:
            raise ValueError("human approval required")
        if rec.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        rec.human_approved = True
        rec.status = "quarantined"
        rec.record_digest = _digest(asdict(rec))
        self._audit.append({"event": "consumer-quarantined", "id": record_id, "digest": rec.record_digest})
        return rec

    def submit_readoption(self, record_id: str, *, receipt: dict[str, Any]) -> QuarantineRecord:
        rec = self._records[record_id]
        if rec.status != "quarantined":
            raise ValueError("consumer is not quarantined")
        findings: list[str] = []
        if receipt.get("workspace_id") != rec.workspace_id:
            findings.append("workspace-mismatch")
        if receipt.get("consumer_id") != rec.consumer_id:
            findings.append("consumer-mismatch")
        if receipt.get("status") != "adopted":
            findings.append("receipt-not-adopted")
        if receipt.get("baseline_id") != rec.expected_baseline_id:
            findings.append("baseline-id-mismatch")
        if int(receipt.get("baseline_version", -1)) != rec.expected_baseline_version:
            findings.append("baseline-version-mismatch")
        if receipt.get("baseline_digest") != rec.expected_baseline_digest:
            findings.append("baseline-digest-mismatch")
        if receipt.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        rec.findings = findings
        rec.readoption_receipt_id = str(receipt.get("receipt_id", ""))
        rec.readoption_digest = _digest(receipt)
        rec.status = "readoption-review-required" if not findings else "quarantined"
        rec.record_digest = _digest(asdict(rec))
        self._audit.append({"event": "readoption-evaluated", "id": record_id, "digest": rec.record_digest})
        return rec

    def approve_readoption(self, record_id: str, *, human_approved: bool) -> QuarantineRecord:
        rec = self._records[record_id]
        if rec.status != "readoption-review-required":
            raise ValueError("re-adoption not eligible")
        if not human_approved:
            raise ValueError("human approval required")
        if rec.risk_brain_blocked or rec.findings:
            raise ValueError("re-adoption blocked")
        rec.status = "readopted"
        rec.human_approved = True
        rec.record_digest = _digest(asdict(rec))
        self._audit.append({"event": "consumer-readopted", "id": record_id, "digest": rec.record_digest})
        return rec

    def get(self, record_id: str) -> QuarantineRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[QuarantineRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
