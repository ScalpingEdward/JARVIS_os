from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

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


class LongTermMemoryService:
    def __init__(self) -> None:
        self._memories: dict[UUID, MemoryRecord] = {}
        self._relationships: dict[UUID, MemoryRelationshipRecord] = {}
        self._trading: list[TradingMemoryCreate] = []
        self._audit: list[MemoryAuditRecord] = []

    def reset(self) -> None:
        self._memories.clear()
        self._relationships.clear()
        self._trading.clear()
        self._audit.clear()

    def create(self, payload: MemoryCreate, actor: str = "human") -> MemoryRecord:
        record = MemoryRecord(**payload.model_dump())
        self._memories[record.id] = record
        self._log(record.id, "created", actor, f"type={record.memory_type.value}")
        return record

    def list_all(self, memory_type: MemoryType | None = None, include_archived: bool = False) -> list[MemoryRecord]:
        records = list(self._memories.values())
        if memory_type is not None:
            records = [item for item in records if item.memory_type == memory_type]
        if not include_archived:
            records = [item for item in records if not item.archived]
        return sorted(records, key=lambda item: (item.importance, item.updated_at), reverse=True)

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        return self._memories.get(memory_id)

    def update(self, memory_id: UUID, payload: MemoryUpdate, actor: str = "human") -> MemoryRecord | None:
        current = self.get(memory_id)
        if current is None:
            return None
        data = current.model_dump()
        changes = payload.model_dump(exclude_none=True, exclude={"reason"})
        data.update(changes)
        data["id"] = current.id
        data["version"] = current.version + 1
        data["supersedes_id"] = current.id
        data["created_at"] = current.created_at
        data["updated_at"] = datetime.now(timezone.utc)
        updated = MemoryRecord(**data)
        self._memories[memory_id] = updated
        self._log(memory_id, "updated", actor, payload.reason)
        return updated

    def search(self, query: str, memory_type: MemoryType | None = None, limit: int = 20) -> list[MemoryRecord]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[float, MemoryRecord]] = []
        for item in self.list_all(memory_type=memory_type):
            haystack = " ".join([item.title, item.content, *item.tags, *item.entities]).lower()
            matches = sum(term in haystack for term in terms)
            if matches:
                score = matches / max(len(terms), 1) + item.importance * 0.25 + item.confidence * 0.1
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def relate(self, payload: MemoryRelationshipCreate, actor: str = "human") -> MemoryRelationshipRecord:
        if payload.source_memory_id not in self._memories or payload.target_memory_id not in self._memories:
            raise ValueError("Both memories must exist")
        record = MemoryRelationshipRecord(**payload.model_dump())
        self._relationships[record.id] = record
        self._log(payload.source_memory_id, "relationship_created", actor, payload.relationship.value)
        return record

    def relationships(self, memory_id: UUID | None = None) -> list[MemoryRelationshipRecord]:
        records = list(self._relationships.values())
        if memory_id is None:
            return records
        return [
            item
            for item in records
            if item.source_memory_id == memory_id or item.target_memory_id == memory_id
        ]

    def add_trading_memory(self, payload: TradingMemoryCreate, actor: str = "trading") -> MemoryRecord:
        self._trading.append(payload)
        content = (
            f"{payload.instrument} {payload.setup} during {payload.session} on {payload.timeframe}; "
            f"outcome={payload.outcome.value}, pnl_r={payload.pnl_r}, conditions={sorted(payload.conditions)}, "
            f"mistakes={sorted(payload.mistakes)}, lessons={payload.lessons or 'none'}"
        )
        record = self.create(
            MemoryCreate(
                memory_type=MemoryType.trading,
                title=f"{payload.instrument}: {payload.setup}",
                content=content,
                source="trading",
                tags={payload.instrument, payload.setup, payload.session, payload.timeframe, payload.outcome.value},
                entities={payload.instrument},
                importance=0.7,
                confidence=0.9,
                occurred_at=payload.occurred_at,
                metadata={
                    "pnl_r": payload.pnl_r or 0.0,
                    "mfe_r": payload.mfe_r or 0.0,
                    "mae_r": payload.mae_r or 0.0,
                },
            ),
            actor=actor,
        )
        return record

    def trading_statistics(self) -> dict[str, object]:
        grouped: dict[str, list[TradingMemoryCreate]] = defaultdict(list)
        for item in self._trading:
            grouped[f"{item.instrument}|{item.setup}|{item.session}"].append(item)
        statistics = []
        for key, items in grouped.items():
            wins = sum(item.outcome.value == "win" for item in items)
            pnl_values = [item.pnl_r for item in items if item.pnl_r is not None]
            statistics.append(
                {
                    "key": key,
                    "sample_size": len(items),
                    "win_rate": round(wins / len(items), 4),
                    "expectancy_r": round(sum(pnl_values) / len(pnl_values), 4) if pnl_values else None,
                }
            )
        return {"items": statistics, "count": len(statistics), "advisory_only": True}

    def consolidate(self, payload: ConsolidationRequest) -> ConsolidationResult:
        active = self.list_all(include_archived=False)
        clusters: dict[tuple[MemoryType, tuple[str, ...]], list[MemoryRecord]] = defaultdict(list)
        for item in active:
            key = (item.memory_type, tuple(sorted(tag.lower() for tag in item.tags)))
            clusters[key].append(item)
        duplicate_clusters = [items for items in clusters.values() if len(items) > 1]
        archived = 0
        generated = 0
        for items in duplicate_clusters:
            items.sort(key=lambda item: (item.importance, item.confidence, item.updated_at), reverse=True)
            primary = items[0]
            if payload.archive_duplicates:
                for duplicate in items[1:]:
                    duplicate.archived = True
                    duplicate.updated_at = datetime.now(timezone.utc)
                    archived += 1
                    self._log(duplicate.id, "archived_duplicate", payload.actor, f"primary={primary.id}")
            lesson = " | ".join(item.content[:300] for item in items)
            self.create(
                MemoryCreate(
                    memory_type=MemoryType.experience,
                    title=f"Consolidated experience: {primary.title}",
                    content=lesson,
                    source="system",
                    tags=set(primary.tags) | {"consolidated"},
                    entities=set(primary.entities),
                    importance=max(item.importance for item in items),
                    confidence=sum(item.confidence for item in items) / len(items),
                ),
                actor=payload.actor,
            )
            generated += 1
        self._log(None, "consolidated", payload.actor, f"clusters={len(duplicate_clusters)}")
        return ConsolidationResult(
            reviewed=len(active),
            clusters=len(duplicate_clusters),
            archived=archived,
            generated_experiences=generated,
        )

    def audit(self) -> list[MemoryAuditRecord]:
        return list(self._audit)

    def status(self) -> MemoryStatus:
        memories = list(self._memories.values())
        return MemoryStatus(
            total=len(memories),
            active=sum(not item.archived for item in memories),
            archived=sum(item.archived for item in memories),
            relationships=len(self._relationships),
            trading_memories=len(self._trading),
            versions=sum(item.version for item in memories),
        )

    def _log(self, memory_id: UUID | None, action: str, actor: str, details: str | None = None) -> None:
        self._audit.append(
            MemoryAuditRecord(memory_id=memory_id, action=action, actor=actor, details=details)
        )


long_term_memory_service = LongTermMemoryService()
