from datetime import datetime, timedelta, timezone

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import CopierEquityRow, CopierStatusRow

from .models import (
    CopierEquityPoint,
    CopierGroupTotal,
    CopierOverview,
    CopierState,
    CopierStatus,
    CopierStatusIn,
    CopierTotals,
)


class CopierStatusError(ValueError):
    pass


class CopierStatusService:
    """Latest status per copier profile, in Postgres so a rebuild keeps it.

    The state (live / stale / offline) is derived on read from received_at,
    not stored: a stored copy goes wrong exactly when nothing arrives.
    """

    stale_after = timedelta(minutes=3)
    offline_after = timedelta(minutes=10)
    sample_every = timedelta(minutes=5)
    keep_history = timedelta(days=30)

    def reset(self) -> None:
        refuse_reset_in_production("copier_status")
        with SessionLocal() as session:
            session.query(CopierStatusRow).delete()
            session.query(CopierEquityRow).delete()
            session.commit()

    def push(self, payload: CopierStatusIn, now: datetime | None = None) -> CopierStatus:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            row = session.get(CopierStatusRow, payload.profile)
            data = payload.model_dump_json()
            if row is None:
                session.add(CopierStatusRow(profile=payload.profile, received_at=now, data=data))
            else:
                row.received_at, row.data = now, data
            self._sample(session, payload, now)
            session.commit()
        return self._status(payload, now, now)

    def _sample(self, session, payload: CopierStatusIn, now: datetime) -> None:
        """Every sample_every a point for the equity curve; older than keep_history goes."""
        last = (session.query(CopierEquityRow.at).filter(CopierEquityRow.profile == payload.profile)
                .order_by(CopierEquityRow.at.desc()).first())
        if last is not None and now - self._aware(last[0]) < self.sample_every:
            return
        session.add(CopierEquityRow(profile=payload.profile, at=now, balance=payload.balance, equity=payload.equity))
        session.query(CopierEquityRow).filter(CopierEquityRow.at < now - self.keep_history).delete()

    def history(self, hours: float = 24, now: datetime | None = None) -> dict[str, list[CopierEquityPoint]]:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            rows = (session.query(CopierEquityRow).filter(CopierEquityRow.at >= now - timedelta(hours=hours))
                    .order_by(CopierEquityRow.at).all())
        out: dict[str, list[CopierEquityPoint]] = {}
        for r in rows:
            out.setdefault(r.profile, []).append(
                CopierEquityPoint(at=self._aware(r.at), balance=r.balance, equity=r.equity))
        return out

    @staticmethod
    def _aware(at: datetime) -> datetime:
        return at if at.tzinfo else at.replace(tzinfo=timezone.utc)  # SQLite returns naive

    def forget(self, profile: str) -> None:
        with SessionLocal() as session:
            row = session.get(CopierStatusRow, profile)
            if row is None:
                raise CopierStatusError(f"no status for profile {profile!r}")
            session.delete(row)
            session.commit()

    def list(self, now: datetime | None = None) -> list[CopierStatus]:
        now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            rows = session.query(CopierStatusRow).order_by(CopierStatusRow.profile).all()
            return [self._status(CopierStatusIn.model_validate_json(r.data), r.received_at, now) for r in rows]

    def overview(self, now: datetime | None = None) -> CopierOverview:
        accounts = self.list(now)
        totals: dict[str, CopierTotals] = {}
        groups: dict[tuple[str, str], CopierGroupTotal] = {}
        for a in accounts:
            t = totals.setdefault(a.currency, CopierTotals(
                currency=a.currency, accounts=0, balance=0, equity=0, pnl_today=0,
                pnl_week=0, pnl_total=0, open_pnl=0, open_positions=0))
            t.accounts += 1
            t.balance += a.balance
            t.equity += a.equity
            for g in a.groups:
                t.pnl_today += g.pnl_today
                t.pnl_week += g.pnl_week
                t.pnl_total += g.pnl_total
                t.open_pnl += g.open_pnl
                t.open_positions += g.open_positions
                total = groups.setdefault((g.name, a.currency), CopierGroupTotal(name=g.name, currency=a.currency))
                for f in ("pnl_today", "pnl_week", "pnl_total", "open_pnl", "closed_trades", "open_positions"):
                    setattr(total, f, getattr(total, f) + getattr(g, f))
                total.accounts.append(a.profile)
        for t in totals.values():
            for f in ("balance", "equity", "pnl_today", "pnl_week", "pnl_total", "open_pnl"):
                setattr(t, f, round(getattr(t, f), 2))
        for g in groups.values():
            for f in ("pnl_today", "pnl_week", "pnl_total", "open_pnl"):
                setattr(g, f, round(getattr(g, f), 2))
        return CopierOverview(
            totals=sorted(totals.values(), key=lambda t: t.currency),
            accounts=accounts,
            groups=sorted(groups.values(), key=lambda g: (-g.pnl_total, g.name)),
        )

    def _status(self, payload: CopierStatusIn, received_at: datetime, now: datetime) -> CopierStatus:
        if received_at.tzinfo is None:  # SQLite hands timezone-aware values back naive
            received_at = received_at.replace(tzinfo=timezone.utc)
        age = now - received_at
        state = (CopierState.offline if age >= self.offline_after
                 else CopierState.stale if age >= self.stale_after else CopierState.live)
        return CopierStatus(**payload.model_dump(), received_at=received_at, state=state)


copier_status_service = CopierStatusService()
