"""Fetch the Form 4 filings of the watched insiders' companies since a date, straight from the SEC, without alerts.

Why (2026-10-27): the SEC publishes its quarterly data sets months late (2026q2 still 404 at the end of October),
so the backtest ends on 31.3.; the live poll only looks back 30 days. That leaves a hole of half a year in which
nobody could say whether a Profi bought. This fills it the way the poll would -- same rows, same 'already seen'
keys, so the next poll does not send all of it to Telegram -- and prints what the watched insiders did.

    docker exec -i jarvis_os-api-1 python - --since 2026-04-01 < tools/insider_backfill.py
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import InsiderTradeRow, SmartAlertRow
from app.smartmoney.insider import parse_form4
from app.smartmoney.service import _norm, smart_money_service as svc

ap = argparse.ArgumentParser()
ap.add_argument("--since", default="2026-04-01")
args = ap.parse_args(sys.argv[1:])
since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)

watched = {_norm(f["owner"]): f["owner"] for f in svc.follows()}
tickers = sorted({t for f in svc.follows() for t in f["tickers"]})
hits = []
for i, ticker in enumerate(tickers, 1):
    cik = svc.sec.cik(ticker)
    if cik is None:
        print(f"[{i}/{len(tickers)}] {ticker}: no CIK", flush=True)
        continue
    with SessionLocal() as s:
        seen = {r[0] for r in s.query(SmartAlertRow.key).filter(SmartAlertRow.key.like(f"f4:{ticker}:%")).all()}
    filings = svc.sec.recent_form4(cik, since, limit=1000)
    print(f"[{i}/{len(tickers)}] {ticker}: {len(filings)} Form 4", flush=True)
    for f in filings:
        key = f"f4:{ticker}:{f['acc']}"
        try:
            trades = parse_form4(svc.sec.form4(cik, f["acc"], f["doc"]))
        except Exception as exc:  # noqa: BLE001 -- one broken filing never stops the rest
            print(f"   {f['acc']}: {exc}", flush=True)
            continue
        with SessionLocal() as s:
            if key not in seen:
                s.merge(SmartAlertRow(key=key[:200], sent_at=datetime.now(timezone.utc)))
            for tr in trades:
                s.merge(InsiderTradeRow(key=f"{f['acc']}#{tr['line']}", ticker=ticker, owner=tr["owner"][:200],
                                        title=tr["title"][:200], code=tr["code"], shares=tr["shares"], price=tr["price"],
                                        value=tr["value"], traded_on=tr["traded_on"], filed_at=f["filed"],
                                        url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['acc'].replace('-', '')}/"))
                if _norm(tr["owner"]) in watched:
                    hits.append((tr["traded_on"].date(), watched[_norm(tr["owner"])], ticker, tr["code"], tr["shares"], tr["price"], tr["value"]))
            s.commit()

print("\n== watched insiders since", args.since)
for d, owner, ticker, code, sh, px, v in sorted(hits, reverse=True):
    print(f"{d} | {owner} | {ticker} | {'KAUF' if code == 'P' else 'VERKAUF'} | {sh:,.0f} @ {px:,.2f} | {v:,.0f} $")
print(f"{sum(h[3] == 'P' for h in hits)} buys, {sum(h[3] == 'S' for h in hits)} sales")
