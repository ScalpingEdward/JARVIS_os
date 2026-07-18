from datetime import datetime, timezone
from uuid import UUID

from .models import (
    CommandCenterMetrics,
    CommandCenterOverview,
    CommandCenterStatus,
    DashboardFilter,
    DomainSummary,
    Priority,
    SignalCreate,
    SignalDomain,
    SignalRecord,
    SignalState,
    TimelinePoint,
)


_STATE_WEIGHT = {
    SignalState.HEALTHY: 100.0,
    SignalState.INFO: 90.0,
    SignalState.UNKNOWN: 60.0,
    SignalState.WARNING: 55.0,
    SignalState.DEGRADED: 35.0,
    SignalState.CRITICAL: 10.0,
    SignalState.OFFLINE: 0.0,
}

_PRIORITY_WEIGHT = {
    Priority.LOW: 1,
    Priority.MEDIUM: 2,
    Priority.HIGH: 3,
    Priority.CRITICAL: 4,
}

_STATE_RANK = {
    SignalState.HEALTHY: 0,
    SignalState.INFO: 1,
    SignalState.UNKNOWN: 2,
    SignalState.WARNING: 3,
    SignalState.DEGRADED: 4,
    SignalState.CRITICAL: 5,
    SignalState.OFFLINE: 6,
}


class CommandCenterService:
    def __init__(self) -> None:
        self.signals: dict[UUID, SignalRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> CommandCenterStatus:
        return CommandCenterStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id) if entity_id else None,
            "created_at": datetime.now(timezone.utc),
        })

    def record_signal(self, payload: SignalCreate) -> SignalRecord:
        item = SignalRecord(**payload.model_dump())
        self.signals[item.id] = item
        self._audit(item.workspace_id, "command-center.signal-recorded", item.reporter_id, item.id)
        return item

    def list_signals(self, filters: DashboardFilter) -> list[SignalRecord]:
        items = [item for item in self.signals.values() if item.workspace_id == filters.workspace_id]
        if filters.domains:
            items = [item for item in items if item.domain in filters.domains]
        if filters.states:
            items = [item for item in items if item.state in filters.states]
        if filters.priorities:
            items = [item for item in items if item.priority in filters.priorities]
        items.sort(
            key=lambda item: (
                _PRIORITY_WEIGHT[item.priority],
                _STATE_RANK[item.state],
                item.observed_at,
            ),
            reverse=True,
        )
        return items[: filters.limit]

    def _workspace_signals(self, workspace_id: str) -> list[SignalRecord]:
        return [item for item in self.signals.values() if item.workspace_id == workspace_id]

    def _score(self, signals: list[SignalRecord]) -> float:
        if not signals:
            return 100.0
        weighted_total = sum(_STATE_WEIGHT[item.state] * _PRIORITY_WEIGHT[item.priority] for item in signals)
        total_weight = sum(_PRIORITY_WEIGHT[item.priority] for item in signals)
        return round(weighted_total / total_weight, 2)

    def _overall_state(self, signals: list[SignalRecord]) -> SignalState:
        if not signals:
            return SignalState.UNKNOWN
        return max(signals, key=lambda item: _STATE_RANK[item.state]).state

    def overview(self, workspace_id: str, limit: int = 10) -> CommandCenterOverview:
        signals = self._workspace_signals(workspace_id)
        domains: list[DomainSummary] = []
        for domain in SignalDomain:
            domain_signals = [item for item in signals if item.domain == domain]
            if not domain_signals:
                continue
            domains.append(DomainSummary(
                domain=domain,
                total=len(domain_signals),
                critical=sum(item.state in {SignalState.CRITICAL, SignalState.OFFLINE} for item in domain_signals),
                warning_or_degraded=sum(item.state in {SignalState.WARNING, SignalState.DEGRADED} for item in domain_signals),
                healthy=sum(item.state == SignalState.HEALTHY for item in domain_signals),
                score=self._score(domain_signals),
            ))
        priorities = sorted(
            signals,
            key=lambda item: (_PRIORITY_WEIGHT[item.priority], _STATE_RANK[item.state], item.observed_at),
            reverse=True,
        )[:limit]
        return CommandCenterOverview(
            workspace_id=workspace_id,
            overall_state=self._overall_state(signals),
            readiness_score=self._score(signals),
            total_signals=len(signals),
            critical_signals=sum(item.state == SignalState.CRITICAL for item in signals),
            warning_signals=sum(item.state in {SignalState.WARNING, SignalState.DEGRADED} for item in signals),
            offline_signals=sum(item.state == SignalState.OFFLINE for item in signals),
            healthy_signals=sum(item.state == SignalState.HEALTHY for item in signals),
            domains=domains,
            top_priorities=priorities,
        )

    def timeline(self, workspace_id: str, limit: int = 100) -> list[TimelinePoint]:
        items = sorted(self._workspace_signals(workspace_id), key=lambda item: item.observed_at, reverse=True)[:limit]
        return [TimelinePoint(
            observed_at=item.observed_at,
            signal_id=item.id,
            domain=item.domain,
            state=item.state,
            priority=item.priority,
            title=item.title,
        ) for item in items]

    def metrics(self, workspace_id: str) -> CommandCenterMetrics:
        signals = self._workspace_signals(workspace_id)
        return CommandCenterMetrics(
            workspace_id=workspace_id,
            signal_records=len(signals),
            monitored_modules=len({item.module for item in signals}),
            monitored_domains=len({item.domain for item in signals}),
            critical_items=sum(item.state in {SignalState.CRITICAL, SignalState.OFFLINE} for item in signals),
            readiness_score=self._score(signals),
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [item for item in self.audit if item["workspace_id"] == workspace_id]


command_center_service = CommandCenterService()
