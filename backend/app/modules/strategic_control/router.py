from fastapi import APIRouter, Header, HTTPException

from .models import AuditEvent, MissionActionRequest, StrategicMission, StrategicMissionCreate
from .service import StrategicControlError, service

router = APIRouter(prefix="/v1/strategic-control", tags=["PHOENIX v21.40 Strategic Control"])


@router.get("/status")
def status() -> dict[str, str]:
    return {"module": "strategic-control", "version": "21.40", "status": "ready"}


@router.post("/missions", response_model=StrategicMission)
def create_mission(payload: StrategicMissionCreate) -> StrategicMission:
    try:
        return service.create(payload)
    except StrategicControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/missions", response_model=list[StrategicMission])
def list_missions(x_workspace_id: str = Header(...)) -> list[StrategicMission]:
    return service.list(x_workspace_id)


@router.get("/missions/{record_id}", response_model=StrategicMission)
def get_mission(record_id: str, x_workspace_id: str = Header(...)) -> StrategicMission:
    try:
        return service.get(record_id, x_workspace_id)
    except StrategicControlError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/missions/{record_id}/actions", response_model=StrategicMission)
def act_on_mission(record_id: str, request: MissionActionRequest, x_workspace_id: str = Header(...)) -> StrategicMission:
    try:
        return service.act(record_id, x_workspace_id, request)
    except StrategicControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/audit", response_model=list[AuditEvent])
def audit(x_workspace_id: str = Header(...)) -> list[AuditEvent]:
    return service.audit(x_workspace_id)
