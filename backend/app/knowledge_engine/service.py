from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from math import sqrt
from uuid import UUID

from .models import (
    AuditRecord,
    ChunkCreate,
    ChunkRecord,
    CollectionCreate,
    CollectionRecord,
    DocumentCreate,
    DocumentMutation,
    DocumentRecord,
    DocumentState,
    EmbeddingRebuildRecord,
    EmbeddingRebuildRequest,
    KnowledgeEngineStatus,
    SearchHit,
    SearchMode,
    SearchRecord,
    SearchRequest,
    TrustLevel,
)


_TRUST_ORDER = {
    TrustLevel.LOW: 0,
    TrustLevel.MEDIUM: 1,
    TrustLevel.HIGH: 2,
    TrustLevel.VERIFIED: 3,
}


class KnowledgeEngineService:
    def __init__(self) -> None:
        self._collections: dict[UUID, CollectionRecord] = {}
        self._documents: dict[UUID, DocumentRecord] = {}
        self._chunks: dict[UUID, ChunkRecord] = {}
        self._searches: list[SearchRecord] = []
        self._rebuilds: list[EmbeddingRebuildRecord] = []
        self._audit: list[AuditRecord] = []

    def status(self) -> KnowledgeEngineStatus:
        return KnowledgeEngineStatus(
            collections=len(self._collections),
            active_documents=sum(d.state == DocumentState.ACTIVE for d in self._documents.values()),
            archived_documents=sum(d.state == DocumentState.ARCHIVED for d in self._documents.values()),
            chunks=len(self._chunks),
            searches=len(self._searches),
            embedding_rebuild_plans=len(self._rebuilds),
        )

    def create_collection(self, payload: CollectionCreate) -> CollectionRecord:
        if any(
            item.workspace_id == payload.workspace_id and item.key == payload.key
            for item in self._collections.values()
        ):
            raise ValueError("collection key already exists in workspace")
        record = CollectionRecord(**payload.model_dump(exclude={"human_approved"}))
        self._collections[record.id] = record
        self._log(record.workspace_id, record.owner_id, "collection.created", "collection", record.id)
        return record

    def list_collections(self, workspace_id: str) -> list[CollectionRecord]:
        return [c for c in self._collections.values() if c.workspace_id == workspace_id]

    def create_document(self, payload: DocumentCreate) -> DocumentRecord:
        collection = self._collections.get(payload.collection_id)
        if collection is None or collection.workspace_id != payload.workspace_id:
            raise ValueError("collection not found in workspace")
        if collection.owner_id != payload.owner_id:
            raise ValueError("collection owner mismatch")
        digest = sha256(payload.content.encode("utf-8")).hexdigest()
        duplicate = any(
            d.workspace_id == payload.workspace_id
            and d.collection_id == payload.collection_id
            and d.content_hash == digest
            and d.version == payload.version
            for d in self._documents.values()
        )
        if duplicate:
            raise ValueError("document version with identical content already exists")
        record = DocumentRecord(
            **payload.model_dump(exclude={"human_approved", "automatic_cloud_upload"}),
            content_hash=digest,
        )
        self._documents[record.id] = record
        collection.document_count += 1
        collection.updated_at = datetime.now(timezone.utc)
        self._log(record.workspace_id, record.owner_id, "document.created", "document", record.id)
        return record

    def list_documents(
        self,
        workspace_id: str,
        collection_id: UUID | None = None,
        include_archived: bool = False,
    ) -> list[DocumentRecord]:
        return [
            d
            for d in self._documents.values()
            if d.workspace_id == workspace_id
            and (collection_id is None or d.collection_id == collection_id)
            and (include_archived or d.state == DocumentState.ACTIVE)
        ]

    def get_document(self, document_id: UUID, workspace_id: str) -> DocumentRecord | None:
        document = self._documents.get(document_id)
        if document is None or document.workspace_id != workspace_id:
            return None
        return document

    def add_chunk(self, payload: ChunkCreate) -> ChunkRecord:
        document = self._documents.get(payload.document_id)
        if document is None or document.workspace_id != payload.workspace_id:
            raise ValueError("document not found in workspace")
        if document.state != DocumentState.ACTIVE:
            raise ValueError("cannot add chunks to archived document")
        if any(c.document_id == payload.document_id and c.ordinal == payload.ordinal for c in self._chunks.values()):
            raise ValueError("chunk ordinal already exists for document")
        record = ChunkRecord(
            **payload.model_dump(exclude={"human_approved", "external_embedding_request"}),
            token_estimate=max(1, len(payload.text.split())),
        )
        self._chunks[record.id] = record
        document.chunk_count += 1
        document.updated_at = datetime.now(timezone.utc)
        collection = self._collections[document.collection_id]
        collection.chunk_count += 1
        collection.updated_at = datetime.now(timezone.utc)
        self._log(record.workspace_id, document.owner_id, "chunk.created", "chunk", record.id)
        return record

    def list_chunks(self, workspace_id: str, document_id: UUID | None = None) -> list[ChunkRecord]:
        return [
            c for c in self._chunks.values()
            if c.workspace_id == workspace_id and (document_id is None or c.document_id == document_id)
        ]

    def search(self, payload: SearchRequest) -> SearchRecord:
        query_terms = self._terms(payload.query)
        hits: list[SearchHit] = []
        for chunk in self._chunks.values():
            if chunk.workspace_id != payload.workspace_id:
                continue
            document = self._documents.get(chunk.document_id)
            if document is None:
                continue
            if not payload.include_archived and document.state == DocumentState.ARCHIVED:
                continue
            if payload.collection_ids and document.collection_id not in payload.collection_ids:
                continue
            if payload.tags and not set(payload.tags).intersection(document.tags):
                continue
            if payload.minimum_trust and _TRUST_ORDER[document.trust_level] < _TRUST_ORDER[payload.minimum_trust]:
                continue

            keyword = self._keyword_score(query_terms, chunk.text)
            semantic = 0.0
            if payload.query_embedding is not None and chunk.embedding is not None:
                semantic = self._cosine(payload.query_embedding, chunk.embedding)
            if payload.mode == SearchMode.KEYWORD:
                score = keyword
            elif payload.mode == SearchMode.SEMANTIC:
                score = semantic
            else:
                score = (keyword * 0.55) + (semantic * 0.35) + (document.priority / 1000)
                score += _TRUST_ORDER[document.trust_level] * 0.025
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    collection_id=document.collection_id,
                    title=document.title,
                    text=chunk.text,
                    section=chunk.section,
                    score=round(score, 6),
                    keyword_score=round(keyword, 6),
                    semantic_score=round(semantic, 6),
                    trust_level=document.trust_level,
                    priority=document.priority,
                    source_uri=document.source_uri,
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        record = SearchRecord(
            workspace_id=payload.workspace_id,
            requester_id=payload.requester_id,
            query=payload.query,
            mode=payload.mode,
            hits=hits[: payload.limit],
        )
        self._searches.append(record)
        self._log(payload.workspace_id, payload.requester_id, "search.executed", "search", record.id, {"hits": len(record.hits)})
        return record

    def list_searches(self, workspace_id: str) -> list[SearchRecord]:
        return [item for item in self._searches if item.workspace_id == workspace_id]

    def archive_document(
        self,
        document_id: UUID,
        workspace_id: str,
        payload: DocumentMutation,
    ) -> DocumentRecord | None:
        document = self._owned_document(document_id, workspace_id, payload.requester_id)
        if document is None:
            return None
        document.state = DocumentState.ARCHIVED
        document.archived_at = datetime.now(timezone.utc)
        document.updated_at = document.archived_at
        self._log(workspace_id, payload.requester_id, "document.archived", "document", document.id, {"reason": payload.reason})
        return document

    def restore_document(
        self,
        document_id: UUID,
        workspace_id: str,
        payload: DocumentMutation,
    ) -> DocumentRecord | None:
        document = self._owned_document(document_id, workspace_id, payload.requester_id)
        if document is None:
            return None
        document.state = DocumentState.ACTIVE
        document.archived_at = None
        document.updated_at = datetime.now(timezone.utc)
        self._log(workspace_id, payload.requester_id, "document.restored", "document", document.id, {"reason": payload.reason})
        return document

    def plan_embedding_rebuild(self, payload: EmbeddingRebuildRequest) -> EmbeddingRebuildRecord:
        candidate_documents = {
            d.id for d in self._documents.values()
            if d.workspace_id == payload.workspace_id
            and d.state == DocumentState.ACTIVE
            and (payload.collection_id is None or d.collection_id == payload.collection_id)
        }
        record = EmbeddingRebuildRecord(
            workspace_id=payload.workspace_id,
            collection_id=payload.collection_id,
            model_key=payload.model_key,
            candidate_chunks=sum(c.document_id in candidate_documents for c in self._chunks.values()),
        )
        self._rebuilds.append(record)
        self._log(payload.workspace_id, payload.requester_id, "embeddings.rebuild_planned", "embedding_rebuild", record.id)
        return record

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _owned_document(self, document_id: UUID, workspace_id: str, requester_id: str) -> DocumentRecord | None:
        document = self._documents.get(document_id)
        if document is None or document.workspace_id != workspace_id or document.owner_id != requester_id:
            return None
        return document

    def _log(
        self,
        workspace_id: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: UUID | None,
        details: dict | None = None,
    ) -> None:
        self._audit.append(
            AuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details or {},
            )
        )

    @staticmethod
    def _terms(text: str) -> Counter[str]:
        return Counter(part.strip(".,:;!?()[]{}\"'").lower() for part in text.split() if part.strip())

    def _keyword_score(self, query_terms: Counter[str], text: str) -> float:
        if not query_terms:
            return 0.0
        document_terms = self._terms(text)
        overlap = sum(min(count, document_terms.get(term, 0)) for term, count in query_terms.items())
        return overlap / max(1, sum(query_terms.values()))

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        denominator = sqrt(sum(v * v for v in left)) * sqrt(sum(v * v for v in right))
        if denominator == 0:
            return 0.0
        return max(0.0, sum(a * b for a, b in zip(left, right)) / denominator)


knowledge_engine_service = KnowledgeEngineService()
