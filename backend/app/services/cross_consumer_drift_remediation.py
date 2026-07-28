"""PHOENIX v21.157 — Cross-Consumer Drift Escalation & Coordinated Remediation Readiness Governance.

Governance only. Converts v21.156 inconsistent adoption evidence into a bounded,
human-reviewed remediation-readiness plan. It performs no runtime mutation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class RemediationRecord:
    record_id: str
    workspace_id: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    affected_consumers: list[str]
    healthy_consumers: list[str]
    remediation_actions: dict[str, str]
    consistency_score: float
    blast_radius: float
    residual_risk: float
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    source_digest: str = ""
    plan_digest: str = ""


class CrossConsumerDriftRemediationService:
    """Fail-closed drift escalation and remediation-readiness governance."""

    def __init__(self) -> None:
        self._records: dict[str, RemediationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(self, *, record_id: str, workspace_id: str, inconsistent_evidence: dict[str, Any], source_key: str,
               max_blast_radius: float = 0.60, max_residual_risk: float = 0.35) -> RemediationRecord:
        key = (workspace_id, source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if inconsistent_evidence.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if inconsistent_evidence.get("status") != "inconsistent":
            findings.append("admission-state-not-inconsistent")
        if inconsistent_evidence.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        eligible = sorted(set(inconsistent_evidence.get("eligible_consumers", [])))
        receipts = inconsistent_evidence.get("receipts", []) or []
        baseline_id = str(inconsistent_evidence.get("baseline_id", ""))
        baseline_version = int(inconsistent_evidence.get("baseline_version", 0) or 0)
        baseline_digest = str(inconsistent_evidence.get("baseline_digest", ""))
        if not baseline_id or baseline_version <= 0 or not baseline_digest:
            findings.append("baseline-binding-missing")

        affected: set[str] = set()
        adopted: set[str] = set()
        for receipt in receipts:
            consumer = str(receipt.get("consumer", ""))
            if not consumer:
                continue
            exact = (
                receipt.get("status") == "adopted"
                and receipt.get("baseline_id") == baseline_id
                and int(receipt.get("baseline_version", 0) or 0) == baseline_version
                and receipt.get("baseline_digest") == baseline_digest
            )
            if exact:
                adopted.add(consumer)
            else:
                affected.add(consumer)

        for consumer in eligible:
            if consumer not in adopted:
                affected.add(consumer)
        healthy = set(eligible) - affected
        if not affected:
            findings.append("no-drift-to-remediate")

        consistency_score = 1.0 if not eligible else len(healthy) / len(eligible)
        blast_radius = 0.0 if not eligible else len(affected) / len(eligible)
        residual_risk = min(1.0, (1.0 - consistency_score) * 0.7 + blast_radius * 0.3)
        if blast_radius > max_blast_radius:
            findings.append("blast-radius-above-limit")
        if residual_risk > max_residual_risk:
            findings.append("residual-risk-above-limit")

        actions = {consumer: "re-adoption-required" for consumer in sorted(affected)}
        risk_blocked = bool(inconsistent_evidence.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "blocked"
        record = RemediationRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            affected_consumers=sorted(affected),
            healthy_consumers=sorted(healthy),
            remediation_actions=actions,
            consistency_score=round(consistency_score, 6),
            blast_radius=round(blast_radius, 6),
            residual_risk=round(residual_risk, 6),
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
            source_digest=_digest(inconsistent_evidence),
        )
        record.plan_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "remediation-evaluated", "id": record_id, "digest": record.plan_digest})
        return record

    def approve(self, record_id: str, *, human_approved: bool) -> RemediationRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("record is not eligible for approval")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "remediation-ready"
        record.plan_digest = _digest(asdict(record))
        self._audit.append({"event": "remediation-ready", "id": record_id, "digest": record.plan_digest})
        return record

    def get(self, record_id: str) -> RemediationRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[RemediationRecord]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
