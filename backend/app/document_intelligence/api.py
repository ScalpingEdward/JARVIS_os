from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AnalysisRecord,
    AnalysisRequest,
    AuditRecord,
    DocumentCreate,
    DocumentIntelligenceStatus,
    DocumentMutation,
    DocumentRecord,
)
from .service import document_intelligence_service


router = APIRouter(prefix="/v1/document-intelligence", tags=["document-intelligence"])


@router.get("/status", response_model=DocumentIntelligenceStatus)
def intelligence_status() -> DocumentIntelligenceStatus:
    return document_intelligence_service.status()


@router.post("/documents", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate) -> DocumentRecord:
    try:
        return document_intelligence_service.create_document(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/documents", response_model=list[DocumentRecord])
def list_documents(
    workspace_id: str = Query(min_length=1, max_length=120),
    include_inactive: bool = Query(default=False),
) -> list[DocumentRecord]:
    return document_intelligence_service.list_documents(workspace_id, include_inactive)


@router.get("/documents/{document_id}", response_model=DocumentRecord)
def get_document(document_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> DocumentRecord:
    record = document_intelligence_service.get_document(document_id, workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return record


@router.post("/documents/{document_id}/archive", response_model=DocumentRecord)
def archive_document(
    document_id: UUID,
    payload: DocumentMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> DocumentRecord:
    record = document_intelligence_service.set_active(document_id, workspace_id, payload, False)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned document not found")
    return record


@router.post("/documents/{document_id}/restore", response_model=DocumentRecord)
def restore_document(
    document_id: UUID,
    payload: DocumentMutation,
    workspace_id: str = Query(min_length=1, max_length=120),
) -> DocumentRecord:
    record = document_intelligence_service.set_active(document_id, workspace_id, payload, True)
    if record is None:
        raise HTTPException(status_code=404, detail="Owned document not found")
    return record


@router.post("/analyses", response_model=AnalysisRecord, status_code=status.HTTP_201_CREATED)
def analyze_document(payload: AnalysisRequest) -> AnalysisRecord:
    return document_intelligence_service.analyze(payload)


@router.get("/analyses", response_model=list[AnalysisRecord])
def list_analyses(
    workspace_id: str = Query(min_length=1, max_length=120),
    document_id: UUID | None = Query(default=None),
) -> list[AnalysisRecord]:
    return document_intelligence_service.list_analyses(workspace_id, document_id)


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return document_intelligence_service.list_audit(workspace_id)
