from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AuditRecord, ExecutionAnalysisCreate, ExecutionAnalysisRecord, StrategicExecutionStatus
from .service import strategic_execution_service

router = APIRouter(prefix="/v1/strategic-execution", tags=["strategic-execution-intelligence"])


@router.get("/status", response_model=StrategicExecutionStatus)
def execution_status(workspace_id: str = Query(min_length=1, max_length=120)) -> StrategicExecutionStatus:
    return strategic_execution_service.status(workspace_id)


@router.post("/analyses", response_model=ExecutionAnalysisRecord, status_code=status.HTTP_201_CREATED)
def create_execution_analysis(payload: ExecutionAnalysisCreate) -> ExecutionAnalysisRecord:
    try:
        return strategic_execution_service.create_analysis(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/analyses", response_model=list[ExecutionAnalysisRecord])
def list_execution_analyses(
    workspace_id: str = Query(min_length=1, max_length=120),
) -> list[ExecutionAnalysisRecord]:
    return strategic_execution_service.list_analyses(workspace_id)


@router.get("/analyses/{analysis_id}", response_model=ExecutionAnalysisRecord)
def get_execution_analysis(
    analysis_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> ExecutionAnalysisRecord:
    record = strategic_execution_service.get_analysis(workspace_id, analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="execution analysis not found")
    return record


@router.get("/audit", response_model=list[AuditRecord])
def execution_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return strategic_execution_service.audit(workspace_id)
