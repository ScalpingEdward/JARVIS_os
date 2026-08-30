"""Tests for ict_silver_bullet strategy."""

from __future__ import annotations

from app.strategies.ict_silver_bullet.strategy import (
    ACTIVE_SESSIONS,
    MIN_RISK_REWARD,
    STRATEGY_ID,
    STRATEGY_NAME,
    evaluate,
)
from app.strategies.models import (
    FairValueGap,
    HTFBias,
    MarketSnapshot,
    StructureLevel,
    TradeSide,
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


def _long_snapshot(**overrides) -> MarketSnapshot:
    data = dict(
        htf_bias=HTFBias.bullish,
        session="london",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
        structure_levels=[
            StructureLevel(level=1.09900, type="low", strength=3),
            StructureLevel(level=1.10500, type="high", strength=4),
        ],
    )
    data.update(overrides)
    return _base_snapshot(**data)


def _short_snapshot(**overrides) -> MarketSnapshot:
    data = dict(
        htf_bias=HTFBias.bearish,
        session="ny",
        current_price=1.10000,
        bid=1.09995,
        ask=1.10005,
        fvgs=[FairValueGap(side="bearish", top=1.10020, bottom=1.09980)],
        structure_levels=[
            StructureLevel(level=1.10100, type="high", strength=3),
            StructureLevel(level=1.09500, type="low", strength=4),
        ],
    )
    data.update(overrides)
    return _base_snapshot(**data)


# -- long setups -------------------------------------------------------------


def test_long_setup_valid() -> None:
    result = evaluate(_long_snapshot())
    assert result.setup is not None
    assert result.no_setup_reason is None
    assert result.setup.side == TradeSide.buy
    assert result.setup.strategy_id == STRATEGY_ID
    assert result.setup.strategy_name == STRATEGY_NAME


def test_long_sl_below_structure_low() -> None:
    snap = _long_snapshot()
    result = evaluate(snap)
    assert result.setup is not None
    # SL sits below the nearest structure low (1.09900) with buffer
    assert result.setup.stop_loss < 1.09900
    assert result.setup.stop_loss == 1.09900 * (1 - 0.0005)


def test_long_target_uses_structure_liquidity() -> None:
    snap = _long_snapshot()
    result = evaluate(snap)
    assert result.setup is not None
    # Final target (TP2) reaches the structure high at 1.10500
    tp2 = result.setup.take_profits[-1]
    assert tp2.price >= 1.10500


def test_long_two_tps_with_partial_closes() -> None:
    result = evaluate(_long_snapshot())
    assert result.setup is not None
    tps = result.setup.take_profits
    assert len(tps) == 2
    assert tps[0].close_pct == 50
    assert tps[1].close_pct == 100
    # TP1 below TP2 for a long
    assert tps[0].price < tps[1].price


def test_long_meets_min_rr() -> None:
    result = evaluate(_long_snapshot())
    assert result.setup is not None
    assert result.setup.risk_reward >= MIN_RISK_REWARD


# -- short setups ------------------------------------------------------------


def test_short_setup_valid() -> None:
    result = evaluate(_short_snapshot())
    assert result.setup is not None
    assert result.setup.side == TradeSide.sell


def test_short_sl_above_structure_high() -> None:
    result = evaluate(_short_snapshot())
    assert result.setup is not None
    assert result.setup.stop_loss > 1.10100
    assert result.setup.stop_loss == 1.10100 * (1 + 0.0005)


def test_short_target_uses_structure_liquidity() -> None:
    result = evaluate(_short_snapshot())
    assert result.setup is not None
    tp2 = result.setup.take_profits[-1]
    assert tp2.price <= 1.09500


def test_short_two_tps_ordered() -> None:
    result = evaluate(_short_snapshot())
    assert result.setup is not None
    tps = result.setup.take_profits
    assert len(tps) == 2
    # TP1 above TP2 for a short
    assert tps[0].price > tps[1].price


# -- session gate ------------------------------------------------------------


def test_off_session_no_setup() -> None:
    result = evaluate(_long_snapshot(session="off"))
    assert result.setup is None
    assert "off" in result.no_setup_reason.lower()


def test_asian_session_no_setup() -> None:
    result = evaluate(_long_snapshot(session="asian"))
    assert result.setup is None
    assert result.no_setup_reason is not None


def test_active_sessions_constant() -> None:
    assert ACTIVE_SESSIONS == ("london", "ny")


# -- no-setup scenarios ------------------------------------------------------


def test_neutral_htf_no_setup() -> None:
    result = evaluate(_long_snapshot(htf_bias=HTFBias.neutral))
    assert result.setup is None
    assert "neutral" in result.no_setup_reason.lower()


def test_bullish_no_fvg_no_setup() -> None:
    result = evaluate(_long_snapshot(fvgs=[]))
    assert result.setup is None
    assert "fvg" in result.no_setup_reason.lower()


def test_mitigated_fvg_no_setup() -> None:
    result = evaluate(
        _long_snapshot(
            fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980, mitigated=True)]
        )
    )
    assert result.setup is None


def test_price_outside_fvg_no_setup() -> None:
    # Price above the FVG range -> not inside
    result = evaluate(
        _long_snapshot(
            current_price=1.10050,
            fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
        )
    )
    assert result.setup is None


def test_wrong_direction_fvg_no_setup() -> None:
    # Bullish bias but only a bearish FVG present
    result = evaluate(
        _long_snapshot(fvgs=[FairValueGap(side="bearish", top=1.10020, bottom=1.09980)])
    )
    assert result.setup is None


# -- fallback SL when no structure ------------------------------------------


def test_long_sl_falls_back_to_fvg_when_no_structure() -> None:
    snap = _long_snapshot(structure_levels=[])
    result = evaluate(snap)
    assert result.setup is not None
    # No structure -> SL derived from FVG bottom (1.09980) with buffer
    assert result.setup.stop_loss == 1.09980 * (1 - 0.0005)


def test_result_setup_xor_reason() -> None:
    for snap in (_long_snapshot(), _long_snapshot(session="off")):
        result = evaluate(snap)
        assert (result.setup is None) != (result.no_setup_reason is None)
