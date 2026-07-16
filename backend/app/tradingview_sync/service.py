from copy import deepcopy
import os
from uuid import UUID

from .models import ChartFrame, ChartFrameCreate, SyncStatus, TradingViewAlert, TradingViewWebhook, WatchlistCreate, WatchlistRecord


class TradingViewSyncError(ValueError):
    pass


class TradingViewSyncService:
    def __init__(self) -> None:
        self._watchlists: dict[UUID, WatchlistRecord] = {}
        self._alerts: list[TradingViewAlert] = []
        self._frames: list[ChartFrame] = []
        self._secret_override: str | None = None

    def reset(self) -> None:
        self._watchlists.clear()
        self._alerts.clear()
        self._frames.clear()
        self._secret_override = None

    def set_webhook_secret(self, secret: str) -> None:
        self._secret_override = secret

    def create_watchlist(self, payload: WatchlistCreate) -> WatchlistRecord:
        record = WatchlistRecord(**payload.model_dump())
        self._watchlists[record.id] = record
        return deepcopy(record)

    def list_watchlists(self) -> list[WatchlistRecord]:
        return [deepcopy(item) for item in self._watchlists.values()]

    def receive_webhook(self, payload: TradingViewWebhook) -> TradingViewAlert:
        expected = self._secret_override or os.getenv("TRADINGVIEW_WEBHOOK_SECRET", "")
        if not expected or payload.secret != expected:
            raise TradingViewSyncError("Invalid TradingView webhook secret")
        if payload.zone_low is not None and payload.zone_high is not None and payload.zone_low > payload.zone_high:
            raise TradingViewSyncError("Zone low must not exceed zone high")
        data = payload.model_dump(exclude={"secret"})
        alert = TradingViewAlert(**data)
        self._alerts.append(alert)
        return deepcopy(alert)

    def list_alerts(self) -> list[TradingViewAlert]:
        return [deepcopy(item) for item in reversed(self._alerts)]

    def add_frame(self, payload: ChartFrameCreate) -> ChartFrame:
        frame = ChartFrame(**payload.model_dump())
        self._frames.append(frame)
        return deepcopy(frame)

    def list_frames(self) -> list[ChartFrame]:
        return [deepcopy(item) for item in reversed(self._frames)]

    def status(self) -> SyncStatus:
        return SyncStatus(
            watchlists=len(self._watchlists),
            watch_items=sum(len(item.items) for item in self._watchlists.values()),
            alerts=len(self._alerts),
            frames=len(self._frames),
        )


tradingview_sync_service = TradingViewSyncService()
