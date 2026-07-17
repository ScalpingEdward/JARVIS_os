import pytest
from pydantic import ValidationError

from app.knowledge_engine.models import (
    ChunkCreate,
    CollectionCreate,
    DocumentCreate,
    DocumentMutation,
    DocumentState,
    EmbeddingRebuildRequest,
    SearchMode,
    SearchRequest,
    SourceType,
    TrustLevel,
)
from app.knowledge_engine.service import KnowledgeEngineService


def collection_payload(workspace: str = "workspace-1", owner: str = "owner-1") -> CollectionCreate:
    return CollectionCreate(
        workspace_id=workspace,
        owner_id=owner,
        key="trading",
        name="Trading Knowledge",
    )


def build_document(service: KnowledgeEngineService, workspace: str = "workspace-1", owner: str = "owner-1"):
    collection = service.create_collection(collection_payload(workspace, owner))
    document = service.create_document(
        DocumentCreate(
            workspace_id=workspace,
            owner_id=owner,
            collection_id=collection.id,
            title="FTMO Risk Rules",
            source_type=SourceType.MANUAL,
            author="PHOENIX",
            version="1.0",
            content="Maximum daily loss and risk rules for funded trading accounts.",
            tags=["ftmo", "risk"],
            trust_level=TrustLevel.VERIFIED,
            priority=90,
        )
    )
    return collection, document


def test_collection_document_chunk_and_keyword_search():
    service = KnowledgeEngineService()
    collection, document = build_document(service)
    service.add_chunk(
        ChunkCreate(
            workspace_id="workspace-1",
            document_id=document.id,
            ordinal=0,
            section="Daily loss",
            text="The maximum daily loss rule includes floating profit and loss.",
        )
    )
    result = service.search(
        SearchRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            query="maximum daily loss",
            collection_ids=[collection.id],
            mode=SearchMode.KEYWORD,
        )
    )
    assert len(result.hits) == 1
    assert result.hits[0].document_id == document.id
    assert result.hits[0].trust_level == TrustLevel.VERIFIED


def test_hybrid_search_uses_supplied_embeddings():
    service = KnowledgeEngineService()
    _, document = build_document(service)
    service.add_chunk(
        ChunkCreate(
            workspace_id="workspace-1",
            document_id=document.id,
            ordinal=0,
            section="Risk",
            text="Funded account safety constraints.",
            embedding=[1.0, 0.0, 0.0],
            embedding_model="local-test",
        )
    )
    result = service.search(
        SearchRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            query="unrelated words",
            mode=SearchMode.HYBRID,
            query_embedding=[1.0, 0.0, 0.0],
        )
    )
    assert result.hits
    assert result.hits[0].semantic_score == 1.0


def test_workspace_isolation_for_documents_and_search():
    service = KnowledgeEngineService()
    _, document = build_document(service)
    service.add_chunk(
        ChunkCreate(
            workspace_id="workspace-1",
            document_id=document.id,
            ordinal=0,
            text="Private workspace knowledge about FTMO rules.",
        )
    )
    assert service.get_document(document.id, "workspace-2") is None
    result = service.search(
        SearchRequest(
            workspace_id="workspace-2",
            requester_id="owner-2",
            query="FTMO rules",
            mode=SearchMode.KEYWORD,
        )
    )
    assert result.hits == []


def test_owner_only_archive_and_restore():
    service = KnowledgeEngineService()
    _, document = build_document(service)
    denied = service.archive_document(
        document.id,
        "workspace-1",
        DocumentMutation(requester_id="wrong-owner"),
    )
    assert denied is None
    archived = service.archive_document(
        document.id,
        "workspace-1",
        DocumentMutation(requester_id="owner-1", reason="superseded"),
    )
    assert archived is not None
    assert archived.state == DocumentState.ARCHIVED
    restored = service.restore_document(
        document.id,
        "workspace-1",
        DocumentMutation(requester_id="owner-1"),
    )
    assert restored is not None
    assert restored.state == DocumentState.ACTIVE


def test_archived_documents_excluded_by_default():
    service = KnowledgeEngineService()
    _, document = build_document(service)
    service.add_chunk(
        ChunkCreate(
            workspace_id="workspace-1",
            document_id=document.id,
            ordinal=0,
            text="Archived knowledge text.",
        )
    )
    service.archive_document(document.id, "workspace-1", DocumentMutation(requester_id="owner-1"))
    hidden = service.search(
        SearchRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            query="archived knowledge",
            mode=SearchMode.KEYWORD,
        )
    )
    visible = service.search(
        SearchRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            query="archived knowledge",
            mode=SearchMode.KEYWORD,
            include_archived=True,
        )
    )
    assert hidden.hits == []
    assert visible.hits


def test_duplicate_document_version_and_chunk_ordinal_rejected():
    service = KnowledgeEngineService()
    collection, document = build_document(service)
    with pytest.raises(ValueError):
        service.create_document(
            DocumentCreate(
                workspace_id="workspace-1",
                owner_id="owner-1",
                collection_id=collection.id,
                title="Duplicate",
                source_type=SourceType.MANUAL,
                version="1.0",
                content="Maximum daily loss and risk rules for funded trading accounts.",
            )
        )
    chunk = ChunkCreate(
        workspace_id="workspace-1",
        document_id=document.id,
        ordinal=0,
        text="First chunk",
    )
    service.add_chunk(chunk)
    with pytest.raises(ValueError):
        service.add_chunk(chunk.model_copy(update={"text": "Duplicate ordinal"}))


def test_embedding_rebuild_is_dry_run_only():
    service = KnowledgeEngineService()
    _, document = build_document(service)
    service.add_chunk(
        ChunkCreate(
            workspace_id="workspace-1",
            document_id=document.id,
            ordinal=0,
            text="Knowledge awaiting embeddings.",
        )
    )
    plan = service.plan_embedding_rebuild(
        EmbeddingRebuildRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            model_key="local-embedding-model",
        )
    )
    assert plan.candidate_chunks == 1
    assert plan.external_requests_executed is False
    with pytest.raises(ValidationError):
        EmbeddingRebuildRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            dry_run=False,
        )


def test_external_embedding_and_cloud_upload_are_rejected():
    service = KnowledgeEngineService()
    collection = service.create_collection(collection_payload())
    with pytest.raises(ValidationError):
        DocumentCreate(
            workspace_id="workspace-1",
            owner_id="owner-1",
            collection_id=collection.id,
            title="Unsafe",
            source_type=SourceType.PDF,
            automatic_cloud_upload=True,
        )
    with pytest.raises(ValidationError):
        SearchRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            query="test",
            external_embedding_request=True,
        )


def test_audit_and_status_report_safety_defaults():
    service = KnowledgeEngineService()
    build_document(service)
    status = service.status()
    assert status.version == "8.2"
    assert status.external_embedding_execution is False
    assert status.automatic_cloud_uploads is False
    assert status.audit_enabled is True
    assert service.list_audit("workspace-1")
