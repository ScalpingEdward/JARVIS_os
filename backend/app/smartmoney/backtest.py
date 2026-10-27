"""Does it pay to follow insiders? The arithmetic, without I/O.

tools/insider_backtest.py feeds this with the SEC's quarterly insider data sets (every
Form 4 of every US company) and daily prices from MT5, and posts the result to the API.

An event is one Form 4 filing with open-market buys (P) -- or, for comparison, large
sales (S). It counts from the FILING date, the day the market could know it, and is
entered at the close of the first trading day after it. Its result is the stock's move
over the next N trading days minus the S&P 500's move over the same days: the excess.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date

HORIZONS = (5, 20, 60, 120)
HOLD = 60                 # the position: held 60 trading days
HOLD_CALENDAR_DAYS = 90   # ...which is about this long -- when its result is known
COST = 0.01               # spread + overnight financing over ~3 months, per position
PROFI_MIN_N, PROFI_MIN_HIT = 3, 0.6
MIN_BUY = 25_000          # smaller buys are noise
MIN_SALE = 1_000_000      # only big sales, as a comparison
CLUSTER_DAYS = 14


def _f(x: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def role_of(relationship: str, title: str) -> str:
    """CEO/CFO, other officer, director, 10 % owner -- the groups the evaluation compares."""
    t = (title or "").upper()
    rel = (relationship or "").upper()
    if any(k in t for k in ("CEO", "CHIEF EXECUTIVE", "PRESIDENT", "CFO", "CHIEF FINANCIAL")):
        return "CEO/CFO"
    if "OFFICER" in rel or t:
        return "Officer"
    if "DIRECTOR" in rel:
        return "Director"
    if "TENPERCENT" in rel.replace(" ", ""):
        return "10%-Owner"
    return "Other"


def events(submissions: dict[str, dict], owners: dict[str, dict], trans: list[dict]) -> list[dict]:
    """One event per filing and direction. submissions/owners keyed by accession number;
    trans: rows of NONDERIV_TRANS (ACCESSION_NUMBER, TRANS_CODE, TRANS_SHARES, TRANS_PRICEPERSHARE)."""
    agg: dict[tuple[str, str], dict] = {}
    for t in trans:
        code = (t.get("TRANS_CODE") or "").strip()
        if code not in ("P", "S"):
            continue
        acc = t["ACCESSION_NUMBER"]
        sub = submissions.get(acc)
        if not sub or not (sub.get("ISSUERTRADINGSYMBOL") or "").strip():
            continue
        e = agg.setdefault((acc, code), {"acc": acc, "code": code, "value": 0.0, "shares": 0.0,
                                          "ticker": sub["ISSUERTRADINGSYMBOL"].strip().upper(),
                                          "issuer": (sub.get("ISSUERNAME") or "").strip(),
                                          "filed": sub["FILING_DATE"]})
        sh, px = _f(t.get("TRANS_SHARES")), _f(t.get("TRANS_PRICEPERSHARE"))
        e["shares"] += sh
        e["value"] += sh * px
    out = []
    for (acc, code), e in agg.items():
        if (code == "P" and e["value"] < MIN_BUY) or (code == "S" and e["value"] < MIN_SALE):
            continue
        o = owners.get(acc, {})
        e["owner"] = (o.get("RPTOWNERNAME") or "").strip()
        e["role"] = role_of(o.get("RPTOWNER_RELATIONSHIP", ""), o.get("RPTOWNER_TITLE", ""))
        out.append(e)
    return out


def mark_clusters(evts: list[dict]) -> None:
    """A buy is part of a cluster when another insider of the same company bought within 14 days."""
    by: dict[str, list[dict]] = defaultdict(list)
    for e in evts:
        if e["code"] == "P":
            by[e["ticker"]].append(e)
    for lst in by.values():
        for e in lst:
            d = date.fromisoformat(e["filed"])
            e["cluster"] = any(o is not e and o["owner"] != e["owner"]
                               and abs((date.fromisoformat(o["filed"]) - d).days) <= CLUSTER_DAYS for o in lst)


MAX_ENTRY_GAP_DAYS = 5   # the entry close must follow the filing closely


def _entry(filed: str, closes: list[tuple[date, float]], bench: dict[date, float]) -> int | None:
    """Index of the first close after the filing -- None when the price history starts later
    (MT5 keeps ~2000 bars, fewer for some stocks): taking the first bar there would hand every
    older filing the same, wrong move."""
    from datetime import timedelta
    d0 = date.fromisoformat(filed)
    start = next((i for i, (d, _) in enumerate(closes) if d > d0 and d in bench), None)
    if start is None or closes[start][0] > d0 + timedelta(days=MAX_ENTRY_GAP_DAYS):
        return None
    return start


def excess_returns(filed: str, closes: list[tuple[date, float]], bench: dict[date, float]) -> dict[int, float] | None:
    """Stock minus S&P 500 over each horizon, entered at the first close after the filing date.
    closes: the stock's (day, close), oldest first; bench: the index's close per day."""
    start = _entry(filed, closes, bench)
    if start is None:
        return None
    out = {}
    s_day, s_px = closes[start]
    for h in HORIZONS:
        j = start + h
        if j >= len(closes):
            continue
        e_day, e_px = closes[j]
        if e_day not in bench or s_px <= 0 or bench[s_day] <= 0:
            continue
        out[h] = round((e_px / s_px - 1) - (bench[e_day] / bench[s_day] - 1), 5)
    return out or None


def position_returns(filed: str, closes: list[tuple[date, float]], bench: dict[date, float]) -> dict[int, dict] | None:
    """The stock's own move and the S&P 500's over each horizon, from the first close after the filing."""
    start = _entry(filed, closes, bench)
    if start is None:
        return None
    s_day, s_px = closes[start]
    out = {}
    for h in HORIZONS:
        j = start + h
        if j >= len(closes):
            continue
        e_day, e_px = closes[j]
        if e_day not in bench or s_px <= 0 or bench[s_day] <= 0:
            continue
        out[h] = {"stock": round(e_px / s_px - 1, 5), "market": round(bench[e_day] / bench[s_day] - 1, 5)}
    return out or None


def signal_profit(e: dict, horizon: int = HOLD, cost: float = COST) -> float | None:
    """What following this one signal made: a buy taken long, a sale taken short, minus costs."""
    mv = (e.get("move") or {}).get(horizon, (e.get("move") or {}).get(str(horizon)))
    if not mv:
        return None
    return round((mv["stock"] if e["code"] == "P" else -mv["stock"]) - cost, 5)


FOLLOW_CODES = ("P",)   # 7 years (2019-2026): shorting insider sales lost -3.7 % per 60 days
                         # (-11 % behind "proven" sellers) in a rising market; only buys are followed.
                         # Re-tested 2026-10-19 with a market filter known at filing time (S&P 500 below its
                         # 200-day average): still -5.2 % per 60 days (2,752 shorts, 44 % hits), "proven"
                         # sellers -12 %; only 2022 broke even (+1.1 %). The +8.8 % seen when the market FELL
                         # during the hold was hindsight -- nobody knows that at filing time. Shorts stay out.


def by_signaler(evts: list[dict], horizon: int = HOLD, codes: tuple = FOLLOW_CODES) -> list[dict]:
    """Per insider (the person, across companies): every buy (by default only buys, see
    FOLLOW_CODES) as a position.
    hit = share of positions in profit after costs; avg/total = profit per position and summed;
    market = the S&P 500 over the same days, on average; value = the dollars they put in, summed. verdict: 'profi' (>= 3 signals,
    >= 60 % hits, average in profit), 'weg' (<= 40 % hits or average in loss), else 'offen'."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in evts:
        if e.get("owner") and e["code"] in codes and signal_profit(e, horizon) is not None:
            groups[e["owner"]].append(e)
    out = []
    for owner, lst in groups.items():
        prof = [signal_profit(e, horizon) for e in lst]
        mkt = [((e["move"].get(horizon) or e["move"].get(str(horizon)))["market"]) for e in lst]
        hit = sum(v > 0 for v in prof) / len(prof)
        avg = statistics.fmean(prof)
        n = len(prof)
        verdict = "profi" if n >= PROFI_MIN_N and hit >= PROFI_MIN_HIT and avg > 0 else \
                  "weg" if n >= PROFI_MIN_N and (hit <= 0.4 or avg < 0) else "offen"
        out.append({"owner": owner, "tickers": sorted({e["ticker"] for e in lst}), "role": lst[0].get("role", ""),
                    "n": n, "buys": sum(e["code"] == "P" for e in lst), "sales": sum(e["code"] == "S" for e in lst),
                    "hit": round(hit, 3), "avg": round(avg, 4), "total": round(sum(prof), 4),
                    "market": round(statistics.fmean(mkt), 4), "last": max(e["filed"] for e in lst), "verdict": verdict,
                    "value": round(sum(e.get("value", 0) for e in lst))})   # dollars put in across these positions
    out.sort(key=lambda x: (x["verdict"] != "profi", -x["avg"] * min(x["n"], 10)))
    return out


