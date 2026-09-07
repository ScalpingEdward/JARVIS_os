"""Tests for smc strategy."""

from __future__ import annotations

from app.strategies.models import HTFBias, MarketSnapshot, OrderBlock, StructureLevel, TradeSide
from app.strategies.smc.strategy import MIN_RISK_REWARD, STRATEGY_ID, STRATEGY_NAME, evaluate


def _base_snapshot(**overrides) -> MarketSnapshot:
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


def _long_snapshot(**overrides) -> MarketSnapshot:
    # Range: low=1.09500, high=1.10500, midpoint=1.10000. Price at 1.09700 is
    # in the discount (lower) half. Bullish OB sits inside that half.
    data = dict(
        htf_bias=HTFBias.bullish,
        current_price=1.09700,
        bid=1.09695,
        ask=1.09705,
        structure_levels=[
            StructureLevel(level=1.09500, type="low", strength=3),
            StructureLevel(level=1.10500, type="high", strength=3),
        ],
        order_blocks=[OrderBlock(type="bullish", high=1.09720, low=1.09680, open=1.09690, close=1.09710)],
    )
    data.update(overrides)
    return _base_snapshot(**data)


def _short_snapshot(**overrides) -> MarketSnapshot:
    # Same range, price at 1.10300 is in the premium (upper) half.
    data = dict(
        htf_bias=HTFBias.bearish,
        current_price=1.10300,
        bid=1.10295,
        ask=1.10305,
        structure_levels=[
            StructureLevel(level=1.09500, type="low", strength=3),
            StructureLevel(level=1.10500, type="high", strength=3),
        ],
        order_blocks=[OrderBlock(type="bearish", high=1.10320, low=1.10280, open=1.10310, close=1.10290)],
    )
    data.update(overrides)
    return _base_snapshot(**data)


def test_valid_long_setup_from_discount_order_block():
    result = evaluate(_long_snapshot())
    assert result.setup is not None
    setup = result.setup
    assert setup.strategy_id == STRATEGY_ID
    assert setup.strategy_name == STRATEGY_NAME
    assert setup.side == TradeSide.buy
    assert setup.risk_reward >= MIN_RISK_REWARD
    assert len(setup.take_profits) == 1
    assert setup.take_profits[0].close_pct == 100


def test_long_target_is_the_opposing_range_side():
    setup = evaluate(_long_snapshot()).setup
    assert setup.take_profits[0].price == 1.10500  # the range high


def test_long_sl_is_below_the_order_block():
    setup = evaluate(_long_snapshot()).setup
    assert setup.stop_loss < 1.09680  # below the OB low, buffered


def test_valid_short_setup_from_premium_order_block():
    result = evaluate(_short_snapshot())
    assert result.setup is not None
    setup = result.setup
    assert setup.side == TradeSide.sell
    assert setup.risk_reward >= MIN_RISK_REWARD
    assert setup.take_profits[0].price == 1.09500  # the range low


def test_no_setup_when_htf_neutral():
    snapshot = _long_snapshot(htf_bias=HTFBias.neutral)
    result = evaluate(snapshot)
    assert result.setup is None
    assert "neutral" in result.no_setup_reason.lower()


def test_no_setup_without_a_bracketing_range():
    snapshot = _long_snapshot(structure_levels=[])
    result = evaluate(snapshot)
    assert result.setup is None
    assert "range" in result.no_setup_reason.lower()


def test_no_setup_with_only_one_side_of_structure():
    # Only a low below price, no high above -- not a real range.
    snapshot = _long_snapshot(structure_levels=[StructureLevel(level=1.09500, type="low", strength=3)])
    result = evaluate(snapshot)
    assert result.setup is None
    assert "range" in result.no_setup_reason.lower()


def test_no_setup_when_price_in_premium_for_a_long():
    # Bullish HTF but price sitting in the premium half -- wrong zone for a long.
    snapshot = _long_snapshot(current_price=1.10300, bid=1.10295, ask=1.10305, order_blocks=[])
    result = evaluate(snapshot)
    assert result.setup is None
    assert "premium" in result.no_setup_reason.lower()


def test_no_setup_when_price_in_discount_for_a_short():
    snapshot = _short_snapshot(current_price=1.09700, bid=1.09695, ask=1.09705, order_blocks=[])
    result = evaluate(snapshot)
    assert result.setup is None
    assert "discount" in result.no_setup_reason.lower()


def test_no_setup_without_a_matching_order_block():
    snapshot = _long_snapshot(order_blocks=[])
    result = evaluate(snapshot)
    assert result.setup is None
    assert "order block" in result.no_setup_reason.lower()


def test_order_block_outside_the_discount_half_is_ignored():
    # A bullish OB that sits in the premium half must not qualify a long.
    snapshot = _long_snapshot(
        current_price=1.09700, bid=1.09695, ask=1.09705,
        order_blocks=[OrderBlock(type="bullish", high=1.10320, low=1.10280, open=1.10300, close=1.10300)],
    )
    result = evaluate(snapshot)
    assert result.setup is None


def test_mitigated_order_block_is_ignored():
    snapshot = _long_snapshot()
    snapshot.order_blocks[0].mitigated = True
    result = evaluate(snapshot)
    assert result.setup is None


def test_wrong_side_order_block_is_ignored_for_long():
    snapshot = _long_snapshot(
        order_blocks=[OrderBlock(type="bearish", high=1.09720, low=1.09680, open=1.09710, close=1.09690)],
    )
    result = evaluate(snapshot)
    assert result.setup is None


def test_min_risk_reward_enforced():
    # Range too shallow relative to the SL distance below the OB to reach 1:2.
    snapshot = _long_snapshot(
        structure_levels=[
            StructureLevel(level=1.09650, type="low", strength=3),
            StructureLevel(level=1.09800, type="high", strength=3),
        ],
    )
    result = evaluate(snapshot)
    assert result.setup is None
    assert result.no_setup_reason is not None


def test_result_model_consistency():
    result = evaluate(_base_snapshot(htf_bias=HTFBias.neutral))
    assert result.symbol == "EURUSD"
    assert result.setup is None
    assert result.no_setup_reason is not None
