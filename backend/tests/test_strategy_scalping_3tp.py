"""Tests for scalping_3tp strategy."""

from __future__ import annotations

import pytest

from app.strategies.models import (
    FairValueGap,
    HTFBias,
    MarketSnapshot,
    OrderBlock,
    OrderBlockType,
    TradeSide,
)
from app.strategies.scalping_3tp.strategy import (
    MIN_RISK_REWARD,
    TP1_RR_FRACTION,
    TP2_RR_FRACTION,
    TP3_RR_FRACTION,
    evaluate,
)


def _base_snapshot(**overrides) -> MarketSnapshot:
    """Create a base market snapshot with default values."""
    data = dict(
        symbol="EURUSD",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        spread=0.00010,
        htf_bias=HTFBias.neutral,
        session="london",
    )
    data.update(overrides)
    return MarketSnapshot(**data)


# -- long setups -------------------------------------------------------------


def test_long_setup_valid() -> None:
    """Valid long setup: bullish HTF + price mitigating bullish OB + FVG."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10010,
                low=1.09990,
                open=1.09990,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )
    result = evaluate(snapshot)
    assert result.setup is not None
    assert result.setup.side == TradeSide.buy
    assert result.setup.entry_price == snapshot.ask
    assert result.setup.stop_loss < snapshot.ask
    assert result.setup.risk_reward >= MIN_RISK_REWARD
    assert len(result.setup.take_profits) == 3
    # Check TP ordering
    assert result.setup.take_profits[0].price < result.setup.take_profits[1].price < result.setup.take_profits[2].price
    # Check TP percentages
    assert result.setup.take_profits[0].close_pct == 30
    assert result.setup.take_profits[1].close_pct == 50
    assert result.setup.take_profits[2].close_pct == 100


def test_long_setup_sl_below_ob_low() -> None:
    """SL must be below the order block low."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10050,
                low=1.09900,
                open=1.09900,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10100, bottom=1.09950)],
    )
    result = evaluate(snapshot)
    assert result.setup is not None
    assert result.setup.stop_loss < 1.09900  # Below OB low


def test_long_setup_tp_calculation() -> None:
    """TPs are calculated at correct RR fractions."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        ask=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10100,
                low=1.09900,
                open=1.09900,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10500, bottom=1.09950)],
    )
    result = evaluate(snapshot)
    assert result.setup is not None
    entry = result.setup.entry_price
    sl = result.setup.stop_loss
    risk = entry - sl
    # TP3 is the full target
    tp3 = result.setup.take_profits[2].price
    reward = tp3 - entry
    # Check RR
    expected_rr = reward / risk
    assert abs(result.setup.risk_reward - expected_rr) < 0.01
    # Check TP1 and TP2
    assert abs(result.setup.take_profits[0].price - (entry + reward * TP1_RR_FRACTION)) < 0.00001
    assert abs(result.setup.take_profits[1].price - (entry + reward * TP2_RR_FRACTION)) < 0.00001


def test_long_setup_confidence_increases_with_rr() -> None:
    """Higher RR should increase confidence score."""
    # Low RR scenario
    snapshot_low_rr = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10050,
                low=1.09950,
                open=1.09950,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10150, bottom=1.09975)],
    )
    result_low = evaluate(snapshot_low_rr)
    # High RR scenario (wider target)
    snapshot_high_rr = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10050,
                low=1.09950,
                open=1.09950,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10500, bottom=1.09975)],
    )
    result_high = evaluate(snapshot_high_rr)
    assert result_low.setup is not None
    assert result_high.setup is not None
    # Higher RR should yield higher confidence
    assert result_high.setup.confidence > result_low.setup.confidence


# -- short setups ------------------------------------------------------------


def test_short_setup_valid() -> None:
    """Valid short setup: bearish HTF + price mitigating bearish OB + FVG."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bearish,
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bearish,
                high=1.10010,
                low=1.09990,
                open=1.10010,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bearish", top=1.10020, bottom=1.09980)],
    )
    result = evaluate(snapshot)
    assert result.setup is not None
    assert result.setup.side == TradeSide.sell
    assert result.setup.entry_price == snapshot.bid
    assert result.setup.stop_loss > snapshot.bid
    assert result.setup.risk_reward >= MIN_RISK_REWARD
    assert len(result.setup.take_profits) == 3
    # Check TP ordering (descending for shorts)
    assert result.setup.take_profits[0].price > result.setup.take_profits[1].price > result.setup.take_profits[2].price


