from copy import deepcopy
from uuid import UUID

from .models import SetupDecision, SetupEvaluationRequest, TradingAgentStatus, TradingSetup


class TradingAgentError(ValueError):
    pass


class TradingAgentService:
    """Scores setups and enforces advisory-only risk gates."""

    def __init__(self) -> None:
        self._items: dict[UUID, TradingSetup] = {}

    def reset(self) -> None:
        self._items.clear()

    def evaluate(self, payload: SetupEvaluationRequest) -> TradingSetup:
        snapshot, policy = payload.snapshot, payload.policy
        rr = abs(payload.take_profit - payload.entry) / abs(payload.entry - payload.stop_loss)
        score = 20
        reasons: list[str] = []
        blockers: list[str] = []

        for matched, points, label in (
            (snapshot.liquidity_sweep, 15, "liquidity sweep"),
            (snapshot.structure_shift, 20, "market structure shift"),
            (snapshot.fair_value_gap, 15, "fair value gap"),
            (snapshot.order_block, 10, "order block"),
        ):
            if matched:
                score += points
                reasons.append(label)
        if snapshot.higher_timeframe_bias.value == payload.side.value.replace("buy", "bullish").replace("sell", "bearish"):
            score += 15
            reasons.append("higher-timeframe alignment")
        if rr >= 3:
            score += 10
            reasons.append("risk-reward at least 1:3")
        elif rr < 2:
            blockers.append("risk-reward below 1:2")

        if snapshot.news_risk:
            blockers.append("high-impact news risk")
        if snapshot.spread_points > policy.max_spread_points:
            blockers.append("spread exceeds policy")
        if policy.current_open_trades >= policy.max_open_trades:
            blockers.append("maximum open trades reached")
        if policy.daily_drawdown_percent >= policy.max_daily_drawdown_percent:
            blockers.append("daily drawdown limit reached")

        score = min(score, 100)
        decision = SetupDecision.rejected if blockers else SetupDecision.valid if score >= 70 else SetupDecision.watch
        item = TradingSetup(
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            side=payload.side,
            entry=payload.entry,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            risk_reward=round(rr, 2),
            score=score,
            decision=decision,
            reasons=reasons,
            blockers=blockers,
            suggested_risk_amount=round(policy.account_balance * policy.risk_percent / 100, 2) if not blockers else 0,
        )
        self._items[item.id] = item
        return deepcopy(item)

    def get(self, setup_id: UUID) -> TradingSetup:
        if setup_id not in self._items:
            raise TradingAgentError("Trading setup not found")
        return deepcopy(self._items[setup_id])

    def list_all(self) -> list[TradingSetup]:
        return [deepcopy(item) for item in self._items.values()]

    def status(self) -> TradingAgentStatus:
        items = list(self._items.values())
        return TradingAgentStatus(
            evaluated_setups=len(items),
            valid_setups=sum(item.decision == SetupDecision.valid for item in items),
        )


trading_agent_service = TradingAgentService()
