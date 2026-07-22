from fastapi import APIRouter, HTTPException, Query

from .models import AuditEvent, OrchestrationAction, OrchestrationCreate, OrchestrationRecord
from .service import GovernedOrchestrationService, OrchestrationError

router = APIRouter(prefix="/v1/governed-orchestration", tags=["PHOENIX v21.22 Governed Orchestration"])
service = GovernedOrchestrationService()


@router.get("/status")
def status() -> dict:
    return {
        "module": "PHOENIX v21.22 Governed Orchestration Engine",
        "status": "operational",
        "live_execution": False,
        "human_approval_required": True,
    }


@router.post("/workflows", response_model=OrchestrationRecord)
def create_workflow(payload: OrchestrationCreate) -> OrchestrationRecord:
    try:
        return service.create(payload)
    except OrchestrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/workflows", response_model=list[OrchestrationRecord])
def list_workflows(workspace_id: str = Query(..., min_length=1)) -> list[OrchestrationRecord]:
    return service.list(workspace_id)


@router.get("/workflows/{record_id}", response_model=OrchestrationRecord)
def get_workflow(record_id: str, workspace_id: str = Query(..., min_length=1)) -> OrchestrationRecord:
    try:
        return service.get(workspace_id, record_id)
    except OrchestrationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/workflows/{record_id}/actions", response_model=OrchestrationRecord)
def apply_action(
    record_id: str,
    payload: OrchestrationAction,
    workspace_id: str = Query(..., min_length=1),
) -> OrchestrationRecord:
    try:
        return service.act(workspace_id, record_id, payload)
    except OrchestrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(..., min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
