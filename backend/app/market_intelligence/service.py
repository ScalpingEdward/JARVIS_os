from collections import Counter
from datetime import datetime, timezone

from .models import (
    Direction,
    IntelligenceStatus,
    MarketRegime,
    MarketSnapshot,
    MarketSnapshotCreate,
    WatchlistItem,
)


class MarketIntelligenceService:
    def __init__(self) -> None:
        self._snapshots: list[MarketSnapshot] = []

    def reset(self) -> None:
        self._snapshots.clear()

    def analyze(self, payload: MarketSnapshotCreate) -> MarketSnapshot:
        directions = [item.direction for item in payload.timeframes]
        counts = Counter(directions)
        bias = counts.most_common(1)[0][0] if directions else Direction.neutral
        agreement = counts.get(bias, 0) / max(len(directions), 1)

        structure = self._average([item.structure_score for item in payload.timeframes], 0.5)
        liquidity = self._average([item.liquidity_score for item in payload.timeframes], 0.5)
        volatility = self._average([item.volatility_score for item in payload.timeframes], 0.5)
        macro_risk = max((event.impact for event in payload.macro_events), default=0)
        correlation_risk = max((abs(item.coefficient) for item in payload.correlations), default=0)

        regime = self._regime(structure, liquidity, volatility, agreement)
        confidence = self._clamp(agreement * 0.45 + structure * 0.35 + liquidity * 0.20)
        risk = self._clamp(macro_risk * 0.45 + volatility * 0.25 + correlation_risk * 0.15 + (1 - payload.spread_score) * 0.15)
        opportunity = self._clamp(confidence * 0.45 + liquidity * 0.25 + payload.session_liquidity * 0.20 + structure * 0.10 - risk * 0.35)

        rationale = [
            f"Multi-timeframe agreement: {agreement:.0%}",
            f"Structure quality: {structure:.0%}",
            f"Liquidity quality: {liquidity:.0%}",
            f"Macro risk: {macro_risk:.0%}",
        ]
        snapshot = MarketSnapshot(
            symbol=payload.symbol.upper(),
            asset_class=payload.asset_class,
            priority=payload.priority,
            regime=regime,
            bias=bias,
            confidence=round(confidence, 4),
            risk_score=round(risk, 4),
            opportunity_score=round(opportunity, 4),
            timeframes=payload.timeframes,
            correlations=payload.correlations,
            macro_events=payload.macro_events,
            rationale=rationale,
            created_at=datetime.now(timezone.utc),
        )
        self._snapshots.append(snapshot)
        return snapshot

    def list_all(self) -> list[MarketSnapshot]:
        return sorted(self._snapshots, key=lambda item: (item.priority, -item.opportunity_score, item.created_at))

    def latest(self, symbol: str) -> MarketSnapshot | None:
        symbol = symbol.upper()
        return next((item for item in reversed(self._snapshots) if item.symbol == symbol), None)

    def watchlist(self, limit: int = 15) -> list[WatchlistItem]:
        latest_by_symbol: dict[str, MarketSnapshot] = {}
        for item in self._snapshots:
            latest_by_symbol[item.symbol] = item
        ranked = sorted(latest_by_symbol.values(), key=lambda item: (item.priority, -item.opportunity_score, item.risk_score))
        return [
            WatchlistItem(
                symbol=item.symbol,
                priority=item.priority,
                opportunity_score=item.opportunity_score,
                risk_score=item.risk_score,
                regime=item.regime,
                bias=item.bias,
            )
            for item in ranked[:limit]
        ]

    def status(self) -> IntelligenceStatus:
        latest = {item.symbol: item for item in self._snapshots}
        values = list(latest.values())
        return IntelligenceStatus(
            total_snapshots=len(self._snapshots),
            tracked_symbols=len(values),
            high_priority=sum(item.priority <= 2 for item in values),
            elevated_risk=sum(item.risk_score >= 0.65 for item in values),
        )

    @staticmethod
    def _average(values: list[float], default: float) -> float:
        return sum(values) / len(values) if values else default

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0, min(1, value))

    @staticmethod
    def _regime(structure: float, liquidity: float, volatility: float, agreement: float) -> MarketRegime:
        if volatility >= 0.75:
            return MarketRegime.volatile
        if agreement >= 0.7 and structure >= 0.65:
            return MarketRegime.trending
        if volatility <= 0.3 and liquidity <= 0.5:
            return MarketRegime.compression
        if agreement <= 0.45 and volatility <= 0.6:
            return MarketRegime.ranging
        return MarketRegime.transition


market_intelligence_service = MarketIntelligenceService()
