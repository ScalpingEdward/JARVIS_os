from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PolicyEngineStatusResponse, PolicyEvaluation, PolicyEvaluationCreate
from .service import executive_policy_engine_service

router = APIRouter(tags=["executive-policy-engine"])
BASE = "/v1/executive-policy-engine"


@router.get(f"{BASE}/status", response_model=PolicyEngineStatusResponse)
def policy_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PolicyEngineStatusResponse:
    return executive_policy_engine_service.status(workspace_id)


@router.post(f"{BASE}/evaluations", response_model=PolicyEvaluation, status_code=status.HTTP_201_CREATED)
def create_evaluation(payload: PolicyEvaluationCreate) -> PolicyEvaluation:
    try:
        return executive_policy_engine_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(f"{BASE}/evaluations", response_model=list[PolicyEvaluation])
def list_evaluations(workspace_id: str = Query(min_length=1, max_length=100)) -> list[PolicyEvaluation]:
    return executive_policy_engine_service.list_evaluations(workspace_id)


@router.get(f"{BASE}/evaluations/{{record_id}}", response_model=PolicyEvaluation)
def get_evaluation(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PolicyEvaluation:
    record = executive_policy_engine_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Policy evaluation not found")
    return record


@router.get(f"{BASE}/policies", response_model=list[str])
def list_policies(workspace_id: str = Query(min_length=1, max_length=100)) -> list[str]:
    return executive_policy_engine_service.policies(workspace_id)


@router.get(f"{BASE}/audit", response_model=list[AuditRecord])
def policy_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_policy_engine_service.audit(workspace_id)
