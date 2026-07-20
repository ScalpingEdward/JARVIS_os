from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    MarketDataState,
    MarketDataStatusResponse,
    MarketDataSubscription,
    MarketDataSubscriptionCreate,
    RecoverStreamRequest,
)


class ExecutiveMarketDataService:
    def __init__(self) -> None:
        self._records: dict[UUID, MarketDataSubscription] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._subscription_ids: set[tuple[str, UUID]] = set()
        self._audit: list[AuditRecord] = []

    def reset(self) -> None:
        self._records.clear()
        self._source_keys.clear()
        self._subscription_ids.clear()
        self._audit.clear()

    def subscribe(self, payload: MarketDataSubscriptionCreate) -> MarketDataSubscription:
        source_key = (payload.workspace_id, payload.source_key)
        subscription_key = (payload.workspace_id, payload.subscription_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate market data source key")
        if subscription_key in self._subscription_ids:
            raise ValueError("Duplicate market data subscription ID")

        state, reasons, action = self._evaluate(payload)
        recovery_required = state in {
            MarketDataState.stream_degraded,
            MarketDataState.gap_detected,
            MarketDataState.latency_exceeded,
        }
        record = MarketDataSubscription(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            subscription_id=payload.subscription_id,
            broker_session_id=payload.broker_session_id,
            feed_id=payload.feed_id,
            feed_kind=payload.feed_kind,
            stream_kind=payload.stream_kind,
            mapping=payload.mapping,
            timeframe=payload.timeframe,
            state=state,
            stream_ready=state == MarketDataState.stream_ready,
            recovery_required=recovery_required,
            failover_available=payload.observation.failover_feed_available,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._subscription_ids.add(subscription_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, subscription_id=record.subscription_id, actor_id=payload.actor_id, action="market-data-subscription-assessed"))
        return record

    def _evaluate(self, payload: MarketDataSubscriptionCreate) -> tuple[MarketDataState, list[str], str]:
        o, p = payload.observation, payload.policy
        if not payload.risk_brain_clear:
            return MarketDataState.blocked, ["Risk Brain blocked market-data activation"], "keep-stream-blocked"
        if p.require_ready_broker_session and o.broker_session_state != "session-ready":
            return MarketDataState.blocked, ["Broker session is not ready"], "restore-broker-session"
        if p.require_registered_symbol and (not o.symbol_registered or not o.symbol_mapping_valid or not o.instrument_discovery_complete):
            return MarketDataState.symbol_unknown, ["Symbol registry, mapping or instrument discovery is incomplete"], "resolve-symbol-mapping"
        if p.require_available_feed and (not o.feed_available or not o.stream_connected):
            return MarketDataState.feed_unavailable, ["Market-data feed or stream connection is unavailable"], "connect-or-failover"
        if not o.market_open:
            return MarketDataState.market_closed, ["Trading session is closed"], "wait-for-market-open"
        if p.reject_gaps and o.gap_detected:
            return MarketDataState.gap_detected, ["Sequence gap detected in market-data stream"], "replay-and-recover"
        if (p.reject_invalid_prices and o.zero_or_negative_price) or (p.reject_outliers and o.outlier_detected) or not o.spread_valid or not o.volume_valid or not o.candle_integrity_valid:
            return MarketDataState.invalid_market_data, ["Price, outlier, spread, volume or candle-integrity validation failed"], "quarantine-market-data"
        if o.latency_ms > p.max_latency_ms or o.clock_drift_ms > p.max_clock_drift_ms:
            return MarketDataState.latency_exceeded, ["Latency or clock-drift budget exceeded"], "switch-feed-or-resynchronize-clock"
        stream_ok = o.heartbeat_fresh and o.sequence_valid and o.timestamp_valid
        duplicate_ok = not p.reject_duplicate_ticks or not o.duplicate_tick_detected
        recovery_ok = not o.gap_detected or (o.replay_available and o.recovery_acknowledged)
        if not stream_ok or not duplicate_ok or not recovery_ok:
            return MarketDataState.stream_degraded, ["Heartbeat, sequence, timestamp, duplicate or recovery evidence is incomplete"], "recover-or-failover"
        return MarketDataState.stream_ready, ["Market-data stream passed symbol, quality and stream governance"], "allow-market-data-consumption"

    def list_subscriptions(self, workspace_id: str) -> list[MarketDataSubscription]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> MarketDataSubscription | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def recover(self, request: RecoverStreamRequest) -> MarketDataSubscription:
        record = next((r for r in self._records.values() if r.workspace_id == request.workspace_id and r.subscription_id == request.subscription_id), None)
        if record is None:
            raise KeyError("Market-data subscription not found")
        if not request.replay_completed or not request.recovery_acknowledged:
            raise ValueError("Replay completion and recovery acknowledgement are required")
        record.recovery_required = False
        record.stream_ready = True
        record.state = MarketDataState.stream_ready
        record.recommended_action = "allow-market-data-consumption"
        record.reasons = ["Replay and stream recovery acknowledgement recorded"]
        self._audit.append(AuditRecord(workspace_id=request.workspace_id, assessment_id=record.id, subscription_id=record.subscription_id, actor_id=request.actor_id, action="market-data-stream-recovered"))
        return record

    def status(self, workspace_id: str) -> MarketDataStatusResponse:
        records = self.list_subscriptions(workspace_id)
        ready = sum(r.stream_ready for r in records)
        return MarketDataStatusResponse(workspace_id=workspace_id, subscriptions=len(records), stream_ready=ready, degraded_or_blocked=len(records) - ready, latest_state=records[-1].state if records else None)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [r for r in self._audit if r.workspace_id == workspace_id]


executive_market_data_service = ExecutiveMarketDataService()
