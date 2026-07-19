from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, MonitoringAssessment, MonitoringInput, MonitoringListResponse, MonitoringStatusResponse
from .service import executive_trading_post_release_drift_service

router = APIRouter(tags=["executive-trading-post-release-drift"])


@router.get("/v1/executive-trading-post-release-drift/status", response_model=MonitoringStatusResponse)
def monitoring_status(workspace_id: str = Query(min_length=1, max_length=100)) -> MonitoringStatusResponse:
    return executive_trading_post_release_drift_service.status(workspace_id)


@router.post("/v1/executive-trading-post-release-drift/assessments", response_model=MonitoringAssessment, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: MonitoringInput) -> MonitoringAssessment:
    try:
        return executive_trading_post_release_drift_service.assess(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-trading-post-release-drift/assessments", response_model=MonitoringListResponse)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> MonitoringListResponse:
    items = executive_trading_post_release_drift_service.list_assessments(workspace_id)
    return MonitoringListResponse(items=items, count=len(items))


@router.get("/v1/executive-trading-post-release-drift/assessments/{assessment_id}", response_model=MonitoringAssessment)
def get_assessment(assessment_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> MonitoringAssessment:
    item = executive_trading_post_release_drift_service.get(assessment_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Post-release drift assessment not found")
    return item


@router.get("/v1/executive-trading-post-release-drift/audit", response_model=list[AuditRecord])
def monitoring_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_trading_post_release_drift_service.audit_records(workspace_id)
