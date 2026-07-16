from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ConnectorAction,
    ConnectorAuditRecord,
    ConnectorCreate,
    ConnectorHealthUpdate,
    ConnectorPlatformStatus,
    ConnectorRecord,
    ConnectorState,
)


class ConnectorService:
    def __init__(self) -> None:
        self._connectors: dict[UUID, ConnectorRecord] = {}
        self._audit: list[ConnectorAuditRecord] = []

    def reset(self) -> None:
        self._connectors.clear()
        self._audit.clear()

    def create(self, payload: ConnectorCreate) -> ConnectorRecord:
        record = ConnectorRecord(**payload.model_dump())
        self._connectors[record.id] = record
        self._log(record.id, "created", "human", f"kind={record.kind.value}")
        return record

    def list_all(self) -> list[ConnectorRecord]:
        return list(self._connectors.values())

    def get(self, connector_id: UUID) -> ConnectorRecord | None:
        return self._connectors.get(connector_id)

    def transition(self, connector_id: UUID, payload: ConnectorAction) -> ConnectorRecord | None:
        record = self.get(connector_id)
        if record is None:
            return None
        allowed = {
            "enable": ConnectorState.connecting,
            "pause": ConnectorState.paused,
            "resume": ConnectorState.connecting,
            "disable": ConnectorState.disabled,
            "reconnect": ConnectorState.connecting,
        }
        state = allowed.get(payload.action)
        if state is None:
            raise ValueError("Unsupported connector action")
        record.state = state
        record.updated_at = datetime.now(timezone.utc)
        record.last_error = None if payload.action in {"enable", "resume", "reconnect"} else record.last_error
        self._log(record.id, payload.action, payload.actor, payload.reason)
        return record

    def update_health(self, connector_id: UUID, payload: ConnectorHealthUpdate) -> ConnectorRecord | None:
        record = self.get(connector_id)
        if record is None:
            return None
        record.last_health_check_at = datetime.now(timezone.utc)
        record.updated_at = record.last_health_check_at
        record.last_error = payload.error
        record.state = ConnectorState.healthy if payload.healthy else ConnectorState.degraded
        if not payload.healthy and record.auto_reconnect:
            record.state = ConnectorState.connecting
        self._log(record.id, "health_check", "system", payload.error or f"latency_ms={payload.latency_ms}")
        return record

    def status(self) -> ConnectorPlatformStatus:
        records = self.list_all()
        return ConnectorPlatformStatus(
            total=len(records),
            healthy=sum(item.state == ConnectorState.healthy for item in records),
            degraded=sum(item.state in {ConnectorState.degraded, ConnectorState.error} for item in records),
            paused=sum(item.state == ConnectorState.paused for item in records),
            disconnected=sum(item.state in {ConnectorState.disabled, ConnectorState.disconnected} for item in records),
        )

    def audit(self, connector_id: UUID | None = None) -> list[ConnectorAuditRecord]:
        if connector_id is None:
            return list(self._audit)
        return [item for item in self._audit if item.connector_id == connector_id]

    def _log(self, connector_id: UUID, event: str, actor: str, details: str | None = None) -> None:
        self._audit.append(ConnectorAuditRecord(connector_id=connector_id, event=event, actor=actor, details=details))


connector_service = ConnectorService()
