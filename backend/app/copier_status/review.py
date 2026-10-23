"""AURON looks back at a group's trades (Brano, 2026-10-23: "four stop losses in a row -- bad entries, a stop
too tight, levels in the wrong place?").

For each closed trade the numbers are worked out here, the same way every time; AURON reads them and
gives his opinion. Definitions -- v1, to be checked against how the trades really went:
  ATR        mean true range of the 14 five-minute candles before the entry
  sl_atr     the stop's distance from the entry, in ATRs (below ~1: inside normal noise)
  swing      the last fractal low (buy) / high (sell) of the 4 hours before the entry: a candle whose low
             (high) is below (above) the two candles on each side
  sl_behind  the stop sits beyond that swing (protected) -- or in front of it, where it is easy to take
  mfe_r      how far the trade ran in its favour before it closed, in R (R = entry-to-stop distance)
  hunt       closed at its stop, and within 4 hours price reached its TP (or 2 R if it had none)
  late_pips  how far price had run from the signal's price when the copier saw it (the copier's timing)
"""
from __future__ import annotations

import re
import time

BEFORE_S, AFTER_S, MIN_SPAN_S = 4 * 3600, 4 * 3600, 3600


def pip_size(symbol: str) -> float:
    """The copier's pips (signal_copier/sizing.py), for the broker's names too: XAUUSD.s is gold."""
    s = re.split(r"[._#\-]", symbol.upper())[0]
    if s in ("XAUUSD", "GOLD"):
        return 0.1
    if s in ("XAGUSD", "SILVER"):
        return 0.01
    if s in {"NAS100", "US100", "USTEC", "US30", "DJ30", "US500", "SP500", "GER40", "DE40", "BTCUSD"}:
        return 1.0
    if s in ("USOIL", "USOUSD", "UKOUSD", "XTIUSD"):
        return 0.01
    return 0.01 if s.endswith("JPY") else 0.0001


def atr(bars: list[list[float]], n: int = 14) -> float | None:
    if len(bars) < n + 1:
        return None
    tr = [max(b[2] - b[3], abs(b[2] - a[4]), abs(b[3] - a[4])) for a, b in zip(bars[-n - 1:-1], bars[-n:])]
    return sum(tr) / n


def swing(bars: list[list[float]], side: str) -> float | None:
    """The newest fractal low (buy) or high (sell) -- not the last two candles, they have no right side yet."""
    for i in range(len(bars) - 3, 1, -1):
        if side == "buy" and bars[i][3] < min(bars[i - 1][3], bars[i - 2][3], bars[i + 1][3], bars[i + 2][3]):
            return bars[i][3]
        if side == "sell" and bars[i][2] > max(bars[i - 1][2], bars[i - 2][2], bars[i + 1][2], bars[i + 2][2]):
            return bars[i][2]
    return None


def measure(t: dict, bars: list[list[float]]) -> dict:
    """One trade against the candles around it."""
    side, entry, sl, tp = t["side"], t["price_open"], t.get("sl") or 0, t.get("tp") or 0
    opened, closed = t.get("opened") or t["closed"], t["closed"]
    sign = 1 if side == "buy" else -1
    pip = pip_size(t["symbol"])
    before = [b for b in bars if opened - BEFORE_S <= b[0] < opened]
    during = [b for b in bars if opened - 300 < b[0] < closed]          # the candles the trade lived in
    after = [b for b in bars if closed < b[0] <= closed + AFTER_S]
    out = {"position": t["position"], "symbol": t["symbol"], "side": side, "opened": opened, "closed": closed,
           "minutes": round((closed - opened) / 60), "entry": entry, "exit": t["price_close"], "sl": sl or None, "tp": tp or None,
           "reason": t.get("reason") or ("sl" if "[sl" in t.get("comment", "") else "tp" if "[tp" in t.get("comment", "") else ""),
           "profit": t["profit"]}
    a = atr(before)
    risk = abs(entry - sl) if sl else None
    if a:
        out["atr_pips"] = round(a / pip, 1)
    if risk:
        out["sl_pips"] = round(risk / pip, 1)
        if a:
            out["sl_atr"] = round(risk / a, 2)
    if tp and risk:
        out["rr"] = round(abs(tp - entry) / risk, 2)
    s = swing(before, side)
    if s is not None:
        out["swing"] = s
        out["swing_pips_from_entry"] = round((entry - s) * sign / pip, 1)
        if sl:
            out["sl_behind_swing"] = (sl - s) * sign < 0          # buy: stop below the low
            out["sl_beyond_swing_pips"] = round((s - sl) * sign / pip, 1)
    if during and risk:
        best = max(b[2] for b in during) if side == "buy" else min(b[3] for b in during)
        out["mfe_r"] = round((best - entry) * sign / risk, 2)
    if out["reason"] == "sl" and after:
        target = tp or (entry + sign * 2 * (risk or 0))
        if target and target != entry:
            hit = next((b for b in after if (b[2] >= target if side == "buy" else b[3] <= target)), None)
            out["hunt"] = bool(hit)
            if hit:
                out["hunt_minutes_after"] = round((hit[0] - closed) / 60)
    return out