def test_short_setup_sl_above_ob_high() -> None:
    """SL must be above the order block high."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bearish,
        current_price=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bearish,
                high=1.10100,
                low=1.09950,
                open=1.10100,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bearish", top=1.10050, bottom=1.09900)],
    )
    result = evaluate(snapshot)
    assert result.setup is not None
    assert result.setup.stop_loss > 1.10100  # Above OB high


# -- no setup scenarios ------------------------------------------------------


def test_no_setup_neutral_htf() -> None:
    """No setup when HTF bias is neutral."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.neutral,
        order_blocks=[OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )
    result = evaluate(snapshot)
    assert result.setup is None
    assert "neutral" in result.no_setup_reason.lower()


def test_no_setup_missing_order_block() -> None:
    """No setup when no valid order block is present."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        order_blocks=[],  # No OBs
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )
    result = evaluate(snapshot)
    assert result.setup is None
    assert "order block" in result.no_setup_reason.lower()


def test_no_setup_missing_fvg() -> None:
    """No setup when no valid FVG is present."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        order_blocks=[OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)],
        fvgs=[],  # No FVGs
    )
    result = evaluate(snapshot)
    assert result.setup is None
    assert "fvg" in result.no_setup_reason.lower()


def test_no_setup_wrong_direction_ob() -> None:
    """No setup when OB direction doesn't match HTF bias."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bearish,  # Wrong type for bullish bias
                high=1.10010,
                low=1.09990,
                open=1.10010,
                close=1.10000,
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )
    result = evaluate(snapshot)
    assert result.setup is None


def test_no_setup_price_not_mitigating() -> None:
    """No setup when price is not inside OB/FVG."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.12000,  # Price far from OB/FVG
        order_blocks=[OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )
    result = evaluate(snapshot)
    assert result.setup is None


def test_no_setup_already_mitigated_ob() -> None:
    """No setup when order block is already mitigated."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10010,
                low=1.09990,
                open=1.09990,
                close=1.10000,
                mitigated=True,  # Already used
            )
        ],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )
    result = evaluate(snapshot)
    assert result.setup is None


def test_no_setup_already_mitigated_fvg() -> None:
    """No setup when FVG is already mitigated."""
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        order_blocks=[OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)],
        fvgs=[
            FairValueGap(
                side="bullish",
                top=1.10020,
                bottom=1.09980,
                mitigated=True,  # Already filled
            )
        ],
    )
    result = evaluate(snapshot)
    assert result.setup is None


# -- risk management ---------------------------------------------------------


def test_minimum_rr_enforced() -> None:
    """Setup is rejected if RR < minimum (1:2)."""
    # Create a scenario where natural RR would be < 2.0
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        ask=1.10000,
        order_blocks=[
            OrderBlock(
                type=OrderBlockType.bullish,
                high=1.10010,
                low=1.09980,  # Risk = 20 pips
                open=1.09980,
                close=1.10000,
            )
        ],
        fvgs=[
            FairValueGap(
                side="bullish",
                top=1.10015,  # Reward would be only 15 pips without extension
                bottom=1.09985,
            )
        ],
    )
    result = evaluate(snapshot)
    # Strategy should either extend target to meet min RR or reject setup
    if result.setup:
        assert result.setup.risk_reward >= MIN_RISK_REWARD


# -- result model consistency ------------------------------------------------


def test_result_has_setup_or_reason() -> None:
    """StrategyResult must have either setup OR no_setup_reason, not both."""
    snapshot_with_setup = _base_snapshot(
        htf_bias=HTFBias.bullish,
        current_price=1.10000,
        order_blocks=[OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)],
        fvgs=[FairValueGap(side="bullish", top=1.10100, bottom=1.09980)],
    )
    result_with = evaluate(snapshot_with_setup)
    if result_with.setup:
        assert result_with.no_setup_reason is None
    else:
        assert result_with.no_setup_reason is not None

    snapshot_without_setup = _base_snapshot(htf_bias=HTFBias.neutral)
    result_without = evaluate(snapshot_without_setup)
    assert result_without.setup is None
    assert result_without.no_setup_reason is not None
