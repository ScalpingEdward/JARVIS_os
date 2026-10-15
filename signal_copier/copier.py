"""Main loop: Telegram messages in, MT5 orders out, every step reported to me.

    python -m signal_copier.copier          # trades (demo unless allow_live)
    python -m signal_copier.copier --dry    # parses, checks, reports -- sends no order

The decisions live in Copier, which gets the execution module passed in, so
the tests run it against a fake terminal. Telegram and the bot only sit
around it in main().
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import queue
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from signal_copier import parser
from signal_copier.book import Book, TrackedSignal, close_half_plan
from signal_copier.parser import BREAKEVEN, CLOSE_ALL, CLOSE_HALF, EXIT_AT_BE, Command, Rejected, Signal, TakeProfits
from signal_copier.risk import breached, day_start, floors, may_open
from signal_copier.sizing import RiskProfile, entry_deviation_ok, lots_for_risk
from signal_copier.symbols import resolve

HERE = Path(__file__).parent
LEGACY_STATE = HERE / "state.json"  # before one file per account
LOG = HERE / "copier.log"
WATCH_EVERY_S = 5

log = logging.getLogger("copier")


def state_path(account: str) -> Path:
    """One book per MT5 account: start balance, loss stop and tickets belong to it alone."""
    return HERE / f"state_{re.sub(r'[^A-Za-z0-9]+', '_', account)}.json"


def migrate_legacy_state(account: str) -> None:
    """The old single state.json goes to the account it was written for -- or, unmarked, to this one."""
    if not LEGACY_STATE.exists():
        return
    owner = Book.load(LEGACY_STATE).account or account
    target = state_path(owner)
    if not target.exists():
        LEGACY_STATE.replace(target)


def profile_from(config: dict) -> RiskProfile:
    r = config["risk"]
    return RiskProfile(r["risk_per_position_pct"], r["daily_loss_stop_pct"], r["overall_loss_stop_pct"],
                       r.get("max_entry_deviation_pips", {}), r.get("default_entry_deviation_pips", 3.0))


class Copier:
    def __init__(self, ex, book: Book, profile: RiskProfile, config: dict, notify,
                 state_path: Path | None = None, clock=time.time, dry: bool = False):
        self.ex, self.book, self.profile, self.config = ex, book, profile, config
        self.notify, self.state_path, self.clock, self.dry = notify, state_path, clock, dry
        self.symbols = ex.tradable_symbols()
        self.overrides = config.get("symbol_overrides", {})
        self.account_lost = False

    def _account_ok(self) -> bool:
        """Same account as the book? Another one would be traded with this one's limits."""
        current = self.ex.account_id()
        if current == self.book.account:
            if self.account_lost:
                self.account_lost = False
                self._say(f"MT5 is back on {current} -- trading again")
            return True
        if not self.account_lost:
            self.account_lost = True
            self._say(f"ACCOUNT CHANGED: MT5 is on {current}, this copier was started for {self.book.account}. "
                      f"No trades, no loss stop until MT5 is back on it -- or restart the copier for {current}.")
        return False

    def _save(self) -> None:
        if self.state_path is not None and not self.dry:
            self.book.save(self.state_path)

    def _say(self, text: str) -> None:
        log.info(text)
        self.notify(("[DRY] " if self.dry else "") + text)

    # --- messages -------------------------------------------------------

    def on_message(self, chat_id: int, msg_id: int, reply_to: int | None, text: str) -> None:
        result = parser.parse(text)
        if result is None:
            return
        where = f"#{msg_id}"
        if not self._account_ok():
            self._say(f"{where} ignored: MT5 is not on {self.book.account}\n{text[:200]}")
            return
        try:
            if isinstance(result, Rejected):
                self._say(f"{where} not traded: {result.reason}\n{text[:200]}")
            elif isinstance(result, Signal):
                self._signal(chat_id, msg_id, result)
            elif isinstance(result, TakeProfits):
                self._take_profits(chat_id, msg_id, reply_to, result)
            elif isinstance(result, Command):
                self._command(chat_id, msg_id, reply_to, result, text)
        except Exception as e:  # one bad message must not stop the copier
            log.exception("handling %s", where)
            self._say(f"{where} ERROR {type(e).__name__}: {e}")
        self._save()

    def _signal(self, chat_id: int, msg_id: int, sig: Signal) -> None:
        where = f"#{msg_id} {sig.side} {sig.symbol}"
        symbol = resolve(sig.symbol, self.symbols, self.overrides)
        if symbol is None:
            self._say(f"{where} not traded: no tradable broker symbol for {sig.symbol}")
            return
        now = self.clock()

        first = self.book.repost_of(chat_id, symbol, sig.side, now)
        if first is not None:
            self.book.link(msg_id, first.msg_id)
            if not first.tps and sig.tps:
                self._say(f"{where} is a repost of #{first.msg_id} -- adding its TPs")
                self._apply_tps(first, sig.tps)
            else:
                self._say(f"{where} is a repost of #{first.msg_id} -- not opened again")
            return

        if self.book.halted(now):
            self._say(f"{where} not traded: trading stopped ({self.book.halt_reason})")
            return

        price = self.ex.price(symbol, sig.side)
        if not entry_deviation_ok(sig.symbol, sig.side, sig.entry, price, self.profile):
            self._say(f"{where} not traded: price {price} ran too far from entry {sig.entry}")
            return

        # One leg per TP, each with the full risk per position. No TP yet: two
        # legs without TP, the TPs follow in their own message.
        tps = list(sig.tps) or [0.0] * self.config.get("legs_without_tp", 2)
        spec = self.ex.spec(symbol)
        state = self.ex.account_state(self.book.initial_balance)
        lots = lots_for_risk(state.balance, self.profile.risk_per_position_pct, price, sig.sl, spec)
        if lots <= 0:
            self._say(f"{where} not traded: even {spec.volume_min} lots would risk more than "
                      f"{self.profile.risk_per_position_pct}%")
            return
        worst = sum(self.ex.pnl_at_sl(symbol, sig.side, lots, price, sig.sl) for _ in tps)
        verdict = may_open(state, self.profile, worst)
        if not verdict.ok:
            self._say(f"{where} not traded: {verdict.reason}")
            return

        if self.dry:
            self._say(f"{where} would open {len(tps)} x {lots} lots at ~{price}, SL {sig.sl}, "
                      f"TP {', '.join(str(t) for t in tps)} (worst case {worst:.2f})")
            return

        tracked = TrackedSignal(msg_id, chat_id, symbol, sig.side, sig.entry, sig.sl, list(sig.tps), now)
        lines = []
        for leg, tp in enumerate(tps, start=1):
            try:
                o = self.ex.open_position(symbol, sig.side, lots, sig.sl, tp, msg_id, leg)
            except Exception as e:
                lines.append(f"leg {leg} FAILED: {e}")
                continue
            tracked.legs[str(leg)] = o.ticket
            lines.append(f"leg {leg}: {o.volume} @ {o.price}, TP {tp or 'later'} (#{o.ticket})")
        if tracked.legs:
            self.book.add(tracked)
        self._say(f"{where} opened, SL {sig.sl}\n" + "\n".join(lines))

    def _take_profits(self, chat_id: int, msg_id: int, reply_to: int | None, tp: TakeProfits) -> None:
        target = None
        if reply_to is not None and str(reply_to) in self.book.about:
            target = self.book.get(self.book.about[str(reply_to)])
        if target is None:
            target = self.book.awaiting_tps(chat_id, self.clock())
        if target is None:
            self._say(f"#{msg_id} TPs {list(tp.tps)} ignored: no recent signal is waiting for TPs")
            return
        if target.tps:
            self._say(f"#{msg_id} TPs ignored: #{target.msg_id} has TPs already")
            return
        self.book.link(msg_id, target.msg_id)
        self._apply_tps(target, tp.tps)

    def _apply_tps(self, s: TrackedSignal, tps: tuple[float, ...]) -> None:
        wrong = [t for t in tps if (t <= s.entry if s.side == "buy" else t >= s.entry)]
        if wrong:
            self._say(f"#{s.msg_id} TPs {list(tps)} not set: {wrong} on the wrong side of entry {s.entry}")
            return
        s.tps = list(tps)
        lines = []
        for leg in sorted(s.legs, key=int):
            tp = tps[min(int(leg), len(tps)) - 1]  # more legs than TPs: the rest take the last one
            pos = self.ex.position(s.legs[leg])
            if pos is None:
                lines.append(f"leg {leg}: already closed")
                continue
            if self.dry:
                lines.append(f"leg {leg}: would set TP {tp}")
                continue
            try:
                self.ex.set_sltp(pos, tp=tp)
                lines.append(f"leg {leg}: TP {tp}")
            except Exception as e:
                lines.append(f"leg {leg}: TP {tp} FAILED: {e}")
        self._say(f"#{s.msg_id} {s.symbol} TPs set\n" + "\n".join(lines))

    def _command(self, chat_id: int, msg_id: int, reply_to: int | None, cmd: Command, text: str) -> None:
        open_tickets = {p.ticket for p in self.ex.bot_positions()}
        open_ids = {s.msg_id for s in self.book.signals.values() if set(s.legs.values()) & open_tickets}
        symbol = cmd.symbol and (resolve(cmd.symbol, self.symbols, self.overrides) or cmd.symbol)
        s, why = self.book.target(chat_id, reply_to, symbol, open_ids)
        actions = "+".join(sorted(cmd.actions))
        if s is None:
            self._say(f"#{msg_id} {actions} not done: {why}\n{text[:200]}")
            return
        self.book.link(msg_id, s.msg_id)
        lines = []
        if CLOSE_ALL in cmd.actions:
            lines += self._close_all(s, open_tickets)
        else:
            if CLOSE_HALF in cmd.actions:
                lines += self._close_half(s, open_tickets)
                open_tickets = {p.ticket for p in self.ex.bot_positions()}
            if BREAKEVEN in cmd.actions:
                lines += self._breakeven(s, open_tickets)
            if EXIT_AT_BE in cmd.actions:
                lines += self._exit_at_be(s, open_tickets)
        self._say(f"#{msg_id} {actions} on #{s.msg_id} {s.symbol}\n" + ("\n".join(lines) or "nothing open"))

    def _open_legs(self, s: TrackedSignal, open_tickets: set[int]):
        for leg in sorted(s.legs, key=int):
            if s.legs[leg] in open_tickets:
                pos = self.ex.position(s.legs[leg])
                if pos is not None:
                    yield leg, pos

    def _close_all(self, s, open_tickets) -> list[str]:
        lines = []
        for leg, pos in self._open_legs(s, open_tickets):
            lines.append(self._do(f"leg {leg}: closed {pos.volume}", self.ex.close_position, pos))
        return lines

    def _close_half(self, s, open_tickets) -> list[str]:
        legs_open = dict(self._open_legs(s, open_tickets))
        volumes = {p.ticket: p.volume for p in legs_open.values()}
        spec = self.ex.spec(s.symbol)
        plan, why = close_half_plan(s.legs, set(volumes), volumes, spec.volume_step, spec.volume_min)
        lines = [f"close half: {why}"]
        by_ticket = {p.ticket: p for p in legs_open.values()}
        for ticket, volume in plan:
            lines.append(self._do(f"  #{ticket} closed {volume or by_ticket[ticket].volume}",
                                  self.ex.close_position, by_ticket[ticket], volume))
        return lines

    def _breakeven(self, s, open_tickets) -> list[str]:
        lines = []
        for leg, pos in self._open_legs(s, open_tickets):
            lines.append(f"leg {leg}: " + self._to_breakeven(s, pos))
        return lines

    def _to_breakeven(self, s, pos) -> str:
        if pos.sl == pos.price_open:
            return "SL already at entry"
        if not self.ex.stop_distance_ok(pos.symbol, pos.price_open, s.side, True):
            if pos.ticket not in self.book.pending_be:
                self.book.pending_be.append(pos.ticket)
            return f"entry {pos.price_open} too close to price -- will retry"
        return self._do(f"SL to entry {pos.price_open}", self.ex.move_sl_to_breakeven, pos)

    def _exit_at_be(self, s, open_tickets) -> list[str]:
        lines = []
        for leg, pos in self._open_legs(s, open_tickets):
            if pos.profit > 0:
                lines.append(f"leg {leg} in profit: " + self._to_breakeven(s, pos))
            elif not self.ex.stop_distance_ok(pos.symbol, pos.price_open, s.side, False):
                lines.append(f"leg {leg} in loss: TP at entry {pos.price_open} too close to price -- not set")
            else:
                lines.append(self._do(f"leg {leg} in loss: TP to entry {pos.price_open}",
                                      self.ex.set_sltp, pos, None, pos.price_open))
        return lines

    def _do(self, done: str, fn, *args) -> str:
        if self.dry:
            return "would: " + done
        try:
            fn(*args)
            return done
        except Exception as e:
            return f"{done} FAILED: {e}"

    # --- watchdog -------------------------------------------------------

    def watch(self) -> None:
        """Every few seconds: loss stops, then stops that could not go to entry yet."""
        if not self._account_ok():
            return
        try:
            self._guard()
            self._retry_breakeven()
        except Exception as e:
            log.exception("watchdog")
            self._say(f"watchdog ERROR {type(e).__name__}: {e}")
        self._save()

    def _guard(self) -> None:
        state = self.ex.account_state(self.book.initial_balance)
        verdict = breached(state, self.profile)
        positions = self.ex.bot_positions()
        if not verdict.ok:
            return
        now = self.clock()
        if not self.book.halted(now):
            _, overall = floors(state, self.profile)
            self.book.halt_reason = verdict.reason
            if state.equity <= overall:
                self.book.halt_until = None
                until = "for good -- restart only after deciding by hand"
            else:
                tomorrow = day_start(datetime.fromtimestamp(now, timezone.utc)) + timedelta(days=1)
                self.book.halt_until = tomorrow.timestamp()
                until = f"until {tomorrow:%Y-%m-%d %H:%M} Prague"
            self._say(f"LOSS STOP: {verdict.reason}. Closing {len(positions)} positions, no new trades {until}")
        if positions and not self.dry:
            for p in positions:
                try:
                    self.ex.close_position(p)
                except Exception as e:
                    self._say(f"LOSS STOP: closing #{p.ticket} FAILED: {e} -- retrying in {WATCH_EVERY_S}s")

    def _retry_breakeven(self) -> None:
        for ticket in list(self.book.pending_be):
            pos = self.ex.position(ticket)
            s = next((s for s in self.book.signals.values() if ticket in s.legs.values()), None)
            if pos is None or s is None or pos.sl == pos.price_open:
                self.book.pending_be.remove(ticket)
                continue
            if self.ex.stop_distance_ok(pos.symbol, pos.price_open, s.side, True):
                self.book.pending_be.remove(ticket)
                self._say(f"#{s.msg_id} {s.symbol} #{ticket}: " +
                          self._do(f"SL to entry {pos.price_open} (retry)", self.ex.move_sl_to_breakeven, pos))


