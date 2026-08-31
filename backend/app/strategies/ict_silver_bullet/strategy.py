"""ICT Silver Bullet strategy implementation.

Session-gated FVG entry using structure levels for stop and target placement.

Entry logic:
- Only during London or NY sessions (the ICT "Silver Bullet" windows)
- Long: HTF bullish + current price inside an unmitigated bullish FVG
- Short: HTF bearish + current price inside an unmitigated bearish FVG

Exit logic:
- SL: beyond the nearest protective swing structure level
      (nearest structure low below entry for longs, nearest structure high above
       entry for shorts); falls back to the FVG boundary with a small buffer.
- Target: nearest opposing structure level (liquidity); if none is available the
      target is extended to satisfy the minimum risk-reward.
- TP1: 50% of the position at 50% of the RR distance
- TP2: remaining 50% at the full target

Risk management:
- Minimum 1:2 risk-reward ratio required, otherwise no setup.
"""

from __future__ import annotations

from ..models import (
    FairValueGap,
    HTFBias,
    MarketSnapshot,
    StrategyResult,
    TakeProfit,
    TradeSide,
    TradingSetup,
)

STRATEGY_ID = "ict_silver_bullet"
STRATEGY_NAME = "ICT Silver Bullet (Session FVG + Structure)"
MIN_RISK_REWARD = 2.0  # Minimum 1:2 RR
TP1_RR_FRACTION = 0.5  # TP1 at 50% of full RR
SL_BUFFER = 0.0005  # 0.05% buffer beyond structure / FVG boundary
ACTIVE_SESSIONS = ("london", "ny")  # Silver Bullet windows only


def evaluate(snapshot: MarketSnapshot) -> StrategyResult:
    """Evaluate a market snapshot and return a trading setup if conditions are met."""
    # Session gate: only trade during London / NY windows
    if snapshot.session in ACTIVE_SESSIONS:
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
    """Check for a valid long (buy) setup."""
    if snapshot.htf_bias != HTFBias.bullish:
        return None

    fvg = _find_mitigating_fvg(snapshot, "bullish")
    if not fvg:
        return None

    entry = snapshot.ask

    # SL: nearest protective structure low below entry, else FVG bottom with buffer
    protective_low = _nearest_structure_below(snapshot, entry)
    if protective_low is not None:
        stop_loss = protective_low * (1 - SL_BUFFER)
    else:
        stop_loss = fvg.bottom * (1 - SL_BUFFER)

    risk = entry - stop_loss
    if risk <= 0:
        return None

    # Target: nearest structure high above entry (liquidity), else min RR target
    target_high = _nearest_structure_above(snapshot, entry)
    min_reward = risk * MIN_RISK_REWARD
    if target_high is not None:
        final_target = max(target_high, entry + min_reward)
    else:
        final_target = entry + min_reward

    reward = final_target - entry
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    tp1_price = entry + (reward * TP1_RR_FRACTION)
    take_profits = [
        TakeProfit(price=tp1_price, close_pct=50, label="TP1 (50% RR)"),
        TakeProfit(price=final_target, close_pct=100, label="TP2 (Full Target)"),
    ]

    confidence = _confidence(rr, target_high, snapshot)
    reasoning = (
        f"Long: {snapshot.session.upper()} session, HTF bullish, price inside bullish "
        f"FVG {fvg.bottom:.5f}-{fvg.top:.5f}, target structure liquidity, RR={rr:.2f}"
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
    """Check for a valid short (sell) setup."""
    if snapshot.htf_bias != HTFBias.bearish:
        return None

    fvg = _find_mitigating_fvg(snapshot, "bearish")
    if not fvg:
        return None

    entry = snapshot.bid

    # SL: nearest protective structure high above entry, else FVG top with buffer
    protective_high = _nearest_structure_above(snapshot, entry)
    if protective_high is not None:
        stop_loss = protective_high * (1 + SL_BUFFER)
    else:
        stop_loss = fvg.top * (1 + SL_BUFFER)

    risk = stop_loss - entry
    if risk <= 0:
        return None

    # Target: nearest structure low below entry (liquidity), else min RR target
    target_low = _nearest_structure_below(snapshot, entry)
    min_reward = risk * MIN_RISK_REWARD
    if target_low is not None:
        final_target = min(target_low, entry - min_reward)
    else:
        final_target = entry - min_reward

    reward = entry - final_target
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    tp1_price = entry - (reward * TP1_RR_FRACTION)
    take_profits = [
        TakeProfit(price=tp1_price, close_pct=50, label="TP1 (50% RR)"),
        TakeProfit(price=final_target, close_pct=100, label="TP2 (Full Target)"),
    ]

    confidence = _confidence(rr, target_low, snapshot)
    reasoning = (
        f"Short: {snapshot.session.upper()} session, HTF bearish, price inside bearish "
        f"FVG {fvg.bottom:.5f}-{fvg.top:.5f}, target structure liquidity, RR={rr:.2f}"
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


def _find_mitigating_fvg(snapshot: MarketSnapshot, side: str) -> FairValueGap | None:
    """Find an unmitigated FVG of the given side that current price is inside."""
    for fvg in snapshot.fvgs:
        if fvg.side != side or fvg.mitigated:
            continue
        if fvg.bottom <= snapshot.current_price <= fvg.top:
            return fvg
    return None


def _nearest_structure_below(snapshot: MarketSnapshot, price: float) -> float | None:
    """Return the nearest structure level strictly below the given price."""
    below = [s.level for s in snapshot.structure_levels if s.level < price]
    return max(below) if below else None


def _nearest_structure_above(snapshot: MarketSnapshot, price: float) -> float | None:
    """Return the nearest structure level strictly above the given price."""
    above = [s.level for s in snapshot.structure_levels if s.level > price]
    return min(above) if above else None


def _confidence(rr: float, structure_target: float | None, snapshot: MarketSnapshot) -> float:
    """Confidence heuristic: base + RR bonus + structure-alignment bonus."""
    confidence = 55 + (rr * 10)  # Base 55%, +10% per RR point
    if structure_target is not None:
        confidence += 10  # Bonus when a real structure liquidity target exists
    return min(100, confidence)


def _no_setup_reason(snapshot: MarketSnapshot) -> str:
    """Generate a human-readable reason why no setup was found."""
    if snapshot.session not in ACTIVE_SESSIONS:
        return (
            f"Session '{snapshot.session}' outside Silver Bullet windows "
            f"({', '.join(ACTIVE_SESSIONS)})"
        )
    if snapshot.htf_bias == HTFBias.neutral:
        return "HTF bias is neutral — no directional bias"
    if snapshot.htf_bias == HTFBias.bullish:
        if not _find_mitigating_fvg(snapshot, "bullish"):
            return "Price not inside an unmitigated bullish FVG"
        return "Bullish FVG present but risk-reward below minimum 1:2"
    if snapshot.htf_bias == HTFBias.bearish:
        if not _find_mitigating_fvg(snapshot, "bearish"):
            return "Price not inside an unmitigated bearish FVG"
        return "Bearish FVG present but risk-reward below minimum 1:2"
    return "No valid setup conditions met"
