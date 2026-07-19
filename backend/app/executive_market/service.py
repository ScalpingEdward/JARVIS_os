from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, ExecutiveMarketPortfolio, MarketPortfolioCreate, MarketStatusResponse, SignalUpdate


class ExecutiveMarketService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveMarketPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: MarketPortfolioCreate) -> ExecutiveMarketPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._items.values()):
            raise ValueError("Executive market portfolio already exists")
        item = ExecutiveMarketPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._record(item.workspace_id, payload.actor_id, "market_portfolio_created", item.portfolio_id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveMarketPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveMarketPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> MarketStatusResponse:
        items = self.list_portfolios(workspace_id)
        return MarketStatusResponse(workspace_id=workspace_id, portfolios=len(items), assessed_portfolios=sum(i.assessed_at is not None for i in items))

    def update_signal(self, portfolio_id: UUID, workspace_id: str, payload: SignalUpdate) -> ExecutiveMarketPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive market portfolio not found")
        signal = next((signal for signal in item.signals if signal.signal_id == payload.signal_id), None)
        if signal is None:
            raise KeyError("Market signal not found")
        for field in ("confidence", "impact", "direction"):
            value = getattr(payload, field)
            if value is not None:
                setattr(signal, field, value)
        self._record(workspace_id, payload.actor_id, "market_signal_updated", portfolio_id)
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveMarketPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive market portfolio not found")
        total_size = sum(segment.market_size for segment in item.segments) or 1
        item.weighted_growth_rate = round(sum(s.market_size * s.growth_rate for s in item.segments) / total_size, 2)
        item.opportunity_score = round(sum(s.attractiveness * max(s.growth_rate, 0) / 100 for s in item.segments) / len(item.segments), 2)
        negative = [s for s in item.signals if s.direction.value == "negative"]
        signal_threat = sum(s.confidence * s.impact / 100 for s in negative) / max(len(negative), 1)
        competitor_threat = sum(c.strategic_threat for c in item.competitors) / max(len(item.competitors), 1)
        item.threat_score = round((signal_threat + competitor_threat) / 2, 2)
        item.positioning_score = round(sum((s.current_share / max(s.target_share, 1)) * s.attractiveness for s in item.segments) / len(item.segments), 2)
        item.whitespace_segments = [s.segment_id for s in item.segments if s.attractiveness >= 70 and s.current_share < s.target_share]
        item.high_threat_competitors = [c.competitor_id for c in item.competitors if c.strategic_threat >= 70]
        recs = []
        if item.whitespace_segments:
            recs.append("Prioritize investment in high-attractiveness whitespace segments")
        if item.high_threat_competitors:
            recs.append("Prepare differentiated response plans for high-threat competitors")
        if item.threat_score >= 60:
            recs.append("Escalate market threat review to executive steering")
        if item.weighted_growth_rate < 0:
            recs.append("Rebalance exposure away from contracting segments")
        item.recommendations = recs or ["Maintain current positioning and continue signal monitoring"]
        item.assessed_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "market_portfolio_assessed", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, portfolio_id: UUID) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, portfolio_id=portfolio_id))


executive_market_service = ExecutiveMarketService()
