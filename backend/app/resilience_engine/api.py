from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AdmissionRecord, AdmissionRequest, MetricsRecord, Mutation, OutcomeRecord,
    OutcomeRequest, PolicyCreate, PolicyRecord, PolicyState, ResilienceStatus,
)
from .service import resilience_service as service

router = APIRouter(prefix="/v1/resilience", tags=["resilience"])


@router.get("/status", response_model=ResilienceStatus)
def get_status() -> ResilienceStatus:
    return service.status()


@router.post("/policies", response_model=PolicyRecord, status_code=status.HTTP_201_CREATED)
def create_policy(payload: PolicyCreate) -> PolicyRecord:
    try:
        return service.create_policy(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/policies", response_model=list[PolicyRecord])
def list_policies(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PolicyRecord]:
    return service.list_policies(workspace_id)


@router.get("/policies/{policy_id}", response_model=PolicyRecord)
def get_policy(policy_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    item = service.get_policy(policy_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Resilience policy not found")
    return item


def _set_policy(policy_id: UUID, workspace_id: str, payload: Mutation, state: PolicyState) -> PolicyRecord:
    item = service.set_policy_state(policy_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned resilience policy not found")
    return item


@router.post("/policies/{policy_id}/activate", response_model=PolicyRecord)
def activate_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.ACTIVE)


@router.post("/policies/{policy_id}/pause", response_model=PolicyRecord)
def pause_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.PAUSED)


@router.post("/policies/{policy_id}/retire", response_model=PolicyRecord)
def retire_policy(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.RETIRED)


@router.post("/policies/{policy_id}/reset-circuit", response_model=PolicyRecord)
def reset_circuit(policy_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    item = service.reset_circuit(policy_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned resilience policy not found")
    return item


@router.post("/admissions", response_model=AdmissionRecord, status_code=status.HTTP_201_CREATED)
def evaluate_admission(payload: AdmissionRequest) -> AdmissionRecord:
    try:
        return service.evaluate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/outcomes", response_model=OutcomeRecord, status_code=status.HTTP_201_CREATED)
def record_outcome(payload: OutcomeRequest) -> OutcomeRecord:
    try:
        return service.record_outcome(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
