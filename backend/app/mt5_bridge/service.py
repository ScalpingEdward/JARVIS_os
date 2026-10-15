from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.db import SessionLocal, refuse_reset_in_production
from app.db_models import MT5TerminalRow

from .models import (
    MT5BridgeStatus,
    MT5ConnectionState,
    MT5Heartbeat,
    MT5SnapshotIngest,
    MT5TerminalData,
    MT5TerminalRecord,
    MT5TerminalRegister,
)


class MT5BridgeError(ValueError):
    pass


class MT5BridgeService:
    """Stores data pushed by local MT5 bridge processes. No trade methods exist.

    In Postgres, not in this process. It used to be a dict, so a rebuild of
    the api container dropped the terminal registration, the balance, the
    ticks and the contract specs -- while the pusher on Brano's machine kept
    sending to a terminal_id it had saved in its own state file and would
    have gone on failing until someone deleted that file by hand. The rest
    of the trading chain was converted away from in-memory state already;
    this was the last piece still holding it.

    Connection state is derived on read rather than stored. It is a function
    of the last heartbeat and the clock, and a stored copy would be wrong
    the moment nothing happens -- which is exactly when it matters.
    """

    stale_after = timedelta(seconds=30)
    disconnect_after = timedelta(minutes=2)

    def reset(self) -> None:
        refuse_reset_in_production("mt5_terminals")
        with SessionLocal() as session:
            session.query(MT5TerminalRow).delete()
            session.commit()

    @staticmethod
    def _save(session, data: MT5TerminalData) -> None:
        row = session.get(MT5TerminalRow, str(data.terminal.id))
        payload = data.model_dump_json()
        now = datetime.now(timezone.utc)
        if row is None:
            session.add(MT5TerminalRow(
                id=str(data.terminal.id),
                account_login=data.terminal.account_login,
                server=data.terminal.server,
                updated_at=now,
                data=payload,
            ))
        else:
            row.data = payload
            row.updated_at = now

    @staticmethod
    def _load(session, terminal_id: UUID) -> MT5TerminalData | None:
        row = session.get(MT5TerminalRow, str(terminal_id))
        return None if row is None else MT5TerminalData.model_validate_json(row.data)

    @staticmethod
    def _load_all(session) -> list[MT5TerminalData]:
        return [MT5TerminalData.model_validate_json(r.data) for r in session.query(MT5TerminalRow).all()]

    def register(self, payload: MT5TerminalRegister) -> MT5TerminalRecord:
        if payload.read_only is not True:
            raise MT5BridgeError("MT5 bridge must be registered in read-only mode")
        with SessionLocal() as session:
            existing = (
                session.query(MT5TerminalRow)
                .filter(
                    MT5TerminalRow.account_login == payload.account_login,
                    MT5TerminalRow.server == payload.server,
                )
                .first()
            )
            if existing is not None:
                raise MT5BridgeError("MT5 terminal is already registered")
            terminal = MT5TerminalRecord(**payload.model_dump())
            self._save(session, MT5TerminalData(terminal=terminal))
            session.commit()
        return deepcopy(terminal)

    def heartbeat(self, terminal_id: UUID, payload: MT5Heartbeat) -> MT5TerminalRecord:
        with SessionLocal() as session:
            data = self._require(session, terminal_id)
            data.terminal.last_heartbeat_at = datetime.now(timezone.utc)
            data.terminal.bridge_version = payload.bridge_version
            data.terminal.latency_ms = payload.latency_ms
            data.terminal.state = MT5ConnectionState.connected
            self._save(session, data)
            session.commit()
        return deepcopy(data.terminal)

    def ingest(self, terminal_id: UUID, payload: MT5SnapshotIngest) -> MT5TerminalData:
        with SessionLocal() as session:
            data = self._require(session, terminal_id)
            if data.terminal.read_only is not True:
                raise MT5BridgeError("Read-only safety contract is not active")
            data.account = payload.account
            data.positions = payload.positions
            data.pending_orders = payload.pending_orders
            data.deals = payload.deals[-1000:]
            data.ticks = payload.ticks[-500:]
            data.candles = payload.candles[-5000:]
            data.journal = payload.journal[-1000:]
            if payload.symbols:
                # Specs rarely change; replace by symbol rather than accumulating
                # or dropping older entries the way the rolling lists above do.
                by_symbol = {spec.symbol: spec for spec in data.symbols}
                for spec in payload.symbols:
                    by_symbol[spec.symbol] = spec
                data.symbols = list(by_symbol.values())
            if payload.sequence is not None:
                # A gap is a real signal (a dropped push, a pusher restart that
                # skipped ahead) worth keeping even after the next push arrives
                # on schedule -- "contiguous" reflects only whether *this*
                # push continued cleanly from the last one, not history overall.
                data.sequence_contiguous = (
                    data.last_sequence is None or payload.sequence == data.last_sequence + 1
                )
                data.last_sequence = payload.sequence
            data.terminal.last_heartbeat_at = datetime.now(timezone.utc)
            data.terminal.state = MT5ConnectionState.connected
            self._save(session, data)
            session.commit()
        return deepcopy(data)

    def get(self, terminal_id: UUID) -> MT5TerminalData:
        with SessionLocal() as session:
            data = self._require(session, terminal_id)
        self._apply_state(data)
        return data

    def list(self) -> list[MT5TerminalData]:
        with SessionLocal() as session:
            items = self._load_all(session)
        for data in items:
            self._apply_state(data)
        return items

    def status(self) -> MT5BridgeStatus:
        states = [item.terminal.state for item in self.list()]
        return MT5BridgeStatus(
            terminals=len(states),
            connected=states.count(MT5ConnectionState.connected),
            stale=states.count(MT5ConnectionState.stale),
            disconnected=states.count(MT5ConnectionState.disconnected),
        )

    def forget(self, terminal_id: UUID) -> None:
        """Remove a terminal record for good.

        Needed the moment the records outlived the process: a terminal
        registered with the wrong login, or a dry run, used to disappear
        with the next rebuild. Now it stays, and a stale record carrying
        another account number is exactly what would confuse the
        (login, server) match the accounts registry relies on.
        """
        with SessionLocal() as session:
            row = session.get(MT5TerminalRow, str(terminal_id))
            if row is None:
                raise MT5BridgeError("MT5 terminal not found")
            session.delete(row)
            session.commit()

    def _apply_state(self, data: MT5TerminalData, now: datetime | None = None) -> None:
        """Connection state from the last heartbeat and the clock.

        Derived, never stored: a terminal whose pusher died goes stale by
        the passing of time, and nothing writes a row when nothing happens.
        A stored state would stay "connected" for exactly as long as the
        truth mattered most.
        """
        current = now or datetime.now(timezone.utc)
        heartbeat = data.terminal.last_heartbeat_at
        if heartbeat is None or current - heartbeat >= self.disconnect_after:
            data.terminal.state = MT5ConnectionState.disconnected
        elif current - heartbeat >= self.stale_after:
            data.terminal.state = MT5ConnectionState.stale
        else:
            data.terminal.state = MT5ConnectionState.connected

    def refresh_states(self, now: datetime | None = None) -> None:
        """Kept for callers that ask for a refresh before reading. State is
        derived on every read now, so this only exists so an explicit call
        with a fixed `now` still means something: it writes that judgement
        back, which is what the position monitor's tests pin."""
        with SessionLocal() as session:
            for data in self._load_all(session):
                self._apply_state(data, now)
                self._save(session, data)
            session.commit()

    def _require(self, session, terminal_id: UUID) -> MT5TerminalData:
        data = self._load(session, terminal_id)
        if data is None:
            raise MT5BridgeError("MT5 terminal not found")
        return data


mt5_bridge_service = MT5BridgeService()
