from signal_copier.market_feed import facts, rsi, sma


def test_sma_and_rsi_basics():
    assert sma([1, 2, 3, 4], 2) == 3.5 and sma([1], 2) is None
    assert rsi([float(x) for x in range(1, 40)]) == 100.0           # only gains
    falling = [float(x) for x in range(40, 1, -1)]
    assert rsi(falling) < 1                                          # only losses


def test_a_pullback_is_described_in_plain_words():
    # a year of rising prices to 200, then a slide to 150
    closes = [100 + i * 0.4 for i in range(250)] + [200 - i * 5 for i in range(10)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    f = facts(150.0, closes, highs, lows)
    assert f["from_high_pct"] < -20 and any("unter dem 52-Wochen-Hoch" in n for n in f["notes"])
    assert any("200-Tage-Schnitt" in n for n in f["notes"])
    assert any("überverkauft" in n for n in f["notes"])
    assert len(f["spark"]) == 30


def test_a_price_near_its_high_says_so():
    closes = [100 + i for i in range(260)]
    f = facts(closes[-1], closes, [c + .5 for c in closes], [c - .5 for c in closes])
    assert "nahe am 52-Wochen-Hoch" in f["notes"] and f["change_pct"] > 0
