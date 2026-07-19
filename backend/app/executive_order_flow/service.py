from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    DataQuality,
    ExecutiveOrderFlowPortfolio,
    MarketSide,
    OrderFlowAssessment,
    OrderFlowPortfolioCreate,
    OrderFlowRiskUpdate,
    OrderFlowStatusResponse,
)


class ExecutiveOrderFlowService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveOrderFlowPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: OrderFlowPortfolioCreate) -> ExecutiveOrderFlowPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower() for item in self._items.values()):
            raise ValueError("Executive order-flow portfolio already exists")
        item = ExecutiveOrderFlowPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._record(item.workspace_id, "system", "portfolio.created", item.portfolio_id)
        return item

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveOrderFlowPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveOrderFlowPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> OrderFlowStatusResponse:
        items = self.list_portfolios(workspace_id)
        snapshots = [snapshot for item in items for snapshot in item.snapshots]
        return OrderFlowStatusResponse(
            workspace_id=workspace_id,
            portfolio_count=len(items),
            snapshot_count=len(snapshots),
            exchange_quality_snapshot_count=sum(snapshot.data_quality == DataQuality.exchange for snapshot in snapshots),
        )

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveOrderFlowPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive order-flow portfolio not found")
        levels = [level for snapshot in item.snapshots for level in snapshot.levels]
        ask = sum(level.ask_volume for level in levels)
        bid = sum(level.bid_volume for level in levels)
        total = ask + bid
        delta = ask - bid
        ratio = delta / total if total else 0.0
        imbalanced = sum(1 for level in levels if max(level.ask_volume, level.bid_volume) >= 3 * max(1.0, min(level.ask_volume, level.bid_volume)))
        imbalance_score = min(100.0, imbalanced / max(1, len(levels)) * 200)
        absorption_candidates = sum(1 for level in levels if level.ask_volume + level.bid_volume > total / max(1, len(levels)) * 1.8 and abs(level.delta) < (level.ask_volume + level.bid_volume) * 0.2)
        absorption_score = min(100.0, absorption_candidates / max(1, len(levels)) * 250)
        quality_map = {DataQuality.simulated: 20.0, DataQuality.broker_tick: 45.0, DataQuality.consolidated: 75.0, DataQuality.exchange: 100.0}
        reliability = sum(quality_map[snapshot.data_quality] for snapshot in item.snapshots) / len(item.snapshots)
        spread_scores = []
        for snapshot in item.snapshots:
            if snapshot.best_bid is not None and snapshot.best_ask is not None and snapshot.best_ask > 0:
                spread_scores.append(max(0.0, 100.0 - ((snapshot.best_ask - snapshot.best_bid) / snapshot.best_ask * 10000)))
        liquidity = sum(spread_scores) / len(spread_scores) if spread_scores else 50.0
        risk = sum(r.severity * r.probability / 100 for r in item.risks) / max(1, len(item.risks))
        bias = MarketSide.buy if ratio > 0.08 else MarketSide.sell if ratio < -0.08 else MarketSide.neutral
        reasons: list[str] = []
        no_trade = reliability < 70 or liquidity < 40 or risk > 65 or bias == MarketSide.neutral
        if reliability < 70:
            reasons.append("Order-flow data quality is insufficient for execution-grade decisions")
        if liquidity < 40:
            reasons.append("Liquidity conditions are weak or spread quality is poor")
        if risk > 65:
            reasons.append("Microstructure risk exceeds the permitted threshold")
        if bias == MarketSide.neutral:
            reasons.append("Aggressor flow does not provide a directional edge")
        recommendations = [
            "Require exchange-grade trade classification before live automation",
            "Confirm footprint signals with higher-timeframe structure and liquidity context",
            "Use no-trade gating when data reliability or liquidity quality deteriorates",
        ]
        item.assessment = OrderFlowAssessment(
            cumulative_delta=round(delta, 4), delta_ratio=round(ratio, 6), imbalance_score=round(imbalance_score, 2),
            absorption_score=round(absorption_score, 2), liquidity_quality_score=round(liquidity, 2),
            data_reliability_score=round(reliability, 2), risk_exposure_score=round(risk, 2),
            directional_bias=bias, no_trade=no_trade, reasons=reasons, recommendations=recommendations,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "portfolio.assessed", portfolio_id)
        return item

    def update_risk(self, portfolio_id: UUID, workspace_id: str, payload: OrderFlowRiskUpdate) -> ExecutiveOrderFlowPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive order-flow portfolio not found")
        risk = next((risk for risk in item.risks if risk.risk_id == payload.risk_id), None)
        if risk is None:
            raise KeyError("Microstructure risk not found")
        updates = payload.model_dump(exclude_none=True, exclude={"risk_id", "actor_id"})
        for key, value in updates.items():
            setattr(risk, key, value)
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "risk.updated", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, portfolio_id: UUID) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, portfolio_id=portfolio_id))


executive_order_flow_service = ExecutiveOrderFlowService()
