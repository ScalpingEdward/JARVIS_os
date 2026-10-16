from datetime import datetime, timedelta, timezone

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import WatchlistRow

from .models import Watchlist, WatchlistIn

STALE_AFTER = timedelta(minutes=5)


class WatchlistService:
    """The latest snapshot only, in Postgres; replaced on every push."""

    def reset(self) -> None:
        refuse_reset_in_production("watchlist")
        with SessionLocal() as session:
            session.query(WatchlistRow).delete()
            session.commit()

    def push(self, payload: WatchlistIn, now: datetime | None = None) -> Watchlist:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            row = session.get(WatchlistRow, "latest")
            if row is None:
                session.add(WatchlistRow(id="latest", received_at=now, data=payload.model_dump_json()))
            else:
                row.received_at, row.data = now, payload.model_dump_json()
            session.commit()
        return Watchlist(**payload.model_dump(), received_at=now, stale=False)

    def get(self, now: datetime | None = None) -> Watchlist:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            row = session.get(WatchlistRow, "latest")
            if row is None:
                return Watchlist(items=[], captured_at=now, received_at=None, stale=True)
            at = row.received_at if row.received_at.tzinfo else row.received_at.replace(tzinfo=timezone.utc)
            data = WatchlistIn.model_validate_json(row.data)
            return Watchlist(**data.model_dump(), received_at=at, stale=now - at > STALE_AFTER)


watchlist_service = WatchlistService()
