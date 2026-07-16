from copy import deepcopy
from uuid import UUID

from .models import Decision, LiveAnalysisRecord, LiveAnalysisRequest, LiveAnalysisStatus


class LiveAnalysisError(ValueError):
    pass


class LiveAnalysisService:
    def __init__(self) -> None:
        self._items: dict[UUID, LiveAnalysisRecord] = {}

    def reset(self) -> None:
        self._items.clear()

    def evaluate(self, payload: LiveAnalysisRequest) -> LiveAnalysisRecord:
        context = payload.context
        blockers: list[str] = []
        confirmations: list[str] = []
        score = 20

        checks = [
            (context.liquidity_sweep, "liquidity sweep", 14),
            (context.structure_shift, "structure shift", 18),
            (context.fair_value_gap, "fair value gap", 12),
            (context.order_block, "order block", 10),
            (context.premium_discount_aligned, "premium/discount alignment", 8),
            (context.higher_timeframe_bias.value != "neutral", "higher-timeframe bias", 8),
        ]
        for passed, label, points in checks:
            if passed:
                confirmations.append(label)
                score += points

        if context.risk_reward >= payload.minimum_rr:
            confirmations.append("risk-reward threshold")
            score += 10
        else:
            blockers.append("risk-reward below minimum")

        if context.spread_points > payload.max_spread_points:
            blockers.append("spread above limit")
        if context.daily_drawdown_percent >= payload.max_daily_drawdown_percent:
            blockers.append("daily drawdown limit reached")
        if context.open_trades >= payload.max_open_trades:
            blockers.append("maximum open trades reached")
        if context.news_minutes is not None and context.news_minutes <= payload.news_block_minutes:
            blockers.append("high-impact news window")

        personal_adjustment = 0
        stats = payload.personal_stats
        if stats.sample_size >= 20 and stats.matching_setup_win_rate is not None:
            personal_adjustment = max(-15, min(15, round((stats.matching_setup_win_rate - 50) / 3)))
            score += personal_adjustment

        score = max(0, min(100, score))
        if blockers:
            decision = Decision.rejected
            confidence = min(score, 49)
        elif score >= 80:
            decision = Decision.valid
            confidence = score
        else:
            decision = Decision.watch
            confidence = score

        record = LiveAnalysisRecord(
            symbol=context.symbol.upper(),
            timeframe=context.timeframe.upper(),
            decision=decision,
            score=score,
            confidence_percent=confidence,
            blockers=blockers,
            confirmations=confirmations,
            personal_adjustment=personal_adjustment,
        )
        self._items[record.id] = record
        return deepcopy(record)

    def get(self, analysis_id: UUID) -> LiveAnalysisRecord:
        item = self._items.get(analysis_id)
        if item is None:
            raise LiveAnalysisError("Live analysis not found")
        return deepcopy(item)

    def list_all(self) -> list[LiveAnalysisRecord]:
        return [deepcopy(item) for item in reversed(list(self._items.values()))]

    def status(self) -> LiveAnalysisStatus:
        items = list(self._items.values())
        return LiveAnalysisStatus(
            analyses=len(items),
            valid=sum(item.decision == Decision.valid for item in items),
            watch=sum(item.decision == Decision.watch for item in items),
            rejected=sum(item.decision == Decision.rejected for item in items),
        )


live_analysis_service = LiveAnalysisService()
