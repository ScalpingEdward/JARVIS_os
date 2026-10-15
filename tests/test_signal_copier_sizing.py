import pytest

from signal_copier.sizing import RiskProfile, SymbolSpec, entry_deviation_ok, lots_for_risk

EURUSD = SymbolSpec(tick_size=0.00001, tick_value=1.0, volume_min=0.01, volume_max=100, volume_step=0.01)
XAUUSD = SymbolSpec(tick_size=0.01, tick_value=1.0, volume_min=0.01, volume_max=100, volume_step=0.01)


def test_forex_half_percent():
    # 100k, 0.5% = 500 $. 25 pips = 250 ticks of 0.00001 at 1 $ = 250 $/lot -> 2.00 lots.
    assert lots_for_risk(100_000, 0.5, 1.32095, 1.31845, EURUSD) == 2.0


def test_gold_signal_from_channel():
    # 4151 -> 4133 = 18 $ = 1800 ticks = 1800 $/lot; 500 $ -> 0.277 -> 0.27, rounded down.
    assert lots_for_risk(100_000, 0.5, 4151, 4133, XAUUSD) == 0.27


def test_risk_is_adjustable_for_a_live_account():
    assert lots_for_risk(100_000, 1.0, 4151, 4133, XAUUSD) == 0.55


def test_too_small_account_skips_instead_of_oversizing():
    assert lots_for_risk(500, 0.5, 4151, 4133, XAUUSD) == 0.0


def test_capped_at_volume_max():
    spec = SymbolSpec(tick_size=0.00001, tick_value=1.0, volume_min=0.01, volume_max=1.0, volume_step=0.01)
    assert lots_for_risk(10_000_000, 1.0, 1.10000, 1.09990, spec) == 1.0


def test_equal_entry_and_sl_is_an_error():
    with pytest.raises(ValueError):
        lots_for_risk(100_000, 0.5, 1.1, 1.1, EURUSD)


@pytest.mark.parametrize("side,price,ok", [
    ("buy", 1.32095, True),
    ("buy", 1.32125, True),    # 3 pips worse: at the limit
    ("buy", 1.32135, False),   # 4 pips worse
    ("buy", 1.31900, True),    # better price is always fine
    ("sell", 1.32065, True),
    ("sell", 1.32055, False),
])
def test_entry_deviation_forex(side, price, ok):
    assert entry_deviation_ok("GBPUSD", side, 1.32095, price, RiskProfile()) is ok


def test_entry_deviation_per_symbol():
    profile = RiskProfile(max_entry_deviation_pips={"XAUUSD": 20})
    assert entry_deviation_ok("XAUUSD", "buy", 4151, 4153.0, profile)      # 20 pips of 0.1
    assert not entry_deviation_ok("XAUUSD", "buy", 4151, 4153.5, profile)


def test_fixed_lots_fit_the_broker_step_and_minimum():
    from signal_copier.sizing import SymbolSpec, fixed_lots
    spec = SymbolSpec(0.01, 1.0, 0.01, 50.0, 0.01)
    assert fixed_lots(0.01, spec) == 0.01
    assert fixed_lots(0.017, spec) == 0.01
    assert fixed_lots(0.005, spec) == 0.0
    assert fixed_lots(80, spec) == 50.0
