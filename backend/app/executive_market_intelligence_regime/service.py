from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    MarketIntelligenceAudit,
    MarketIntelligenceCreate,
    MarketIntelligenceExecuteRequest,
    MarketIntelligenceRecord,
    MarketIntelligenceState,
    MarketIntelligenceStatus,
    MarketRegime,
    TradePermission,
)


class MarketIntelligenceRegimeService:
    def __init__(self) -> None:
        self._records: dict[UUID, MarketIntelligenceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[MarketIntelligenceAudit] = []

    def create(self, payload: MarketIntelligenceCreate) -> MarketIntelligenceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, permission, detail, metrics, reasons = self._evaluate(payload)
        record = MarketIntelligenceRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            permission=permission,
            detail=detail,
            request=payload,
            reasons=reasons,
            **metrics,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, p: MarketIntelligenceCreate):
        regimes = [item.regime for item in p.timeframes]
        dominant = Counter(regimes).most_common(1)[0][0]
        alignment = regimes.count(dominant) / len(regimes) * 100
        volatility = max(p.atr_percentile, p.realized_volatility_percentile)
        liquidity = p.liquidity_score
        macro_score = 100.0
        reasons: list[str] = []

        high_impact = [event for event in p.macro_events if event.impact == "high"]
        for event in high_impact:
            if -p.news_blackout_after_minutes <= event.minutes_until_event <= p.news_blackout_before_minutes:
                macro_score = 0
                reasons.append(f"high-impact news blackout: {event.name}")

        session_score = {
            "overlap": 100,
            "london": 90,
            "new-york": 90,
            "asian": 65,
            "lunch": 35,
            "closed": 0,
        }[p.session]
        if p.killzone_active:
            session_score = min(100, session_score + 5)

        asset_environment = {
            "metals": p.gold_environment_score,
            "crypto": p.crypto_environment_score,
            "forex": 100 - abs(p.usd_strength_score - 50),
            "indices": 75 if p.risk_environment.value != "neutral" else 60,
        }[p.asset_class]
        volatility_score = max(0.0, 100 - max(0.0, volatility - 50) * 2)
        dynamic_score = round(
            alignment * 0.25
            + volatility_score * 0.20
            + liquidity * 0.20
            + macro_score * 0.15
            + session_score * 0.10
            + asset_environment * 0.10,
            2,
        )
        metrics = {
            "dominant_regime": dominant,
            "regime_alignment_score": round(alignment, 2),
            "volatility_score": round(volatility_score, 2),
            "liquidity_environment_score": round((liquidity + session_score) / 2, 2),
            "macro_environment_score": round(macro_score, 2),
            "dynamic_market_score": dynamic_score,
        }

        def blocked(state: MarketIntelligenceState, detail: str):
            reasons.append(detail)
            return state, TradePermission.BLOCKED, detail, metrics, reasons

        if p.upstream_risk_brain_blocked:
            return blocked(MarketIntelligenceState.BLOCKED, "upstream Risk Brain hard block")
        if not p.account_risk_approved or not p.prop_rules_approved:
            return blocked(MarketIntelligenceState.BLOCKED, "account-risk and prop-rule approval required")
        if p.timestamp_age_seconds > p.max_data_age_seconds:
            return blocked(MarketIntelligenceState.DATA_STALE, "market intelligence snapshot is stale")
        if p.rollover_active:
            return blocked(MarketIntelligenceState.ROLLOVER_BLOCKED, "rollover window blocks new exposure")
        if p.session == "closed":
            return blocked(MarketIntelligenceState.LIQUIDITY_REJECTED, "market session is closed")
        if macro_score == 0:
            return blocked(MarketIntelligenceState.NEWS_BLACKOUT, reasons[0])
        if p.spread_bps > p.max_spread_bps:
            return blocked(MarketIntelligenceState.SPREAD_REJECTED, "spread ceiling exceeded")
        if p.liquidity_score < p.minimum_liquidity_score:
            return blocked(MarketIntelligenceState.LIQUIDITY_REJECTED, "liquidity floor not met")
        if volatility > p.max_volatility_percentile or dominant == MarketRegime.VOLATILITY_SPIKE:
            return blocked(MarketIntelligenceState.VOLATILITY_REJECTED, "volatility hazard blocks new exposure")
        if p.required_regimes and dominant not in p.required_regimes:
            return blocked(MarketIntelligenceState.REGIME_REJECTED, "dominant market regime is not approved")
        if p.correlation_score > p.max_correlation_score:
            return blocked(MarketIntelligenceState.CORRELATION_REJECTED, "correlation ceiling exceeded")
        if p.risk_environment not in p.allowed_risk_environments:
            return blocked(MarketIntelligenceState.RISK_ENVIRONMENT_REJECTED, "risk environment is not approved")
        if dynamic_score < 55:
            return blocked(MarketIntelligenceState.REGIME_REJECTED, "dynamic market score below trade threshold")
        if not p.human_approved:
            return MarketIntelligenceState.APPROVAL_REQUIRED, TradePermission.BLOCKED, "market is eligible but human approval is required", metrics, ["human approval required"]
        return MarketIntelligenceState.MARKET_READY, TradePermission.TRADE_ALLOWED, "market environment approved for governed trading", metrics, []

    def execute(self, record_id: UUID, workspace_id: str, request: MarketIntelligenceExecuteRequest) -> MarketIntelligenceRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("market intelligence record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if request.action == "activate":
            if not approved:
                raise ValueError("human approval required")
            if record.state != MarketIntelligenceState.APPROVAL_REQUIRED and record.permission != TradePermission.TRADE_ALLOWED:
                raise ValueError("market intelligence cannot be activated from current state")
            record.state = MarketIntelligenceState.TRADE_ALLOWED
            record.permission = TradePermission.TRADE_ALLOWED
            record.detail = "governed market trade permission activated"
        elif request.action == "monitor":
            record.state = MarketIntelligenceState.MONITORING
            record.detail = "market environment under active monitoring"
        else:
            raise ValueError("unsupported action")
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> MarketIntelligenceRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[MarketIntelligenceRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> MarketIntelligenceStatus:
        records = self.list_records(workspace_id)
        return MarketIntelligenceStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            allowed_records=sum(record.permission == TradePermission.TRADE_ALLOWED for record in records),
            blocked_records=sum(record.permission == TradePermission.BLOCKED for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[MarketIntelligenceAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: MarketIntelligenceRecord, actor_id: str, action: str) -> None:
        self._audit.append(MarketIntelligenceAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            permission=record.permission,
            detail=record.detail,
        ))


market_intelligence_regime_service = MarketIntelligenceRegimeService()
