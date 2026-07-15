from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response, status

from .agent_adapters.api import router as agent_adapters_router
from .approvals.api import router as approvals_router
from .autofix.api import router as autofix_router
from .collaboration.api import router as collaboration_router
from .commands.api import router as commands_router
from .config import get_settings
from .execution.api import router as execution_router
from .github_remote.api import router as github_remote_router
from .memory.models import MemoryCreate, MemoryListResponse, MemoryRecord
from .memory.service import memory_service
from .models.api import GenerateRequest, GenerateResponse, ProvidersResponse
from .models.contracts import ModelRequest
from .models.router import UnknownProviderError, model_router
from .orchestrator.models import (
    AgentCreate,
    AgentListResponse,
    AgentRecord,
    OrchestratorStatus,
    TaskCreate,
    TaskListResponse,
    TaskRecord,
    TaskStatus,
    TaskStatusUpdate,
)
from .orchestrator.service import orchestrator_service
from .planner.api import router as planner_router
from .runtime.api import router as runtime_router
from .sandbox.api import router as sandbox_router
from .tools.api import router as tools_router
from .workers.api import router as workers_router
from .workspace.api import router as workspace_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(agent_adapters_router)
app.include_router(approvals_router)
app.include_router(autofix_router)
app.include_router(collaboration_router)
app.include_router(commands_router)
app.include_router(execution_router)
app.include_router(github_remote_router)
app.include_router(planner_router)
app.include_router(runtime_router)
app.include_router(sandbox_router)
app.include_router(tools_router)
app.include_router(workers_router)
app.include_router(workspace_router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": settings.version, "status": "online"}


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "healthy", "environment": settings.environment}


@app.get("/v1/models/providers", response_model=ProvidersResponse, tags=["models"])
def list_model_providers() -> ProvidersResponse:
    return ProvidersResponse(providers=model_router.available_providers())


@app.post("/v1/models/generate", response_model=GenerateResponse, tags=["models"])
def generate_model_response(payload: GenerateRequest) -> GenerateResponse:
    try:
        result = model_router.generate(
            ModelRequest(prompt=payload.prompt, task_type=payload.task_type),
            provider_name=payload.provider,
        )
    except UnknownProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenerateResponse(provider=result.provider, model=result.model, content=result.content)


@app.post("/v1/memory", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED, tags=["memory"])
def create_memory(payload: MemoryCreate) -> MemoryRecord:
    return memory_service.create(payload)


@app.get("/v1/memory", response_model=MemoryListResponse, tags=["memory"])
def list_memories(category: str | None = None) -> MemoryListResponse:
    items = memory_service.list_all(category=category)
    return MemoryListResponse(items=items, count=len(items))


@app.get("/v1/memory/search", response_model=MemoryListResponse, tags=["memory"])
def search_memories(q: str = Query(min_length=1, max_length=500), category: str | None = None) -> MemoryListResponse:
    items = memory_service.search(query=q, category=category)
    return MemoryListResponse(items=items, count=len(items))


@app.delete("/v1/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["memory"])
def delete_memory(memory_id: UUID) -> Response:
    if not memory_service.delete(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/agents", response_model=AgentRecord, status_code=status.HTTP_201_CREATED, tags=["orchestrator"])
def register_agent(payload: AgentCreate) -> AgentRecord:
    return orchestrator_service.register_agent(payload)


@app.get("/v1/agents", response_model=AgentListResponse, tags=["orchestrator"])
def list_agents() -> AgentListResponse:
    items = orchestrator_service.list_agents()
    return AgentListResponse(items=items, count=len(items))


@app.post("/v1/tasks", response_model=TaskRecord, status_code=status.HTTP_201_CREATED, tags=["orchestrator"])
def create_task(payload: TaskCreate) -> TaskRecord:
    return orchestrator_service.create_task(payload)


@app.get("/v1/tasks", response_model=TaskListResponse, tags=["orchestrator"])
def list_tasks(task_status: TaskStatus | None = None) -> TaskListResponse:
    items = orchestrator_service.list_tasks(status=task_status)
    return TaskListResponse(items=items, count=len(items))


@app.patch("/v1/tasks/{task_id}/status", response_model=TaskRecord, tags=["orchestrator"])
def update_task_status(task_id: UUID, payload: TaskStatusUpdate) -> TaskRecord:
    task = orchestrator_service.update_task_status(task_id, payload.status)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/v1/orchestrator/assign-next", response_model=TaskRecord, tags=["orchestrator"])
def assign_next_task() -> TaskRecord:
    task = orchestrator_service.assign_next()
    if task is None:
        raise HTTPException(status_code=409, detail="No compatible task and agent available")
    return task


@app.get("/v1/orchestrator/status", response_model=OrchestratorStatus, tags=["orchestrator"])
def orchestrator_status() -> OrchestratorStatus:
    return orchestrator_service.status()
