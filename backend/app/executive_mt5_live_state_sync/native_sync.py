from datetime import datetime, timezone
from typing import Any


class NativeMT5StateProvider:
    """Replaceable boundary around the Windows-only MetaTrader5 package."""

    def __init__(self, mt5: Any | None = None):
        if mt5 is None:
            try:
                import MetaTrader5 as mt5_package
            except ImportError as exc:
                raise RuntimeError("MetaTrader5 package is unavailable") from exc
            mt5 = mt5_package
        self.mt5 = mt5

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "_asdict"):
            return dict(value._asdict())
        if isinstance(value, dict):
            return value
        return vars(value)

    def snapshot(self, history_from_epoch: int) -> dict[str, Any]:
        account = self._as_dict(self.mt5.account_info())
        if not account:
            raise RuntimeError("MT5 account information is unavailable")
        positions = [self._as_dict(item) for item in (self.mt5.positions_get() or [])]
        orders = [self._as_dict(item) for item in (self.mt5.orders_get() or [])]
        start = datetime.fromtimestamp(history_from_epoch, timezone.utc)
        end = datetime.now(timezone.utc)
        deals = [self._as_dict(item) for item in (self.mt5.history_deals_get(start, end) or [])]
        order_history = [self._as_dict(item) for item in (self.mt5.history_orders_get(start, end) or [])]
        return {"account": account, "positions": positions, "orders": orders, "deals": deals, "order_history": order_history}
