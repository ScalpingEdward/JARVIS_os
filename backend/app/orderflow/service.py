from collections import defaultdict
from uuid import UUID

from .models import (
    OrderflowSignal,
    OrderflowSnapshot,
    OrderflowSnapshotCreate,
    OrderflowStatus,
)


class OrderflowService:
    def __init__(self) -> None:
        self._snapshots: dict[UUID, OrderflowSnapshot] = {}

    def reset(self) -> None:
        self._snapshots.clear()

    def create(self, payload: OrderflowSnapshotCreate) -> OrderflowSnapshot:
        total_bid = sum(level.bid_volume for level in payload.levels)
        total_ask = sum(level.ask_volume for level in payload.levels)
        total = total_bid + total_ask
        delta = total_ask - total_bid
        delta_percent = delta / total if total else 0
        oi_change = None
        if payload.open_interest is not None and payload.previous_open_interest is not None:
            oi_change = payload.open_interest - payload.previous_open_interest

        buy_imbalances: list[float] = []
        sell_imbalances: list[float] = []
        absorption: list[float] = []
        liquidity: list[float] = []

        for level in payload.levels:
            if level.ask_volume >= max(level.bid_volume * 3, 1):
                buy_imbalances.append(level.price)
            if level.bid_volume >= max(level.ask_volume * 3, 1):
                sell_imbalances.append(level.price)
            traded = level.bid_volume + level.ask_volume
            resting = level.resting_bid + level.resting_ask
            if traded > 0 and resting >= traded * 2:
                absorption.append(level.price)
            if level.resting_bid > 0 or level.resting_ask > 0:
                liquidity.append(level.price)

        signal = OrderflowSignal.neutral
        if delta_percent >= 0.12 and len(buy_imbalances) >= len(sell_imbalances):
            signal = OrderflowSignal.bullish
        elif delta_percent <= -0.12 and len(sell_imbalances) >= len(buy_imbalances):
            signal = OrderflowSignal.bearish
        elif absorption:
            strongest = max(payload.levels, key=lambda item: item.resting_bid + item.resting_ask)
            signal = (
                OrderflowSignal.absorption_buy
                if strongest.resting_bid >= strongest.resting_ask
                else OrderflowSignal.absorption_sell
            )

        evidence = min(len(payload.levels) / 20, 1)
        agreement = min(abs(delta_percent) * 2 + (len(buy_imbalances) + len(sell_imbalances)) / 10, 1)
        confidence = round(min(1, evidence * 0.45 + agreement * 0.55), 4)
        data_quality = round(min(1, evidence * 0.7 + (0.3 if payload.source_timestamp else 0)), 4)

        snapshot = OrderflowSnapshot(
            **payload.model_dump(),
            symbol=payload.symbol.upper(),
            total_bid_volume=round(total_bid, 4),
            total_ask_volume=round(total_ask, 4),
            delta=round(delta, 4),
            delta_percent=round(delta_percent, 6),
            open_interest_change=oi_change,
            stacked_buy_imbalances=buy_imbalances,
            stacked_sell_imbalances=sell_imbalances,
            absorption_levels=absorption,
            liquidity_levels=liquidity,
            signal=signal,
            confidence=confidence,
            data_quality=data_quality,
        )
        self._snapshots[snapshot.id] = snapshot
        return snapshot

    def list_all(self, symbol: str | None = None) -> list[OrderflowSnapshot]:
        values = list(self._snapshots.values())
        if symbol:
            values = [item for item in values if item.symbol == symbol.upper()]
        return sorted(values, key=lambda item: item.created_at, reverse=True)

    def get(self, snapshot_id: UUID) -> OrderflowSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def latest(self, symbol: str) -> OrderflowSnapshot | None:
        values = self.list_all(symbol=symbol)
        return values[0] if values else None

    def status(self) -> OrderflowStatus:
        values = list(self._snapshots.values())
        grouped = defaultdict(int)
        for item in values:
            if item.signal in {OrderflowSignal.bullish, OrderflowSignal.absorption_buy, OrderflowSignal.exhaustion_sell}:
                grouped["bullish"] += 1
            elif item.signal in {OrderflowSignal.bearish, OrderflowSignal.absorption_sell, OrderflowSignal.exhaustion_buy}:
                grouped["bearish"] += 1
            else:
                grouped["neutral"] += 1
        return OrderflowStatus(
            symbols=len({item.symbol for item in values}),
            snapshots=len(values),
            bullish=grouped["bullish"],
            bearish=grouped["bearish"],
            neutral=grouped["neutral"],
        )


orderflow_service = OrderflowService()
