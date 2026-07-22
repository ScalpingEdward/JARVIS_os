from fastapi import APIRouter, HTTPException, Query

from .models import AuditEvent, OptimizerAction, OptimizerCreate, OptimizerRecord
from .service import OptimizerError, SelfLearningPerformanceOptimizerService

router = APIRouter(
    prefix="/v1/performance-optimizer",
    tags=["PHOENIX v21.20 Self-Learning Performance Optimizer"],
)
service = SelfLearningPerformanceOptimizerService()


@router.get("/status")
def status() -> dict:
    return {
        "module": "PHOENIX v21.20 Self-Learning Performance Optimizer",
        "status": "operational",
        "live_strategy_mutation": False,
        "human_approval_required": True,
    }


@router.post("/records", response_model=OptimizerRecord)
def create_record(payload: OptimizerCreate) -> OptimizerRecord:
    try:
        return service.create(payload)
    except OptimizerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/records", response_model=list[OptimizerRecord])
def list_records(workspace_id: str = Query(..., min_length=1)) -> list[OptimizerRecord]:
    return service.list(workspace_id)


@router.get("/records/{record_id}", response_model=OptimizerRecord)
def get_record(record_id: str, workspace_id: str = Query(..., min_length=1)) -> OptimizerRecord:
    try:
        return service.get(workspace_id, record_id)
    except OptimizerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/records/{record_id}/actions", response_model=OptimizerRecord)
def apply_action(
    record_id: str,
    payload: OptimizerAction,
    workspace_id: str = Query(..., min_length=1),
) -> OptimizerRecord:
    try:
        return service.act(workspace_id, record_id, payload)
    except OptimizerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(..., min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
