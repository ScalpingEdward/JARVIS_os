from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditRecord,
    ChunkCreate,
    ChunkRecord,
    CollectionCreate,
    CollectionRecord,
    DocumentCreate,
    DocumentMutation,
    DocumentRecord,
    EmbeddingRebuildRecord,
    EmbeddingRebuildRequest,
    KnowledgeEngineStatus,
    SearchRecord,
    SearchRequest,
)
from .service import knowledge_engine_service


router = APIRouter(prefix="/v1/knowledge-engine", tags=["knowledge-engine"])


@router.get("/status", response_model=KnowledgeEngineStatus)
def engine_status() -> KnowledgeEngineStatus:
    return knowledge_engine_service.status()


@router.post("/collections", response_model=CollectionRecord, status_code=status.HTTP_201_CREATED)
def create_collection(payload: CollectionCreate) -> CollectionRecord:
    try:
        return knowledge_engine_service.create_collection(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/collections", response_model=list[CollectionRecord])
def list_collections(workspace_id: str = Query(min_length=1, max_length=120)) -> list[CollectionRecord]:
    return knowledge_engine_service.list_collections(workspace_id)


@router.post("/documents", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate) -> DocumentRecord:
    try:
        return knowledge_engine_service.create_document(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/documents", response_model=list[DocumentRecord])
def list_documents(
    workspace_id: str = Query(min_length=1, max_length=120),
    collection_id: UUID | None = Query(default=None),
    include_archived: bool = Query(default=False),
) -> list[DocumentRecord]:
    return knowledge_engine_service.list_documents(workspace_id, collection_id, include_archived)


@router.get("/documents/{document_id}", response_model=DocumentRecord)
def get_document(
    document_id: UUID,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> DocumentRecord:
    document = knowledge_engine_service.get_document(document_id, workspace_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/chunks", response_model=ChunkRecord, status_code=status.HTTP_201_CREATED)
def create_chunk(payload: ChunkCreate) -> ChunkRecord:
    try:
        return knowledge_engine_service.add_chunk(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/chunks", response_model=list[ChunkRecord])
def list_chunks(
    workspace_id: str = Query(min_length=1, max_length=120),
    document_id: UUID | None = Query(default=None),
) -> list[ChunkRecord]:
    return knowledge_engine_service.list_chunks(workspace_id, document_id)


@router.post("/search", response_model=SearchRecord, status_code=status.HTTP_201_CREATED)
def search_knowledge(payload: SearchRequest) -> SearchRecord:
    return knowledge_engine_service.search(payload)


@router.get("/search-history", response_model=list[SearchRecord])
def search_history(workspace_id: str = Query(min_length=1, max_length=120)) -> list[SearchRecord]:
    return knowledge_engine_service.list_searches(workspace_id)


@router.post("/embeddings/rebuild", response_model=EmbeddingRebuildRecord, status_code=status.HTTP_202_ACCEPTED)
def rebuild_embeddings(payload: EmbeddingRebuildRequest) -> EmbeddingRebuildRecord:
    return knowledge_engine_service.plan_embedding_rebuild(payload)


@router.post("/documents/{document_id}/archive", response_model=DocumentRecord)
def archive_document(
    document_id: UUID,
    payload: DocumentMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> DocumentRecord:
    document = knowledge_engine_service.archive_document(document_id, workspace_id, payload)
    if document is None:
        raise HTTPException(status_code=404, detail="Owned document not found")
    return document


@router.post("/documents/{document_id}/restore", response_model=DocumentRecord)
def restore_document(
    document_id: UUID,
    payload: DocumentMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> DocumentRecord:
    document = knowledge_engine_service.restore_document(document_id, workspace_id, payload)
    if document is None:
        raise HTTPException(status_code=404, detail="Owned document not found")
    return document


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return knowledge_engine_service.list_audit(workspace_id)
