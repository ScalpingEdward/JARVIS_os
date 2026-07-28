"""PHOENIX v21.144 — Human-Approved Reliability Baseline Commit & Versioned Rollback Governance.

Creates versioned reliability baseline records only after a human-approved incident
closure from v21.143. No routing, policy, credential, permission, or execution
setting is mutated by this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class BaselineVersion:
    baseline_id: str
    workspace_id: str
    subject_id: str
    version: int
    previous_version: int | None
    baseline_value: float
    previous_value: float | None
    closure_id: str
    closure_digest: str
    status: str
    rollback_target_version: int | None = None
    approved_by: str | None = None
    risk_brain_blocked: bool = False
    record_digest: str = ""


class ReliabilityBaselineCommitService:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, int], BaselineVersion] = {}
        self._latest: dict[tuple[str, str], int] = {}
        self._ops: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def propose(self, *, baseline_id: str, workspace_id: str, subject_id: str, closure: dict[str, Any], operation_id: str) -> BaselineVersion:
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        self._ops.add((workspace_id, operation_id))
        if closure.get("workspace_id") != workspace_id:
            raise ValueError("workspace mismatch")
        if closure.get("status") != "closed" or not closure.get("human_approved", False):
            raise ValueError("human-approved closed incident required")
        risk_blocked = bool(closure.get("risk_brain_blocked", False))
        if risk_blocked:
            raise ValueError("risk brain hard block")

        key = (workspace_id, subject_id)
        previous_version = self._latest.get(key)
        previous_value = None
        if previous_version is not None:
            previous_value = self._records[(workspace_id, subject_id, previous_version)].baseline_value
        version = 1 if previous_version is None else previous_version + 1
        value = float(closure.get("proposed_baseline"))
        if not 0.0 <= value <= 1.0:
            raise ValueError("baseline outside allowed range")

        record = BaselineVersion(
            baseline_id=baseline_id,
            workspace_id=workspace_id,
            subject_id=subject_id,
            version=version,
            previous_version=previous_version,
            baseline_value=value,
            previous_value=previous_value,
            closure_id=str(closure.get("closure_id")),
            closure_digest=_digest(closure),
            status="review-required",
            risk_brain_blocked=False,
        )
        record.record_digest = _digest(asdict(record))
        self._records[(workspace_id, subject_id, version)] = record
        self._audit.append({"event":"baseline-proposed","subject_id":subject_id,"version":version,"digest":record.record_digest})
        return record

    def approve(self, workspace_id: str, subject_id: str, version: int, *, actor: str, operation_id: str) -> BaselineVersion:
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        self._ops.add((workspace_id, operation_id))
        record = self._records[(workspace_id, subject_id, version)]
        if record.status != "review-required":
            raise ValueError("baseline not awaiting approval")
        if record.risk_brain_blocked:
            raise ValueError("risk brain hard block")
        record.status = "active"
        record.approved_by = actor
        record.record_digest = _digest(asdict(record))
        self._latest[(workspace_id, subject_id)] = version
        self._audit.append({"event":"baseline-activated","subject_id":subject_id,"version":version,"actor":actor,"digest":record.record_digest})
        return record

    def propose_rollback(self, workspace_id: str, subject_id: str, *, target_version: int, actor: str, operation_id: str) -> BaselineVersion:
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        self._ops.add((workspace_id, operation_id))
        latest_version = self._latest.get((workspace_id, subject_id))
        if latest_version is None:
            raise ValueError("no active baseline")
        if target_version >= latest_version:
            raise ValueError("rollback target must be older than active version")
        target = self._records[(workspace_id, subject_id, target_version)]
        current = self._records[(workspace_id, subject_id, latest_version)]
        new_version = latest_version + 1
        rollback = BaselineVersion(
            baseline_id=f"{current.baseline_id}-rollback-{new_version}",
            workspace_id=workspace_id,
            subject_id=subject_id,
            version=new_version,
            previous_version=latest_version,
            baseline_value=target.baseline_value,
            previous_value=current.baseline_value,
            closure_id=current.closure_id,
            closure_digest=current.closure_digest,
            status="rollback-review-required",
            rollback_target_version=target_version,
        )
        rollback.record_digest = _digest(asdict(rollback))
        self._records[(workspace_id, subject_id, new_version)] = rollback
        self._audit.append({"event":"rollback-proposed","subject_id":subject_id,"version":new_version,"target":target_version,"actor":actor})
        return rollback

    def approve_rollback(self, workspace_id: str, subject_id: str, version: int, *, actor: str, operation_id: str) -> BaselineVersion:
        if (workspace_id, operation_id) in self._ops:
            raise ValueError("operation replay detected")
        self._ops.add((workspace_id, operation_id))
        record = self._records[(workspace_id, subject_id, version)]
        if record.status != "rollback-review-required":
            raise ValueError("rollback not awaiting approval")
        record.status = "active"
        record.approved_by = actor
        record.record_digest = _digest(asdict(record))
        self._latest[(workspace_id, subject_id)] = version
        self._audit.append({"event":"rollback-activated","subject_id":subject_id,"version":version,"actor":actor,"digest":record.record_digest})
        return record

    def list_records(self, workspace_id: str, subject_id: str | None = None) -> list[BaselineVersion]:
        out = [r for (ws, _, _), r in self._records.items() if ws == workspace_id]
        if subject_id is not None:
            out = [r for r in out if r.subject_id == subject_id]
        return sorted(out, key=lambda r: (r.subject_id, r.version))

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
