from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .models import (
    AccountComplianceStatus,
    AccountStateUpdate,
    AccountStatus,
    AccountType,
    DrawdownType,
    PropFirmRules,
    StrategyAssignment,
    StrategyAssignmentCreate,
    TradingAccountCreate,
    TradingAccountRecord,
)

DEFAULT_DB_PATH = "data/accounts.db"


class AccountRegistryError(RuntimeError):
    """Raised on any registry violation. Fail-closed: on ambiguity or a rule
    breach the write is rejected and no partial state is persisted."""


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class AccountRegistryService:
    """Persistent registry of trading accounts and their strategy assignments.

    Source of truth for which accounts AURON manages, the prop-firm rule set each
    must respect, and which (1-2) strategies run on each account. Every mutation
    is written to sqlite and mirrored to an append-only audit trail.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS accounts(
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    broker TEXT NOT NULL,
                    login TEXT NOT NULL,
                    server TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    initial_balance REAL NOT NULL,
                    max_strategies INTEGER NOT NULL,
                    prop_rules TEXT,
                    status TEXT NOT NULL,
                    balance REAL NOT NULL,
                    equity REAL NOT NULL,
                    day_start_balance REAL NOT NULL,
                    peak_equity REAL NOT NULL,
                    trading_days INTEGER NOT NULL,
                    last_trading_day TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(login, server)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS strategy_assignments(
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    allocation_pct REAL NOT NULL,
                    enabled INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(account_id, strategy_id),
                    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS account_audit(
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )"""
            )

    def _audit(self, conn: sqlite3.Connection, account_id: str | None, action: str, detail: str) -> None:
        conn.execute(
            "INSERT INTO account_audit(id, account_id, action, detail, created_at) VALUES (?,?,?,?,?)",
            (str(uuid4()), account_id, action, detail, datetime.now(timezone.utc).isoformat()),
        )

    # -- serialization helpers ------------------------------------------------

    def _row_to_record(self, row: sqlite3.Row) -> TradingAccountRecord:
        prop_rules = None
        if row["prop_rules"]:
            prop_rules = PropFirmRules(**json.loads(row["prop_rules"]))
        return TradingAccountRecord(
            id=UUID(row["id"]),
            label=row["label"],
            account_type=AccountType(row["account_type"]),
            broker=row["broker"],
            login=row["login"],
            server=row["server"],
            currency=row["currency"],
            initial_balance=row["initial_balance"],
            max_strategies=row["max_strategies"],
            prop_rules=prop_rules,
            status=AccountStatus(row["status"]),
            balance=row["balance"],
            equity=row["equity"],
            day_start_balance=row["day_start_balance"],
            peak_equity=row["peak_equity"],
            trading_days=row["trading_days"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_assignment(self, row: sqlite3.Row) -> StrategyAssignment:
        return StrategyAssignment(
            id=UUID(row["id"]),
            account_id=UUID(row["account_id"]),
            strategy_id=row["strategy_id"],
            strategy_name=row["strategy_name"],
            allocation_pct=row["allocation_pct"],
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _fetch_row(self, conn: sqlite3.Connection, account_id: UUID) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (str(account_id),)).fetchone()
        if row is None:
            raise AccountRegistryError(f"account {account_id} not found")
        return row

    # -- account lifecycle ----------------------------------------------------

    def register_account(self, payload: TradingAccountCreate) -> TradingAccountRecord:
        now = datetime.now(timezone.utc).isoformat()
        record = TradingAccountRecord(
            label=payload.label,
            account_type=payload.account_type,
            broker=payload.broker,
            login=payload.login,
            server=payload.server,
            currency=payload.currency,
            initial_balance=payload.initial_balance,
            max_strategies=payload.max_strategies,
            prop_rules=payload.prop_rules,
            status=AccountStatus.active,
            balance=payload.initial_balance,
            equity=payload.initial_balance,
            day_start_balance=payload.initial_balance,
            peak_equity=payload.initial_balance,
            trading_days=0,
        )
        prop_json = record.prop_rules.model_dump_json() if record.prop_rules else None
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO accounts(
                        id, label, account_type, broker, login, server, currency,
                        initial_balance, max_strategies, prop_rules, status, balance,
                        equity, day_start_balance, peak_equity, trading_days,
                        last_trading_day, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        str(record.id), record.label, record.account_type.value, record.broker,
                        record.login, record.server, record.currency, record.initial_balance,
                        record.max_strategies, prop_json, record.status.value, record.balance,
                        record.equity, record.day_start_balance, record.peak_equity,
                        record.trading_days, None, now, now,
                    ),
                )
                self._audit(conn, str(record.id), "register", f"{record.account_type.value}:{record.login}@{record.server}")
        except sqlite3.IntegrityError as exc:
            raise AccountRegistryError(
                f"an account with login {payload.login!r} on server {payload.server!r} already exists"
            ) from exc
        return record

    def list_accounts(self) -> list[TradingAccountRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY created_at").fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_account(self, account_id: UUID) -> TradingAccountRecord:
        with self._connect() as conn:
            return self._row_to_record(self._fetch_row(conn, account_id))

    # -- strategy assignment --------------------------------------------------

    def list_assignments(self, account_id: UUID) -> list[StrategyAssignment]:
        with self._connect() as conn:
            self._fetch_row(conn, account_id)
            rows = conn.execute(
                "SELECT * FROM strategy_assignments WHERE account_id = ? ORDER BY created_at",
                (str(account_id),),
            ).fetchall()
        return [self._row_to_assignment(r) for r in rows]

    def assign_strategy(self, account_id: UUID, payload: StrategyAssignmentCreate) -> StrategyAssignment:
        with self._connect() as conn:
            account = self._fetch_row(conn, account_id)
            existing = conn.execute(
                "SELECT strategy_id, allocation_pct FROM strategy_assignments WHERE account_id = ?",
                (str(account_id),),
            ).fetchall()
            if any(e["strategy_id"] == payload.strategy_id for e in existing):
                raise AccountRegistryError(
                    f"strategy {payload.strategy_id!r} is already assigned to account {account_id}"
                )
            if len(existing) >= account["max_strategies"]:
                raise AccountRegistryError(
                    f"account {account_id} already has the maximum of {account['max_strategies']} strategies assigned"
                )
            total_allocation = sum(e["allocation_pct"] for e in existing) + payload.allocation_pct
            if total_allocation > 100.0 + 1e-9:
                raise AccountRegistryError(
                    f"total allocation would be {total_allocation:.2f}%, which exceeds 100%"
                )
            assignment = StrategyAssignment(
                account_id=account_id,
                strategy_id=payload.strategy_id,
                strategy_name=payload.strategy_name,
                allocation_pct=payload.allocation_pct,
                enabled=payload.enabled,
            )
            conn.execute(
                """INSERT INTO strategy_assignments(
                    id, account_id, strategy_id, strategy_name, allocation_pct, enabled, created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    str(assignment.id), str(account_id), assignment.strategy_id,
                    assignment.strategy_name, assignment.allocation_pct,
                    int(assignment.enabled), assignment.created_at.isoformat(),
                ),
            )
            self._audit(conn, str(account_id), "assign_strategy", f"{payload.strategy_id}:{payload.allocation_pct}%")
        return assignment

    def unassign_strategy(self, account_id: UUID, strategy_id: str) -> None:
        with self._connect() as conn:
            self._fetch_row(conn, account_id)
            cur = conn.execute(
                "DELETE FROM strategy_assignments WHERE account_id = ? AND strategy_id = ?",
                (str(account_id), strategy_id),
            )
            if cur.rowcount == 0:
                raise AccountRegistryError(
                    f"strategy {strategy_id!r} is not assigned to account {account_id}"
                )
            self._audit(conn, str(account_id), "unassign_strategy", strategy_id)

    # -- state & compliance ---------------------------------------------------

    def update_state(self, account_id: UUID, payload: AccountStateUpdate) -> TradingAccountRecord:
        as_of = payload.as_of_date or _utc_today()
        with self._connect() as conn:
            row = self._fetch_row(conn, account_id)
            day_start = payload.day_start_balance if payload.day_start_balance is not None else row["day_start_balance"]
            peak_equity = max(row["peak_equity"], payload.equity)
            trading_days = row["trading_days"]
            last_day = row["last_trading_day"]
            if last_day != as_of:
                trading_days += 1
            now = datetime.now(timezone.utc).isoformat()
            status = AccountStatus(row["status"])
            # Compute compliance to auto-flag breaches on prop accounts.
            compliance = self._compute_compliance(
                account_type=AccountType(row["account_type"]),
                status=status,
                balance=payload.balance,
                equity=payload.equity,
                day_start_balance=day_start,
                peak_equity=peak_equity,
                initial_balance=row["initial_balance"],
                trading_days=trading_days,
                prop_rules=(PropFirmRules(**json.loads(row["prop_rules"])) if row["prop_rules"] else None),
            )
            if compliance.breached and status not in (AccountStatus.breached, AccountStatus.suspended):
                status = AccountStatus.breached
            conn.execute(
                """UPDATE accounts SET balance=?, equity=?, day_start_balance=?, peak_equity=?,
                    trading_days=?, last_trading_day=?, status=?, updated_at=? WHERE id=?""",
                (
                    payload.balance, payload.equity, day_start, peak_equity, trading_days,
                    as_of, status.value, now, str(account_id),
                ),
            )
            detail = f"eq={payload.equity} bal={payload.balance} status={status.value}"
            self._audit(conn, str(account_id), "update_state", detail)
            return self._row_to_record(self._fetch_row(conn, account_id))

    def _compute_compliance(
        self,
        *,
        account_type: AccountType,
        status: AccountStatus,
        balance: float,
        equity: float,
        day_start_balance: float,
        peak_equity: float,
        initial_balance: float,
        trading_days: int,
        prop_rules: PropFirmRules | None,
    ) -> AccountComplianceStatus:
        daily_loss_pct = max(0.0, (day_start_balance - equity) / day_start_balance * 100.0)
        profit_pct = (equity - initial_balance) / initial_balance * 100.0
        if prop_rules and prop_rules.drawdown_type == DrawdownType.trailing:
            total_drawdown_pct = max(0.0, (peak_equity - equity) / peak_equity * 100.0)
        else:
            total_drawdown_pct = max(0.0, (initial_balance - equity) / initial_balance * 100.0)

        breach_reasons: list[str] = []
        daily_headroom = None
        drawdown_headroom = None
        profit_progress = None
        min_days_met = None
        if prop_rules is not None:
            daily_headroom = prop_rules.max_daily_loss_pct - daily_loss_pct
            drawdown_headroom = prop_rules.max_total_drawdown_pct - total_drawdown_pct
            if prop_rules.profit_target_pct > 0:
                profit_progress = max(0.0, profit_pct) / prop_rules.profit_target_pct * 100.0
            min_days_met = trading_days >= prop_rules.min_trading_days
            if daily_loss_pct > prop_rules.max_daily_loss_pct + 1e-9:
                breach_reasons.append(
                    f"daily loss {daily_loss_pct:.2f}% exceeds limit {prop_rules.max_daily_loss_pct:.2f}%"
                )
            if total_drawdown_pct > prop_rules.max_total_drawdown_pct + 1e-9:
                breach_reasons.append(
                    f"total drawdown {total_drawdown_pct:.2f}% exceeds limit {prop_rules.max_total_drawdown_pct:.2f}%"
                )

        breached = bool(breach_reasons)
        return AccountComplianceStatus(
            account_id=uuid4(),  # overwritten by caller
            account_type=account_type,
            status=status,
            balance=balance,
            equity=equity,
            day_start_balance=day_start_balance,
            peak_equity=peak_equity,
            daily_loss_pct=round(daily_loss_pct, 4),
            total_drawdown_pct=round(total_drawdown_pct, 4),
            profit_pct=round(profit_pct, 4),
            trading_days=trading_days,
            daily_loss_headroom_pct=(round(daily_headroom, 4) if daily_headroom is not None else None),
            drawdown_headroom_pct=(round(drawdown_headroom, 4) if drawdown_headroom is not None else None),
            profit_target_progress_pct=(round(profit_progress, 4) if profit_progress is not None else None),
            min_trading_days_met=min_days_met,
            breached=breached,
            breach_reasons=breach_reasons,
        )

    def compliance(self, account_id: UUID) -> AccountComplianceStatus:
        with self._connect() as conn:
            row = self._fetch_row(conn, account_id)
        prop_rules = PropFirmRules(**json.loads(row["prop_rules"])) if row["prop_rules"] else None
        result = self._compute_compliance(
            account_type=AccountType(row["account_type"]),
            status=AccountStatus(row["status"]),
            balance=row["balance"],
            equity=row["equity"],
            day_start_balance=row["day_start_balance"],
            peak_equity=row["peak_equity"],
            initial_balance=row["initial_balance"],
            trading_days=row["trading_days"],
            prop_rules=prop_rules,
        )
        return result.model_copy(update={"account_id": account_id})

    # -- status transitions ---------------------------------------------------

    def suspend(self, account_id: UUID) -> TradingAccountRecord:
        return self._set_status(account_id, AccountStatus.suspended, "suspend")

    def activate(self, account_id: UUID) -> TradingAccountRecord:
        with self._connect() as conn:
            row = self._fetch_row(conn, account_id)
            if AccountStatus(row["status"]) == AccountStatus.breached:
                raise AccountRegistryError(
                    f"account {account_id} is breached and cannot be re-activated"
                )
        return self._set_status(account_id, AccountStatus.active, "activate")

    def _set_status(self, account_id: UUID, status: AccountStatus, action: str) -> TradingAccountRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            self._fetch_row(conn, account_id)
            conn.execute(
                "UPDATE accounts SET status=?, updated_at=? WHERE id=?",
                (status.value, now, str(account_id)),
            )
            self._audit(conn, str(account_id), action, status.value)
            return self._row_to_record(self._fetch_row(conn, account_id))

    def reset(self) -> None:
        """Clears all registry state. Intended for tests and local resets."""
        with self._connect() as conn:
            conn.execute("DELETE FROM strategy_assignments")
            conn.execute("DELETE FROM account_audit")
            conn.execute("DELETE FROM accounts")


account_registry_service = AccountRegistryService()
