from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AgentCreate,
    AgentRecord,
    AgentState,
    CheckpointCreate,
    CheckpointRecord,
    FailureRequest,
    MemoryRecord,
    MemoryWrite,
    ProgressUpdate,
    TaskCreate,
    TaskEngineStatus,
    TaskEvent,
    TaskMutation,
    TaskRecord,
    TaskState,
)
from .service import task_engine_service


router = APIRouter(prefix="/v1/task-engine", tags=["task-engine"])


@router.get("/status", response_model=TaskEngineStatus)
def engine_status() -> TaskEngineStatus:
    return task_engine_service.status()


@router.post("/agents", response_model=AgentRecord, status_code=status.HTTP_201_CREATED)
def create_agent(payload: AgentCreate) -> AgentRecord:
    try:
        return task_engine_service.create_agent(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/agents", response_model=list[AgentRecord])
def list_agents(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AgentRecord]:
    return task_engine_service.list_agents(workspace_id)


@router.get("/agents/{agent_id}", response_model=AgentRecord)
def get_agent(agent_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> AgentRecord:
    item = task_engine_service.get_agent(agent_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return item


def _agent_state(agent_id: UUID, workspace_id: str, payload: TaskMutation, state: AgentState) -> AgentRecord:
    item = task_engine_service.set_agent_state(agent_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned agent not found")
    return item


@router.post("/agents/{agent_id}/activate", response_model=AgentRecord)
def activate_agent(agent_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AgentRecord:
    return _agent_state(agent_id, workspace_id, payload, AgentState.ACTIVE)


@router.post("/agents/{agent_id}/pause", response_model=AgentRecord)
def pause_agent(agent_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AgentRecord:
    return _agent_state(agent_id, workspace_id, payload, AgentState.PAUSED)


@router.post("/agents/{agent_id}/disable", response_model=AgentRecord)
def disable_agent(agent_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> AgentRecord:
    return _agent_state(agent_id, workspace_id, payload, AgentState.DISABLED)


@router.post("/tasks", response_model=TaskRecord, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> TaskRecord:
    try:
        return task_engine_service.create_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks", response_model=list[TaskRecord])
def list_tasks(workspace_id: str = Query(min_length=1, max_length=120), agent_id: UUID | None = None) -> list[TaskRecord]:
    return task_engine_service.list_tasks(workspace_id, agent_id)


@router.get("/tasks/{task_id}", response_model=TaskRecord)
def get_task(task_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    item = task_engine_service.get_task(task_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return item


def _task_state(task_id: UUID, workspace_id: str, payload: TaskMutation, state: TaskState) -> TaskRecord:
    item = task_engine_service.mutate_task(task_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned task not found")
    return item


@router.post("/tasks/{task_id}/start", response_model=TaskRecord)
def start_task(task_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    return _task_state(task_id, workspace_id, payload, TaskState.RUNNING)


@router.post("/tasks/{task_id}/pause", response_model=TaskRecord)
def pause_task(task_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    return _task_state(task_id, workspace_id, payload, TaskState.PAUSED)


@router.post("/tasks/{task_id}/resume", response_model=TaskRecord)
def resume_task(task_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    return _task_state(task_id, workspace_id, payload, TaskState.QUEUED)


@router.post("/tasks/{task_id}/complete", response_model=TaskRecord)
def complete_task(task_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    return _task_state(task_id, workspace_id, payload, TaskState.COMPLETED)


@router.post("/tasks/{task_id}/cancel", response_model=TaskRecord)
def cancel_task(task_id: UUID, payload: TaskMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    return _task_state(task_id, workspace_id, payload, TaskState.CANCELLED)


@router.post("/tasks/{task_id}/progress", response_model=TaskRecord)
def update_progress(task_id: UUID, payload: ProgressUpdate, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    item = task_engine_service.update_progress(task_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Running owned task not found")
    return item


@router.post("/tasks/{task_id}/fail", response_model=TaskRecord)
def fail_task(task_id: UUID, payload: FailureRequest, workspace_id: str = Query(min_length=1, max_length=120)) -> TaskRecord:
    item = task_engine_service.fail_task(task_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned task not found")
    return item


@router.get("/queue", response_model=list[TaskRecord])
def get_queue(workspace_id: str = Query(min_length=1, max_length=120)) -> list[TaskRecord]:
    return task_engine_service.queue(workspace_id)


@router.post("/checkpoints", response_model=CheckpointRecord, status_code=status.HTTP_201_CREATED)
def create_checkpoint(payload: CheckpointCreate) -> CheckpointRecord:
    try:
        return task_engine_service.create_checkpoint(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/checkpoints", response_model=list[CheckpointRecord])
def list_checkpoints(workspace_id: str = Query(min_length=1, max_length=120), task_id: UUID | None = None) -> list[CheckpointRecord]:
    return task_engine_service.list_checkpoints(workspace_id, task_id)


@router.post("/memory", response_model=MemoryRecord)
def write_memory(payload: MemoryWrite) -> MemoryRecord:
    try:
        return task_engine_service.write_memory(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/memory", response_model=list[MemoryRecord])
def list_memory(workspace_id: str = Query(min_length=1, max_length=120), agent_id: UUID = Query()) -> list[MemoryRecord]:
    return task_engine_service.list_memory(workspace_id, agent_id)


@router.get("/events", response_model=list[TaskEvent])
def list_events(workspace_id: str = Query(min_length=1, max_length=120)) -> list[TaskEvent]:
    return task_engine_service.list_events(workspace_id)


@router.get("/audit", response_model=list[TaskEvent])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[TaskEvent]:
    return task_engine_service.list_events(workspace_id)
