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


def excess_returns(filed: str, closes: list[tuple[date, float]], bench: dict[date, float]) -> dict[int, float] | None:
    """Stock minus S&P 500 over each horizon, entered at the first close after the filing date.
    closes: the stock's (day, close), oldest first; bench: the index's close per day."""
    d0 = date.fromisoformat(filed)
    start = next((i for i, (d, _) in enumerate(closes) if d > d0 and d in bench), None)
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
        "events": len(evts), "buys": len(buys), "with_prices": sum(1 for e in evts if e.get("ret")),
    }
