from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ConsolidationRequest,
    ConsolidationResult,
    MemoryAuditRecord,
    MemoryCreate,
    MemoryRecord,
    MemoryRelationshipCreate,
    MemoryRelationshipRecord,
    MemoryStatus,
    MemoryType,
    MemoryUpdate,
    TradingMemoryCreate,
)
from .service import long_term_memory_service

router = APIRouter(prefix="/v1/long-term-memory", tags=["long-term-memory"])


@router.get("/status", response_model=MemoryStatus)
def get_status() -> MemoryStatus:
    return long_term_memory_service.status()


@router.post("", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED)
def create_memory(payload: MemoryCreate) -> MemoryRecord:
    return long_term_memory_service.create(payload)


@router.get("", response_model=list[MemoryRecord])
def list_memories(
    memory_type: MemoryType | None = None,
    include_archived: bool = False,
) -> list[MemoryRecord]:
    return long_term_memory_service.list_all(memory_type=memory_type, include_archived=include_archived)


@router.get("/search", response_model=list[MemoryRecord])
def search_memories(
    q: str = Query(min_length=1, max_length=500),
    memory_type: MemoryType | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[MemoryRecord]:
    return long_term_memory_service.search(q, memory_type=memory_type, limit=limit)


@router.get("/audit", response_model=list[MemoryAuditRecord])
def get_audit() -> list[MemoryAuditRecord]:
    return long_term_memory_service.audit()


@router.get("/{memory_id}", response_model=MemoryRecord)
def get_memory(memory_id: UUID) -> MemoryRecord:
    record = long_term_memory_service.get(memory_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return record


@router.patch("/{memory_id}", response_model=MemoryRecord)
def update_memory(memory_id: UUID, payload: MemoryUpdate) -> MemoryRecord:
    record = long_term_memory_service.update(memory_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return record


@router.post("/relationships", response_model=MemoryRelationshipRecord, status_code=status.HTTP_201_CREATED)
def create_relationship(payload: MemoryRelationshipCreate) -> MemoryRelationshipRecord:
    try:
        return long_term_memory_service.relate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/relationships/all", response_model=list[MemoryRelationshipRecord])
def list_relationships(memory_id: UUID | None = None) -> list[MemoryRelationshipRecord]:
    return long_term_memory_service.relationships(memory_id)


@router.post("/trading", response_model=MemoryRecord, status_code=status.HTTP_201_CREATED)
def add_trading_memory(payload: TradingMemoryCreate) -> MemoryRecord:
    return long_term_memory_service.add_trading_memory(payload)


@router.get("/trading/statistics")
def trading_statistics() -> dict[str, object]:
    return long_term_memory_service.trading_statistics()


@router.post("/consolidate", response_model=ConsolidationResult)
def consolidate(payload: ConsolidationRequest) -> ConsolidationResult:
    return long_term_memory_service.consolidate(payload)
