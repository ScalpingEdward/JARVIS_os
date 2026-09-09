"""VWAP Pullback strategy implementation.

Real, well-established intraday setup, not invented for this codebase --
checked current (2026) practice before building: price trends on one side
of the session VWAP, pulls back to touch or slightly penetrate it, and
continues in the trend direction. VWAP acts as a running "fair value"
reference institutional flow tends to defend, which is the whole reason
a pullback to it (rather than a random moving average) tends to hold.

Entry logic:
- Requires `vwap` on the snapshot. Not invented or derived from anything
  else here -- if the caller has not computed the session's VWAP yet,
  this strategy has nothing to trade on and says so.
- Long: HTF bias must be bullish (a pullback-continuation trade needs a
  confirmed trend, unlike open_range's "not actively opposed" bar --
  VWAP pullback's whole thesis is trading *with* an established trend,
  not just not fighting it). Price must be at or slightly below VWAP
  (the "touch or slight penetration" moment), within a bounded tolerance
  band -- too far below is a breakdown, not a pullback.
- Short: symmetric -- HTF bearish, price at or slightly above VWAP.

Exit logic:
- SL: a small buffer beyond VWAP itself (below for a long, above for a
  short) -- "if price chops back through VWAP, the setup is usually
  dead" is the standard practitioner rule; a stop anywhere else does not
  match what actually invalidates this specific thesis.
- Target: the +1SD VWAP band when `vwap_std_dev` is available on the
  snapshot (the standard VWAP-band target practitioners use) -- this is
  the primary, preferred target. Falls back to a fixed minimum
  risk-reward multiple projected from entry when no std-dev is provided,
  same "degrade gracefully, never invent a number" pattern already used
  elsewhere in this package.

Risk management:
- Minimum 1:2 risk-reward ratio required, otherwise no setup.
"""

from __future__ import annotations

from ..models import HTFBias, MarketSnapshot, StrategyResult, TakeProfit, TradeSide, TradingSetup

STRATEGY_ID = "vwap_pullback"
STRATEGY_NAME = "VWAP Pullback (Trend Continuation)"
MIN_RISK_REWARD = 2.0  # Minimum 1:2 RR
SL_BUFFER = 0.0005  # 0.05% beyond VWAP itself
#: How far price may sit on the "wrong" side of VWAP and still count as a
#: pullback rather than a breakdown/breakout through it -- practitioner
#: guidance is "touch or slightly penetrate", not any specific number, so
#: this stays a small, explicit, documented choice rather than an
#: invented precision.
PULLBACK_TOLERANCE = 0.0015  # 0.15% beyond VWAP on the trade's own side
#: How close price must already be to VWAP, on the trend's side, to count
#: as "arrived at the pullback" rather than still approaching it.
TOUCH_ZONE = 0.0025  # 0.25% of VWAP


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


def _in_pullback_zone(price: float, vwap: float, *, below_is_pullback: bool) -> bool:
    """True when price sits between a small overshoot past VWAP (still a
    valid pullback -- "slight penetration") and the outer touch zone on
    the correct side (close enough to call it "arrived", not still
    approaching)."""
    if below_is_pullback:
        floor = vwap * (1 - PULLBACK_TOLERANCE)
        ceiling = vwap * (1 + TOUCH_ZONE)
        return floor <= price <= ceiling
    floor = vwap * (1 - TOUCH_ZONE)
    ceiling = vwap * (1 + PULLBACK_TOLERANCE)
    return floor <= price <= ceiling


def _check_long_setup(snapshot: MarketSnapshot) -> TradingSetup | None:
    """Check for a valid long (buy) setup: pullback to VWAP within an
    established uptrend."""
    vwap = snapshot.vwap
    if vwap is None:
        return None
    if snapshot.htf_bias != HTFBias.bullish:
        return None
    if not _in_pullback_zone(snapshot.current_price, vwap, below_is_pullback=True):
        return None

    entry = snapshot.ask
    stop_loss = vwap * (1 - SL_BUFFER)
    risk = entry - stop_loss
    if risk <= 0:
        return None

    if snapshot.vwap_std_dev is not None:
        final_target = vwap + snapshot.vwap_std_dev
    else:
        final_target = entry + (risk * MIN_RISK_REWARD)
    reward = final_target - entry
    if reward <= 0:
        return None
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    label = "TP (+1SD VWAP band)" if snapshot.vwap_std_dev is not None else "TP (min RR)"
    take_profits = [TakeProfit(price=final_target, close_pct=100, label=label)]
    confidence = _confidence(rr, snapshot)
    reasoning = (
        f"Long: pullback to VWAP {vwap:.5f} in a confirmed uptrend, "
        f"entry {entry:.5f}, target {final_target:.5f}, RR={rr:.2f}"
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
    """Check for a valid short (sell) setup: pullback to VWAP within an
    established downtrend."""
    vwap = snapshot.vwap
    if vwap is None:
        return None
    if snapshot.htf_bias != HTFBias.bearish:
        return None
    if not _in_pullback_zone(snapshot.current_price, vwap, below_is_pullback=False):
        return None

    entry = snapshot.bid
    stop_loss = vwap * (1 + SL_BUFFER)
    risk = stop_loss - entry
    if risk <= 0:
        return None

    if snapshot.vwap_std_dev is not None:
        final_target = vwap - snapshot.vwap_std_dev
    else:
        final_target = entry - (risk * MIN_RISK_REWARD)
    reward = entry - final_target
    if reward <= 0:
        return None
    rr = reward / risk
    if rr < MIN_RISK_REWARD:
        return None

    label = "TP (-1SD VWAP band)" if snapshot.vwap_std_dev is not None else "TP (min RR)"
    take_profits = [TakeProfit(price=final_target, close_pct=100, label=label)]
    confidence = _confidence(rr, snapshot)
    reasoning = (
        f"Short: pullback to VWAP {vwap:.5f} in a confirmed downtrend, "
        f"entry {entry:.5f}, target {final_target:.5f}, RR={rr:.2f}"
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
    """Confidence heuristic: base 55% + 10%/RR point, +10% when a real
    +1SD band target was available rather than the fixed-RR fallback --
    a band target reflects the session's own actual volatility, a bonus
    over an assumed multiple, not a requirement."""
    confidence = 55 + (rr * 10)
    if snapshot.vwap_std_dev is not None:
        confidence += 10
    return min(100, confidence)


def _no_setup_reason(snapshot: MarketSnapshot) -> str:
    """Generate a human-readable reason why no setup was found."""
    if snapshot.vwap is None:
        return "No VWAP data (vwap not set on the snapshot)"
    vwap = snapshot.vwap
    if snapshot.htf_bias == HTFBias.neutral:
        return "VWAP pullback needs a confirmed trend; HTF bias is neutral"
    if snapshot.htf_bias == HTFBias.bullish and not _in_pullback_zone(
        snapshot.current_price, vwap, below_is_pullback=True
    ):
        return f"HTF bullish but price {snapshot.current_price:.5f} is not in the VWAP {vwap:.5f} pullback zone"
    if snapshot.htf_bias == HTFBias.bearish and not _in_pullback_zone(
        snapshot.current_price, vwap, below_is_pullback=False
    ):
        return f"HTF bearish but price {snapshot.current_price:.5f} is not in the VWAP {vwap:.5f} pullback zone"
    return "Pullback risk-reward below minimum 1:2"
