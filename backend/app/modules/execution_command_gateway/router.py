from fastapi import APIRouter, HTTPException, Query

from .models import AuditEvent, CommandAction, ExecutionCommandCreate, ExecutionCommandRecord
from .service import ExecutionCommandGatewayService, GatewayError

router = APIRouter(prefix="/v1/execution-command-gateway", tags=["PHOENIX v21.23 Execution Command Gateway"])
service = ExecutionCommandGatewayService()


@router.get("/status")
def status() -> dict:
    return {
        "module": "PHOENIX v21.23 Execution Command Gateway",
        "status": "operational",
        "live_execution": False,
        "human_approval_required": True,
        "supported_adapters": ["mt5", "dxtrade", "ctrader", "fix", "rest"],
    }


@router.post("/commands", response_model=ExecutionCommandRecord)
def create_command(payload: ExecutionCommandCreate) -> ExecutionCommandRecord:
    try:
        return service.create(payload)
    except GatewayError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/commands", response_model=list[ExecutionCommandRecord])
def list_commands(workspace_id: str = Query(..., min_length=1)) -> list[ExecutionCommandRecord]:
    return service.list(workspace_id)


@router.get("/commands/{record_id}", response_model=ExecutionCommandRecord)
def get_command(record_id: str, workspace_id: str = Query(..., min_length=1)) -> ExecutionCommandRecord:
    try:
        return service.get(workspace_id, record_id)
    except GatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/commands/{record_id}/actions", response_model=ExecutionCommandRecord)
def apply_action(
    record_id: str,
    payload: CommandAction,
    workspace_id: str = Query(..., min_length=1),
) -> ExecutionCommandRecord:
    try:
        return service.act(workspace_id, record_id, payload)
    except GatewayError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(workspace_id: str = Query(..., min_length=1)) -> list[AuditEvent]:
    return service.audit(workspace_id)
