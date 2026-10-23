"""Charts for AURON's dashboard, in their own process -- so a chart never holds up a trade.

    python -m signal_copier.chart_feed        (chart_feed.bat keeps it running; it starts with Windows)

MT5 blocks for about ten seconds the first time a symbol's timeframe is asked (it loads the history then).
While the copiers served the charts, that froze their loop -- signals and orders waited too (2026-10-23).
Now this process does it, on the PU Prime terminal (watchlist.json "terminal", like the market feed):
  rates   the candles of every chart open on a dashboard, about once a second each, newest first
  hist    a past stretch for AURON's trade review, once
  quote   price and contract data for a trade ticket (both accounts are PU Prime EUR, so one terminal serves both)
Read-only towards MT5: no orders, nothing changed in the terminal.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
EVERY_S = 0.25          # how often AURON is asked what is wanted
REFRESH_S = 1.0         # an open chart's candles, again after this
log = logging.getLogger("chart_feed")


def call(url: str, body: dict | None = None):
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    raw = urllib.request.urlopen(req, timeout=10).read()
    return json.loads(raw) if raw else None


def main() -> None:
    from dotenv import load_dotenv

    from signal_copier import execution
    from signal_copier.symbols import resolve

    load_dotenv(HERE / ".env")
    from signal_copier import fast_auron_url
    fast_auron_url()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(HERE / "chart_feed.log", encoding="utf-8"), logging.StreamHandler()])
    terminal = os.environ.get("CHART_TERMINAL") or json.loads((HERE / "watchlist.json").read_text(encoding="utf-8"))["terminal"]
    base = (os.environ.get("AURON_URL") or "http://127.0.0.1:8000").rstrip("/") + "/v1/copier"
    import MetaTrader5 as mt5
    if not mt5.initialize(path=terminal):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    symbols = execution.tradable_symbols()
    real = lambda s: s if s in symbols else (resolve(s, symbols) or s)   # XAUUSD -> XAUUSD.s
    sent: dict[str, float] = {}
    log.info("chart feed started on %s: %d symbols", terminal, len(symbols))
    while True:
        try:
            w = call(f"{base}/feed/wants") or {}
            now = time.monotonic()
            for r in w.get("rates", [])[:4]:                     # newest first; each about once a second
                if now - sent.get(r["profile"] + r["key"], 0) < REFRESH_S:
                    continue
                sym, at, tf = r["key"].partition("@")
                name, t0 = real(sym), time.monotonic()
                bars = execution.rates(name + at + tf)
                took = time.monotonic() - t0
                call(f"{base}/rates", {"profile": r["profile"], "symbol": r["key"], "bars": bars, "name": name})
                if took > 0.5:                                   # MT5 loading a timeframe the first time, mostly
                    log.info("%s took %.1f s in MT5 (%d candles)", r["key"], took, len(bars))
                sent[r["profile"] + r["key"]] = time.monotonic()
            for h in w.get("hist", [])[:2]:
                name = real(h["symbol"])
                call(f"{base}/rates", {"profile": h["profile"], "symbol": h["key"], "name": name,
                                       "bars": execution.rates_range(name, h.get("tf", "M5"), h["from"], h["to"])})
            for q in w.get("quote", [])[:2]:
                name = real(q["symbol"])
                try:
                    body = {"profile": q["profile"], "key": q["key"], **execution.quote(name)}
                except Exception as e:  # noqa: BLE001 -- an unknown symbol: AURON says so
                    body = {"profile": q["profile"], "key": q["key"], "symbol": name, "error": str(e)[:200]}
                call(f"{base}/quote", body)
            if len(sent) > 500:
                sent = {k: v for k, v in sent.items() if now - v < 60}
        except Exception as e:  # noqa: BLE001 -- AURON restarting or MT5 busy: try again shortly
            log.warning("chart feed: %s", e)
            time.sleep(2)
        time.sleep(EVERY_S)


if __name__ == "__main__":
    main()
