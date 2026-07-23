from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas.model_risk_ai_assurance import (
    ModelRiskAssuranceAction,
    ModelRiskAssuranceCreate,
    ModelRiskAssuranceRecord,
)
from app.services.model_risk_ai_assurance import model_risk_ai_assurance_service


router = APIRouter(prefix="/v1/model-risk-ai-assurance", tags=["model-risk-ai-assurance"])


@router.get("/status")
def status() -> dict:
    return model_risk_ai_assurance_service.status()


@router.post("/records", response_model=ModelRiskAssuranceRecord, status_code=201)
def create_record(payload: ModelRiskAssuranceCreate) -> ModelRiskAssuranceRecord:
    try:
        return model_risk_ai_assurance_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[ModelRiskAssuranceRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[ModelRiskAssuranceRecord]:
    return model_risk_ai_assurance_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=ModelRiskAssuranceRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> ModelRiskAssuranceRecord:
    try:
        return model_risk_ai_assurance_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=ModelRiskAssuranceRecord)
def apply_action(
    record_id: str,
    payload: ModelRiskAssuranceAction,
    workspace_id: str = Header(alias="X-Workspace-ID"),
) -> ModelRiskAssuranceRecord:
    try:
        return model_risk_ai_assurance_service.act(
            workspace_id=workspace_id,
            record_id=record_id,
            action=payload.action,
            actor=payload.actor,
            operation_id=payload.operation_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1)) -> list[dict]:
    return [entry.__dict__ for entry in model_risk_ai_assurance_service.audit(workspace_id)]
