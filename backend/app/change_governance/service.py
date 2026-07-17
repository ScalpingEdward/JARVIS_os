from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalCreate, ApprovalDecision, ApprovalRecord, AuditRecord, ChangeCreate,
    ChangeGovernanceStatus, ChangeRecord, ChangeState, MetricsRecord, Mutation,
    ReleaseCreate, ReleaseRecord, RiskLevel,
)


class ChangeGovernanceService:
    def __init__(self) -> None:
        self.changes: dict[UUID, ChangeRecord] = {}
        self.approvals: dict[UUID, ApprovalRecord] = {}
        self.releases: dict[UUID, ReleaseRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details))

    def status(self) -> ChangeGovernanceStatus:
        return ChangeGovernanceStatus(changes=len(self.changes), approvals=len(self.approvals), releases=len(self.releases))

    def create_change(self, payload: ChangeCreate) -> ChangeRecord:
        if any(c.workspace_id == payload.workspace_id and c.change_key == payload.change_key and c.state not in {ChangeState.CLOSED, ChangeState.CANCELLED} for c in self.changes.values()):
            raise ValueError("active change key already exists")
        data = payload.model_dump(exclude={"human_approved", "automatic_approval", "execute_change", "external_deployment"})
        item = ChangeRecord(**data)
        self.changes[item.id] = item
        self._audit(item.workspace_id, "change.created", "change", item.id, item.owner_id)
        return item

    def list_changes(self, workspace_id: str, state: ChangeState | None = None) -> list[ChangeRecord]:
        return [c for c in self.changes.values() if c.workspace_id == workspace_id and (state is None or c.state == state)]

    def get_change(self, change_id: UUID, workspace_id: str) -> ChangeRecord | None:
        item = self.changes.get(change_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_state(self, change_id: UUID, workspace_id: str, payload: Mutation, state: ChangeState) -> ChangeRecord | None:
        item = self.changes.get(change_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        allowed = {
            ChangeState.REVIEW: {ChangeState.DRAFT},
            ChangeState.SCHEDULED: {ChangeState.APPROVED},
            ChangeState.IMPLEMENTED: {ChangeState.SCHEDULED},
            ChangeState.VERIFIED: {ChangeState.IMPLEMENTED},
            ChangeState.ROLLED_BACK: {ChangeState.IMPLEMENTED, ChangeState.VERIFIED},
            ChangeState.CLOSED: {ChangeState.VERIFIED, ChangeState.ROLLED_BACK},
            ChangeState.CANCELLED: {ChangeState.DRAFT, ChangeState.REVIEW, ChangeState.APPROVED, ChangeState.SCHEDULED},
        }
        if item.state not in allowed.get(state, set()):
            raise ValueError("invalid change transition")
        if state == ChangeState.SCHEDULED and not any(r.change_id == item.id for r in self.releases.values()):
            raise ValueError("release plan is required before scheduling")
        if state == ChangeState.IMPLEMENTED:
            item.implemented_at = datetime.now(timezone.utc)
        if state == ChangeState.VERIFIED:
            item.verified_at = datetime.now(timezone.utc)
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"change.{state.value}", "change", item.id, payload.requester_id, reason=payload.reason)
        return item

    def record_approval(self, payload: ApprovalCreate) -> ApprovalRecord:
        item = self.changes.get(payload.change_id)
        if not item or item.workspace_id != payload.workspace_id or item.state != ChangeState.REVIEW:
            raise ValueError("reviewable change not found")
        if payload.requester_id == item.owner_id:
            raise ValueError("change owner cannot approve own change")
        if any(a.change_id == item.id and a.requester_id == payload.requester_id for a in self.approvals.values()):
            raise ValueError("reviewer already decided")
        record = ApprovalRecord(**payload.model_dump(exclude={"human_approved", "automatic_decision"}))
        self.approvals[record.id] = record
        if record.decision == ApprovalDecision.APPROVE:
            item.approval_count += 1
            if item.approval_count >= item.required_approvals and item.rejection_count == 0:
                item.state = ChangeState.APPROVED
        else:
            item.rejection_count += 1
        item.updated_at = datetime.now(timezone.utc)
        self._audit(item.workspace_id, f"change.{record.decision.value}", "approval", record.id, record.requester_id, change_id=str(item.id))
        return record

    def create_release(self, payload: ReleaseCreate) -> ReleaseRecord:
        change = self.changes.get(payload.change_id)
        if not change or change.workspace_id != payload.workspace_id or change.owner_id != payload.requester_id or change.state != ChangeState.APPROVED:
            raise ValueError("approved owned change not found")
        if not change.evidence_references:
            raise ValueError("evidence references are required before release planning")
        if any(r.workspace_id == payload.workspace_id and r.release_key == payload.release_key for r in self.releases.values()):
            raise ValueError("release key already exists")
        record = ReleaseRecord(**payload.model_dump(exclude={"human_approved", "execute_release"}))
        self.releases[record.id] = record
        self._audit(record.workspace_id, "release.planned", "release", record.id, record.requester_id, change_id=str(change.id))
        return record

    def list_releases(self, workspace_id: str, change_id: UUID | None = None) -> list[ReleaseRecord]:
        return [r for r in self.releases.values() if r.workspace_id == workspace_id and (change_id is None or r.change_id == change_id)]

    def metrics(self, workspace_id: str) -> MetricsRecord:
        changes = [c for c in self.changes.values() if c.workspace_id == workspace_id]
        return MetricsRecord(
            workspace_id=workspace_id,
            changes=len(changes),
            pending_review=sum(c.state == ChangeState.REVIEW for c in changes),
            approved=sum(c.state == ChangeState.APPROVED for c in changes),
            scheduled=sum(c.state == ChangeState.SCHEDULED for c in changes),
            implemented=sum(c.state == ChangeState.IMPLEMENTED for c in changes),
            verified=sum(c.state == ChangeState.VERIFIED for c in changes),
            rolled_back=sum(c.state == ChangeState.ROLLED_BACK for c in changes),
            open_high_risk=sum(c.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL} and c.state not in {ChangeState.CLOSED, ChangeState.CANCELLED} for c in changes),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self.audit if a.workspace_id == workspace_id]


change_governance_service = ChangeGovernanceService()