CONTRA_MAX_HIT = 0.35    # an insider this often wrong (with >= 3 known results) is traded against


def walk_forward(evts: list[dict], horizon: int = HOLD, contra: bool = False, codes: tuple = FOLLOW_CODES) -> dict:
    """The honest test: go through the signals in time order; follow one only if its insider
    already qualified for the profi list on results known BEFORE that day. No hindsight.
    contra=True: the mirror -- trade AGAINST insiders who had proven themselves wrong."""
    from datetime import timedelta
    held_days = round(horizon * HOLD_CALENDAR_DAYS / HOLD)
    timeline = sorted((e for e in evts if e.get("owner") and e["code"] in codes and signal_profit(e, horizon) is not None),
                      key=lambda e: e["filed"])
    history: dict[str, list[tuple[date, float]]] = defaultdict(list)  # owner -> (result known on, profit)
    taken = []
    for e in timeline:
        d = date.fromisoformat(e["filed"])
        known = [p for (k, p) in history[e["owner"]] if k <= d]
        raw = signal_profit(e, horizon, cost=0)
        if len(known) >= PROFI_MIN_N:
            hit = sum(p > 0 for p in known) / len(known)
            if not contra and hit >= PROFI_MIN_HIT and statistics.fmean(known) > 0:
                taken.append({"filed": e["filed"], "owner": e["owner"], "ticker": e["ticker"],
                              "side": "long" if e["code"] == "P" else "short", "profit": round(raw - COST, 5)})
            elif contra and hit <= CONTRA_MAX_HIT and statistics.fmean(known) < 0:
                taken.append({"filed": e["filed"], "owner": e["owner"], "ticker": e["ticker"],
                              "side": "short" if e["code"] == "P" else "long", "profit": round(-raw - COST, 5)})
        history[e["owner"]].append((d + timedelta(days=held_days), signal_profit(e, horizon)))
    prof = [t["profit"] for t in taken]
    by_year: dict[str, list[float]] = defaultdict(list)
    for t in taken:
        by_year[t["filed"][:4]].append(t["profit"])
    every = [signal_profit(e, horizon) for e in timeline]
    return {
        "followed": {"n": len(prof), "hit": round(sum(v > 0 for v in prof) / len(prof), 3) if prof else None,
                     "avg": round(statistics.fmean(prof), 4) if prof else None, "total": round(sum(prof), 4)},
        "all_signals": {"n": len(every), "hit": round(sum(v > 0 for v in every) / len(every), 3) if every else None,
                        "avg": round(statistics.fmean(every), 4) if every else None},
        "by_year": {y: {"n": len(v), "hit": round(sum(x > 0 for x in v) / len(v), 3), "avg": round(statistics.fmean(v), 4)}
                    for y, v in sorted(by_year.items())},
        "recent": taken[-25:][::-1],
        "rules": {"hold_days": horizon, "cost": COST, "min_n": PROFI_MIN_N, "min_hit": PROFI_MIN_HIT, "contra": contra,
                  "codes": list(codes)},
    }


