"""Scalping 3TP strategy implementation — FVG + Order Block mitigation with 3 TPs."""

from __future__ import annotations

from ..models import (
    HTFBias,
    MarketSnapshot,
    OrderBlockType,
    StrategyResult,
    TakeProfit,
    TradeSide,
    TradingSetup,
)

STRATEGY_ID = "scalping_3tp"
STRATEGY_NAME = "Scalping 3TP (FVG + Order Block)"
MIN_RISK_REWARD = 2.0  # Minimum 1:2 RR
TP1_RR_FRACTION = 0.3  # TP1 at 30% of full RR
TP2_RR_FRACTION = 0.5  # TP2 at 50% of full RR
TP3_RR_FRACTION = 1.0  # TP3 at 100% of full RR (full target)


def evaluate(snapshot: MarketSnapshot) -> StrategyResult:
    """Evaluate a market snapshot and return a trading setup if conditions are met.

    Entry logic:
    - Long: HTF bullish + current price mitigates a bullish Order Block + bullish FVG
    - Short: HTF bearish + current price mitigates a bearish Order Block + bearish FVG

    Exit logic:
    - TP1: 30% of position at 30% of full RR distance
    - TP2: 50% of remaining (total 80% closed) at 50% of full RR
    - TP3: Final 20% at 100% of full RR (full target)
    - SL: Below bullish OB low (long) or above bearish OB high (short)

    Risk management:
    - Minimum 1:2 risk-reward ratio required
    - Setup invalidated if structure breaks (order block mitigated in opposite direction)
    """
    # Check for long setup
    long_setup = _check_long_setup(snapshot)
    if long_setup:
        return StrategyResult(
            strategy_id=STRATEGY_ID,
            strategy_name=STRATEGY_NAME,
            symbol=snapshot.symbol,
            setup=long_setup,
        )

    # Check for short setup
    short_setup = _check_short_setup(snapshot)
    if short_setup:
        return StrategyResult(
            strategy_id=STRATEGY_ID,
            strategy_name=STRATEGY_NAME,
            symbol=snapshot.symbol,
            setup=short_setup,
        )

    # No setup found
    reason = _no_setup_reason(snapshot)
    return StrategyResult(
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        symbol=snapshot.symbol,
        no_setup_reason=reason,
    )


def _check_long_setup(snapshot: MarketSnapshot) -> TradingSetup | None:
    """Check for a valid long (buy) setup."""
    # HTF must be bullish
    if snapshot.htf_bias != HTFBias.bullish:
        return None

    # Find a bullish order block that current price is mitigating
    bullish_ob = _find_mitigating_order_block(snapshot, OrderBlockType.bullish)
    if not bullish_ob:
        return None

    # Find a bullish FVG that current price is inside
    bullish_fvg = _find_mitigating_fvg(snapshot, "bullish")
    if not bullish_fvg:
        return None

    # Entry: current ask price
    entry = snapshot.ask
    # SL: below the order block low (with small buffer)
    stop_loss = bullish_ob.low * 0.9995  # 0.05% buffer
    # Initial target: top of FVG or order block high, whichever is higher
    initial_target = max(bullish_fvg.top, bullish_ob.high)

    # Calculate risk and reward
    risk = entry - stop_loss
    if risk <= 0:
        return None

    # Ensure minimum RR (extend target if needed)
    min_reward = risk * MIN_RISK_REWARD
    final_target = max(initial_target, entry + min_reward)
    reward = final_target - entry
    rr = reward / risk

    if rr < MIN_RISK_REWARD:
        return None

    # Calculate 3 TPs
    tp1_price = entry + (reward * TP1_RR_FRACTION)
    tp2_price = entry + (reward * TP2_RR_FRACTION)
    tp3_price = final_target

    take_profits = [
        TakeProfit(price=tp1_price, close_pct=30, label="TP1 (30% RR)"),
        TakeProfit(price=tp2_price, close_pct=50, label="TP2 (50% RR)"),
        TakeProfit(price=tp3_price, close_pct=100, label="TP3 (Full Target)"),
    ]

    # Confidence calculation (simple heuristic based on RR and FVG/OB alignment)
    confidence = min(100, 60 + (rr * 10))  # Base 60%, +10% per RR point

    reasoning = (
        f"Long: HTF bullish, price mitigating bullish OB @ {bullish_ob.low:.5f} "
        f"+ bullish FVG {bullish_fvg.bottom:.5f}-{bullish_fvg.top:.5f}, RR={rr:.2f}"
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
        invalidation_price=stop_loss,  # Setup invalid if SL hit
    )


