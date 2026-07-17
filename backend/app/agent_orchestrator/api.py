from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AgentRecord,
    AgentRegister,
    OrchestratorStatus,
    TaskApproval,
    TaskComplete,
    TaskCreate,
    TaskRecord,
    TaskState,
)
from .service import agent_orchestrator_service


router = APIRouter(prefix="/v1/agent-orchestrator", tags=["agent-orchestrator"])


@router.get("/status", response_model=OrchestratorStatus)
def orchestrator_status() -> OrchestratorStatus:
    return agent_orchestrator_service.status()


@router.post("/agents", response_model=AgentRecord, status_code=status.HTTP_201_CREATED)
def register_agent(payload: AgentRegister) -> AgentRecord:
    return agent_orchestrator_service.register_agent(payload)


@router.get("/agents", response_model=list[AgentRecord])
def list_agents() -> list[AgentRecord]:
    return agent_orchestrator_service.list_agents()


@router.get("/agents/{agent_id}", response_model=AgentRecord)
def get_agent(agent_id: UUID) -> AgentRecord:
    agent = agent_orchestrator_service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/agents/{agent_id}/heartbeat", response_model=AgentRecord)
def heartbeat(agent_id: UUID) -> AgentRecord:
    agent = agent_orchestrator_service.heartbeat(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/tasks", response_model=TaskRecord, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> TaskRecord:
    return agent_orchestrator_service.create_task(payload)


@router.get("/tasks", response_model=list[TaskRecord])
def list_tasks(state: TaskState | None = Query(default=None)) -> list[TaskRecord]:
    return agent_orchestrator_service.list_tasks(state)


@router.get("/tasks/{task_id}", response_model=TaskRecord)
def get_task(task_id: UUID) -> TaskRecord:
    task = agent_orchestrator_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/approval", response_model=TaskRecord)
def approve_task(task_id: UUID, payload: TaskApproval) -> TaskRecord:
    task = agent_orchestrator_service.approve_task(task_id, payload)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/dispatch", response_model=TaskRecord | None)
def dispatch_next_task() -> TaskRecord | None:
    return agent_orchestrator_service.dispatch_next()


@router.post("/tasks/{task_id}/complete", response_model=TaskRecord)
def complete_task(task_id: UUID, payload: TaskComplete) -> TaskRecord:
    task = agent_orchestrator_service.complete_task(task_id, payload)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=TaskRecord)
def cancel_task(task_id: UUID) -> TaskRecord:
    task = agent_orchestrator_service.cancel_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
