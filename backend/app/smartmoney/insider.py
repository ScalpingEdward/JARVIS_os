"""Insider buys and sales from SEC Form 4 -- for the US stocks on Brano's watchlist.

Officers, directors and 10 % owners must report trades in their own company's stock
within two business days. Only open-market trades count here: code P (bought with
their own money) and S (sold). Grants, option exercises and tax withholdings are not
a view on the stock and are left out.

The SEC serves this for free but wants a contact in every request's User-Agent
(its fair-access rule); without SEC_CONTACT in .env nothing is fetched.
"""
from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx

# Watchlist name -> US ticker. Foreign companies (Novo, Adidas, BYD, Siemens ...) file no Form 4.
TICKERS = {
    "NVIDIA": "NVDA", "Microsoft": "MSFT", "Amazon": "AMZN", "Meta": "META", "Tesla": "TSLA", "Palantir": "PLTR",
    "Oracle": "ORCL", "Intel": "INTC", "IBM": "IBM", "Marvell": "MRVL", "Snowflake": "SNOW", "Okta": "OKTA",
    "Rigetti": "RGTI", "C3.ai": "AI", "Tempus AI": "TEM", "Duolingo": "DUOL", "Goldman Sachs": "GS",
    "BlackRock": "BLK", "S&P Global": "SPGI", "Virtu Financial": "VIRT", "Nike": "NKE", "McDonald's": "MCD",
    "P&G": "PG", "Coupang": "CPNG", "AT&T": "T", "Verizon": "VZ", "Southern Company": "SO", "Nucor": "NUE",
    "Virgin Galactic": "SPCE", "Valmont": "VMI",
}
TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
PAUSE_S = 0.15  # the SEC allows 10 requests a second; stay well below


class InsiderError(RuntimeError):
    pass


class SecClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30)
        self._ciks: dict[str, int] = {}

    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("SEC_CONTACT"))

    def _get(self, url: str) -> httpx.Response:
        if not self.configured():
            raise InsiderError("SEC_CONTACT is not set (the SEC wants a contact address in the User-Agent)")
        time.sleep(PAUSE_S)
        r = self._client.get(url, headers={"User-Agent": f"AURON personal dashboard {os.getenv('SEC_CONTACT')}",
                                           "Accept-Encoding": "gzip, deflate"})
        if r.status_code >= 400:
            raise InsiderError(f"SEC {r.status_code} for {url}")
        return r

    def cik(self, ticker: str) -> int | None:
        if not self._ciks:
            self._ciks = {v["ticker"].upper(): int(v["cik_str"]) for v in self._get(TICKER_MAP).json().values()}
        return self._ciks.get(ticker.upper())

    def recent_form4(self, cik: int, since: datetime, limit: int = 15) -> list[dict]:
        rec = self._get(SUBMISSIONS.format(cik=cik)).json()["filings"]["recent"]
        out = []
        for form, acc, doc, filed in zip(rec["form"], rec["accessionNumber"], rec["primaryDocument"], rec["filingDate"]):
            if form != "4":
                continue
            at = datetime.fromisoformat(filed).replace(tzinfo=timezone.utc)
            if at < since:
                break  # newest first
            out.append({"acc": acc, "doc": doc.split("/")[-1], "filed": at})
            if len(out) >= limit:
                break
        return out

    def form4(self, cik: int, acc: str, doc: str) -> str:
        return self._get(ARCHIVE.format(cik=cik, acc=acc.replace("-", ""), doc=doc)).text


def parse_form4(xml: str) -> list[dict]:
    """The open-market trades (P, S) in one Form 4: who, what, how many, at what price."""
    root = ET.fromstring(xml)
    t = lambda el, path: (el.findtext(path) or "").strip()  # noqa: E731
    owner = t(root, "reportingOwner/reportingOwnerId/rptOwnerName")
    rel = root.find("reportingOwner/reportingOwnerRelationship")
    title = ""
    if rel is not None:
        title = t(rel, "officerTitle") or ("Director" if t(rel, "isDirector") in ("1", "true") else
                                           "10 % owner" if t(rel, "isTenPercentOwner") in ("1", "true") else "")
    out = []
    for i, tx in enumerate(root.findall("nonDerivativeTable/nonDerivativeTransaction")):
        code = t(tx, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        try:
            shares = float(t(tx, "transactionAmounts/transactionShares/value") or 0)
            price = float(t(tx, "transactionAmounts/transactionPricePerShare/value") or 0)
            day = datetime.fromisoformat(t(tx, "transactionDate/value")[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        out.append({"line": i, "owner": owner, "title": title, "code": code, "shares": shares, "price": price,
                    "value": round(shares * price, 2), "traded_on": day})
    return out


def clusters(trades: list[dict], days: int = 14, min_owners: int = 2) -> dict[str, list[str]]:
    """Tickers where several different insiders bought within `days` -- the pattern worth a look."""
    now = datetime.now(timezone.utc)
    by: dict[str, set[str]] = {}
    for tr in trades:
        if tr["code"] == "P" and now - tr["traded_on"] <= timedelta(days=days):
            by.setdefault(tr["ticker"], set()).add(tr["owner"])
    return {k: sorted(v) for k, v in by.items() if len(v) >= min_owners}