def summary(rows: list[dict]) -> dict:
    losses = [r for r in rows if r["profit"] < 0]
    pick = lambda key, rs: [r[key] for r in rs if r.get(key) is not None]
    avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    return {"trades": len(rows), "wins": sum(1 for r in rows if r["profit"] > 0), "losses": len(losses),
            "net": round(sum(r["profit"] for r in rows), 2),
            "stopped_out": sum(1 for r in rows if r["reason"] == "sl"),
            "avg_sl_atr": avg(pick("sl_atr", rows)), "avg_sl_atr_losses": avg(pick("sl_atr", losses)),
            "sl_in_front_of_swing": sum(1 for r in rows if r.get("sl_behind_swing") is False),
            "hunted": sum(1 for r in rows if r.get("hunt")),
            "avg_mfe_r_losses": avg(pick("mfe_r", losses)),
            "avg_late_pips": avg(pick("late_pips", rows))}


def review(group: str, last: int = 12, wait_s: float = 25) -> dict:
    """The group's last closed trades, measured. Candles come from the copier that traded them."""
    from app.copier_status import api
    from app.copier_status.service import copier_status_service
    g = group.strip().lower()
    trades, timings = [], []
    for a in copier_status_service.overview().accounts:
        trades += [(a.profile, t.model_dump()) for t in a.closed if g in t.group.lower()]
        timings += [(a.profile, x) for x in a.timings]
    if not trades:
        return {"error": f"keine abgeschlossenen Trades von {group!r}"}
    trades = sorted(trades, key=lambda x: x[1]["closed"], reverse=True)[:max(1, min(last, 40))]
    by = {}
    for prof, t in trades:
        by.setdefault((prof, t["symbol"]), []).append(t)
    keys = {}
    for (prof, sym), ts in by.items():
        start = min((t.get("opened") or t["closed"]) for t in ts) - BEFORE_S
        end = min(max(t["closed"] for t in ts) + AFTER_S, time.time())
        keys[(prof, sym)] = api.want_hist(prof, sym, start - start % 300, max(end - end % 300, start + MIN_SPAN_S))
    deadline = time.time() + wait_s
    bars = {}
    while time.time() < deadline and len(bars) < len(keys):
        for k, key in keys.items():
            if k not in bars and (got := api.hist(k[0], key)) is not None:
                bars[k] = got
        time.sleep(0.5)
    rows = []
    for prof, t in trades:
        r = measure(t, bars.get((prof, t["symbol"]), []))
        tm = min((x for p, x in timings if p == prof and x.get("side") == t["side"] and x.get("received_at")
                  and abs(x["received_at"] - (t.get("opened") or 0)) < 600),
                 key=lambda x: abs(x["received_at"] - (t.get("opened") or 0)), default=None)
        if tm:
            r["late_pips"] = tm.get("drift_pips")
            r["signal_delay_s"] = tm.get("delay_s")
        rows.append(r)
    missing = [f"{p}/{s}" for (p, s) in keys if (p, s) not in bars]
    return {"group": group, "summary": summary(rows), "trades": rows,
            "definitions": __doc__.split("v1, to be checked against how the trades really went:")[1].strip(),
            **({"no_candles": missing, "note": "the copier did not send candles in time -- levels without ATR/swing"} if missing else {}),
            **({"note_sl": "no SL/TP recorded for these trades yet (older copier) -- the copier reports them from now on"}
               if not any(r["sl"] for r in rows) else {})}