def _check_short_setup(snapshot: MarketSnapshot) -> TradingSetup | None:
    """Check for a valid short (sell) setup."""
    # HTF must be bearish
    if snapshot.htf_bias != HTFBias.bearish:
        return None

    # Find a bearish order block that current price is mitigating
    bearish_ob = _find_mitigating_order_block(snapshot, OrderBlockType.bearish)
    if not bearish_ob:
        return None

    # Find a bearish FVG that current price is inside
    bearish_fvg = _find_mitigating_fvg(snapshot, "bearish")
    if not bearish_fvg:
        return None

    # Entry: current bid price
    entry = snapshot.bid
    # SL: above the order block high (with small buffer)
    stop_loss = bearish_ob.high * 1.0005  # 0.05% buffer
    # Initial target: bottom of FVG or order block low, whichever is lower
    initial_target = min(bearish_fvg.bottom, bearish_ob.low)

    # Calculate risk and reward
    risk = stop_loss - entry
    if risk <= 0:
        return None

    # Ensure minimum RR (extend target if needed)
    min_reward = risk * MIN_RISK_REWARD
    final_target = min(initial_target, entry - min_reward)
    reward = entry - final_target
    rr = reward / risk

    if rr < MIN_RISK_REWARD:
        return None

    # Calculate 3 TPs
    tp1_price = entry - (reward * TP1_RR_FRACTION)
    tp2_price = entry - (reward * TP2_RR_FRACTION)
    tp3_price = final_target

    take_profits = [
        TakeProfit(price=tp1_price, close_pct=30, label="TP1 (30% RR)"),
        TakeProfit(price=tp2_price, close_pct=50, label="TP2 (50% RR)"),
        TakeProfit(price=tp3_price, close_pct=100, label="TP3 (Full Target)"),
    ]

    # Confidence calculation
    confidence = min(100, 60 + (rr * 10))

    reasoning = (
        f"Short: HTF bearish, price mitigating bearish OB @ {bearish_ob.high:.5f} "
        f"+ bearish FVG {bearish_fvg.bottom:.5f}-{bearish_fvg.top:.5f}, RR={rr:.2f}"
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


def _find_mitigating_order_block(snapshot: MarketSnapshot, ob_type: OrderBlockType) -> object | None:
    """Find an order block that current price is mitigating (touching/inside)."""
    for ob in snapshot.order_blocks:
        if ob.type != ob_type or ob.mitigated:
            continue
        # Check if current price is inside or touching the order block
        if ob.low <= snapshot.current_price <= ob.high:
            return ob
    return None


def _find_mitigating_fvg(snapshot: MarketSnapshot, side: str) -> object | None:
    """Find an FVG that current price is inside (mitigating)."""
    for fvg in snapshot.fvgs:
        if fvg.side != side or fvg.mitigated:
            continue
        # Check if current price is inside the FVG
        if fvg.bottom <= snapshot.current_price <= fvg.top:
            return fvg
    return None


def _no_setup_reason(snapshot: MarketSnapshot) -> str:
    """Generate a human-readable reason why no setup was found."""
    if snapshot.htf_bias == HTFBias.neutral:
        return "HTF bias is neutral — no directional bias"

    if snapshot.htf_bias == HTFBias.bullish:
        if not any(ob.type == OrderBlockType.bullish and not ob.mitigated for ob in snapshot.order_blocks):
            return "No unmitigated bullish order block found"
        if not any(fvg.side == "bullish" and not fvg.mitigated for fvg in snapshot.fvgs):
            return "No unmitigated bullish FVG found"
        return "Price not mitigating bullish OB + FVG simultaneously"

    if snapshot.htf_bias == HTFBias.bearish:
        if not any(ob.type == OrderBlockType.bearish and not ob.mitigated for ob in snapshot.order_blocks):
            return "No unmitigated bearish order block found"
        if not any(fvg.side == "bearish" and not fvg.mitigated for fvg in snapshot.fvgs):
            return "No unmitigated bearish FVG found"
        return "Price not mitigating bearish OB + FVG simultaneously"

    return "No valid setup conditions met"
