from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response, status

from .config import get_settings
from .memory.models import MemoryCreate, MemoryListResponse, MemoryRecord
from .memory.service import memory_service
from .models.api import GenerateRequest, GenerateResponse, ProvidersResponse
from .models.contracts import ModelRequest
from .models.router import UnknownProviderError, model_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.version)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.version,
        "status": "online",
    }


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
    }


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

    return GenerateResponse(
        provider=result.provider,
        model=result.model,
        content=result.content,
    )


@app.post(
    "/v1/memory",
    response_model=MemoryRecord,
    status_code=status.HTTP_201_CREATED,
    tags=["memory"],
)
def create_memory(payload: MemoryCreate) -> MemoryRecord:
    return memory_service.create(payload)


@app.get("/v1/memory", response_model=MemoryListResponse, tags=["memory"])
def list_memories(category: str | None = None) -> MemoryListResponse:
    items = memory_service.list_all(category=category)
    return MemoryListResponse(items=items, count=len(items))


@app.get("/v1/memory/search", response_model=MemoryListResponse, tags=["memory"])
def search_memories(
    q: str = Query(min_length=1, max_length=500),
    category: str | None = None,
) -> MemoryListResponse:
    items = memory_service.search(query=q, category=category)
    return MemoryListResponse(items=items, count=len(items))


@app.delete(
    "/v1/memory/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["memory"],
)
def delete_memory(memory_id: UUID) -> Response:
    if not memory_service.delete(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
