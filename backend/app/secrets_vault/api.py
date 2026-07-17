from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord, LeaseCreate, LeaseDecision, LeaseRecord, RotationPlanCreate,
    RotationPlanRecord, RotationState, SecretMutation, SecretReferenceCreate,
    SecretReferenceRecord, SecretState, VaultStatus,
)
from .service import secrets_vault_service


router = APIRouter(prefix="/v1/secrets-vault", tags=["secrets-vault"])


@router.get("/status", response_model=VaultStatus)
def get_status() -> VaultStatus:
    return secrets_vault_service.status()


@router.post("/secrets", response_model=SecretReferenceRecord, status_code=status.HTTP_201_CREATED)
def create_secret(payload: SecretReferenceCreate) -> SecretReferenceRecord:
    try:
        return secrets_vault_service.create_secret(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/secrets", response_model=list[SecretReferenceRecord])
def list_secrets(workspace_id: str = Query(min_length=1, max_length=120)) -> list[SecretReferenceRecord]:
    return secrets_vault_service.list_secrets(workspace_id)


@router.get("/secrets/{secret_id}", response_model=SecretReferenceRecord)
def get_secret(secret_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> SecretReferenceRecord:
    item = secrets_vault_service.get_secret(secret_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Secret reference not found")
    return item


def _set_secret(secret_id: UUID, workspace_id: str, payload: SecretMutation, state: SecretState) -> SecretReferenceRecord:
    item = secrets_vault_service.set_secret_state(secret_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned secret reference not found")
    return item


@router.post("/secrets/{secret_id}/suspend", response_model=SecretReferenceRecord)
def suspend_secret(secret_id: UUID, payload: SecretMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> SecretReferenceRecord:
    return _set_secret(secret_id, workspace_id, payload, SecretState.SUSPENDED)


@router.post("/secrets/{secret_id}/activate", response_model=SecretReferenceRecord)
def activate_secret(secret_id: UUID, payload: SecretMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> SecretReferenceRecord:
    return _set_secret(secret_id, workspace_id, payload, SecretState.ACTIVE)


@router.post("/secrets/{secret_id}/revoke", response_model=SecretReferenceRecord)
def revoke_secret(secret_id: UUID, payload: SecretMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> SecretReferenceRecord:
    return _set_secret(secret_id, workspace_id, payload, SecretState.REVOKED)


@router.post("/leases", response_model=LeaseRecord, status_code=status.HTTP_201_CREATED)
def create_lease(payload: LeaseCreate) -> LeaseRecord:
    try:
        return secrets_vault_service.create_lease(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/leases", response_model=list[LeaseRecord])
def list_leases(workspace_id: str = Query(min_length=1, max_length=120)) -> list[LeaseRecord]:
    return secrets_vault_service.list_leases(workspace_id)


@router.post("/leases/{lease_id}/decision", response_model=LeaseRecord)
def decide_lease(lease_id: UUID, payload: LeaseDecision, workspace_id: str = Query(min_length=1, max_length=120)) -> LeaseRecord:
    item = secrets_vault_service.decide_lease(lease_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Pending owned lease not found")
    return item


@router.post("/leases/{lease_id}/revoke", response_model=LeaseRecord)
def revoke_lease(lease_id: UUID, payload: SecretMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> LeaseRecord:
    item = secrets_vault_service.revoke_lease(lease_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Revocable owned lease not found")
    return item


@router.post("/rotations", response_model=RotationPlanRecord, status_code=status.HTTP_201_CREATED)
def create_rotation(payload: RotationPlanCreate) -> RotationPlanRecord:
    try:
        return secrets_vault_service.create_rotation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/rotations", response_model=list[RotationPlanRecord])
def list_rotations(workspace_id: str = Query(min_length=1, max_length=120)) -> list[RotationPlanRecord]:
    return secrets_vault_service.list_rotations(workspace_id)


def _set_rotation(rotation_id: UUID, workspace_id: str, payload: SecretMutation, state: RotationState) -> RotationPlanRecord:
    item = secrets_vault_service.set_rotation_state(rotation_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned rotation plan not found")
    return item


@router.post("/rotations/{rotation_id}/approve", response_model=RotationPlanRecord)
def approve_rotation(rotation_id: UUID, payload: SecretMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RotationPlanRecord:
    return _set_rotation(rotation_id, workspace_id, payload, RotationState.APPROVED)


@router.post("/rotations/{rotation_id}/complete", response_model=RotationPlanRecord)
def complete_rotation(rotation_id: UUID, payload: SecretMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RotationPlanRecord:
    return _set_rotation(rotation_id, workspace_id, payload, RotationState.COMPLETED)


@router.post("/rotations/{rotation_id}/cancel", response_model=RotationPlanRecord)
def cancel_rotation(rotation_id: UUID, payload: SecretMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RotationPlanRecord:
    return _set_rotation(rotation_id, workspace_id, payload, RotationState.CANCELLED)


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return secrets_vault_service.list_audit(workspace_id)
