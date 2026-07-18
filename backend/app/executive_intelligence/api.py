from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, BriefingCreate, BriefingListResponse, ExecutiveBriefing, IntelligenceStatus
from .service import executive_intelligence_service

router = APIRouter(tags=["executive-intelligence"])


@router.get("/v1/executive-intelligence/status", response_model=IntelligenceStatus)
def intelligence_status(workspace_id: str = Query(min_length=1, max_length=100)) -> IntelligenceStatus:
    return executive_intelligence_service.status(workspace_id)


@router.post("/v1/executive-intelligence/briefings", response_model=ExecutiveBriefing, status_code=status.HTTP_201_CREATED)
def create_briefing(payload: BriefingCreate) -> ExecutiveBriefing:
    try:
        return executive_intelligence_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-intelligence/briefings", response_model=BriefingListResponse)
def list_briefings(workspace_id: str = Query(min_length=1, max_length=100)) -> BriefingListResponse:
    items = executive_intelligence_service.list_briefings(workspace_id)
    return BriefingListResponse(items=items, count=len(items))


@router.get("/v1/executive-intelligence/briefings/{briefing_id}", response_model=ExecutiveBriefing)
def get_briefing(briefing_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> ExecutiveBriefing:
    record = executive_intelligence_service.get(briefing_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Executive briefing not found")
    return record


@router.post("/v1/executive-intelligence/briefings/{briefing_id}/analyze", response_model=ExecutiveBriefing)
def analyze_briefing(briefing_id: UUID, workspace_id: str = Query(min_length=1, max_length=100), actor_id: str = Query(min_length=1, max_length=100)) -> ExecutiveBriefing:
    try:
        return executive_intelligence_service.analyze(briefing_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-intelligence/audit", response_model=list[AuditRecord])
def intelligence_audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_intelligence_service.audit_records(workspace_id)
