from fastapi import APIRouter, HTTPException, Query

from app.schemas.agent_promotion_deployment_readiness import (
    AgentPromotionAction,
    AgentPromotionCreate,
    AgentPromotionRecord,
)
from app.services.agent_promotion_deployment_readiness import agent_promotion_deployment_readiness_service


router = APIRouter(prefix="/v1/agent-promotion-readiness", tags=["agent-promotion-readiness"])


@router.get("/status")
def status() -> dict:
    return agent_promotion_deployment_readiness_service.status()


@router.post("/records", response_model=AgentPromotionRecord)
def create_record(payload: AgentPromotionCreate) -> AgentPromotionRecord:
    try:
        return agent_promotion_deployment_readiness_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[AgentPromotionRecord])
def list_records(workspace_id: str = Query(min_length=1)) -> list[AgentPromotionRecord]:
    return agent_promotion_deployment_readiness_service.list(workspace_id)


@router.get("/records/{record_id}", response_model=AgentPromotionRecord)
def get_record(record_id: str, workspace_id: str = Query(min_length=1)) -> AgentPromotionRecord:
    try:
        return agent_promotion_deployment_readiness_service.get(workspace_id, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=AgentPromotionRecord)
def act(record_id: str, payload: AgentPromotionAction) -> AgentPromotionRecord:
    try:
        return agent_promotion_deployment_readiness_service.act(
            workspace_id=payload.workspace_id,
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
    return [entry.__dict__ for entry in agent_promotion_deployment_readiness_service.audit(workspace_id)]
