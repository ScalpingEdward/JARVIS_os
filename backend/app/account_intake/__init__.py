"""Turns a spoken/typed instruction like "add a new trading account,
broker X, login 12345, server Y, trade it with VWAP" into a proposed
account registration a human then explicitly confirms -- never a
password.

The one hard rule this whole module exists to enforce: AURON's own
account model (see app/accounts/models.py TradingAccountCreate) has no
password field at all, by design -- the real broker login happens
entirely on the MT5 terminal itself, a separate, local step that never
touches this backend. Nothing about that changes here. Any message that
even mentions a password is refused before a single word of it is
forwarded to an AI model, logged, or stored anywhere -- see
credential_guard.py's own docstring for why that check has to run first,
unconditionally, ahead of everything else.
"""
