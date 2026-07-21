from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, BreakEvenAssessment, BreakEvenAssessmentCreate, BreakEvenListResponse, BreakEvenStatusResponse
from .service import executive_mt5_break_even_scale_out_service

router = APIRouter(tags=["executive-mt5-break-even-scale-out"])


@router.get("/v1/executive-mt5-break-even-scale-out/status", response_model=BreakEvenStatusResponse)
def module_status(workspace_id: str = Query(min_length=1, max_length=100)) -> BreakEvenStatusResponse:
    return executive_mt5_break_even_scale_out_service.status(workspace_id)


@router.post(
    "/v1/executive-mt5-break-even-scale-out/assessments",
    response_model=BreakEvenAssessment,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(payload: BreakEvenAssessmentCreate, actor_id: str = Query(min_length=1, max_length=100)) -> BreakEvenAssessment:
    try:
        return executive_mt5_break_even_scale_out_service.create(payload, actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-break-even-scale-out/assessments", response_model=BreakEvenListResponse)
def list_assessments(workspace_id: str = Query(min_length=1, max_length=100)) -> BreakEvenListResponse:
    items = executive_mt5_break_even_scale_out_service.list_records(workspace_id)
    return BreakEvenListResponse(items=items, count=len(items))


@router.get("/v1/executive-mt5-break-even-scale-out/assessments/{record_id}", response_model=BreakEvenAssessment)
def get_assessment(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)) -> BreakEvenAssessment:
    record = executive_mt5_break_even_scale_out_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Break-even assessment not found")
    return record


@router.post("/v1/executive-mt5-break-even-scale-out/assessments/{record_id}/execute", response_model=BreakEvenAssessment)
def execute_assessment(
    record_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=100),
    actor_id: str = Query(min_length=1, max_length=100),
) -> BreakEvenAssessment:
    try:
        return executive_mt5_break_even_scale_out_service.execute(record_id, workspace_id, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v1/executive-mt5-break-even-scale-out/audit", response_model=list[AuditRecord])
def audit(workspace_id: str = Query(min_length=1, max_length=100)) -> list[AuditRecord]:
    return executive_mt5_break_even_scale_out_service.audit_records(workspace_id)
