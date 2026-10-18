"""Smart money: insider trades on the watchlist and the week's big macro dates, with alerts.

Telegram gets: an insider BUY of $100k or more, several insiders buying the same stock
within two weeks, and every high-impact macro event 30 minutes before it hits. Each
alert once. Observation, not advice -- the dashboard and AURON say so.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import InsiderTradeRow, SmartAlertRow, SmartBacktestRow

from . import macro
from .backtest import role_of
from .insider import TICKERS, SecClient, clusters, parse_form4

log = logging.getLogger(__name__)
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s smart money: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False

BIG_BUY = 100_000
LOOKBACK_DAYS = 30


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


class SmartMoneyService:
    def __init__(self) -> None:
        self.sec = SecClient()
        self.last_insider_poll: datetime | None = None
        self.insider_error = ""
        self.macro_error = ""

    def reset(self) -> None:
        refuse_reset_in_production("smart money")
        with SessionLocal() as s:
            s.query(InsiderTradeRow).delete()
            s.query(SmartAlertRow).delete()
            s.query(SmartBacktestRow).delete()
            s.commit()
        self._bt_cache = None

    # ------------------------------------------------------------ alerts
    def _once(self, key: str) -> bool:
        """True the first time a key is seen -- the alert may go out."""
        with SessionLocal() as s:
            if s.get(SmartAlertRow, key):
                return False
            s.add(SmartAlertRow(key=key[:200], sent_at=datetime.now(timezone.utc)))
            s.commit()
            return True

    @staticmethod
    def _telegram(title: str, text: str) -> None:
        from app.notification_hub.telegram_delivery import TelegramDeliveryClient, TelegramDeliveryError
        try:
            TelegramDeliveryClient().send(title, text)
        except TelegramDeliveryError as exc:
            log.warning("telegram failed: %s", exc)

    # ------------------------------------------------------------ insiders
    def poll_insiders(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        since = now - timedelta(days=LOOKBACK_DAYS)
        new = 0
        try:
            for name, ticker in TICKERS.items():
                cik = self.sec.cik(ticker)
                if cik is None:
                    continue
                with SessionLocal() as s:  # every filing is read once, with or without trades in it
                    seen = {r[0] for r in s.query(SmartAlertRow.key).filter(SmartAlertRow.key.like(f"f4:{ticker}:%")).all()}
                for f in self.sec.recent_form4(cik, since):
                    if f"f4:{ticker}:{f['acc']}" in seen:
                        continue
                    trades = parse_form4(self.sec.form4(cik, f["acc"], f["doc"]))
                    self._once(f"f4:{ticker}:{f['acc']}")
                    with SessionLocal() as s:
                        for tr in trades:
                            s.merge(InsiderTradeRow(key=f"{f['acc']}#{tr['line']}", ticker=ticker, owner=tr["owner"][:200],
                                                    title=tr["title"][:200], code=tr["code"], shares=tr["shares"], price=tr["price"],
                                                    value=tr["value"], traded_on=tr["traded_on"], filed_at=f["filed"],
                                                    url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['acc'].replace('-', '')}/"))
                            new += 1
                            if tr["code"] == "P" and tr["value"] >= BIG_BUY:
                                note = self.track_record(ticker, role_of("Officer" if tr["title"] else "", tr["title"]))
                                v = self.insider_verdict(tr["owner"], ticker, "buy")
                                if v:
                                    note = (f"Bilanz dieses Käufers: {v['right'] * 100:.0f} % richtig in {v['n']} Käufen -> {v['verdict']}. " + note).strip()
                                self._telegram("Insider-Kauf", f"{name} ({ticker}): {tr['owner']}{', ' + tr['title'] if tr['title'] else ''} "
                                               f"kauft {tr['shares']:,.0f} Aktien zu {tr['price']:,.2f} $ = {tr['value']:,.0f} $."
                                               + (f"\n{note}" if note else "") + "\n\nBeobachtung, keine Empfehlung.")
                        s.commit()
        except Exception as exc:  # noqa: BLE001 -- SEC hiccup or an odd filing: logged, retried next run
            self.insider_error = str(exc)
            log.warning("insider poll failed: %s", exc)
            return {"new": new, "error": self.insider_error}
        for ticker, owners in clusters(self.trades(days=14)).items():
            week = now.strftime("%G-%V")
            if self._once(f"cluster:{ticker}:{week}"):
                name = next((n for n, t in TICKERS.items() if t == ticker), ticker)
                self._telegram("Mehrere Insider kaufen", f"{name} ({ticker}): {len(owners)} Insider haben in 14 Tagen gekauft -- "
                               + ", ".join(owners[:5]) + ".\n\nBeobachtung, keine Empfehlung.")
        self.last_insider_poll, self.insider_error = now, ""
        log.info("insiders polled: %d new trades", new)
        return {"new": new, "error": ""}

    def trades(self, days: int = 30, ticker: str | None = None) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with SessionLocal() as s:
            q = s.query(InsiderTradeRow).filter(InsiderTradeRow.traded_on >= since)
            if ticker:
                q = q.filter(InsiderTradeRow.ticker == ticker.upper())
            names = {t: n for n, t in TICKERS.items()}
            return [{"ticker": r.ticker, "name": names.get(r.ticker, r.ticker), "owner": r.owner, "title": r.title,
                     "code": r.code, "shares": r.shares, "price": r.price, "value": r.value,
                     "traded_on": _aware(r.traded_on), "url": r.url}
                    for r in q.order_by(InsiderTradeRow.traded_on.desc()).limit(200).all()]

    # ------------------------------------------------------------ backtest
    def save_backtest(self, payload: dict) -> dict:
        at = datetime.fromisoformat(payload["generated_at"])
        with SessionLocal() as s:
            s.merge(SmartBacktestRow(key="latest", generated_at=at, data=json.dumps(payload)))
            s.commit()
        self._bt_cache = None
        return {"events": len(payload.get("events", [])), "generated_at": payload["generated_at"]}

    def backtest(self) -> dict | None:
        if getattr(self, "_bt_cache", None) is not None:
            return self._bt_cache
        with SessionLocal() as s:
            r = s.get(SmartBacktestRow, "latest")
            self._bt_cache = json.loads(r.data) if r else None
        return self._bt_cache

    def track_record(self, ticker: str, role: str = "", cluster: bool = False, horizon: str = "60") -> str:
        """One sentence: how earlier buys like this one did -- for alerts and AURON."""
        bt = self.backtest()
        if not bt:
            return ""
        sm = bt["summary"]
        parts = []
        for label, table, key in ((ticker, "by_ticker", ticker), (role, "by_role", role),
                                  ("Cluster" if cluster else "", "by_cluster", "Cluster")):
            st = (sm.get(table, {}).get(key) or {}).get(horizon) if label else None
            if st and st.get("n", 0) >= 3:
                parts.append(f"{label}: {st['avg'] * 100:+.1f} % ggü. S&P nach {horizon} Tagen, {st['hit'] * 100:.0f} % im Plus ({st['n']} Fälle)")
        return "Frühere Käufe – " + "; ".join(parts) if parts else ""

    def insider_verdict(self, owner: str, ticker: str, side: str = "buy") -> dict | None:
        bt = self.backtest()
        if not bt:
            return None
        return next((x for x in bt["summary"].get("by_insider", []) if x["owner"].lower() == owner.lower()
                     and x["ticker"] == ticker and x.get("side", "buy") == side), None)

    # ------------------------------------------------------------ macro
    def macro_tick(self, now: datetime | None = None) -> int:
        try:
            evts = macro.events()
            self.macro_error = ""
        except macro.MacroError as exc:
            self.macro_error = str(exc)
            return 0
        sent = 0
        for e in macro.due_for_alert(evts, now):
            if self._once(f"macro:{e['currency']}:{e['title']}:{e['at']}"):
                at = datetime.fromisoformat(e["at"]).astimezone(_berlin())
                de = f" ({e['title_de']})" if e["title_de"] else ""
                self._telegram("Makro in 30 Minuten", f"{at:%H:%M} {e['currency']} {e['title']}{de}\n"
                               f"Prognose {e['forecast'] or '–'}, vorher {e['previous'] or '–'}.\nGold und Indizes können springen.")
                sent += 1
        return sent

    def overview(self) -> dict:
        try:
            evts = macro.upcoming(macro.events())
        except macro.MacroError as exc:
            self.macro_error, evts = str(exc), []
        trades = self.trades(days=30)
        return {"macro": evts, "macro_error": self.macro_error,
                "insider": [{**t, "traded_on": t["traded_on"].isoformat()} for t in trades],
                "clusters": clusters(trades), "insider_connected": self.sec.configured(),
                "insider_error": self.insider_error,
                "last_insider_poll": self.last_insider_poll.isoformat() if self.last_insider_poll else None,
                "backtest": self._backtest_brief()}

    def _backtest_brief(self) -> dict | None:
        bt = self.backtest()
        if not bt:
            return None
        sm = bt["summary"]
        return {"generated_at": bt["generated_at"], "quarters": bt.get("quarters", []),
                **{k: sm.get(k) for k in ("overall", "by_role", "by_size", "by_cluster", "events", "buys", "with_prices")}}


def _berlin():
    from zoneinfo import ZoneInfo
    return ZoneInfo("Europe/Berlin")


class SmartMoneyPoller:
    """Macro check every minute; insiders every SMART_INSIDER_HOURS (default 2)."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        every_ins = float(os.getenv("SMART_INSIDER_HOURS", "2")) * 3600
        next_ins = 0.0
        loop = asyncio.get_running_loop()
        while True:
            try:
                await asyncio.to_thread(smart_money_service.macro_tick)
                if loop.time() >= next_ins and smart_money_service.sec.configured():
                    next_ins = loop.time() + every_ins
                    await asyncio.to_thread(smart_money_service.poll_insiders)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("tick crashed: %s", exc)
            await asyncio.sleep(60)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        log.info("smart money polling started")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


smart_money_service = SmartMoneyService()
smart_money_poller = SmartMoneyPoller()
