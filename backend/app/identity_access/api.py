from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AccessCheckRequest, AccessDecision, AuditRecord, DelegationCreate,
    DelegationRecord, IdentityAccessStatus, IdentityCreate, IdentityMutation,
    IdentityRecord, IdentityState, RoleAssignmentCreate, RoleAssignmentRecord,
    RoleCreate, RoleRecord,
)
from .service import identity_access_service


router = APIRouter(prefix="/v1/identity-access", tags=["identity-access"])


@router.get("/status", response_model=IdentityAccessStatus)
def get_status() -> IdentityAccessStatus:
    return identity_access_service.status()


@router.post("/identities", response_model=IdentityRecord, status_code=status.HTTP_201_CREATED)
def create_identity(payload: IdentityCreate) -> IdentityRecord:
    try:
        return identity_access_service.create_identity(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/identities", response_model=list[IdentityRecord])
def list_identities(workspace_id: str = Query(min_length=1, max_length=120)) -> list[IdentityRecord]:
    return identity_access_service.list_identities(workspace_id)


@router.get("/identities/{identity_id}", response_model=IdentityRecord)
def get_identity(identity_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> IdentityRecord:
    item = identity_access_service.get_identity(identity_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Identity not found")
    return item


def _set_identity(identity_id: UUID, workspace_id: str, payload: IdentityMutation, state: IdentityState) -> IdentityRecord:
    item = identity_access_service.set_identity_state(identity_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned identity not found")
    return item


@router.post("/identities/{identity_id}/suspend", response_model=IdentityRecord)
def suspend_identity(identity_id: UUID, payload: IdentityMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IdentityRecord:
    return _set_identity(identity_id, workspace_id, payload, IdentityState.SUSPENDED)


@router.post("/identities/{identity_id}/activate", response_model=IdentityRecord)
def activate_identity(identity_id: UUID, payload: IdentityMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IdentityRecord:
    return _set_identity(identity_id, workspace_id, payload, IdentityState.ACTIVE)


@router.post("/identities/{identity_id}/revoke", response_model=IdentityRecord)
def revoke_identity(identity_id: UUID, payload: IdentityMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> IdentityRecord:
    return _set_identity(identity_id, workspace_id, payload, IdentityState.REVOKED)


@router.post("/roles", response_model=RoleRecord, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate) -> RoleRecord:
    try:
        return identity_access_service.create_role(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/roles", response_model=list[RoleRecord])
def list_roles(workspace_id: str = Query(min_length=1, max_length=120)) -> list[RoleRecord]:
    return identity_access_service.list_roles(workspace_id)


@router.post("/assignments", response_model=RoleAssignmentRecord, status_code=status.HTTP_201_CREATED)
def create_assignment(payload: RoleAssignmentCreate) -> RoleAssignmentRecord:
    try:
        return identity_access_service.create_assignment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assignments", response_model=list[RoleAssignmentRecord])
def list_assignments(workspace_id: str = Query(min_length=1, max_length=120), identity_id: UUID | None = None) -> list[RoleAssignmentRecord]:
    return identity_access_service.list_assignments(workspace_id, identity_id)


@router.post("/assignments/{assignment_id}/revoke", response_model=RoleAssignmentRecord)
def revoke_assignment(assignment_id: UUID, payload: IdentityMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RoleAssignmentRecord:
    item = identity_access_service.revoke_assignment(assignment_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Revocable owned assignment not found")
    return item


@router.post("/delegations", response_model=DelegationRecord, status_code=status.HTTP_201_CREATED)
def create_delegation(payload: DelegationCreate) -> DelegationRecord:
    try:
        return identity_access_service.create_delegation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/delegations", response_model=list[DelegationRecord])
def list_delegations(workspace_id: str = Query(min_length=1, max_length=120)) -> list[DelegationRecord]:
    return identity_access_service.list_delegations(workspace_id)


@router.post("/delegations/{delegation_id}/accept", response_model=DelegationRecord)
def accept_delegation(delegation_id: UUID, payload: IdentityMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> DelegationRecord:
    item = identity_access_service.accept_delegation(delegation_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Acceptable delegation not found")
    return item


@router.post("/delegations/{delegation_id}/revoke", response_model=DelegationRecord)
def revoke_delegation(delegation_id: UUID, payload: IdentityMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> DelegationRecord:
    item = identity_access_service.revoke_delegation(delegation_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Revocable owned delegation not found")
    return item


@router.post("/access/check", response_model=AccessDecision)
def check_access(payload: AccessCheckRequest) -> AccessDecision:
    return identity_access_service.check_access(payload)


@router.get("/access/decisions", response_model=list[AccessDecision])
def list_decisions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AccessDecision]:
    return identity_access_service.list_decisions(workspace_id)


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return identity_access_service.list_audit(workspace_id)