# --- around it: Telegram, the bot, the terminal ---------------------------

class BotNotifier:
    """Sends through @Auronsignalbot on its own thread, so a slow Telegram never delays an order."""

    def __init__(self, token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def __call__(self, text: str) -> None:
        self.q.put(text)

    def _run(self) -> None:
        while True:
            text = self.q.get()
            data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": text[:4000]}).encode()
            for attempt in range(3):
                try:
                    urllib.request.urlopen(self.url, data, timeout=15).read()
                    break
                except Exception as e:
                    log.warning("bot send failed (%s), attempt %d", e, attempt + 1)
                    time.sleep(5)


async def main(dry: bool) -> None:
    from dotenv import load_dotenv
    from telethon import TelegramClient, events

    from signal_copier import execution
    from signal_copier.telegram_check import _plain

    load_dotenv(HERE / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(LOG, encoding="utf-8"), logging.StreamHandler()])
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    notify = BotNotifier(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_NOTIFY_CHAT_ID"])

    execution.connect(allow_live=config.get("allow_live", False))
    account = execution.account_id()
    migrate_legacy_state(account)
    state = state_path(account)
    book = Book.load(state)
    if not book.account:
        book.account = account
    if book.account != account:
        raise SystemExit(f"{state.name} belongs to {book.account}, MT5 is on {account}")
    if config.get("initial_balance"):
        book.initial_balance = config["initial_balance"]
    elif book.initial_balance is None:
        book.initial_balance = execution.account_state(0.0).balance
    copier = Copier(execution, book, profile_from(config), config, notify, state, dry=dry)
    copier._save()

    client = TelegramClient(str(HERE / "copier"), int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"])
    await client.start()
    dialogs = [d async for d in client.iter_dialogs()]
    chats = []
    for name in config["channels"]:
        found = [d for d in dialogs if _plain(name) in _plain(d.name or "")]
        if len(found) != 1:
            raise SystemExit(f"{len(found)} chats match {name!r}: {[d.name for d in found]}")
        chats.append(found[0])

    @client.on(events.NewMessage(chats=[c.id for c in chats]))
    async def handler(event) -> None:
        m = event.message
        reply_to = m.reply_to.reply_to_msg_id if m.reply_to else None
        copier.on_message(event.chat_id, m.id, reply_to, m.message or "")

    async def watchdog() -> None:
        while True:
            copier.watch()
            await asyncio.sleep(WATCH_EVERY_S)

    halted = f", TRADING STOPPED: {book.halt_reason}" if book.halted(time.time()) else ""
    copier._say(f"copier started on {account}{halted}: {', '.join(c.name for c in chats)}, "
                f"initial balance {book.initial_balance}, {len(book.signals)} signals in the book")
    asyncio.create_task(watchdog())
    await client.run_until_disconnected()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="parse, check and report; send no order")
    asyncio.run(main(ap.parse_args().dry))
