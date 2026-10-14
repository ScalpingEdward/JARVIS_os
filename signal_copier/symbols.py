"""Canonical symbol (from the parser) -> the name this broker actually uses.

Brokers decorate names: EURUSD.s, EURUSDm, EURUSD.pro, and indices get
entirely different names (US100.cash, USTEC, NAS100). The broker's list comes
from mt5.symbols_get() at startup, and only the TRADABLE names may go in: PU
Prime lists a plain "EURUSD" that only shows quotes (trade_mode 0) next to the
"EURUSD.s" that takes orders.
"""
from __future__ import annotations

import re

# Names an index or commodity goes by at different brokers.
BROKER_NAMES = {
    "NAS100": ["NAS100", "US100", "USTEC", "NDX100", "NASDAQ", "NQ100"],
    "US30": ["US30", "DJ30", "DOW30", "WS30", "USA30"],
    "US500": ["US500", "SPX500", "SP500", "USA500"],
    "GER40": ["GER40", "DE40", "DAX40", "GER30", "DE30"],
    "USOIL": ["USOIL", "WTI", "XTIUSD", "USCRUDE", "OILUSD", "CL"],  # CL-OIL.s at PU Prime
    "XAUUSD": ["XAUUSD", "GOLD"],
    "XAGUSD": ["XAGUSD", "SILVER"],
    "BTCUSD": ["BTCUSD", "BITCOIN"],
}


def _core(name: str) -> str:
    """Broker name without decoration: 'US100.cash' -> 'US100', 'EURUSDm' -> 'EURUSD'."""
    base = re.split(r"[._#\-]", name.upper())[0]
    return base


def resolve(canonical: str, broker_symbols: list[str], overrides: dict[str, str] | None = None) -> str | None:
    """None when there is no match or more than one -- a guessed symbol is a wrong trade."""
    if overrides and canonical in overrides:
        return overrides[canonical] if overrides[canonical] in broker_symbols else None
    if canonical in broker_symbols:
        return canonical

    wanted = BROKER_NAMES.get(canonical, [canonical])
    exact = [s for s in broker_symbols if _core(s) in wanted]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None

    # Suffix glued on without a separator: EURUSDm, EURUSDpro.
    glued = [s for s in broker_symbols
             if any(s.upper().startswith(w) and s[len(w):].isalpha() and len(s) - len(w) <= 4 for w in wanted)]
    return glued[0] if len(glued) == 1 else None
