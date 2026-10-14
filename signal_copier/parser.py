"""Turns a Telegram message into a trade signal, a management command, or nothing.

Pure text in, data out: no Telegram, no MT5. Anything ambiguous returns None
(or a Rejected with a reason) instead of a guess -- a wrong guess here is a
real order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CURRENCIES = {"EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}

# Names the channel uses -> canonical symbol. The broker's own name
# (e.g. US100.cash at FTMO) is mapped later, next to MT5, not here.
ALIASES = {
    "gold": "XAUUSD", "xauusd": "XAUUSD", "xausd": "XAUUSD", "xau": "XAUUSD",
    "eu": "EURUSD",
    "silver": "XAGUSD", "xagusd": "XAGUSD",
    "nasdaq": "NAS100", "nas100": "NAS100", "us100": "NAS100", "nq": "NAS100",
    "us30": "US30", "dow": "US30", "dowjones": "US30",
    "spx": "US500", "sp500": "US500", "us500": "US500",
    "dax": "GER40", "ger40": "GER40", "de40": "GER40",
    "oil": "USOIL", "usoil": "USOIL", "wti": "USOIL",
    "btc": "BTCUSD", "btcusd": "BTCUSD", "bitcoin": "BTCUSD",
}

NUM = r"(\d[\d,]*(?:\.\d+)?)"

CLOSE_HALF = "close_half"
BREAKEVEN = "breakeven"
CLOSE_ALL = "close_all"
EXIT_AT_BE = "exit_at_be"  # out when price is back at entry: SL there if in profit, TP there if not


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: str  # "buy" | "sell"
    entry: float
    sl: float
    tps: tuple[float, ...]  # may be empty: fast signals send the TPs a moment later


@dataclass(frozen=True)
class TakeProfits:
    """'Tp1@4330 / Tp2@4380' on its own -- the second half of a fast signal."""
    tps: tuple[float, ...]


@dataclass(frozen=True)
class Command:
    actions: frozenset[str]
    symbol: str | None  # None: the message names no symbol, use reply/context


@dataclass(frozen=True)
class Rejected:
    reason: str
    text: str


def _num(raw: str) -> float:
    return float(raw.replace(",", ""))


def find_symbols(text: str) -> list[str]:
    found = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in ALIASES:
            symbol = ALIASES[word]
        elif len(word) == 6 and word[:3].upper() in CURRENCIES and word[3:].upper() in CURRENCIES:
            symbol = word.upper()
        else:
            continue
        if symbol not in found:
            found.append(symbol)
    return found


def find_symbol(text: str) -> str | None:
    symbols = find_symbols(text)
    return symbols[0] if symbols else None


def _parse_signal(text: str, side: str) -> Signal | Rejected:
    low = text.lower()
    symbol = find_symbol(text)
    entry = re.search(rf"\b{side}\b[^@\n]*@\s*{NUM}", low)
    sl = re.search(rf"\bsl\s*@\s*{NUM}", low)
    tps = [_num(m) for m in re.findall(rf"\btp\s*-?\s*\d?\s*@\s*{NUM}", low)]

    if symbol is None:
        return Rejected("no symbol", text)
    if entry is None:
        return Rejected("no entry", text)
    if sl is None:
        return Rejected("no stop loss -- risk cannot be sized", text)

    e, s = _num(entry.group(1)), _num(sl.group(1))
    # A typo in one number would flip the trade's risk; refuse instead.
    if side == "buy" and not (s < e and all(tp > e for tp in tps)):
        return Rejected("buy needs sl < entry < tps", text)
    if side == "sell" and not (s > e and all(tp < e for tp in tps)):
        return Rejected("sell needs sl > entry > tps", text)
    return Signal(symbol, side, e, s, tuple(tps))


def parse(text: str) -> Signal | TakeProfits | Command | Rejected | None:
    low = text.lower()

    side = re.search(r"\b(buy|sell)\b", low)
    # Any level after buy/sell makes it a signal, so a missing SL is refused
    # loudly instead of passing as chatter.
    if side and re.search(r"\b(sl|tp)\s*-?\s*\d?\s*@", low):
        return _parse_signal(text, side.group(1))
    if not side:
        tps = [_num(m) for m in re.findall(rf"\btp\s*-?\s*\d?\s*@\s*{NUM}", low)]
        if tps:
            return TakeProfits(tuple(tps))

    # A recap ("WEEKLY SIGNAL REPORT ... XAUUSD breakeven") names many symbols;
    # an instruction names one or none.
    if len(find_symbols(text)) > 1 or "report" in low:
        return None

    symbol = find_symbol(text)
    # Exit first: "Exit gold now at breakeven" closes, it does not move the SL.
    # Without "now", "exit at be / when it comes to be" waits for entry.
    if re.search(r"\bexit\b", low):
        waits = re.search(r"\b(be|breakeven)\b", low) and not re.search(r"\bnow\b", low)
        return Command(frozenset({EXIT_AT_BE if waits else CLOSE_ALL}), symbol)
    if re.search(r"\bclose\s+(all|now|everything|full|(this|the)\s+trades?)\b", low):
        return Command(frozenset({CLOSE_ALL}), symbol)

    actions = set()
    if re.search(r"\bclose\s+(half|some|partial|max|50\s*%)|\bhalf\s+lots?\b|\bpartials?\b", low):
        actions.add(CLOSE_HALF)
    # "sl in profit zone" names no price; entry is the safe floor of it.
    if re.search(r"\bbreak\s*-?even\b|\bsl\s+(to\s+)?(be|entry)\b|\bset\s+(sl\s+)?(to\s+)?be\b"
                 r"|\bbe\s+here\b|\bprofit\s+zone\b", low):
        actions.add(BREAKEVEN)
    if actions:
        return Command(frozenset(actions), symbol)
    return None  # "Running 🔥", "Tp1 Smashed" -- commentary, no action
