from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Protocol

from .models import AdapterRuntimeEvidence


class MetaTrader5Adapter(Protocol):
    def connect(self, requested_login: int, required_symbols: list[str]) -> AdapterRuntimeEvidence: ...

    def heartbeat(self, required_symbols: list[str]) -> AdapterRuntimeEvidence: ...

    def disconnect(self) -> AdapterRuntimeEvidence: ...


class NativeMetaTrader5Adapter:
    """Thin runtime boundary around the optional Windows-only MetaTrader5 package.

    Credentials are intentionally not accepted here. The terminal must already be
    configured or obtain secrets through an external secret-backed bootstrap.
    """

    def __init__(self) -> None:
        self._mt5: Any | None = None

    def _load(self) -> Any | None:
        if self._mt5 is not None:
            return self._mt5
        try:
            self._mt5 = import_module("MetaTrader5")
        except ImportError:
            return None
        return self._mt5

    @staticmethod
    def _error(mt5: Any) -> tuple[int | None, str | None]:
        try:
            code, message = mt5.last_error()
            return int(code), str(message)
        except Exception:
            return None, None

    def _snapshot(self, required_symbols: list[str]) -> AdapterRuntimeEvidence:
        mt5 = self._load()
        if mt5 is None:
            return AdapterRuntimeEvidence(package_available=False)
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        visible: list[str] = []
        for symbol in required_symbols:
            info = mt5.symbol_info(symbol)
            if info is not None and bool(getattr(info, "visible", False)):
                visible.append(symbol)
        code, message = self._error(mt5)
        return AdapterRuntimeEvidence(
            package_available=True,
            initialized=terminal is not None,
            logged_in=account is not None,
            terminal_connected=bool(getattr(terminal, "connected", False)) if terminal else False,
            trade_allowed=bool(getattr(terminal, "trade_allowed", False)) if terminal else False,
            account_login=int(getattr(account, "login")) if account and getattr(account, "login", None) else None,
            account_server=str(getattr(account, "server")) if account and getattr(account, "server", None) else None,
            visible_symbols=visible,
            last_error_code=code,
            last_error_message=message,
            heartbeat_at=datetime.now(timezone.utc),
        )

    def connect(self, requested_login: int, required_symbols: list[str]) -> AdapterRuntimeEvidence:
        mt5 = self._load()
        if mt5 is None:
            return AdapterRuntimeEvidence(package_available=False)
        initialized = bool(mt5.initialize())
        if not initialized:
            return self._snapshot(required_symbols)
        evidence = self._snapshot(required_symbols)
        if evidence.account_login != requested_login:
            return evidence
        for symbol in required_symbols:
            mt5.symbol_select(symbol, True)
        return self._snapshot(required_symbols)

    def heartbeat(self, required_symbols: list[str]) -> AdapterRuntimeEvidence:
        return self._snapshot(required_symbols)

    def disconnect(self) -> AdapterRuntimeEvidence:
        mt5 = self._load()
        if mt5 is None:
            return AdapterRuntimeEvidence(package_available=False)
        mt5.shutdown()
        return AdapterRuntimeEvidence(
            package_available=True,
            initialized=False,
            logged_in=False,
            terminal_connected=False,
            trade_allowed=False,
            heartbeat_at=datetime.now(timezone.utc),
        )
