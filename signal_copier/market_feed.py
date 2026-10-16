"""Watchlist feed: prices and a few plain facts per symbol from MT5, pushed to AURON.

    python -m signal_copier.market_feed

Read-only towards MT5 (quotes and daily bars, never an order). The list is
watchlist.json; symbols PU Prime does not offer (mt5: null) are sent without a
price so the dashboard can say so.

What it computes is observation, not advice: where the price stands against
its 52-week range, its 50- and 200-day averages and the 14-day RSI. Whether
any of that is a reason to buy is Brano's call.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
QUOTES_EVERY_S = 60
BARS_EVERY_S = 15 * 60
log = logging.getLogger("market_feed")


def sma(values: list[float], n: int) -> float | None:
    return sum(values[-n:]) / n if len(values) >= n else None


def rsi(closes: list[float], n: int = 14) -> float | None:
    """Wilder's RSI over daily closes."""
    if len(closes) <= n:
        return None
    gains, losses = [], []
    for a, b in zip(closes[:-1], closes[1:]):
        d = b - a
        gains.append(max(d, 0.0)); losses.append(max(-d, 0.0))
    avg_g, avg_l = sum(gains[:n]) / n, sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        avg_g = (avg_g * (n - 1) + g) / n
        avg_l = (avg_l * (n - 1) + l) / n
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


def facts(price: float, closes: list[float], highs: list[float], lows: list[float]) -> dict:
    """The numbers and the plain-language notes the dashboard shows for one symbol.
    closes/highs/lows: daily bars, oldest first, the last one being today's."""
    year_h, year_l = (max(highs[-260:]), min(lows[-260:])) if highs else (None, None)
    prev = closes[-2] if len(closes) >= 2 else None
    s50, s200, r = sma(closes, 50), sma(closes, 200), rsi(closes)
    pct = lambda a, b: round((a / b - 1) * 100, 2) if a is not None and b else None
    out = {
        "price": price, "change_pct": pct(price, prev),
        "high_52w": year_h, "low_52w": year_l, "from_high_pct": pct(price, year_h),
        "sma50": s50, "sma200": s200, "vs_sma50_pct": pct(price, s50), "vs_sma200_pct": pct(price, s200),
        "rsi14": round(r, 1) if r is not None else None,
        "spark": [round(c, 6) for c in closes[-30:]],
    }
    notes = []
    if out["from_high_pct"] is not None and out["from_high_pct"] <= -20:
        notes.append(f"{abs(out['from_high_pct']):.0f} % unter dem 52-Wochen-Hoch")
    if year_l and price <= year_l * 1.05:
        notes.append("nahe am 52-Wochen-Tief")
    if s200 and price < s200:
        notes.append("unter dem 200-Tage-Schnitt")
    if r is not None and r < 30:
        notes.append(f"RSI {r:.0f} – überverkauft")
    elif r is not None and r > 70:
        notes.append(f"RSI {r:.0f} – überkauft")
    if out["from_high_pct"] is not None and out["from_high_pct"] > -3:
        notes.append("nahe am 52-Wochen-Hoch")
    out["notes"] = notes
    return out


def push(url: str, payload: dict) -> None:
    req = urllib.request.Request(url.rstrip("/") + "/v1/watchlist/snapshot", json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20).read()


def main() -> None:
    import MetaTrader5 as mt5
    from dotenv import load_dotenv

    load_dotenv(HERE / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(HERE / "market_feed.log", encoding="utf-8"), logging.StreamHandler()])
    cfg = json.loads((HERE / "watchlist.json").read_text(encoding="utf-8"))
    url = os.environ.get("AURON_URL") or "http://localhost:8000"
    if not mt5.initialize(path=cfg["terminal"]):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    items = cfg["items"]
    for it in items:
        if it.get("mt5"):
            mt5.symbol_select(it["mt5"], True)
    bars: dict[str, tuple[list, list, list]] = {}
    bars_at = 0.0
    log.info("market feed started: %d symbols, %d without MT5 data", len(items), sum(1 for i in items if not i.get("mt5")))
    failing = False
    while True:
        now = time.time()
        if now - bars_at > BARS_EVERY_S:
            for it in items:
                sym = it.get("mt5")
                if not sym:
                    continue
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 260)
                if rates is not None and len(rates):
                    bars[sym] = ([float(r["close"]) for r in rates], [float(r["high"]) for r in rates], [float(r["low"]) for r in rates])
            bars_at = now
        rows = []
        for it in items:
            row = {"name": it["name"], "symbol": it.get("mt5"), "category": it["category"], "top": it.get("top")}
            sym = it.get("mt5")
            tick = mt5.symbol_info_tick(sym) if sym else None
            if tick is not None and (tick.bid or tick.last) and sym in bars:
                price = float(tick.bid or tick.last)
                closes, highs, lows = bars[sym]
                closes = closes[:-1] + [price]  # today's bar ends at the live price
                row.update(facts(price, closes, highs, lows))
                row["quoted_at"] = datetime.fromtimestamp(tick.time, timezone.utc).isoformat()
            rows.append(row)
        try:
            push(url, {"items": rows, "captured_at": datetime.now(timezone.utc).isoformat()})
            if failing:
                log.info("AURON reachable again")
            failing = False
        except Exception as e:
            if not failing:
                log.warning("push to AURON failed (%s) -- retrying every minute", e)
            failing = True
        time.sleep(QUOTES_EVERY_S)


if __name__ == "__main__":
    main()
