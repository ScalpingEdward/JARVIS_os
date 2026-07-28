"""PHOENIX v21.156 — Reintegration Baseline Adoption Receipt & Cross-Consumer Consistency Governance.

Governance only. Downstream consumers acknowledge the exact active reintegration
baseline they use. The service detects adoption drift or inconsistent adoption
across the governed consumer set without mutating runtime configuration.
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
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    consumer_state: str
    source_digest: str


@dataclass
class ConsistencyRecord:
    record_id: str
    workspace_id: str
    rollout_id: str
    expected_baseline_id: str
    expected_baseline_version: int
    expected_baseline_digest: str
    eligible_consumers: list[str]
    receipts: list[AdoptionReceipt]
    adopted_consumers: list[str]
    missing_consumers: list[str]
    mismatched_consumers: list[str]
    duplicate_consumers: list[str]
    consistency_score: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    evidence_digest: str = ""
    record_digest: str = ""


class ReintegrationBaselineAdoptionConsistencyService:
    """Fail-closed adoption receipt and cross-consumer consistency governance."""

    def __init__(self) -> None:
        self._records: dict[str, ConsistencyRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        active_rollout: dict[str, Any],
        receipts: list[AdoptionReceipt],
        source_key: str,
    ) -> ConsistencyRecord:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if active_rollout.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if active_rollout.get("status") != "active":
            findings.append("rollout-not-active")
        if not active_rollout.get("human_approved", False):
            findings.append("rollout-human-approval-missing")
        if active_rollout.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        expected_id = str(active_rollout.get("baseline_id", ""))
        expected_version = int(active_rollout.get("baseline_version", 0))
        expected_digest = str(active_rollout.get("baseline_digest", ""))
        eligible = sorted(set(str(x) for x in active_rollout.get("consumers", [])))
        if not expected_id or expected_version <= 0 or not expected_digest:
            findings.append("baseline-binding-incomplete")
        if not eligible:
            findings.append("eligible-consumers-empty")

        by_consumer: dict[str, list[AdoptionReceipt]] = {}
        for receipt in receipts:
            by_consumer.setdefault(receipt.consumer_id, []).append(receipt)

        duplicates = sorted(c for c, rs in by_consumer.items() if len(rs) > 1)
        missing = sorted(c for c in eligible if c not in by_consumer)
        mismatched: list[str] = []
        adopted: list[str] = []

        for consumer in eligible:
            rs = by_consumer.get(consumer, [])
            if len(rs) != 1:
                continue
            receipt = rs[0]
            exact = (
                receipt.baseline_id == expected_id
                and receipt.baseline_version == expected_version
                and receipt.baseline_digest == expected_digest
                and receipt.consumer_state == "adopted"
            )
            if exact:
                adopted.append(consumer)
            else:
                mismatched.append(consumer)

        unsupported = sorted(c for c in by_consumer if c not in eligible)
        if missing:
            findings.append("missing-adoption-receipts")
        if mismatched:
            findings.append("baseline-adoption-mismatch")
        if duplicates:
            findings.append("duplicate-consumer-receipts")
        if unsupported:
            findings.append("unsupported-consumer-receipt")

        consistency_score = round((len(adopted) / len(eligible)) if eligible else 0.0, 6)
        risk_blocked = bool(active_rollout.get("risk_brain_blocked", False))
        status = "review-required" if not findings and consistency_score == 1.0 else "inconsistent"

        evidence_digest = _digest([asdict(r) for r in receipts])
        record = ConsistencyRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            rollout_id=str(active_rollout.get("record_id", "")),
            expected_baseline_id=expected_id,
            expected_baseline_version=expected_version,
            expected_baseline_digest=expected_digest,
            eligible_consumers=eligible,
            receipts=receipts,
            adopted_consumers=sorted(adopted),
            missing_consumers=missing,
            mismatched_consumers=sorted(mismatched),
            duplicate_consumers=duplicates,
            consistency_score=consistency_score,
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
            evidence_digest=evidence_digest,
        )
        record.record_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "consistency-evaluated", "id": record_id, "digest": record.record_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> ConsistencyRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked or record.consistency_score != 1.0:
            raise ValueError("consistency approval blocked")
        record.human_approved = True
        record.status = "consistent"
        record.record_digest = _digest(asdict(record))
        self._audit.append({"event": "consistency-approved", "id": record_id, "digest": record.record_digest})
        return record

    def get(self, record_id: str) -> ConsistencyRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[ConsistencyRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
