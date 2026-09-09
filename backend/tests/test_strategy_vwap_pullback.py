"""Tests for vwap_pullback strategy."""

from __future__ import annotations

from app.strategies.models import HTFBias, MarketSnapshot, TradeSide
from app.strategies.vwap_pullback.strategy import MIN_RISK_REWARD, STRATEGY_ID, STRATEGY_NAME, evaluate


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
    # VWAP at 1.10000, price pulled back to sit just at/slightly below it
    # (a real "touch" moment, not deep into a breakdown), confirmed uptrend.
    data = dict(
        htf_bias=HTFBias.bullish,
        current_price=1.09995,
        bid=1.09990,
        ask=1.10010,
        vwap=1.10000,
        vwap_std_dev=0.00200,
    )
    data.update(overrides)
    return _base_snapshot(**data)


def _short_snapshot(**overrides) -> MarketSnapshot:
    data = dict(
        htf_bias=HTFBias.bearish,
        current_price=1.10005,
        bid=1.09990,
        ask=1.10010,
        vwap=1.10000,
        vwap_std_dev=0.00200,
    )
    data.update(overrides)
    return _base_snapshot(**data)


def test_long_pullback_produces_a_valid_setup():
    result = evaluate(_long_snapshot())
    assert result.setup is not None
    setup = result.setup
    assert setup.strategy_id == STRATEGY_ID
    assert setup.side == TradeSide.buy
    assert setup.risk_reward >= MIN_RISK_REWARD
    assert setup.take_profits[0].label == "TP (+1SD VWAP band)"
    assert "VWAP" in setup.reasoning


def test_short_pullback_produces_a_valid_setup():
    result = evaluate(_short_snapshot())
    assert result.setup is not None
    setup = result.setup
    assert setup.side == TradeSide.sell
    assert setup.risk_reward >= MIN_RISK_REWARD
    assert setup.take_profits[0].label == "TP (-1SD VWAP band)"


def test_no_vwap_data_means_no_setup():
    result = evaluate(_long_snapshot(vwap=None))
    assert result.setup is None
    assert "vwap not set" in result.no_setup_reason


def test_neutral_htf_bias_refuses_the_trade():
    """VWAP pullback needs a confirmed trend -- unlike open_range's 'not
    actively opposed' bar, a neutral bias is not enough here."""
    result = evaluate(_long_snapshot(htf_bias=HTFBias.neutral))
    assert result.setup is None
    assert "neutral" in result.no_setup_reason.lower()


def test_bearish_htf_refuses_a_long_pullback():
    """The price data alone (near VWAP) can legitimately also satisfy a
    short setup -- correctly so, evaluate() checks both independently.
    What this test actually verifies is that no *long* comes out of it."""
    result = evaluate(_long_snapshot(htf_bias=HTFBias.bearish))
    assert result.setup is None or result.setup.side != TradeSide.buy


def test_price_too_far_below_vwap_is_a_breakdown_not_a_pullback():
    result = evaluate(_long_snapshot(current_price=1.09000, bid=1.08995, ask=1.09005))
    assert result.setup is None
    assert "not in the VWAP" in result.no_setup_reason


def test_price_too_far_above_vwap_has_not_pulled_back_yet():
    result = evaluate(_long_snapshot(current_price=1.10500, bid=1.10495, ask=1.10505))
    assert result.setup is None


def test_falls_back_to_fixed_rr_target_without_a_std_dev():
    result = evaluate(_long_snapshot(vwap_std_dev=None))
    assert result.setup is not None
    assert result.setup.take_profits[0].label == "TP (min RR)"
    assert result.setup.risk_reward >= MIN_RISK_REWARD


def test_confidence_gets_a_bonus_for_a_real_band_target():
    with_band = evaluate(_long_snapshot()).setup
    without_band = evaluate(_long_snapshot(vwap_std_dev=None)).setup
    # same entry/stop, so the only difference is the target -- band data
    # should never produce *lower* confidence than the fallback
    assert with_band.confidence >= without_band.confidence


def test_reasoning_mentions_the_actual_vwap_level():
    result = evaluate(_long_snapshot())
    assert "1.10000" in result.setup.reasoning


def test_short_setup_is_symmetric_to_long():
    long_result = evaluate(_long_snapshot())
    short_result = evaluate(_short_snapshot())
    assert long_result.setup.risk_reward == short_result.setup.risk_reward


def test_strategy_metadata():
    result = evaluate(_base_snapshot())
    assert result.strategy_id == STRATEGY_ID
    assert result.strategy_name == STRATEGY_NAME
    assert result.setup is None  # no vwap on a bare base snapshot
