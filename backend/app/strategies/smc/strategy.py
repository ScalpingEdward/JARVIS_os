"""SMC (Smart Money Concepts) strategy implementation -- premium/discount + Order Block.

Entry logic:
- Requires a bracketing range: the nearest structure high above current price
  and the nearest structure low below it. No range, no setup -- this strategy
  has nothing to say about price outside a defined structure.
- Long: HTF bullish + current price sits in the discount half (lower 50%) of
  that range + price is mitigating an unmitigated bullish Order Block inside
  the discount half. Institutional logic: smart money accumulates from
  discount, not premium.
- Short: symmetric -- HTF bearish + premium half (upper 50%) + bearish OB
  mitigation inside it.

Exit logic:
- SL: below the Order Block low (long) / above the Order Block high (short),
  with the same 0.05% buffer convention as scalping_3tp.
- Target: the opposing structure level that bounds the range (the range's
  other side) -- a single clean TP, not scaled. The premise here is a range
  run, not a partial-profit scalp.

Risk management:
- Minimum 1:2 risk-reward ratio required, otherwise no setup.
"""

from __future__ import annotations

from ..models import (
    HTFBias,
    MarketSnapshot,
    OrderBlock,
    OrderBlockType,
    StrategyResult,
    TakeProfit,
    TradeSide,
    TradingSetup,
)

STRATEGY_ID = "smc"
STRATEGY_NAME = "SMC Premium/Discount (Order Block + Range)"
MIN_RISK_REWARD = 2.0  # Minimum 1:2 RR
SL_BUFFER = 0.0005  # 0.05% buffer beyond the order block, same as scalping_3tp


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
    """Check for a valid long (buy) setup: discount-zone Order Block retest."""
    if snapshot.htf_bias != HTFBias.bullish:
        return None

    range_high, range_low = _bracketing_range(snapshot)
    if range_high is None or range_low is None:
        return None

    midpoint = (range_high + range_low) / 2
    if snapshot.current_price >= midpoint:
        return None  # not in the discount half

    ob = _find_mitigating_order_block(snapshot, OrderBlockType.bullish, above=range_low, below=midpoint)
    if not ob:
        return None

    entry = snapshot.ask
    stop_loss = ob.low * (1 - SL_BUFFER)
    risk = entry - stop_loss
    if risk <= 0:
        return None

    final_target = range_high
    reward = final_target - entry
    if reward <= 0:
        return None
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    take_profits = [TakeProfit(price=final_target, close_pct=100, label="TP (Range Liquidity)")]
    confidence = _confidence(rr)
    reasoning = (
        f"Long: HTF bullish, price in discount ({snapshot.current_price:.5f} < "
        f"mid {midpoint:.5f}) of range {range_low:.5f}-{range_high:.5f}, bullish OB "
        f"retest @ {ob.low:.5f}-{ob.high:.5f}, RR={rr:.2f}"
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
    """Check for a valid short (sell) setup: premium-zone Order Block retest."""
    if snapshot.htf_bias != HTFBias.bearish:
        return None

    range_high, range_low = _bracketing_range(snapshot)
    if range_high is None or range_low is None:
        return None

    midpoint = (range_high + range_low) / 2
    if snapshot.current_price <= midpoint:
        return None  # not in the premium half

    ob = _find_mitigating_order_block(snapshot, OrderBlockType.bearish, above=midpoint, below=range_high)
    if not ob:
        return None

    entry = snapshot.bid
    stop_loss = ob.high * (1 + SL_BUFFER)
    risk = stop_loss - entry
    if risk <= 0:
        return None

    final_target = range_low
    reward = entry - final_target
    if reward <= 0:
        return None
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    take_profits = [TakeProfit(price=final_target, close_pct=100, label="TP (Range Liquidity)")]
    confidence = _confidence(rr)
    reasoning = (
        f"Short: HTF bearish, price in premium ({snapshot.current_price:.5f} > "
        f"mid {midpoint:.5f}) of range {range_low:.5f}-{range_high:.5f}, bearish OB "
        f"retest @ {ob.low:.5f}-{ob.high:.5f}, RR={rr:.2f}"
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


def _bracketing_range(snapshot: MarketSnapshot) -> tuple[float | None, float | None]:
    """Nearest structure high above and structure low below current price.

    Both are required: a range needs two sides. One-sided structure data
    (e.g. only highs, or only levels on one side of price) yields (None, None)
    rather than guessing a range from a single level.
    """
    price = snapshot.current_price
    highs = [s.level for s in snapshot.structure_levels if s.type == "high" and s.level > price]
    lows = [s.level for s in snapshot.structure_levels if s.type == "low" and s.level < price]
    if not highs or not lows:
        return None, None
    return min(highs), max(lows)


def _find_mitigating_order_block(
    snapshot: MarketSnapshot, ob_type: OrderBlockType, above: float, below: float
) -> OrderBlock | None:
    """An unmitigated order block of the given type, inside (above, below),
    that current price is touching."""
    for ob in snapshot.order_blocks:
        if ob.type != ob_type or ob.mitigated:
            continue
        if not (above <= ob.low and ob.high <= below):
            continue
        if ob.low <= snapshot.current_price <= ob.high:
            return ob
    return None


def _confidence(rr: float) -> float:
    """Confidence heuristic: base 55% + 10%/RR point, same shape as the other
    strategies -- no structure-alignment bonus here since a qualifying range
    is already a hard requirement, not a bonus condition."""
    return min(100, 55 + (rr * 10))


def _no_setup_reason(snapshot: MarketSnapshot) -> str:
    """Generate a human-readable reason why no setup was found."""
    if snapshot.htf_bias == HTFBias.neutral:
        return "HTF bias is neutral -- no directional bias"

    range_high, range_low = _bracketing_range(snapshot)
    if range_high is None or range_low is None:
        return "No bracketing structure range (need a structure high above and low below price)"

    midpoint = (range_high + range_low) / 2
    if snapshot.htf_bias == HTFBias.bullish:
        if snapshot.current_price >= midpoint:
            return f"Price in premium, not discount (mid={midpoint:.5f})"
        return "In discount range but no matching bullish Order Block retest"
    if snapshot.htf_bias == HTFBias.bearish:
        if snapshot.current_price <= midpoint:
            return f"Price in discount, not premium (mid={midpoint:.5f})"
        return "In premium range but no matching bearish Order Block retest"
    return "No valid setup conditions met"
