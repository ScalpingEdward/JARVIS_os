"""PHOENIX v21.158 — Coordinated Re-Adoption Authorization & Consumer Recovery Sequencing Governance.

Governance only. Converts a human-approved remediation-ready plan into a bounded,
ordered recovery sequence. No consumer, baseline, route, policy, credential,
permission or execution setting is mutated by this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass
class RecoveryStep:
    step_index: int
    consumer_id: str
    action: str = "re-adopt-baseline"
    status: str = "pending"
    human_approved: bool = False


@dataclass
class RecoverySequenceRecord:
    record_id: str
    workspace_id: str
    source_plan_id: str
    source_plan_digest: str
    baseline_id: str
    baseline_version: int
    baseline_digest: str
    affected_consumers: list[str]
    healthy_consumers: list[str]
    sequence: list[RecoveryStep]
    current_step: int
    status: str
    findings: list[str] = field(default_factory=list)
    human_approved: bool = False
    risk_brain_blocked: bool = False
    sequence_digest: str = ""


class ConsumerReAdoptionSequenceService:
    def __init__(self) -> None:
        self._records: dict[str, RecoverySequenceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def create(
        self,
        *,
        record_id: str,
        workspace_id: str,
        remediation_plan: dict[str, Any],
        source_key: str,
    ) -> RecoverySequenceRecord:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)
        if record_id in self._records:
            raise ValueError("duplicate record id")

        findings: list[str] = []
        if remediation_plan.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if remediation_plan.get("status") != "remediation-ready":
            findings.append("remediation-not-ready")
        if not remediation_plan.get("human_approved", False):
            findings.append("remediation-human-approval-missing")
        if remediation_plan.get("risk_brain_blocked", False):
            findings.append("risk-brain-hard-block")

        affected = list(dict.fromkeys(remediation_plan.get("affected_consumers", [])))
        healthy = list(dict.fromkeys(remediation_plan.get("healthy_consumers", [])))
        if not affected:
            findings.append("no-affected-consumers")
        if set(affected) & set(healthy):
            findings.append("consumer-set-overlap")

        baseline_id = str(remediation_plan.get("baseline_id", ""))
        baseline_digest = str(remediation_plan.get("baseline_digest", ""))
        baseline_version = int(remediation_plan.get("baseline_version", 0) or 0)
        if not baseline_id or not baseline_digest or baseline_version <= 0:
            findings.append("baseline-binding-missing")

        sequence = [RecoveryStep(step_index=i, consumer_id=consumer) for i, consumer in enumerate(affected)]
        risk_blocked = bool(remediation_plan.get("risk_brain_blocked", False))
        status = "review-required" if not findings else "blocked"
        record = RecoverySequenceRecord(
            record_id=record_id,
            workspace_id=workspace_id,
            source_plan_id=str(remediation_plan.get("record_id", "")),
            source_plan_digest=_digest(remediation_plan),
            baseline_id=baseline_id,
            baseline_version=baseline_version,
            baseline_digest=baseline_digest,
            affected_consumers=affected,
            healthy_consumers=healthy,
            sequence=sequence,
            current_step=0,
            status=status,
            findings=findings,
            risk_brain_blocked=risk_blocked,
        )
        record.sequence_digest = _digest(asdict(record))
        self._records[record_id] = record
        self._audit.append({"event": "sequence-created", "id": record_id, "digest": record.sequence_digest})
        return record

    def authorize(self, record_id: str, *, human_approved: bool) -> RecoverySequenceRecord:
        record = self._records[record_id]
        if record.status != "review-required":
            raise ValueError("sequence is not eligible for authorization")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.human_approved = True
        record.status = "authorized"
        record.sequence_digest = _digest(asdict(record))
        self._audit.append({"event": "sequence-authorized", "id": record_id, "digest": record.sequence_digest})
        return record

    def approve_next_step(self, record_id: str, *, human_approved: bool) -> RecoverySequenceRecord:
        record = self._records[record_id]
        if record.status not in {"authorized", "staged"}:
            raise ValueError("sequence is not ready for step approval")
        if not human_approved:
            raise ValueError("human approval required for every recovery step")
        if record.current_step >= len(record.sequence):
            raise ValueError("recovery sequence already complete")

        step = record.sequence[record.current_step]
        if step.status != "pending":
            raise ValueError("current step is not pending")
        step.human_approved = True
        step.status = "approved"
        record.current_step += 1
        record.status = "recovery-ready" if record.current_step == len(record.sequence) else "staged"
        record.sequence_digest = _digest(asdict(record))
        self._audit.append({"event": "step-approved", "id": record_id, "consumer_id": step.consumer_id, "digest": record.sequence_digest})
        return record

    def get(self, record_id: str) -> RecoverySequenceRecord:
        return self._records[record_id]

    def list_records(self, workspace_id: str | None = None) -> list[RecoverySequenceRecord]:
        records = list(self._records.values())
        return records if workspace_id is None else [r for r in records if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
