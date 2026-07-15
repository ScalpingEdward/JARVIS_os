from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ActorRole,
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequestCreate,
    ApprovalStatus,
    ApprovalTokenResponse,
    AuditEvent,
    RiskLevel,
)


class ApprovalError(ValueError):
    pass


class ApprovalService:
    """Controls approval-gated actions and records an immutable in-memory audit trail."""

    _approver_roles = {ActorRole.approver, ActorRole.admin}
    _blocked_actions = {
        "system.disable_safety",
        "database.drop",
        "secrets.export",
    }

    def __init__(self) -> None:
        self._approvals: dict[UUID, ApprovalRecord] = {}
        self._token_hashes: dict[UUID, str] = {}
        self._audit: list[AuditEvent] = []

    def reset(self) -> None:
        self._approvals.clear()
        self._token_hashes.clear()
        self._audit.clear()

    def request(self, payload: ApprovalRequestCreate) -> ApprovalRecord:
        if payload.action in self._blocked_actions:
            self._log("request_blocked", payload.requested_by, None, {"action": payload.action})
            raise ApprovalError("Action is permanently blocked by safety policy")
        if payload.requester_role == ActorRole.viewer:
            raise ApprovalError("Viewer role cannot request actions")
        record = ApprovalRecord(**payload.model_dump())
        self._approvals[record.id] = record
        self._log("approval_requested", payload.requested_by, record.id, {"action": record.action, "risk": record.risk})
        return record

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRecord]:
        items = list(self._approvals.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get(self, approval_id: UUID) -> ApprovalRecord | None:
        return self._approvals.get(approval_id)

    def approve(self, approval_id: UUID, decision: ApprovalDecision) -> ApprovalTokenResponse:
        record = self._require_pending(approval_id)
        if decision.role not in self._approver_roles:
            raise ApprovalError("Actor role is not allowed to approve")
        if decision.actor == record.requested_by:
            raise ApprovalError("Requester cannot approve their own action")
        token = secrets.token_urlsafe(32)
        self._token_hashes[approval_id] = self._hash(token)
        record.status = ApprovalStatus.approved
        record.approved_by = decision.actor
        record.decided_at = datetime.now(timezone.utc)
        self._log("approval_granted", decision.actor, record.id, {"note": decision.note})
        return ApprovalTokenResponse(approval=record, confirmation_token=token)

    def reject(self, approval_id: UUID, decision: ApprovalDecision) -> ApprovalRecord:
        record = self._require_pending(approval_id)
        if decision.role not in self._approver_roles:
            raise ApprovalError("Actor role is not allowed to reject")
        record.status = ApprovalStatus.rejected
        record.rejected_by = decision.actor
        record.decided_at = datetime.now(timezone.utc)
        self._log("approval_rejected", decision.actor, record.id, {"note": decision.note})
        return record

    def consume(self, approval_id: UUID, token: str, actor: str) -> ApprovalRecord:
        record = self._approvals.get(approval_id)
        if record is None:
            raise ApprovalError("Approval not found")
        if record.status != ApprovalStatus.approved:
            raise ApprovalError("Approval is not available for execution")
        expected = self._token_hashes.get(approval_id)
        if expected is None or not secrets.compare_digest(expected, self._hash(token)):
            self._log("token_rejected", actor, approval_id, {})
            raise ApprovalError("Invalid confirmation token")
        record.status = ApprovalStatus.consumed
        record.consumed_at = datetime.now(timezone.utc)
        self._token_hashes.pop(approval_id, None)
        self._log("approval_consumed", actor, approval_id, {"action": record.action})
        return record

    def requires_approval(self, action: str, risk: RiskLevel) -> bool:
        return action in self._blocked_actions or risk in {RiskLevel.high, RiskLevel.critical}

    def audit_events(self) -> list[AuditEvent]:
        return list(reversed(self._audit))

    def _require_pending(self, approval_id: UUID) -> ApprovalRecord:
        record = self._approvals.get(approval_id)
        if record is None:
            raise ApprovalError("Approval not found")
        if record.status != ApprovalStatus.pending:
            raise ApprovalError("Approval has already been decided")
        return record

    def _log(self, event_type: str, actor: str, approval_id: UUID | None, details: dict) -> None:
        self._audit.append(
            AuditEvent(event_type=event_type, actor=actor, approval_id=approval_id, details=details)
        )

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


approval_service = ApprovalService()
