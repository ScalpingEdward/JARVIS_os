from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from .models import EventState, ResearchBrief, ResearchEvent, ResearchEventCreate, ResearchStatus


class AutonomousResearchService:
    def __init__(self) -> None:
        self._events: dict[UUID, ResearchEvent] = {}

    def reset(self) -> None:
        self._events.clear()

    def create(self, payload: ResearchEventCreate) -> ResearchEvent:
        event = ResearchEvent(**payload.model_dump())
        event.graph_links = sorted(set(payload.entities + payload.topics))
        event.confidence = self._confidence(event)
        duplicate = self._find_duplicate(event)
        if duplicate:
            event.state = EventState.duplicate
            event.duplicate_of = duplicate.id
        else:
            contradictions = self._find_contradictions(event)
            event.contradiction_ids = [item.id for item in contradictions]
            event.state = EventState.disputed if contradictions else (
                EventState.verified if event.confidence >= 0.65 else EventState.new
            )
            for item in contradictions:
                if event.id not in item.contradiction_ids:
                    item.contradiction_ids.append(event.id)
                    item.state = EventState.disputed
                    item.updated_at = datetime.now(timezone.utc)
        self._events[event.id] = event
        return event

    def list_all(self, state: EventState | None = None, min_relevance: float = 0) -> list[ResearchEvent]:
        values = [item for item in self._events.values() if item.relevance >= min_relevance]
        if state:
            values = [item for item in values if item.state == state]
        return sorted(values, key=lambda item: (item.relevance, item.confidence, item.created_at), reverse=True)

    def get(self, event_id: UUID) -> ResearchEvent | None:
        return self._events.get(event_id)

    def brief(self, limit: int = 10) -> ResearchBrief:
        events = [item for item in self.list_all() if item.state != EventState.duplicate][:limit]
        entities = Counter(entity for item in events for entity in item.entities)
        opportunities = []
        risks = []
        for item in events:
            for impact in item.impacts:
                text = f"{impact.target}: {impact.rationale or item.title}"
                (opportunities if impact.direction > 0 else risks if impact.direction < 0 else risks).append(text)
        contradictions = [item.title for item in events if item.state == EventState.disputed]
        confidence = sum(item.confidence for item in events) / len(events) if events else 0
        return ResearchBrief(
            event_ids=[item.id for item in events],
            headline=events[0].title if events else "No research events",
            summary=" ".join(item.summary for item in events[:3]) if events else "No verified research available.",
            key_entities=[name for name, _ in entities.most_common(10)],
            opportunities=opportunities[:10],
            risks=risks[:10],
            contradictions=contradictions[:10],
            confidence=round(confidence, 4),
        )

    def status(self) -> ResearchStatus:
        values = list(self._events.values())
        return ResearchStatus(
            total_events=len(values),
            verified=sum(item.state == EventState.verified for item in values),
            disputed=sum(item.state == EventState.disputed for item in values),
            duplicates=sum(item.state == EventState.duplicate for item in values),
            high_relevance=sum(item.relevance >= 0.75 for item in values),
            sources=len({item.source.name for item in values}),
        )

    def _confidence(self, event: ResearchEvent) -> float:
        evidence = min(len(event.evidence) / 3, 1)
        claims = 0.7 if event.claims else 0.4
        primary = 1 if event.source.primary_source else 0.6
        score = event.source.credibility * 0.45 + evidence * 0.25 + claims * 0.1 + primary * 0.2
        return round(min(1, score), 4)

    def _find_duplicate(self, event: ResearchEvent) -> ResearchEvent | None:
        normalized = set((event.title + " " + event.summary).lower().split())
        for existing in self._events.values():
            other = set((existing.title + " " + existing.summary).lower().split())
            overlap = len(normalized & other) / max(len(normalized | other), 1)
            if overlap >= 0.72 or (set(event.entities) == set(existing.entities) and set(event.claims) == set(existing.claims) and event.claims):
                return existing
        return None

    def _find_contradictions(self, event: ResearchEvent) -> list[ResearchEvent]:
        results = []
        claims = {claim.lower().strip() for claim in event.claims}
        for existing in self._events.values():
            if not set(event.entities) & set(existing.entities):
                continue
            existing_claims = {claim.lower().strip() for claim in existing.claims}
            if any(self._opposes(a, b) for a in claims for b in existing_claims):
                results.append(existing)
        return results

    @staticmethod
    def _opposes(a: str, b: str) -> bool:
        pairs = [("increase", "decrease"), ("rise", "fall"), ("approve", "reject"), ("launch", "cancel"), ("beat", "miss")]
        return any((left in a and right in b) or (right in a and left in b) for left, right in pairs)


autonomous_research_service = AutonomousResearchService()
