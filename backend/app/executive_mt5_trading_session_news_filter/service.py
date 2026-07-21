from datetime import timedelta
from uuid import UUID

from .models import (
    AuditRecord,
    SessionNewsAssessment,
    SessionNewsAssessmentCreate,
    SessionNewsExecuteRequest,
    SessionNewsState,
    SessionNewsStatus,
)


class TradingSessionNewsFilterService:
    def __init__(self) -> None:
        self._records: dict[UUID, SessionNewsAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: SessionNewsAssessmentCreate) -> tuple[SessionNewsState, list[str]]:
        if payload.risk_brain_blocked:
            return SessionNewsState.BLOCKED, ["Risk Brain blocked trading-window activation"]
        if not payload.pending_order_ready:
            return SessionNewsState.PENDING_ORDER_REQUIRED, ["v18.91 pending-order dependency is not ready"]
        if not payload.clock_synchronized or abs(payload.clock_drift_seconds) > payload.max_clock_drift_seconds:
            return SessionNewsState.CLOCK_UNSYNCED, ["Runtime clock is not synchronized within tolerance"]
        if not payload.market_open:
            return SessionNewsState.MARKET_CLOSED, ["Broker market is closed"]
        if not payload.session_open:
            return SessionNewsState.SESSION_CLOSED, [f"Trading session {payload.session_name} is closed"]
        if payload.rollover_window:
            return SessionNewsState.ROLLOVER_BLOCKED, ["Broker rollover window blocks new exposure"]
        if not payload.news_feed_connected or payload.news_snapshot_age_seconds > payload.max_news_snapshot_age_seconds:
            return SessionNewsState.NEWS_DATA_STALE, ["Economic-calendar evidence is unavailable or stale"]
        if payload.impacted_currency and payload.high_impact_event and payload.event_time is not None:
            start = payload.event_time - timedelta(minutes=payload.blackout_before_minutes)
            end = payload.event_time + timedelta(minutes=payload.blackout_after_minutes)
            if start <= payload.evaluated_at <= end:
                return SessionNewsState.NEWS_BLACKOUT, ["High-impact news blackout is active"]
        if payload.maximum_spread_points > 0 and payload.current_spread_points > payload.maximum_spread_points:
            return SessionNewsState.SPREAD_REJECTED, ["Current spread exceeds configured session limit"]
        if payload.liquidity_score < payload.minimum_liquidity_score:
            return SessionNewsState.LIQUIDITY_REJECTED, ["Observed liquidity is below the configured floor"]
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return SessionNewsState.RISK_REJECTED, ["Account-risk and prop-rule approval are mandatory"]
        if not payload.human_approved:
            return SessionNewsState.APPROVAL_REQUIRED, ["Human approval is required"]
        if payload.terminal_error:
            return SessionNewsState.FAILED, [payload.terminal_error]
        return SessionNewsState.WINDOW_READY, []

    def create(self, payload: SessionNewsAssessmentCreate) -> SessionNewsAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate source_key in workspace")
        state, reasons = self._evaluate(payload)
        record = SessionNewsAssessment(state=state, reasons=reasons, payload=payload)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="assessment-created", actor_id=payload.actor_id, record_id=record.id))
        return record

    def execute(self, record_id: UUID, workspace_id: str, request: SessionNewsExecuteRequest) -> SessionNewsAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("Session/news assessment not found")
        payload = record.payload.model_copy(update=request.model_dump(exclude={"actor_id"}, exclude_none=True))
        state, reasons = self._evaluate(payload)
        updated = record.model_copy(update={"payload": payload, "state": state, "reasons": reasons})
        self._records[record_id] = updated
        self._audit.append(AuditRecord(workspace_id=workspace_id, action="assessment-executed", actor_id=request.actor_id, record_id=record_id))
        return updated

    def get(self, record_id: UUID, workspace_id: str) -> SessionNewsAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.payload.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[SessionNewsAssessment]:
        return [record for record in self._records.values() if record.payload.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> SessionNewsStatus:
        records = self.list_records(workspace_id)
        return SessionNewsStatus(workspace_id=workspace_id, latest_state=records[-1].state if records else None, count=len(records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


trading_session_news_filter_service = TradingSessionNewsFilterService()
