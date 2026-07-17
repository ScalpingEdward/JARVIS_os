from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalCreate, ApprovalRecord, ChangeCreate, ChangeGovernanceStatus,
    ChangeRecord, ChangeState, MetricsRecord, Mutation, ReleaseCreate, ReleaseRecord,
)
from .service import change_governance_service as service

router = APIRouter(prefix="/v1/change-governance", tags=["change-governance"])


@router.get("/status", response_model=ChangeGovernanceStatus)
def get_status() -> ChangeGovernanceStatus:
    return service.status()


@router.post("/changes", response_model=ChangeRecord, status_code=status.HTTP_201_CREATED)
def create_change(payload: ChangeCreate) -> ChangeRecord:
    try:
        return service.create_change(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/changes", response_model=list[ChangeRecord])
def list_changes(workspace_id: str = Query(min_length=1, max_length=120), state: ChangeState | None = None) -> list[ChangeRecord]:
    return service.list_changes(workspace_id, state)


@router.get("/changes/{change_id}", response_model=ChangeRecord)
def get_change(change_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    item = service.get_change(change_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Change not found")
    return item


def _set_change(change_id: UUID, workspace_id: str, payload: Mutation, state: ChangeState) -> ChangeRecord:
    try:
        item = service.set_state(change_id, workspace_id, payload, state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Owned change not found")
    return item


@router.post("/changes/{change_id}/review", response_model=ChangeRecord)
def submit_review(change_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    return _set_change(change_id, workspace_id, payload, ChangeState.REVIEW)


@router.post("/approvals", response_model=ApprovalRecord, status_code=status.HTTP_201_CREATED)
def record_approval(payload: ApprovalCreate) -> ApprovalRecord:
    try:
        return service.record_approval(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/releases", response_model=ReleaseRecord, status_code=status.HTTP_201_CREATED)
def create_release(payload: ReleaseCreate) -> ReleaseRecord:
    try:
        return service.create_release(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/releases", response_model=list[ReleaseRecord])
def list_releases(workspace_id: str = Query(min_length=1, max_length=120), change_id: UUID | None = None) -> list[ReleaseRecord]:
    return service.list_releases(workspace_id, change_id)


@router.post("/changes/{change_id}/schedule", response_model=ChangeRecord)
def schedule(change_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    return _set_change(change_id, workspace_id, payload, ChangeState.SCHEDULED)


@router.post("/changes/{change_id}/implemented", response_model=ChangeRecord)
def implemented(change_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    return _set_change(change_id, workspace_id, payload, ChangeState.IMPLEMENTED)


@router.post("/changes/{change_id}/verified", response_model=ChangeRecord)
def verified(change_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    return _set_change(change_id, workspace_id, payload, ChangeState.VERIFIED)


@router.post("/changes/{change_id}/rollback", response_model=ChangeRecord)
def rollback(change_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    return _set_change(change_id, workspace_id, payload, ChangeState.ROLLED_BACK)


@router.post("/changes/{change_id}/close", response_model=ChangeRecord)
def close(change_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    return _set_change(change_id, workspace_id, payload, ChangeState.CLOSED)


@router.post("/changes/{change_id}/cancel", response_model=ChangeRecord)
def cancel(change_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ChangeRecord:
    return _set_change(change_id, workspace_id, payload, ChangeState.CANCELLED)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
