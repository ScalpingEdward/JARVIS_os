from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import AgentRecord, AgentRegistration, AuditRecord, MissionAction, MissionControlStatus, MissionCreate, MissionRecord
from .service import MissionControlError, mission_control_service

router = APIRouter(prefix="/v1/mission-control", tags=["mission-control"])


def _call(fn, *args):
    try:
        return fn(*args)
    except MissionControlError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status", response_model=MissionControlStatus)
def get_status() -> MissionControlStatus:
    return mission_control_service.status()


@router.post("/agents", response_model=AgentRecord, status_code=status.HTTP_201_CREATED)
def register_agent(payload: AgentRegistration) -> AgentRecord:
    return _call(mission_control_service.register_agent, payload)


@router.get("/agents", response_model=list[AgentRecord])
def list_agents(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AgentRecord]:
    return mission_control_service.list_agents(workspace_id)


@router.post("/agents/{agent_id}/heartbeat", response_model=AgentRecord)
def heartbeat(agent_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> AgentRecord:
    return _call(mission_control_service.heartbeat, agent_id, workspace_id)


@router.post("/missions", response_model=MissionRecord, status_code=status.HTTP_201_CREATED)
def create_mission(payload: MissionCreate) -> MissionRecord:
    return _call(mission_control_service.create_mission, payload)


@router.get("/missions", response_model=list[MissionRecord])
def list_missions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[MissionRecord]:
    return mission_control_service.list_missions(workspace_id)


@router.get("/missions/{mission_id}", response_model=MissionRecord)
def get_mission(mission_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> MissionRecord:
    return _call(mission_control_service.get_mission, mission_id, workspace_id)


@router.post("/missions/{mission_id}/plan", response_model=MissionRecord)
def plan_mission(mission_id: UUID, payload: MissionAction, workspace_id: str = Query(min_length=1, max_length=120)) -> MissionRecord:
    return _call(mission_control_service.plan, mission_id, workspace_id, payload)


@router.post("/missions/{mission_id}/approve", response_model=MissionRecord)
def approve_mission(mission_id: UUID, payload: MissionAction, workspace_id: str = Query(min_length=1, max_length=120)) -> MissionRecord:
    return _call(mission_control_service.approve, mission_id, workspace_id, payload)


@router.post("/missions/{mission_id}/start", response_model=MissionRecord)
def start_mission(mission_id: UUID, payload: MissionAction, workspace_id: str = Query(min_length=1, max_length=120)) -> MissionRecord:
    return _call(mission_control_service.start, mission_id, workspace_id, payload)


@router.post("/missions/{mission_id}/pause", response_model=MissionRecord)
def pause_mission(mission_id: UUID, payload: MissionAction, workspace_id: str = Query(min_length=1, max_length=120)) -> MissionRecord:
    return _call(mission_control_service.pause, mission_id, workspace_id, payload)


@router.post("/missions/{mission_id}/tasks/{task_key}/complete", response_model=MissionRecord)
def complete_task(mission_id: UUID, task_key: str, payload: MissionAction, workspace_id: str = Query(min_length=1, max_length=120)) -> MissionRecord:
    return _call(mission_control_service.complete_task, mission_id, task_key, workspace_id, payload)


@router.post("/missions/{mission_id}/archive", response_model=MissionRecord)
def archive_mission(mission_id: UUID, payload: MissionAction, workspace_id: str = Query(min_length=1, max_length=120)) -> MissionRecord:
    return _call(mission_control_service.archive, mission_id, workspace_id, payload)


@router.get("/audit", response_model=list[AuditRecord])
def get_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return mission_control_service.audit(workspace_id)
