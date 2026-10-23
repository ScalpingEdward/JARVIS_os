from app.copier_status import review

T0 = 1_800_000_000


def bars_with(lows_highs, start=T0 - 4 * 3600, step=300, base=4100.0):
    """Candles every 5 minutes: (low, high) pairs, open/close in the middle."""
    out = []
    for i, (lo, hi) in enumerate(lows_highs):
        mid = (lo + hi) / 2
        out.append([start + i * step, mid, hi, lo, mid])
    return out


def test_a_tight_stop_in_front_of_the_swing_that_got_hunted():
    # 4 h before entry: price around 4100, a clear swing low at 4090; 2 pips of noise per candle
    before = [(4099, 4101)] * 40 + [(4095, 4100), (4092, 4097), (4090, 4096), (4093, 4098), (4096, 4100)] + [(4099, 4101)] * 3
    during = [(4097, 4101), (4093.5, 4099)]                    # dips to the stop at 4094
    after = [(4096, 4104), (4103, 4112), (4110, 4121)]          # then runs to the TP at 4120
    bars = bars_with(before + during + after)
    entry_t = bars[len(before)][0]
    t = {"position": 1, "symbol": "XAUUSD.s", "side": "buy", "price_open": 4100.0, "price_close": 4094.0,
         "sl": 4094.0, "tp": 4120.0, "opened": entry_t, "closed": entry_t + 600, "reason": "sl", "profit": -60.0}
    r = review.measure(t, bars)
    assert r["sl_pips"] == 60.0 and r["rr"] == 3.33
    assert r["swing"] == 4090 and r["sl_behind_swing"] is False          # the stop sat above the low: easy to take
    assert r["hunt"] is True and r["hunt_minutes_after"] <= 15
    assert r["sl_atr"] is not None and r["mfe_r"] <= 0.2


def test_summary_counts_what_matters():
    rows = [{"profit": -50, "reason": "sl", "sl_atr": 0.7, "sl_behind_swing": False, "hunt": True, "mfe_r": 0.3},
            {"profit": -40, "reason": "sl", "sl_atr": 0.9, "sl_behind_swing": True, "hunt": False, "mfe_r": 0.1},
            {"profit": 120, "reason": "tp", "sl_atr": 1.8, "sl_behind_swing": True}]
    s = review.summary(rows)
    assert (s["trades"], s["wins"], s["losses"], s["stopped_out"], s["hunted"], s["sl_in_front_of_swing"]) == (3, 1, 2, 2, 1, 1)
    assert s["avg_sl_atr_losses"] == 0.8 and s["net"] == 30


def test_gold_pips_with_the_brokers_name():
    assert review.pip_size("XAUUSD.s") == 0.1 and review.pip_size("EURUSD.s") == 0.0001 and review.pip_size("NAS100.s") == 1.0
