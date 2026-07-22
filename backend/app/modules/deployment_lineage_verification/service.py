from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from .models import (
    AuditEntry,
    CheckSeverity,
    DeploymentVerificationCreate,
    DeploymentVerificationRecord,
    VerificationAction,
    VerificationState,
)


class DeploymentVerificationError(ValueError):
    pass


class DeploymentLineageVerificationService:
    def __init__(self) -> None:
        self._records: dict[str, DeploymentVerificationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEntry] = []

    def status(self) -> dict[str, object]:
        return {"module": "deployment-lineage-verification", "version": "21.30", "healthy": True}

    def create(self, payload: DeploymentVerificationCreate) -> DeploymentVerificationRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise DeploymentVerificationError("duplicate source_key in workspace")

        state = VerificationState.DRAFT
        if payload.risk_brain_blocked:
            state = VerificationState.BLOCKED
        elif not payload.rollout_evidence_ref or not payload.runtime_evidence_ref:
            state = VerificationState.EVIDENCE_REQUIRED

        record = DeploymentVerificationRecord(
            **payload.model_dump(),
            state=state,
            lineage=[payload.previous_config_version, payload.deployed_config_version],
        )
        self._records[record.record_id] = record
        self._source_keys.add(source_identity)
        return deepcopy(record)

    def list(self, workspace_id: str) -> list[DeploymentVerificationRecord]:
        return [deepcopy(item) for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> DeploymentVerificationRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise DeploymentVerificationError("deployment verification not found")
        return deepcopy(record)

    def act(self, workspace_id: str, record_id: str, payload: VerificationAction) -> DeploymentVerificationRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise DeploymentVerificationError("deployment verification not found")
        if record.risk_brain_blocked:
            raise DeploymentVerificationError("Risk Brain hard block is authoritative")
        if record.state == VerificationState.EVIDENCE_REQUIRED:
            raise DeploymentVerificationError("mandatory upstream evidence is missing")

        previous = record.state
        action = payload.action
        if action == "verify":
            self._require_state(record, VerificationState.DRAFT)
            record.state = VerificationState.VERIFYING
            for check in record.checks:
                check.passed = check.expected_value == check.observed_value
            record.drift_count = sum(check.passed is False for check in record.checks)
            record.critical_drift_count = sum(
                check.passed is False and check.severity == CheckSeverity.CRITICAL for check in record.checks
            )
            record.state = (
                VerificationState.VERIFIED
                if record.drift_count == 0
                else VerificationState.HUMAN_REVIEW_REQUIRED
            )
        elif action == "approve":
            self._require_state(record, VerificationState.HUMAN_REVIEW_REQUIRED)
            if not payload.approval_token:
                raise DeploymentVerificationError("approval_token is required")
            if payload.approval_token in self._approval_tokens:
                raise DeploymentVerificationError("approval token replay detected")
            self._approval_tokens.add(payload.approval_token)
            record.approval_token = payload.approval_token
            record.state = VerificationState.APPROVED
        elif action == "queue-remediation":
            self._require_state(record, VerificationState.APPROVED)
            self._consume_receipt(payload.receipt_id)
            record.state = VerificationState.REMEDIATION_QUEUED
        elif action == "resolve":
            self._require_state(record, VerificationState.REMEDIATION_QUEUED)
            self._consume_receipt(payload.receipt_id)
            failed_ids = {check.check_id for check in record.checks if check.passed is False}
            completed = set(payload.completed_check_ids)
            if not failed_ids.issubset(completed):
                raise DeploymentVerificationError("all failed checks must be remediated before resolution")
            record.remediation_completed_check_ids.update(completed)
            record.state = VerificationState.RESOLVED
        elif action == "fail":
            if record.state in {VerificationState.RESOLVED, VerificationState.ARCHIVED}:
                raise DeploymentVerificationError("resolved or archived record cannot fail")
            self._consume_receipt(payload.receipt_id)
            record.state = VerificationState.FAILED
        elif action == "archive":
            if record.state not in {VerificationState.VERIFIED, VerificationState.RESOLVED, VerificationState.FAILED}:
                raise DeploymentVerificationError("record is not terminal")
            self._consume_receipt(payload.receipt_id)
            record.state = VerificationState.ARCHIVED
        else:
            raise DeploymentVerificationError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._audit.append(
            AuditEntry(
                workspace_id=workspace_id,
                record_id=record_id,
                action=action,
                actor_id=payload.actor_id,
                from_state=previous,
                to_state=record.state,
                note=payload.note,
            )
        )
        return deepcopy(record)

    def audit(self, workspace_id: str) -> list[AuditEntry]:
        return [deepcopy(item) for item in self._audit if item.workspace_id == workspace_id]

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise DeploymentVerificationError("receipt_id is required")
        if receipt_id in self._receipts:
            raise DeploymentVerificationError("action receipt replay detected")
        self._receipts.add(receipt_id)

    @staticmethod
    def _require_state(record: DeploymentVerificationRecord, expected: VerificationState) -> None:
        if record.state != expected:
            raise DeploymentVerificationError(
                f"invalid state transition from {record.state.value}; expected {expected.value}"
            )


service = DeploymentLineageVerificationService()
