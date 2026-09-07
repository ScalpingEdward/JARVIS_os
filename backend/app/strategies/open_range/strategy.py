"""Opening Range Breakout (ORB) strategy implementation.

Entry logic:
- Requires both `opening_range_high` and `opening_range_low` on the snapshot.
  Neither invented nor derived from anything else here -- if the caller has
  not computed the session's opening range yet, this strategy has nothing to
  trade on and says so.
- Long: current price closes above opening_range_high (a breakout) and HTF
  bias is not bearish (avoid buying a breakout straight into a downtrend).
- Short: symmetric -- price breaks below opening_range_low, HTF not bullish.
- A price still inside the range is not a breakout; no setup either way.

Exit logic:
- SL: just inside the broken level itself (opening_range_high for a long,
  opening_range_low for a short), with a small buffer -- if price falls back
  through the level it broke out of, the breakout has failed. This is
  standard ORB risk management: a stop at the *opposite* side of the whole
  range would make a 1:2 minimum RR essentially unreachable, since the
  measured-move reward is capped at roughly the range height while that stop
  distance is the range height plus the full breakout distance.
- Target: the classic ORB measured move -- the range's own height, projected
  from the breakout level. A single clean TP, matching the pattern's own
  logic (the measured move is the whole thesis, not a scaled partial-exit).

Risk management:
- Minimum 1:2 risk-reward ratio required, otherwise no setup.
"""

from __future__ import annotations

from ..models import HTFBias, MarketSnapshot, StrategyResult, TakeProfit, TradeSide, TradingSetup

STRATEGY_ID = "open_range"
STRATEGY_NAME = "Opening Range Breakout (Measured Move)"
MIN_RISK_REWARD = 2.0  # Minimum 1:2 RR
SL_BUFFER = 0.0005  # 0.05% buffer beyond the broken level


def evaluate(snapshot: MarketSnapshot) -> StrategyResult:
    """Evaluate a market snapshot and return a trading setup if conditions are met."""
    long_setup = _check_long_setup(snapshot)
    if long_setup:
        return StrategyResult(
            strategy_id=STRATEGY_ID,
            strategy_name=STRATEGY_NAME,
            symbol=snapshot.symbol,
            setup=long_setup,
        )

    short_setup = _check_short_setup(snapshot)
    if short_setup:
        return StrategyResult(
            strategy_id=STRATEGY_ID,
            strategy_name=STRATEGY_NAME,
            symbol=snapshot.symbol,
            setup=short_setup,
        )

    return StrategyResult(
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        symbol=snapshot.symbol,
        no_setup_reason=_no_setup_reason(snapshot),
    )


def _check_long_setup(snapshot: MarketSnapshot) -> TradingSetup | None:
    """Check for a valid long (buy) setup: breakout above the opening range high."""
    high, low = snapshot.opening_range_high, snapshot.opening_range_low
    if high is None or low is None or high <= low:
        return None
    if snapshot.htf_bias == HTFBias.bearish:
        return None
    if snapshot.current_price <= high:
        return None  # not a breakout

    entry = snapshot.ask
    stop_loss = high * (1 - SL_BUFFER)
    risk = entry - stop_loss
    if risk <= 0:
        return None

    range_height = high - low
    final_target = high + range_height  # classic ORB measured move
    reward = final_target - entry
    if reward <= 0:
        return None
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    take_profits = [TakeProfit(price=final_target, close_pct=100, label="TP (Measured Move)")]
    confidence = _confidence(rr, snapshot)
    reasoning = (
        f"Long: breakout above opening range high {high:.5f} "
        f"(range {low:.5f}-{high:.5f}), measured-move target {final_target:.5f}, RR={rr:.2f}"
    )

    return TradingSetup(
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        symbol=snapshot.symbol,
        side=TradeSide.buy,
        entry_price=entry,
        stop_loss=stop_loss,
        take_profits=take_profits,
        risk_reward=rr,
        confidence=confidence,
        reasoning=reasoning,
        invalidation_price=stop_loss,
    )


def _check_short_setup(snapshot: MarketSnapshot) -> TradingSetup | None:
    """Check for a valid short (sell) setup: breakdown below the opening range low."""
    high, low = snapshot.opening_range_high, snapshot.opening_range_low
    if high is None or low is None or high <= low:
        return None
    if snapshot.htf_bias == HTFBias.bullish:
        return None
    if snapshot.current_price >= low:
        return None  # not a breakdown

    entry = snapshot.bid
    stop_loss = low * (1 + SL_BUFFER)
    risk = stop_loss - entry
    if risk <= 0:
        return None

    range_height = high - low
    final_target = low - range_height
    if final_target <= 0:
        return None
    reward = entry - final_target
    if reward <= 0:
        return None
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    take_profits = [TakeProfit(price=final_target, close_pct=100, label="TP (Measured Move)")]
    confidence = _confidence(rr, snapshot)
    reasoning = (
        f"Short: breakdown below opening range low {low:.5f} "
        f"(range {low:.5f}-{high:.5f}), measured-move target {final_target:.5f}, RR={rr:.2f}"
    )

    return TradingSetup(
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        symbol=snapshot.symbol,
        side=TradeSide.sell,
        entry_price=entry,
        stop_loss=stop_loss,
        take_profits=take_profits,
        risk_reward=rr,
        confidence=confidence,
        reasoning=reasoning,
        invalidation_price=stop_loss,
    )


def _confidence(rr: float, snapshot: MarketSnapshot) -> float:
    """Confidence heuristic: base 55% + 10%/RR point, +10% when HTF bias
    actively agrees with the breakout direction (a bonus, not a requirement --
    a neutral HTF still allows the trade, just without the bonus)."""
    confidence = 55 + (rr * 10)
    if snapshot.htf_bias != HTFBias.neutral:
        confidence += 10
    return min(100, confidence)


def _no_setup_reason(snapshot: MarketSnapshot) -> str:
    """Generate a human-readable reason why no setup was found."""
    high, low = snapshot.opening_range_high, snapshot.opening_range_low
    if high is None or low is None:
        return "No opening range data (opening_range_high/opening_range_low not set)"
    if high <= low:
        return "Invalid opening range (high must be above low)"
    if low <= snapshot.current_price <= high:
        return f"Price still inside the opening range ({low:.5f}-{high:.5f})"
    if snapshot.current_price > high and snapshot.htf_bias == HTFBias.bearish:
        return "Broke above the range but HTF bias is bearish -- breakout not taken"
    if snapshot.current_price < low and snapshot.htf_bias == HTFBias.bullish:
        return "Broke below the range but HTF bias is bullish -- breakdown not taken"
    return "Breakout risk-reward below minimum 1:2"