def strategies(evts: list[dict]) -> dict:
    """Which way of working with insider signals has paid -- all walk-forward, after costs:
    follow the proven ones for 5 / 20 / 60 / 120 trading days, or trade against the proven-wrong."""
    out = {}
    for h in HORIZONS:
        f = walk_forward(evts, h)["followed"]
        out[f"follow_{h}"] = {**f, "label": f"Käufe der Profis long, {h} Handelstage", "hold_days": h}
    a = walk_forward(evts, HOLD)["all_signals"]
    out["all_buys"] = {**a, "label": f"Jeden Insider-Kauf long, {HOLD} Handelstage", "hold_days": HOLD}
    s = walk_forward(evts, HOLD, codes=("S",))
    out["short_sales"] = {**s["all_signals"], "label": f"Jeden großen Verkauf short, {HOLD} Handelstage", "hold_days": HOLD}
    out["short_profi_sellers"] = {**s["followed"], "label": f"Verkäufe der 'Profi'-Verkäufer short, {HOLD} Handelstage", "hold_days": HOLD}
    c = walk_forward(evts, HOLD, contra=True, codes=("P", "S"))["followed"]
    out["contra"] = {**c, "label": f"Gegen die Dauer-Falschen, {HOLD} Handelstage", "hold_days": HOLD}
    return out


