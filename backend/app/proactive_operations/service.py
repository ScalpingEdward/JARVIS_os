from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AlertSeverity,
    AlertStatus,
    OperationsAlert,
    OperationsEventCreate,
    OperationsStatus,
)


class ProactiveOperationsService:
    """Prioritizes events and produces advisory executive alerts."""

    _severity_weight = {
        AlertSeverity.info: 5,
        AlertSeverity.low: 15,
        AlertSeverity.medium: 30,
        AlertSeverity.high: 45,
        AlertSeverity.critical: 60,
    }

    def __init__(self) -> None:
        self._alerts: dict[UUID, OperationsAlert] = {}
        self._deduplication: dict[str, UUID] = {}
        self._suppressed_duplicates = 0

    def reset(self) -> None:
        self._alerts.clear()
        self._deduplication.clear()
        self._suppressed_duplicates = 0

    def ingest(self, payload: OperationsEventCreate) -> OperationsAlert:
        key = payload.deduplication_key
        if key and key in self._deduplication:
            existing = self._alerts[self._deduplication[key]]
            if existing.status not in {AlertStatus.resolved, AlertStatus.suppressed}:
                self._suppressed_duplicates += 1
                return existing.model_copy(deep=True)

        score = min(
            100.0,
            self._severity_weight[payload.severity]
            + payload.urgency * 20
            + payload.impact * 15
            + payload.confidence * 5
            + (10 if payload.requires_human_approval else 0),
        )
        message = self._executive_message(payload, score)
        record = OperationsAlert(
            **payload.model_dump(),
            priority_score=round(score, 2),
            executive_message=message,
        )
        self._alerts[record.id] = record
        if key:
            self._deduplication[key] = record.id
        return record.model_copy(deep=True)

    def list_all(self, status: AlertStatus | None = None) -> list[OperationsAlert]:
        items = [item for item in self._alerts.values() if status is None or item.status == status]
        return [item.model_copy(deep=True) for item in sorted(items, key=lambda x: (x.priority_score, x.created_at), reverse=True)]

    def get(self, alert_id: UUID) -> OperationsAlert | None:
        item = self._alerts.get(alert_id)
        return item.model_copy(deep=True) if item else None

    def update_status(self, alert_id: UUID, status: AlertStatus) -> OperationsAlert | None:
        item = self._alerts.get(alert_id)
        if item is None:
            return None
        item.status = status
        item.updated_at = datetime.now(timezone.utc)
        return item.model_copy(deep=True)

    def status(self) -> OperationsStatus:
        open_items = [a for a in self._alerts.values() if a.status in {AlertStatus.new, AlertStatus.acknowledged, AlertStatus.snoozed}]
        return OperationsStatus(
            total_alerts=len(self._alerts),
            open_alerts=len(open_items),
            critical_alerts=sum(a.severity == AlertSeverity.critical for a in open_items),
            pending_approvals=sum(a.requires_human_approval for a in open_items),
            suppressed_duplicates=self._suppressed_duplicates,
        )

    @staticmethod
    def _executive_message(payload: OperationsEventCreate, score: float) -> str:
        prefix = "Immediate attention" if score >= 80 else "Priority review" if score >= 60 else "Monitor"
        approval = " Human approval is required." if payload.requires_human_approval else ""
        return f"{prefix}, MASTER Brano: {payload.title}. {payload.summary}{approval}"


proactive_operations_service = ProactiveOperationsService()
