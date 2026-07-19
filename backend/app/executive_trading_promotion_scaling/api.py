from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, PromotionAssessment, PromotionInput, PromotionListResponse, PromotionStatusResponse
from .service import executive_trading_promotion_scaling_service

router = APIRouter(tags=["executive-trading-promotion-scaling"])


@router.get("/v1/executive-trading-promotion-scaling/status", response_model=PromotionStatusResponse)
def promotion_status(workspace_id: str = Query(min_length=1, max_length=100)) -> PromotionStatusResponse:
    return executive_trading_promotion_scaling_service.status(workspace_id)


@router.post("/v1/executive-trading-promotion-scaling/assessments", response_model=PromotionAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: PromotionInput) -> PromotionAssessment:
    try:
        return executive_trading_promotion_scaling_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-trading-promotion-scaling/assessments", response_model=PromotionListResponse)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> PromotionListResponse:
    items = executive_trading_promotion_scaling_service.list_assessments(workspace_id)
    return PromotionListResponse(items=items, count=len(items))


@router.get("/v1/executive-trading-promotion-scaling/assessments/{assessment_id}", response_model=PromotionAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> PromotionAssessment:
    item = executive_trading_promotion_scaling_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Trading promotion assessment not found")
    return item


@router.get("/v1/executive-trading-promotion-scaling/audit", response_model=list[AuditRecord])
def promotion_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_trading_promotion_scaling_service.audit_records(workspace_id)
