import re
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    MemoryCreate,
    MemoryEngineStatus,
    MemoryQuery,
    MemoryRecord,
    MemorySearchResult,
    MemoryState,
    MemoryStateChange,
    MemoryUpdate,
    MemoryVisibility,
)


class MemoryEngineService:
    def __init__(self) -> None:
        self._memories: dict[UUID, MemoryRecord] = {}

    def status(self) -> MemoryEngineStatus:
        memories = list(self._memories.values())
        return MemoryEngineStatus(
            total_memories=len(memories),
            active_memories=sum(item.state == MemoryState.ACTIVE for item in memories),
            archived_memories=sum(item.state == MemoryState.ARCHIVED for item in memories),
            deleted_memories=sum(item.state == MemoryState.DELETED for item in memories),
        )

    def create(self, payload: MemoryCreate) -> MemoryRecord:
        related = [item for item in payload.related_memory_ids if item in self._memories]
        record = MemoryRecord(
            workspace_id=payload.workspace_id.strip(),
            owner_id=payload.owner_id.strip(),
            title=payload.title.strip(),
            content=payload.content.strip(),
            memory_type=payload.memory_type,
            visibility=payload.visibility,
            tags=self._normalize_tags(payload.tags),
            source=payload.source.strip(),
            importance=payload.importance,
            confidence=payload.confidence,
            related_memory_ids=related,
        )
        self._memories[record.id] = record
        return record

    def list_all(
        self,
        workspace_id: str,
        requester_id: str,
        include_archived: bool = False,
    ) -> list[MemoryRecord]:
        records = [
            item
            for item in self._memories.values()
            if self._can_access(item, workspace_id, requester_id)
            and item.state != MemoryState.DELETED
            and (include_archived or item.state == MemoryState.ACTIVE)
        ]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def get(self, memory_id: UUID, workspace_id: str, requester_id: str) -> MemoryRecord | None:
        record = self._memories.get(memory_id)
        if record is None or record.state == MemoryState.DELETED:
            return None
        if not self._can_access(record, workspace_id, requester_id):
            return None
        record.access_count += 1
        record.last_accessed_at = datetime.now(timezone.utc)
        return record

    def update(
        self,
        memory_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: MemoryUpdate,
    ) -> MemoryRecord | None:
        record = self._owned_active(memory_id, workspace_id, requester_id)
        if record is None:
            return None
        changes = payload.model_dump(exclude_unset=True, exclude={"human_approved"})
        for field, value in changes.items():
            if field == "tags" and value is not None:
                value = self._normalize_tags(value)
            if field == "related_memory_ids" and value is not None:
                value = [item for item in value if item in self._memories and item != memory_id]
            if isinstance(value, str):
                value = value.strip()
            setattr(record, field, value)
        record.updated_at = datetime.now(timezone.utc)
        return record

    def search(self, payload: MemoryQuery) -> list[MemorySearchResult]:
        query_terms = self._terms(payload.query)
        requested_tags = set(self._normalize_tags(payload.tags))
        results: list[MemorySearchResult] = []
        for record in self._memories.values():
            if not self._can_access(record, payload.workspace_id, payload.requester_id):
                continue
            if record.state == MemoryState.DELETED:
                continue
            if record.state == MemoryState.ARCHIVED and not payload.include_archived:
                continue
            if payload.memory_types and record.memory_type not in payload.memory_types:
                continue
            record_terms = self._terms(f"{record.title} {record.content} {' '.join(record.tags)}")
            matched = sorted(query_terms & record_terms)
            tag_matches = requested_tags & set(record.tags)
            if not matched and not tag_matches:
                continue
            lexical = len(matched) / max(1, len(query_terms))
            tag_score = len(tag_matches) / max(1, len(requested_tags)) if requested_tags else 0
            score = round(
                min(1.0, lexical * 0.55 + tag_score * 0.15 + record.importance * 0.2 + record.confidence * 0.1),
                4,
            )
            results.append(
                MemorySearchResult(
                    memory=record,
                    relevance_score=score,
                    matched_terms=matched,
                )
            )
        results.sort(key=lambda item: (-item.relevance_score, -item.memory.importance, item.memory.created_at))
        selected = results[: payload.limit]
        now = datetime.now(timezone.utc)
        for result in selected:
            result.memory.access_count += 1
            result.memory.last_accessed_at = now
        return selected

    def archive(
        self,
        memory_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: MemoryStateChange,
    ) -> MemoryRecord | None:
        record = self._owned_active(memory_id, workspace_id, requester_id)
        if record is None:
            return None
        record.state = MemoryState.ARCHIVED
        record.updated_at = datetime.now(timezone.utc)
        return record

    def restore(
        self,
        memory_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: MemoryStateChange,
    ) -> MemoryRecord | None:
        record = self._memories.get(memory_id)
        if record is None or record.state != MemoryState.ARCHIVED:
            return None
        if record.workspace_id != workspace_id or record.owner_id != requester_id:
            return None
        record.state = MemoryState.ACTIVE
        record.updated_at = datetime.now(timezone.utc)
        return record

    def delete(
        self,
        memory_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: MemoryStateChange,
    ) -> MemoryRecord | None:
        record = self._memories.get(memory_id)
        if record is None or record.state == MemoryState.DELETED:
            return None
        if record.workspace_id != workspace_id or record.owner_id != requester_id:
            return None
        record.state = MemoryState.DELETED
        record.content = "[deleted]"
        record.tags = []
        record.related_memory_ids = []
        record.updated_at = datetime.now(timezone.utc)
        return record

    def related(self, memory_id: UUID, workspace_id: str, requester_id: str) -> list[MemoryRecord] | None:
        record = self.get(memory_id, workspace_id, requester_id)
        if record is None:
            return None
        related = []
        for related_id in record.related_memory_ids:
            candidate = self._memories.get(related_id)
            if candidate and candidate.state != MemoryState.DELETED and self._can_access(candidate, workspace_id, requester_id):
                related.append(candidate)
        return related

    def _owned_active(self, memory_id: UUID, workspace_id: str, requester_id: str) -> MemoryRecord | None:
        record = self._memories.get(memory_id)
        if record is None or record.state != MemoryState.ACTIVE:
            return None
        if record.workspace_id != workspace_id or record.owner_id != requester_id:
            return None
        return record

    @staticmethod
    def _can_access(record: MemoryRecord, workspace_id: str, requester_id: str) -> bool:
        if record.workspace_id != workspace_id:
            return False
        if record.visibility == MemoryVisibility.PRIVATE:
            return record.owner_id == requester_id
        return True

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in tags if item.strip()})

    @staticmethod
    def _terms(value: str) -> set[str]:
        return {item for item in re.findall(r"[a-zA-Z0-9_-]+", value.lower()) if len(item) > 1}


memory_engine_service = MemoryEngineService()
