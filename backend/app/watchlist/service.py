from datetime import datetime, timedelta, timezone

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import WatchlistNoteRow, WatchlistRow

from . import alerts
from .analysis import analyse

from .models import ReasonIn, WatchItem, Watchlist, WatchlistIn

STALE_AFTER = timedelta(minutes=5)


class WatchlistService:
    """The latest snapshot only, in Postgres; replaced on every push."""

    def reset(self) -> None:
        refuse_reset_in_production("watchlist")
        with SessionLocal() as session:
            session.query(WatchlistRow).delete()
            session.query(WatchlistNoteRow).delete()
            from app.db_models import WatchlistAlertRow
            session.query(WatchlistAlertRow).delete()
            session.commit()

    alert = staticmethod(alerts.send)  # replaced in tests: no test messages Brano

    def push(self, payload: WatchlistIn, now: datetime | None = None) -> Watchlist:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            row = session.get(WatchlistRow, "latest")
            previous = WatchlistIn.model_validate_json(row.data).items if row is not None else []
            if row is None:
                session.add(WatchlistRow(id="latest", received_at=now, data=payload.model_dump_json()))
            else:
                row.received_at, row.data = now, payload.model_dump_json()
            session.commit()
        # Compared with the previous snapshot: alerts fire on the change, once a day each.
        self.alert(alerts.collect(payload.items, previous, now.date()))
        return Watchlist(**payload.model_dump(), received_at=now, stale=False)

    def get(self, now: datetime | None = None) -> Watchlist:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            row = session.get(WatchlistRow, "latest")
            if row is None:
                return Watchlist(items=[], captured_at=now, received_at=None, stale=True)
            at = row.received_at if row.received_at.tzinfo else row.received_at.replace(tzinfo=timezone.utc)
            data = WatchlistIn.model_validate_json(row.data)
            notes = {n.name: n for n in session.query(WatchlistNoteRow).all()}
        items = []
        for item in data.items:
            n = notes.get(item.name)
            if n is not None:
                item = item.model_copy(update={"reason": n.reason, "recommended_by": n.recommended_by,
                                               "analysis": n.analysis, "analysis_at": n.analysis_at})
            items.append(item)
        return Watchlist(items=items, captured_at=data.captured_at, received_at=at, stale=now - at > STALE_AFTER)

    def _item(self, name: str) -> WatchItem:
        for item in self.get().items:
            if item.name == name:
                return item
        raise KeyError(name)

    def set_reason(self, name: str, payload: ReasonIn) -> WatchItem:
        self._item(name)  # only symbols on the list
        with SessionLocal() as session:
            n = session.get(WatchlistNoteRow, name) or WatchlistNoteRow(name=name, reason="", recommended_by="", analysis="")
            n.reason, n.recommended_by, n.updated_at = payload.reason.strip(), payload.recommended_by.strip(), datetime.now(timezone.utc)
            session.merge(n); session.commit()
        return self._item(name)

    def analyse(self, name: str, writer=analyse) -> WatchItem:
        item = self._item(name)
        text = writer(item, item.reason, item.recommended_by)
        with SessionLocal() as session:
            n = session.get(WatchlistNoteRow, name) or WatchlistNoteRow(name=name, reason="", recommended_by="")
            n.analysis, n.analysis_at, n.updated_at = text, datetime.now(timezone.utc), datetime.now(timezone.utc)
            session.merge(n); session.commit()
        return self._item(name)


watchlist_service = WatchlistService()
