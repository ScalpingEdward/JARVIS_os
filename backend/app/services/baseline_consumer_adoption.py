"""PHOENIX v21.147 — Baseline Consumer Adoption Receipt & Drift Monitoring Governance.

Governance only. Downstream consumers acknowledge the exact approved baseline
version they adopted. Drift is detected and reported fail-closed; no autonomous
correction, routing mutation, or policy change is performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any

SUPPORTED_CONSUMERS = {
    "adapter-selection",
    "worker-selection",
    "dispatch-planning",
    "failover-health",
    "recovery-readiness",
}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass
class AdoptionReceipt:
    receipt_id: str
    workspace_id: str
    rollout_id: str
    consumer_id: str
    consumer_type: str
    expected_baseline_id: str
    expected_baseline_version: int
    expected_baseline_digest: str
    observed_baseline_id: str
    observed_baseline_version: int
    observed_baseline_digest: str
    status: str
    drift_detected: bool
    findings: list[str] = field(default_factory=list)
    human_reviewed: bool = False
    risk_brain_blocked: bool = False
    receipt_digest: str = ""


class BaselineConsumerAdoptionService:
    def __init__(self) -> None:
        self._records: dict[str, AdoptionReceipt] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def acknowledge(
        self,
        *,
        receipt_id: str,
        workspace_id: str,
        rollout: dict[str, Any],
        consumer_id: str,
        consumer_type: str,
        observed_baseline_id: str,
        observed_baseline_version: int,
        observed_baseline_digest: str,
        source_key: str,
    ) -> AdoptionReceipt:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if receipt_id in self._records:
            raise ValueError("duplicate receipt id")

        findings: list[str] = []
        if rollout.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if rollout.get("status") != "active":
            findings.append("rollout-not-active")
        allowed_consumers = set(rollout.get("consumers", []))
        if consumer_type not in SUPPORTED_CONSUMERS:
            findings.append("unsupported-consumer")
        if consumer_type not in allowed_consumers:
            findings.append("consumer-not-allow-listed")
        if rollout.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        expected_id = str(rollout.get("baseline_id", ""))
        expected_version = int(rollout.get("baseline_version", 0))
        expected_digest = str(rollout.get("baseline_digest", ""))
        if observed_baseline_id != expected_id:
            findings.append("baseline-id-drift")
        if observed_baseline_version != expected_version:
            findings.append("baseline-version-drift")
        if observed_baseline_digest != expected_digest:
            findings.append("baseline-digest-drift")

        drift = any(item.endswith("-drift") for item in findings)
        blocked = bool(rollout.get("risk_brain_blocked", False))
        status = "drift-detected" if drift else ("blocked" if findings else "adopted")
        record = AdoptionReceipt(
            receipt_id=receipt_id,
            workspace_id=workspace_id,
            rollout_id=str(rollout.get("rollout_id", "")),
            consumer_id=consumer_id,
            consumer_type=consumer_type,
            expected_baseline_id=expected_id,
            expected_baseline_version=expected_version,
            expected_baseline_digest=expected_digest,
            observed_baseline_id=observed_baseline_id,
            observed_baseline_version=observed_baseline_version,
            observed_baseline_digest=observed_baseline_digest,
            status=status,
            drift_detected=drift,
            findings=findings,
            risk_brain_blocked=blocked,
        )
        record.receipt_digest = _digest(asdict(record))
        self._records[receipt_id] = record
        self._audit.append({"event": "adoption-receipt", "id": receipt_id, "digest": record.receipt_digest})
        return record

    def review_drift(self, receipt_id: str, *, human_reviewed: bool) -> AdoptionReceipt:
        record = self._records[receipt_id]
        if record.status != "drift-detected":
            raise ValueError("receipt has no drift to review")
        if not human_reviewed:
            raise ValueError("human review required")
        record.human_reviewed = True
        record.status = "drift-reviewed"
        record.receipt_digest = _digest(asdict(record))
        self._audit.append({"event": "drift-reviewed", "id": receipt_id, "digest": record.receipt_digest})
        return record

    def get(self, receipt_id: str) -> AdoptionReceipt:
        return self._records[receipt_id]

    def list_records(self, workspace_id: str | None = None) -> list[AdoptionReceipt]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
