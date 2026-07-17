from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ActionState, ConsentCreate, ConsentRecord, DataAssetCreate, DataAssetRecord,
    GovernanceActionCreate, GovernanceActionRecord, GovernanceStatus,
    HoldState, LegalHoldCreate, LegalHoldRecord, Mutation, PolicyState,
    PrivacyRequestCreate, PrivacyRequestRecord, RetentionPolicyCreate,
    RetentionPolicyRecord,
)
from .service import data_governance_service


router = APIRouter(prefix="/v1/data-governance", tags=["data-governance"])


@router.get("/status", response_model=GovernanceStatus)
def get_status() -> GovernanceStatus:
    return data_governance_service.status()


@router.post("/policies", response_model=RetentionPolicyRecord, status_code=status.HTTP_201_CREATED)
def create_policy(payload: RetentionPolicyCreate) -> RetentionPolicyRecord:
    try:
        return data_governance_service.create_policy(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/policies", response_model=list[RetentionPolicyRecord])
def list_policies(workspace_id: str = Query(min_length=1, max_length=120)) -> list[RetentionPolicyRecord]:
    return data_governance_service.list_policies(workspace_id)


def _set_policy(policy_id: UUID, workspace_id: str, payload: Mutation, state: PolicyState) -> RetentionPolicyRecord:
    item = data_governance_service.set_policy_state(policy_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned policy not found")
    return item


@router.post("/policies/{policy_id}/activate", response_model=RetentionPolicyRecord)
def activate_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RetentionPolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.ACTIVE)


@router.post("/policies/{policy_id}/retire", response_model=RetentionPolicyRecord)
def retire_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> RetentionPolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.RETIRED)


@router.post("/assets", response_model=DataAssetRecord, status_code=status.HTTP_201_CREATED)
def create_asset(payload: DataAssetCreate) -> DataAssetRecord:
    try:
        return data_governance_service.create_asset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assets", response_model=list[DataAssetRecord])
def list_assets(workspace_id: str = Query(min_length=1, max_length=120)) -> list[DataAssetRecord]:
    return data_governance_service.list_assets(workspace_id)


@router.post("/holds", response_model=LegalHoldRecord, status_code=status.HTTP_201_CREATED)
def create_hold(payload: LegalHoldCreate) -> LegalHoldRecord:
    try:
        return data_governance_service.create_hold(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/holds", response_model=list[LegalHoldRecord])
def list_holds(workspace_id: str = Query(min_length=1, max_length=120)) -> list[LegalHoldRecord]:
    return data_governance_service.list_holds(workspace_id)


@router.post("/holds/{hold_id}/release", response_model=LegalHoldRecord)
def release_hold(hold_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> LegalHoldRecord:
    item = data_governance_service.release_hold(hold_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Releasable owned hold not found")
    return item


@router.post("/consents", response_model=ConsentRecord, status_code=status.HTTP_201_CREATED)
def create_consent(payload: ConsentCreate) -> ConsentRecord:
    return data_governance_service.create_consent(payload)


@router.get("/consents", response_model=list[ConsentRecord])
def list_consents(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ConsentRecord]:
    return data_governance_service.list_consents(workspace_id)


@router.post("/consents/{consent_id}/withdraw", response_model=ConsentRecord)
def withdraw_consent(consent_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ConsentRecord:
    item = data_governance_service.withdraw_consent(consent_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Withdrawable owned consent not found")
    return item


@router.post("/privacy-requests", response_model=PrivacyRequestRecord, status_code=status.HTTP_201_CREATED)
def create_privacy_request(payload: PrivacyRequestCreate) -> PrivacyRequestRecord:
    return data_governance_service.create_request(payload)


@router.get("/privacy-requests", response_model=list[PrivacyRequestRecord])
def list_privacy_requests(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PrivacyRequestRecord]:
    return data_governance_service.list_requests(workspace_id)


@router.post("/privacy-requests/{request_id}/approve", response_model=PrivacyRequestRecord)
def approve_privacy_request(request_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PrivacyRequestRecord:
    item = data_governance_service.decide_request(request_id, workspace_id, payload, True)
    if item is None:
        raise HTTPException(status_code=404, detail="Pending owned request not found")
    return item


@router.post("/privacy-requests/{request_id}/reject", response_model=PrivacyRequestRecord)
def reject_privacy_request(request_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PrivacyRequestRecord:
    item = data_governance_service.decide_request(request_id, workspace_id, payload, False)
    if item is None:
        raise HTTPException(status_code=404, detail="Pending owned request not found")
    return item


@router.post("/actions", response_model=GovernanceActionRecord, status_code=status.HTTP_201_CREATED)
def create_action(payload: GovernanceActionCreate) -> GovernanceActionRecord:
    try:
        return data_governance_service.create_action(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/actions", response_model=list[GovernanceActionRecord])
def list_actions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[GovernanceActionRecord]:
    return data_governance_service.list_actions(workspace_id)


def _set_action(action_id: UUID, workspace_id: str, payload: Mutation, state: ActionState) -> GovernanceActionRecord:
    item = data_governance_service.set_action_state(action_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned unblocked action not found")
    return item


@router.post("/actions/{action_id}/approve", response_model=GovernanceActionRecord)
def approve_action(action_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> GovernanceActionRecord:
    return _set_action(action_id, workspace_id, payload, ActionState.APPROVED)


@router.post("/actions/{action_id}/complete", response_model=GovernanceActionRecord)
def complete_action(action_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> GovernanceActionRecord:
    return _set_action(action_id, workspace_id, payload, ActionState.COMPLETED)


@router.post("/actions/{action_id}/cancel", response_model=GovernanceActionRecord)
def cancel_action(action_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> GovernanceActionRecord:
    return _set_action(action_id, workspace_id, payload, ActionState.CANCELLED)


@router.get("/audit")
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return data_governance_service.list_audit(workspace_id)
