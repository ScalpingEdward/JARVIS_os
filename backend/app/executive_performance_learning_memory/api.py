from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    PerformanceLearningAudit,
    PerformanceLearningCreate,
    PerformanceLearningExecuteRequest,
    PerformanceLearningRecord,
    PerformanceLearningStatus,
)
from .service import performance_learning_memory_service

router = APIRouter(tags=["executive-performance-learning-memory"])


@router.get("/v1/executive-performance-learning/status", response_model=PerformanceLearningStatus)
def performance_status(workspace_id: str = Query(min_length=1, max_length=100)):
    return performance_learning_memory_service.status(workspace_id)


@router.post("/v1/executive-performance-learning/records", response_model=PerformanceLearningRecord, status_code=status.HTTP_201_CREATED)
def create_performance_record(payload: PerformanceLearningCreate):
    try:
        return performance_learning_memory_service.create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-performance-learning/records", response_model=list[PerformanceLearningRecord])
def list_performance_records(workspace_id: str = Query(min_length=1, max_length=100)):
    return performance_learning_memory_service.list_records(workspace_id)


@router.get("/v1/executive-performance-learning/records/{record_id}", response_model=PerformanceLearningRecord)
def get_performance_record(record_id: UUID, workspace_id: str = Query(min_length=1, max_length=100)):
    record = performance_learning_memory_service.get(record_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="performance record not found")
    return record


@router.post("/v1/executive-performance-learning/records/{record_id}/execute", response_model=PerformanceLearningRecord)
def execute_performance_record(record_id: UUID, request: PerformanceLearningExecuteRequest, workspace_id: str = Query(min_length=1, max_length=100)):
    try:
        return performance_learning_memory_service.execute(record_id, workspace_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/v1/executive-performance-learning/audit", response_model=list[PerformanceLearningAudit])
def performance_audit(workspace_id: str = Query(min_length=1, max_length=100)):
    return performance_learning_memory_service.audit_records(workspace_id)