def _stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "avg": round(statistics.fmean(vals), 4), "median": round(statistics.median(vals), 4),
            "hit": round(sum(v > 0 for v in vals) / len(vals), 3)}


def _r(ret: dict, h: int):
    """The result at a horizon -- keys are ints here, strings after a JSON round trip."""
    return ret.get(h, ret.get(str(h))) if ret else None


def by_insider(evts: list[dict], horizon: int = 60, min_n: int = 3) -> list[dict]:
    """Each insider's record at one company, buys and sales apart.

    Buyers: a buy was right when the stock then beat the S&P 500 -> 'folgen' (>= 60 % right
    and ahead on average) or 'aussortieren' (<= 40 % right or behind on average).
    Sellers: a sale was right when the stock then lagged -> 'warnung' (his sales were a real
    warning) or 'ignorieren' (they said nothing). In between: 'offen'.
    edge: average of +excess for buys and -excess for sales, so positive is always good."""
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for e in evts:
        if _r(e.get("ret") or {}, horizon) is not None and e.get("owner"):
            groups[(e["owner"], e["ticker"], e["code"])].append(e)
    out = []
    for (owner, ticker, code), lst in groups.items():
        if len(lst) < min_n:
            continue
        signed = [(_r(e["ret"], horizon) if code == "P" else -_r(e["ret"], horizon)) for e in lst]
        right = sum(v > 0 for v in signed) / len(signed)
        edge = statistics.fmean(signed)
        good, bad = ("folgen", "aussortieren") if code == "P" else ("warnung", "ignorieren")
        verdict = good if right >= 0.6 and edge > 0 else bad if right <= 0.4 or edge < 0 else "offen"
        out.append({"owner": owner, "ticker": ticker, "role": lst[0].get("role", ""), "side": "buy" if code == "P" else "sell",
                    "n": len(lst), "right": round(right, 3), "edge": round(edge, 4), "verdict": verdict})
    out.sort(key=lambda x: (-x["edge"], -x["n"]))
    return out


def summarize(evts: list[dict]) -> dict:
    """Averages, medians and hit rates of the excess return, overall and by group."""
    def table(select) -> dict:
        groups: dict[str, list[dict]] = defaultdict(list)
        for e in evts:
            if e.get("ret"):
                for g in select(e):
                    groups[g].append(e)
        return {g: {str(h): _stats([_r(e["ret"], h) for e in lst if _r(e["ret"], h) is not None]) for h in HORIZONS}
                for g, lst in groups.items()}

    def size(e):
        v = e["value"]
        return ["≥ 1 Mio $" if v >= 1e6 else "100k–1 Mio $" if v >= 1e5 else "< 100k $"]

    buys = [e for e in evts if e["code"] == "P"]
    return {
        "overall": table(lambda e: ["Käufe" if e["code"] == "P" else "Große Verkäufe"]),
        "by_role": table(lambda e: [e["role"]] if e["code"] == "P" else []),
        "by_size": table(lambda e: size(e) if e["code"] == "P" else []),
        "by_cluster": table(lambda e: (["Cluster" if e.get("cluster") else "Einzeln"]) if e["code"] == "P" else []),
        "by_ticker": table(lambda e: [e["ticker"]] if e["code"] == "P" else []),
        "by_insider": by_insider(evts),
        "by_signaler": by_signaler(evts),
        "walk_forward": walk_forward(evts),
        "strategies": strategies(evts),
        "events": len(evts), "buys": len(buys), "with_prices": sum(1 for e in evts if e.get("ret")),
    }
