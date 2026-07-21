from typing import Any, Protocol


class NativeOrderExecutor(Protocol):
    def symbol_info(self, symbol: str) -> Any: ...
    def symbol_info_tick(self, symbol: str) -> Any: ...
    def order_check(self, request: dict[str, Any]) -> Any: ...
    def order_send(self, request: dict[str, Any]) -> Any: ...


class MetaTrader5OrderExecutor:
    """Thin optional boundary around the Windows-only MetaTrader5 package."""

    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise RuntimeError("MetaTrader5 package is unavailable") from exc
        self.mt5 = mt5

    def symbol_info(self, symbol: str) -> Any:
        return self.mt5.symbol_info(symbol)

    def symbol_info_tick(self, symbol: str) -> Any:
        return self.mt5.symbol_info_tick(symbol)

    def order_check(self, request: dict[str, Any]) -> Any:
        return self.mt5.order_check(request)

    def order_send(self, request: dict[str, Any]) -> Any:
        return self.mt5.order_send(request)

    def build_request(self, payload: Any) -> dict[str, Any]:
        mt5 = self.mt5
        is_buy = payload.side == "buy"
        type_map = {
            ("market", True): mt5.ORDER_TYPE_BUY,
            ("market", False): mt5.ORDER_TYPE_SELL,
            ("limit", True): mt5.ORDER_TYPE_BUY_LIMIT,
            ("limit", False): mt5.ORDER_TYPE_SELL_LIMIT,
            ("stop", True): mt5.ORDER_TYPE_BUY_STOP,
            ("stop", False): mt5.ORDER_TYPE_SELL_STOP,
        }
        tif_map = {
            "gtc": mt5.ORDER_TIME_GTC,
            "day": mt5.ORDER_TIME_DAY,
        }
        filling_map = {
            "ioc": mt5.ORDER_FILLING_IOC,
            "fok": mt5.ORDER_FILLING_FOK,
        }
        price = payload.requested_price
        if payload.order_type == "market":
            price = payload.quote_ask if is_buy else payload.quote_bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL if payload.order_type == "market" else mt5.TRADE_ACTION_PENDING,
            "symbol": payload.symbol,
            "volume": payload.volume,
            "type": type_map[(payload.order_type, is_buy)],
            "price": price,
            "deviation": payload.max_deviation_points,
            "magic": payload.magic,
            "comment": payload.comment,
            "type_time": tif_map.get(payload.time_in_force, mt5.ORDER_TIME_GTC),
            "type_filling": filling_map.get(payload.time_in_force, mt5.ORDER_FILLING_IOC),
        }
        if payload.stop_loss is not None:
            request["sl"] = payload.stop_loss
        if payload.take_profit is not None:
            request["tp"] = payload.take_profit
        return request
