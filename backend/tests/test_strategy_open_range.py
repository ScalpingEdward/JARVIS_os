"""Tests for open_range strategy."""

from __future__ import annotations

from app.strategies.models import HTFBias, MarketSnapshot, TradeSide
from app.strategies.open_range.strategy import MIN_RISK_REWARD, STRATEGY_ID, STRATEGY_NAME, evaluate


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
    # Opening range 1.09900-1.10100; price just broke above to 1.10110 (close
    # to the boundary -- a realistic ORB entry, not deep into the move).
    data = dict(
        htf_bias=HTFBias.bullish,
        current_price=1.10110,
        bid=1.10105,
        ask=1.10110,
        opening_range_high=1.10100,
        opening_range_low=1.09900,
    )
    data.update(overrides)
    return _base_snapshot(**data)


def _short_snapshot(**overrides) -> MarketSnapshot:
    data = dict(
        htf_bias=HTFBias.bearish,
        current_price=1.09890,
        bid=1.09890,
        ask=1.09895,
        opening_range_high=1.10100,
        opening_range_low=1.09900,
    )
    data.update(overrides)
    return _base_snapshot(**data)


def test_valid_long_breakout_setup():
    result = evaluate(_long_snapshot())
    assert result.setup is not None
    setup = result.setup
    assert setup.strategy_id == STRATEGY_ID
    assert setup.strategy_name == STRATEGY_NAME
    assert setup.side == TradeSide.buy
    assert setup.risk_reward >= MIN_RISK_REWARD
    assert len(setup.take_profits) == 1


def test_long_target_is_the_measured_move():
    setup = evaluate(_long_snapshot()).setup
    # range height 0.00200, projected from the range high 1.10100
    assert round(setup.take_profits[0].price, 5) == 1.10300


def test_long_sl_is_just_below_the_broken_level():
    setup = evaluate(_long_snapshot()).setup
    assert setup.stop_loss < 1.10100
    assert setup.stop_loss > 1.09900  # tighter than the far side of the range


def test_valid_short_breakdown_setup():
    result = evaluate(_short_snapshot())
    assert result.setup is not None
    setup = result.setup
    assert setup.side == TradeSide.sell
    assert round(setup.take_profits[0].price, 5) == 1.09700


def test_no_setup_without_opening_range_data():
    snapshot = _base_snapshot(current_price=1.10150, htf_bias=HTFBias.bullish)
    result = evaluate(snapshot)
    assert result.setup is None
    assert "opening range" in result.no_setup_reason.lower()


def test_no_setup_when_only_high_is_set():
    snapshot = _base_snapshot(opening_range_high=1.10100, current_price=1.10150)
    result = evaluate(snapshot)
    assert result.setup is None
    assert "opening range" in result.no_setup_reason.lower()


def test_no_setup_when_price_still_inside_the_range():
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish, current_price=1.10000,
        opening_range_high=1.10100, opening_range_low=1.09900,
    )
    result = evaluate(snapshot)
    assert result.setup is None
    assert "inside" in result.no_setup_reason.lower()


def test_bullish_breakout_refused_against_bearish_htf():
    snapshot = _long_snapshot(htf_bias=HTFBias.bearish)
    result = evaluate(snapshot)
    assert result.setup is None
    assert "bearish" in result.no_setup_reason.lower()


def test_bearish_breakdown_refused_against_bullish_htf():
    snapshot = _short_snapshot(htf_bias=HTFBias.bullish)
    result = evaluate(snapshot)
    assert result.setup is None
    assert "bullish" in result.no_setup_reason.lower()


def test_neutral_htf_allows_the_breakout():
    setup = evaluate(_long_snapshot(htf_bias=HTFBias.neutral)).setup
    assert setup is not None


def test_neutral_htf_gets_no_confidence_bonus():
    aligned = evaluate(_long_snapshot(htf_bias=HTFBias.bullish)).setup
    neutral = evaluate(_long_snapshot(htf_bias=HTFBias.neutral)).setup
    assert aligned.confidence > neutral.confidence


def test_invalid_range_high_below_low_is_refused():
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish, current_price=1.10150,
        opening_range_high=1.09900, opening_range_low=1.10100,
    )
    result = evaluate(snapshot)
    assert result.setup is None
    assert "invalid" in result.no_setup_reason.lower()


def test_min_risk_reward_enforced():
    # A very thin range gives a small reward relative to the SL distance.
    snapshot = _base_snapshot(
        htf_bias=HTFBias.bullish, current_price=1.10011,
        bid=1.10009, ask=1.10012,
        opening_range_high=1.10010, opening_range_low=1.10000,
    )
    result = evaluate(snapshot)
    # range height is tiny (0.00010) -> measured move barely clears entry;
    # whether it passes or fails 1:2 depends on the buffer, but it must be
    # internally consistent: if there is a setup its RR meets the minimum.
    if result.setup is not None:
        assert result.setup.risk_reward >= MIN_RISK_REWARD
    else:
        assert result.no_setup_reason is not None


def test_result_model_consistency():
    result = evaluate(_base_snapshot())
    assert result.symbol == "EURUSD"
    assert result.setup is None
    assert result.no_setup_reason is not None


def test_existing_snapshots_without_opening_range_fields_still_validate():
    """The whole point of making the new fields optional: every strategy and
    every existing test snapshot that never mentions opening_range_* must
    keep working unchanged."""
    snapshot = MarketSnapshot(
        symbol="EURUSD", current_price=1.1, bid=1.0999, ask=1.1001, spread=0.0002,
    )
    assert snapshot.opening_range_high is None
    assert snapshot.opening_range_low is None
    result = evaluate(snapshot)
    assert result.setup is None
