"""Insider backtest: does following insider buys pay off? Runs on the laptop (needs MT5).

    python tools/insider_backtest.py            # last 10 quarters, all US companies
    python tools/insider_backtest.py --quarters 4

1. Downloads the SEC's quarterly insider data sets (every Form 4, ~8 MB a quarter) into
   data/insider/ -- once; finished quarters never change.
2. Builds events: per filing, open-market buys of 25k $+ and, for comparison, sales of 1 Mio $+.
3. Daily closes from the PU Prime MT5 terminal for every company it lists (ticker, ticker+USD,
   or the company name), the S&P 500 (SP500.s) as the yardstick.
4. Excess return over 5/20/60/120 trading days from the first close after the filing date.
5. Posts the summary and the per-event results to the API (/v1/smartmoney/backtest).

Needs SEC_CONTACT in .env (the SEC's fair-access rule) and a running PU Prime terminal.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.smartmoney.backtest import events, excess_returns, mark_clusters, position_returns, summarize  # noqa: E402

DATA = ROOT / "data" / "insider"
PRICES = DATA / "prices"
URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
TERMINAL = r"C:\Program Files\PU Prime MT5 Terminal\terminal64.exe"
API = os.getenv("AURON_API", "http://127.0.0.1:8000")
csv.field_size_limit(10**8)


def env(key: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return os.getenv(key, "")


def quarters(n: int) -> list[str]:
    """The last n published quarters (the SEC publishes a quarter some weeks after it ends)."""
    today = date.today()
    y, q = today.year, (today.month - 1) // 3  # the quarter before the current one
    if q == 0:
        y, q = y - 1, 4
    out = []
    while len(out) < n:
        out.append(f"{y}q{q}")
        y, q = (y, q - 1) if q > 1 else (y - 1, 4)
    return out[::-1]


def download(q: str, contact: str) -> Path | None:
    DATA.mkdir(parents=True, exist_ok=True)
    f = DATA / f"{q}_form345.zip"
    if f.exists() and f.stat().st_size > 1000:
        return f
    req = urllib.request.Request(URL.format(q=q), headers={"User-Agent": f"AURON personal dashboard {contact}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            f.write_bytes(r.read())
    except Exception as exc:  # noqa: BLE001 -- a quarter not published yet
        print(f"  {q}: not available ({exc})")
        return None
    time.sleep(0.5)
    return f


def tables(zf: Path) -> tuple[dict, dict, list]:
    z = zipfile.ZipFile(zf)
    names = {n.upper().split("/")[-1]: n for n in z.namelist()}

    def rows(name: str):
        with z.open(names[name]) as fh:
            yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), delimiter="\t")

    subs = {}
    for r in rows("SUBMISSION.TSV"):
        if r.get("DOCUMENT_TYPE") != "4":
            continue
        try:
            filed = datetime.strptime(r["FILING_DATE"], "%d-%b-%Y").date().isoformat()
        except ValueError:
            continue
        subs[r["ACCESSION_NUMBER"]] = {**r, "FILING_DATE": filed}
    owners = {}
    for r in rows("REPORTINGOWNER.TSV"):
        owners.setdefault(r["ACCESSION_NUMBER"], r)
    trans = [r for r in rows("NONDERIV_TRANS.TSV") if r["ACCESSION_NUMBER"] in subs and r.get("TRANS_CODE") in ("P", "S")]
    return subs, owners, trans


def norm(name: str) -> str:
    n = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    n = re.sub(r"\b(INC|CORP|CORPORATION|CO|THE|LTD|PLC|HOLDINGS|HLDGS|GROUP|CLASS A|CL A|COM|NV|SA|AG)\b", " ", n)
    return " ".join(n.split())


def mt5_prices(evts: list[dict]):
    import MetaTrader5 as mt5
    print("  connecting to MT5 ...", flush=True)
    if not mt5.initialize(path=TERMINAL, timeout=60000):
        raise SystemExit(f"MT5 not reachable: {mt5.last_error()}")
    syms = mt5.symbols_get()
    by_name = {s.name.upper(): s.name for s in syms}
    by_desc = {}
    for s in syms:
        if s.path.startswith(("Equity-US", "247 Product")):
            by_desc.setdefault(norm(s.description), s.name)

    def symbol_for(ticker: str, issuer: str) -> str | None:
        for cand in (ticker, ticker + "USD"):
            if cand.upper() in by_name:
                return by_name[cand.upper()]
        return by_desc.get(norm(issuer))

    PRICES.mkdir(parents=True, exist_ok=True)

    def closes(sym: str) -> list[tuple[date, float]]:
        """Daily closes, from the cache when it is from today -- and the terminal left as found:
        on 2026-10-17 the first run put 487 symbols into the Market Watch of the very terminal the
        copiers trade on, and that evening all copiers were gone. Now each symbol leaves again."""
        f = PRICES / (re.sub(r"[^A-Za-z0-9._-]", "_", sym) + ".json")
        if f.exists() and date.fromtimestamp(f.stat().st_mtime) == date.today():
            return [(date.fromisoformat(d), c) for d, c in json.loads(f.read_text())]
        info = mt5.symbol_info(sym)
        was_visible = bool(info and info.visible)
        mt5.symbol_select(sym, True)
        time.sleep(0.05)
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 2000)
        if not was_visible:
            mt5.symbol_select(sym, False)
        out = [] if r is None else [(datetime.fromtimestamp(int(x["time"]), timezone.utc).date(), float(x["close"])) for x in r]
        f.write_text(json.dumps([(d.isoformat(), c) for d, c in out]))
        return out

    bench = dict(closes("SP500.s"))
    if not bench:
        raise SystemExit("no S&P 500 prices (SP500.s)")
    cache: dict[str, list] = {}
    mapped = 0
    print(f"  benchmark: {len(bench)} days; mapping {len(evts)} events ...", flush=True)
    for n, e in enumerate(evts):
        if n % 2000 == 0:
            print(f"    {n}/{len(evts)} events, {len(cache)} symbols loaded", flush=True)
        sym = symbol_for(e["ticker"], e["issuer"])
        if not sym:
            continue
        if sym not in cache:
            cache[sym] = closes(sym)
        if cache[sym]:
            mapped += 1
            e["symbol"] = sym
            e["ret"] = excess_returns(e["filed"], cache[sym], bench)
            e["move"] = position_returns(e["filed"], cache[sym], bench)
    mt5.shutdown()
    print(f"  prices: {len(cache)} symbols, {mapped} events mapped")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=28)  # seven years; MT5 holds ~8 years of daily prices
    ap.add_argument("--no-post", action="store_true")
    args = ap.parse_args()
    contact = env("SEC_CONTACT")
    if not contact:
        raise SystemExit("SEC_CONTACT missing in .env")
    evts: list[dict] = []
    for q in quarters(args.quarters):
        f = download(q, contact)
        if not f:
            continue
        subs, owners, trans = tables(f)
        e = events(subs, owners, trans)
        print(f"  {q}: {len(subs)} Form 4, {sum(x['code'] == 'P' for x in e)} buys, {sum(x['code'] == 'S' for x in e)} big sales", flush=True)
        evts += e
    mark_clusters(evts)
    mt5_prices(evts)
    summary = summarize(evts)
    rows = [{k: e.get(k) for k in ("ticker", "issuer", "owner", "role", "code", "value", "filed", "cluster", "ret", "move", "symbol")}
            for e in evts if e.get("ret")]
    symbols = {e["ticker"]: e["symbol"] for e in evts if e.get("symbol")}
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "quarters": quarters(args.quarters),
               "summary": summary, "events": rows, "symbols": symbols}
    (DATA / "result.json").write_text(json.dumps(payload, default=str), encoding="utf-8")
    print(json.dumps(summary["overall"], indent=1))
    if not args.no_post:
        req = urllib.request.Request(f"{API}/v1/smartmoney/backtest", data=json.dumps(payload, default=str).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            print("  posted:", r.status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
