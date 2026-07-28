"""PHOENIX v21.141 — governed primary recovery reconciliation.

This module is intentionally non-executing. It reconciles evidence produced after a
consumed v21.140 recovery permit and attests that recovery stayed inside the
approved read-only boundary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any

READ_ONLY_OPERATIONS = {"GET", "HEAD"}
PROTECTED_OPERATIONS = {"trade-execute", "order-submit", "fund-move", "credential-mutate", "permission-expand"}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryReceipt:
    receipt_id: str
    permit_id: str
    recovery_plan_digest: str
    primary_adapter_id: str
    primary_worker_id: str
    gateway_id: str
    operation: str
    target: str
    response_digest: str
    success: bool
    side_effects: list[str] = field(default_factory=list)


@dataclass
class RecoveryAttestation:
    attestation_id: str
    workspace_id: str
    permit_id: str
    permit_digest: str
    recovery_plan_digest: str
    receipt_id: str
    receipt_digest: str
    status: str
    side_effect_safe: bool
    identity_match: bool
    human_approved: bool = False
    risk_brain_blocked: bool = False
    findings: list[str] = field(default_factory=list)
    attestation_digest: str = ""


class PrimaryRecoveryReconciliationService:
    """Fail-closed reconciliation and completion attestation for primary recovery."""

    def __init__(self) -> None:
        self._records: dict[str, RecoveryAttestation] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[dict[str, Any]] = []

    def reconcile(
        self,
        *,
        attestation_id: str,
        workspace_id: str,
        consumed_permit: dict[str, Any],
        receipt: RecoveryReceipt,
        source_key: str,
    ) -> RecoveryAttestation:
        replay_key = (workspace_id, source_key)
        if replay_key in self._source_keys:
            raise ValueError("duplicate source key")
        self._source_keys.add(replay_key)

        findings: list[str] = []
        if consumed_permit.get("workspace_id") != workspace_id:
            findings.append("workspace-mismatch")
        if consumed_permit.get("status") != "consumed":
            findings.append("permit-not-consumed")
        if consumed_permit.get("permit_id") != receipt.permit_id:
            findings.append("permit-id-mismatch")
        if consumed_permit.get("recovery_plan_digest") != receipt.recovery_plan_digest:
            findings.append("recovery-plan-digest-mismatch")

        expected_adapter = consumed_permit.get("primary_adapter_id")
        expected_worker = consumed_permit.get("primary_worker_id")
        expected_gateway = consumed_permit.get("gateway_id")
        identity_match = (
            expected_adapter == receipt.primary_adapter_id
            and expected_worker == receipt.primary_worker_id
            and expected_gateway == receipt.gateway_id
        )
        if not identity_match:
            findings.append("primary-handoff-identity-mismatch")

        operation = receipt.operation.upper()
        if operation not in READ_ONLY_OPERATIONS:
            findings.append("non-read-only-operation")
        if receipt.operation.lower() in PROTECTED_OPERATIONS:
            findings.append("protected-operation")
        if not receipt.success:
            findings.append("receipt-unsuccessful")

        forbidden_effects = {
            "write", "credential-mutation", "permission-mutation", "fund-movement",
            "order-execution", "trading-execution", "repository-mutation", "route-mutation",
        }
        detected = sorted(set(receipt.side_effects) & forbidden_effects)
        if detected:
            findings.extend(f"side-effect:{item}" for item in detected)

        risk_blocked = bool(consumed_permit.get("risk_brain_blocked")) or "protected-operation" in findings
        if risk_blocked:
            findings.append("risk-brain-hard-block")

        safe = not detected and operation in READ_ONLY_OPERATIONS
        status = "review-required" if not findings else "mismatch"
        permit_digest = _digest(consumed_permit)
        receipt_digest = _digest(asdict(receipt))
        record = RecoveryAttestation(
            attestation_id=attestation_id,
            workspace_id=workspace_id,
            permit_id=receipt.permit_id,
            permit_digest=permit_digest,
            recovery_plan_digest=receipt.recovery_plan_digest,
            receipt_id=receipt.receipt_id,
            receipt_digest=receipt_digest,
            status=status,
            side_effect_safe=safe,
            identity_match=identity_match,
            risk_brain_blocked=risk_blocked,
            findings=findings,
        )
        record.attestation_digest = _digest(asdict(record))
        self._records[attestation_id] = record
        self._audit.append({"event": "reconciled", "id": attestation_id, "digest": record.attestation_digest})
        return record

    def approve(self, attestation_id: str, *, human_approved: bool) -> RecoveryAttestation:
        record = self._records[attestation_id]
        if record.status != "review-required":
            raise ValueError("only clean reconciliation may be approved")
        if not human_approved:
            raise ValueError("human approval required")
        if record.risk_brain_blocked or not record.side_effect_safe or not record.identity_match:
            raise ValueError("recovery attestation blocked")
        record.human_approved = True
        record.status = "attested"
        record.attestation_digest = _digest(asdict(record))
        self._audit.append({"event": "attested", "id": attestation_id, "digest": record.attestation_digest})
        return record

    def get(self, attestation_id: str) -> RecoveryAttestation:
        return self._records[attestation_id]

    def list_records(self, workspace_id: str | None = None) -> list[RecoveryAttestation]:
        values = list(self._records.values())
        return values if workspace_id is None else [r for r in values if r.workspace_id == workspace_id]

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)
