from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    MemoryCreate,
    MemoryEngineStatus,
    MemoryQuery,
    MemoryRecord,
    MemorySearchResult,
    MemoryStateChange,
    MemoryUpdate,
)
from .service import memory_engine_service


router = APIRouter(prefix="/v1/memory-engine", tags=["memory-engine"])


@router.get("/status", response_model=MemoryEngineStatus)
def memory_status() -> MemoryEngineStatus:
    return memory_engine_service.status()


@router.post("/memories", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED)
def create_memory(payload: MemoryCreate) -> MemoryRecord:
    return memory_engine_service.create(payload)


@router.get("/memories", response_model=list[MemoryRecord])
def list_memories(
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
    include_archived: bool = False,
) -> list[MemoryRecord]:
    return memory_engine_service.list_all(workspace_id, requester_id, include_archived)


@router.get("/memories/{memory_id}", response_model=MemoryRecord)
def get_memory(
    memory_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> MemoryRecord:
    record = memory_engine_service.get(memory_id, workspace_id, requester_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return record


@router.patch("/memories/{memory_id}", response_model=MemoryRecord)
def update_memory(
    memory_id: UUID,
    payload: MemoryUpdate,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> MemoryRecord:
    record = memory_engine_service.update(memory_id, workspace_id, requester_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned active memory not found")
    return record


@router.post("/search", response_model=list[MemorySearchResult])
def search_memories(payload: MemoryQuery) -> list[MemorySearchResult]:
    return memory_engine_service.search(payload)


@router.get("/memories/{memory_id}/related", response_model=list[MemoryRecord])
def related_memories(
    memory_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> list[MemoryRecord]:
    records = memory_engine_service.related(memory_id, workspace_id, requester_id)
    if records is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return records


@router.post("/memories/{memory_id}/archive", response_model=MemoryRecord)
def archive_memory(
    memory_id: UUID,
    payload: MemoryStateChange,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> MemoryRecord:
    record = memory_engine_service.archive(memory_id, workspace_id, requester_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned active memory not found")
    return record


@router.post("/memories/{memory_id}/restore", response_model=MemoryRecord)
def restore_memory(
    memory_id: UUID,
    payload: MemoryStateChange,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> MemoryRecord:
    record = memory_engine_service.restore(memory_id, workspace_id, requester_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned archived memory not found")
    return record


@router.delete("/memories/{memory_id}", response_model=MemoryRecord)
def delete_memory(
    memory_id: UUID,
    payload: MemoryStateChange,
    workspace_id: str = Query(min_length=1, max_length=120),
    requester_id: str = Query(min_length=1, max_length=120),
) -> MemoryRecord:
    record = memory_engine_service.delete(memory_id, workspace_id, requester_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned memory not found")
    return record
