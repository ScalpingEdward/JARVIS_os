from app.memory.service import memory_service
from app.schemas.phoenix_demo1_memory_binding_v21_229 import (
    MemoryContextItem,
    MemoryContextQuery,
    MemoryContextResponse,
)


def _token_hits(query: str, content: str, category: str, tags: list[str]) -> int:
    tokens = [token for token in query.casefold().strip().split() if token]
    hay = f"{content} {category} {' '.join(tags)}".casefold()
    return sum(1 for token in tokens if token in hay)


def _score(query: str, content: str, category: str, tags: list[str], priority: int) -> float:
    needle = query.casefold().strip()
    hay = f"{content} {category} {' '.join(tags)}".casefold()
    token_hits = _token_hits(query, content, category, tags)
    exact = 1.0 if needle and needle in hay else 0.0
    return round(min(1.0, 0.15 * priority + 0.15 * token_hits + 0.4 * exact), 4)


def retrieve_memory_context(req: MemoryContextQuery) -> MemoryContextResponse:
    if req.risk_brain_hard_block:
        return MemoryContextResponse(
            state='blocked', provider='memory_service/SQLMemoryStore', provider_bound=True,
            query=req.query, items=[], count=0, context_available=False,
            reasons=['risk-brain-hard-block'],
        )

    # The canonical MemoryService.search() intentionally performs a strict substring
    # match. Demo 1 context retrieval needs multi-token recall (for example
    # "gold xauusd" should match a memory containing both terms separately), so we
    # read through the canonical provider and apply governed token matching here.
    records = memory_service.list_all(category=req.category)
    items: list[MemoryContextItem] = []
    for record in records:
        if int(record.priority) < req.min_priority:
            continue
        if _token_hits(req.query, record.content, record.category, record.tags) == 0:
            continue
        score = _score(req.query, record.content, record.category, record.tags, int(record.priority))
        items.append(MemoryContextItem(
            memory_id=str(record.id), category=record.category, priority=int(record.priority),
            tags=record.tags, content=record.content if req.include_content else None,
            relevance_score=score,
        ))
    items = sorted(items, key=lambda item: (item.relevance_score, item.priority), reverse=True)[:req.limit]
    return MemoryContextResponse(
        state='ready' if items else 'empty', provider='memory_service/SQLMemoryStore', provider_bound=True,
        query=req.query, items=items, count=len(items), context_available=bool(items),
        reasons=[] if items else ['no-matching-memory'],
    )


def memory_binding_status() -> dict:
    return {
        'version': 'v21.229',
        'provider': 'memory_service/SQLMemoryStore',
        'provider_bound': True,
        'read_path_bound': True,
        'write_path_existing': True,
        'deletion_path_existing': True,
        'context_retrieval_enabled': True,
        'autonomous_memory_mutation_enabled': False,
    }
