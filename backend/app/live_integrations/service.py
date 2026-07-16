from datetime import datetime, timezone
from uuid import UUID

from .models import (
    IntegrationHeartbeat,
    IntegrationHubStatus,
    IntegrationState,
    LiveIntegration,
    LiveIntegrationCreate,
    NormalizedMarketEvent,
)


class LiveIntegrationError(ValueError):
    pass


class LiveIntegrationService:
    def __init__(self) -> None:
        self._integrations: dict[UUID, LiveIntegration] = {}
        self._events: list[NormalizedMarketEvent] = []

    def reset(self) -> None:
        self._integrations.clear()
        self._events.clear()

    def create(self, payload: LiveIntegrationCreate) -> LiveIntegration:
        if not payload.read_only:
            raise LiveIntegrationError("Live integrations are read-only in PHOENIX v5.4")
        record = LiveIntegration(**payload.model_dump())
        self._integrations[record.id] = record
        return record

    def list_all(self) -> list[LiveIntegration]:
        return sorted(self._integrations.values(), key=lambda item: item.created_at)

    def get(self, integration_id: UUID) -> LiveIntegration | None:
        return self._integrations.get(integration_id)

    def heartbeat(self, integration_id: UUID, payload: IntegrationHeartbeat) -> LiveIntegration | None:
        record = self.get(integration_id)
        if record is None:
            return None
        record.state = payload.state
        record.latency_ms = payload.latency_ms
        record.records_received += payload.records_received
        record.last_error = payload.last_error
        record.metadata.update(payload.metadata)
        record.last_heartbeat_at = datetime.now(timezone.utc)
        record.updated_at = record.last_heartbeat_at
        return record

    def ingest(self, event: NormalizedMarketEvent) -> NormalizedMarketEvent:
        event.symbol = event.symbol.upper()
        self._events.append(event)
        self._events = self._events[-2000:]
        return event

    def events(self, symbol: str | None = None, limit: int = 100) -> list[NormalizedMarketEvent]:
        values = self._events
        if symbol:
            values = [item for item in values if item.symbol == symbol.upper()]
        return list(reversed(values[-limit:]))

    def status(self) -> IntegrationHubStatus:
        values = list(self._integrations.values())
        return IntegrationHubStatus(
            total=len(values),
            online=sum(item.state == IntegrationState.online for item in values),
            degraded=sum(item.state == IntegrationState.degraded for item in values),
            disconnected=sum(item.state == IntegrationState.disconnected for item in values),
            errors=sum(item.state == IntegrationState.error for item in values),
            records_received=sum(item.records_received for item in values),
        )


live_integration_service = LiveIntegrationService()
