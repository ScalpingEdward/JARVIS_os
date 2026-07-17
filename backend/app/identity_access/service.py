from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AccessCheckRequest, AccessDecision, AssignmentState, AuditRecord,
    DelegationCreate, DelegationRecord, DelegationState, IdentityAccessStatus,
    IdentityCreate, IdentityMutation, IdentityRecord, IdentityState,
    RoleAssignmentCreate, RoleAssignmentRecord, RoleCreate, RoleRecord,
)


class IdentityAccessService:
    def __init__(self) -> None:
        self.identities: dict[UUID, IdentityRecord] = {}
        self.roles: dict[UUID, RoleRecord] = {}
        self.assignments: dict[UUID, RoleAssignmentRecord] = {}
        self.delegations: dict[UUID, DelegationRecord] = {}
        self.decisions: list[AccessDecision] = []
        self.audit: list[AuditRecord] = []

    def status(self) -> IdentityAccessStatus:
        return IdentityAccessStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, subject_id: str, **details: object) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, subject_id=subject_id, details=details))

    def create_identity(self, payload: IdentityCreate) -> IdentityRecord:
        if any(i.workspace_id == payload.workspace_id and i.identity_key == payload.identity_key for i in self.identities.values()):
            raise ValueError("identity key already exists in workspace")
        record = IdentityRecord(**payload.model_dump(exclude={"human_approved", "capture_credentials", "external_identity_sync"}))
        self.identities[record.id] = record
        self._audit(record.workspace_id, "identity.created", record.owner_id, str(record.id), identity_key=record.identity_key)
        return record

    def list_identities(self, workspace_id: str) -> list[IdentityRecord]:
        return [i for i in self.identities.values() if i.workspace_id == workspace_id]

    def get_identity(self, identity_id: UUID, workspace_id: str) -> IdentityRecord | None:
        item = self.identities.get(identity_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_identity_state(self, identity_id: UUID, workspace_id: str, payload: IdentityMutation, state: IdentityState) -> IdentityRecord | None:
        item = self.get_identity(identity_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"identity.{state.value}", payload.requester_id, str(identity_id), reason=payload.reason)
        return item

    def create_role(self, payload: RoleCreate) -> RoleRecord:
        if any(r.workspace_id == payload.workspace_id and r.role_key == payload.role_key for r in self.roles.values()):
            raise ValueError("role key already exists in workspace")
        record = RoleRecord(**payload.model_dump())
        self.roles[record.id] = record
        self._audit(record.workspace_id, "role.created", record.owner_id, str(record.id), role_key=record.role_key)
        return record

    def list_roles(self, workspace_id: str) -> list[RoleRecord]:
        return [r for r in self.roles.values() if r.workspace_id == workspace_id]

    def get_role(self, role_id: UUID, workspace_id: str) -> RoleRecord | None:
        item = self.roles.get(role_id)
        return item if item and item.workspace_id == workspace_id else None

    def create_assignment(self, payload: RoleAssignmentCreate) -> RoleAssignmentRecord:
        identity = self.get_identity(payload.identity_id, payload.workspace_id)
        role = self.get_role(payload.role_id, payload.workspace_id)
        if identity is None or role is None:
            raise ValueError("identity and role must belong to the same workspace")
        if identity.state != IdentityState.ACTIVE or not role.active:
            raise ValueError("identity and role must be active")
        if any(a.workspace_id == payload.workspace_id and a.identity_id == payload.identity_id and a.role_id == payload.role_id and a.state == AssignmentState.ACTIVE for a in self.assignments.values()):
            raise ValueError("active assignment already exists")
        record = RoleAssignmentRecord(
            workspace_id=payload.workspace_id, owner_id=payload.owner_id,
            identity_id=payload.identity_id, role_id=payload.role_id,
            reason=payload.reason, expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.valid_minutes),
        )
        self.assignments[record.id] = record
        self._audit(record.workspace_id, "assignment.created", payload.owner_id, str(record.id))
        return record

    def list_assignments(self, workspace_id: str, identity_id: UUID | None = None) -> list[RoleAssignmentRecord]:
        self._expire()
        return [a for a in self.assignments.values() if a.workspace_id == workspace_id and (identity_id is None or a.identity_id == identity_id)]

    def revoke_assignment(self, assignment_id: UUID, workspace_id: str, payload: IdentityMutation) -> RoleAssignmentRecord | None:
        item = self.assignments.get(assignment_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = AssignmentState.REVOKED
        item.revoked_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "assignment.revoked", payload.requester_id, str(assignment_id), reason=payload.reason)
        return item

    def create_delegation(self, payload: DelegationCreate) -> DelegationRecord:
        delegator = self.get_identity(payload.delegator_identity_id, payload.workspace_id)
        delegate = self.get_identity(payload.delegate_identity_id, payload.workspace_id)
        role = self.get_role(payload.role_id, payload.workspace_id)
        if not delegator or not delegate or not role:
            raise ValueError("delegator, delegate and role must belong to the workspace")
        self._expire()
        owns_role = any(a.workspace_id == payload.workspace_id and a.identity_id == delegator.id and a.role_id == role.id and a.state == AssignmentState.ACTIVE for a in self.assignments.values())
        if not owns_role:
            raise ValueError("delegator does not hold the role")
        record = DelegationRecord(
            workspace_id=payload.workspace_id, owner_id=payload.owner_id,
            delegator_identity_id=payload.delegator_identity_id,
            delegate_identity_id=payload.delegate_identity_id, role_id=payload.role_id,
            reason=payload.reason,
            state=DelegationState.PENDING if payload.requires_acceptance else DelegationState.ACTIVE,
            activated_at=None if payload.requires_acceptance else datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.valid_minutes),
        )
        self.delegations[record.id] = record
        self._audit(record.workspace_id, "delegation.created", payload.owner_id, str(record.id))
        return record

    def list_delegations(self, workspace_id: str) -> list[DelegationRecord]:
        self._expire()
        return [d for d in self.delegations.values() if d.workspace_id == workspace_id]

    def accept_delegation(self, delegation_id: UUID, workspace_id: str, payload: IdentityMutation) -> DelegationRecord | None:
        item = self.delegations.get(delegation_id)
        if item is None or item.workspace_id != workspace_id or item.state != DelegationState.PENDING:
            return None
        delegate = self.get_identity(item.delegate_identity_id, workspace_id)
        if delegate is None or delegate.owner_id != payload.requester_id:
            return None
        item.state = DelegationState.ACTIVE
        item.activated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "delegation.accepted", payload.requester_id, str(delegation_id))
        return item

    def revoke_delegation(self, delegation_id: UUID, workspace_id: str, payload: IdentityMutation) -> DelegationRecord | None:
        item = self.delegations.get(delegation_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = DelegationState.REVOKED
        item.revoked_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "delegation.revoked", payload.requester_id, str(delegation_id), reason=payload.reason)
        return item

    def check_access(self, payload: AccessCheckRequest) -> AccessDecision:
        self._expire()
        identity = self.get_identity(payload.identity_id, payload.workspace_id)
        matched: list[UUID] = []
        allowed = False
        reason = "identity not active or no matching permission"
        if identity and identity.state == IdentityState.ACTIVE:
            role_ids = {a.role_id for a in self.assignments.values() if a.workspace_id == payload.workspace_id and a.identity_id == identity.id and a.state == AssignmentState.ACTIVE}
            role_ids.update(d.role_id for d in self.delegations.values() if d.workspace_id == payload.workspace_id and d.delegate_identity_id == identity.id and d.state == DelegationState.ACTIVE)
            for role_id in role_ids:
                role = self.get_role(role_id, payload.workspace_id)
                if role and role.active and any(p.resource == payload.resource and payload.action in p.actions for p in role.permissions):
                    matched.append(role.id)
            if matched:
                allowed, reason = True, "matching least-privilege role permission"
        decision = AccessDecision(workspace_id=payload.workspace_id, identity_id=payload.identity_id, resource=payload.resource, action=payload.action, allowed=allowed, matched_role_ids=matched, reason=reason)
        self.decisions.append(decision)
        self._audit(payload.workspace_id, "access.checked", str(payload.identity_id), str(decision.id), allowed=allowed)
        return decision

    def list_decisions(self, workspace_id: str) -> list[AccessDecision]:
        return [d for d in self.decisions if d.workspace_id == workspace_id]

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self.audit if a.workspace_id == workspace_id]

    def _expire(self) -> None:
        now = datetime.now(timezone.utc)
        for assignment in self.assignments.values():
            if assignment.state == AssignmentState.ACTIVE and assignment.expires_at <= now:
                assignment.state = AssignmentState.EXPIRED
        for delegation in self.delegations.values():
            if delegation.state in {DelegationState.PENDING, DelegationState.ACTIVE} and delegation.expires_at <= now:
                delegation.state = DelegationState.EXPIRED


identity_access_service = IdentityAccessService()
