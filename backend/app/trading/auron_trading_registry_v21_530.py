from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

AccountPhase = Literal['evaluation', 'verification', 'funded', 'broker-live', 'paper']
AccountStatus = Literal['active', 'paused', 'disabled']


class TradingRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderRuleProfile:
    provider: str
    profile_name: str
    daily_drawdown_pct: float | None
    max_drawdown_pct: float | None
    profit_target_pct: float | None
    minimum_trading_days: int | None
    minimum_holding_seconds: int | None
    news_restriction_minutes: int | None
    ea_allowed: bool
    grid_allowed: bool
    hedging_allowed: bool
    copy_trading_allowed: bool
    cross_account_hedging_allowed: bool
    consistency_rule_pct: float | None
    payout_cycle_limit: str | None
    notes: str = ''


@dataclass(frozen=True)
class TradingAccount:
    account_id: str
    provider: str
    provider_account_ref: str
    account_name: str
    phase: AccountPhase
    status: AccountStatus
    currency: str
    initial_balance: float
    rule_profile_name: str


class TradingAccountRegistry:
    """Persistent registry for prop-firm and broker accounts.

    B1 stores identities and rule profiles only. It does not connect to MT5,
    brokers, prop firms, or place/copy any order.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trading_rule_profiles (
                    provider TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    daily_drawdown_pct REAL,
                    max_drawdown_pct REAL,
                    profit_target_pct REAL,
                    minimum_trading_days INTEGER,
                    minimum_holding_seconds INTEGER,
                    news_restriction_minutes INTEGER,
                    ea_allowed INTEGER NOT NULL,
                    grid_allowed INTEGER NOT NULL,
                    hedging_allowed INTEGER NOT NULL,
                    copy_trading_allowed INTEGER NOT NULL,
                    cross_account_hedging_allowed INTEGER NOT NULL,
                    consistency_rule_pct REAL,
                    payout_cycle_limit TEXT,
                    notes TEXT NOT NULL,
                    PRIMARY KEY(provider, profile_name)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trading_accounts (
                    account_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_account_ref TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    initial_balance REAL NOT NULL,
                    rule_profile_name TEXT NOT NULL,
                    UNIQUE(provider, provider_account_ref),
                    FOREIGN KEY(provider, rule_profile_name)
                        REFERENCES trading_rule_profiles(provider, profile_name)
                )
            ''')

    @staticmethod
    def _bool(value: int) -> bool:
        return bool(value)

    def upsert_rule_profile(self, profile: ProviderRuleProfile) -> None:
        if not profile.provider.strip() or not profile.profile_name.strip():
            raise TradingRegistryError('provider and profile_name are required')
        for value, name in (
            (profile.daily_drawdown_pct, 'daily_drawdown_pct'),
            (profile.max_drawdown_pct, 'max_drawdown_pct'),
            (profile.profit_target_pct, 'profit_target_pct'),
            (profile.consistency_rule_pct, 'consistency_rule_pct'),
        ):
            if value is not None and value < 0:
                raise TradingRegistryError(f'{name} cannot be negative')

        with self._connect() as conn:
            conn.execute('''
                INSERT INTO trading_rule_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(provider, profile_name) DO UPDATE SET
                    daily_drawdown_pct=excluded.daily_drawdown_pct,
                    max_drawdown_pct=excluded.max_drawdown_pct,
                    profit_target_pct=excluded.profit_target_pct,
                    minimum_trading_days=excluded.minimum_trading_days,
                    minimum_holding_seconds=excluded.minimum_holding_seconds,
                    news_restriction_minutes=excluded.news_restriction_minutes,
                    ea_allowed=excluded.ea_allowed,
                    grid_allowed=excluded.grid_allowed,
                    hedging_allowed=excluded.hedging_allowed,
                    copy_trading_allowed=excluded.copy_trading_allowed,
                    cross_account_hedging_allowed=excluded.cross_account_hedging_allowed,
                    consistency_rule_pct=excluded.consistency_rule_pct,
                    payout_cycle_limit=excluded.payout_cycle_limit,
                    notes=excluded.notes
            ''', (
                profile.provider, profile.profile_name,
                profile.daily_drawdown_pct, profile.max_drawdown_pct,
                profile.profit_target_pct, profile.minimum_trading_days,
                profile.minimum_holding_seconds, profile.news_restriction_minutes,
                int(profile.ea_allowed), int(profile.grid_allowed), int(profile.hedging_allowed),
                int(profile.copy_trading_allowed), int(profile.cross_account_hedging_allowed),
                profile.consistency_rule_pct, profile.payout_cycle_limit, profile.notes,
            ))

    def get_rule_profile(self, provider: str, profile_name: str) -> ProviderRuleProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM trading_rule_profiles WHERE provider=? AND profile_name=?',
                (provider, profile_name),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        for key in ('ea_allowed','grid_allowed','hedging_allowed','copy_trading_allowed','cross_account_hedging_allowed'):
            data[key] = self._bool(data[key])
        return ProviderRuleProfile(**data)

    def register_account(self, account: TradingAccount) -> None:
        if account.initial_balance <= 0:
            raise TradingRegistryError('initial_balance must be positive')
        if self.get_rule_profile(account.provider, account.rule_profile_name) is None:
            raise TradingRegistryError('referenced rule profile does not exist')
        try:
            with self._connect() as conn:
                conn.execute('''
                    INSERT INTO trading_accounts(
                        account_id,provider,provider_account_ref,account_name,phase,status,currency,initial_balance,rule_profile_name
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                ''', (
                    account.account_id, account.provider, account.provider_account_ref,
                    account.account_name, account.phase, account.status, account.currency,
                    account.initial_balance, account.rule_profile_name,
                ))
        except sqlite3.IntegrityError as exc:
            raise TradingRegistryError('duplicate account id or provider account reference') from exc

    def list_accounts(self, provider: str | None = None) -> list[TradingAccount]:
        with self._connect() as conn:
            if provider is None:
                rows = conn.execute('SELECT * FROM trading_accounts ORDER BY provider, account_name').fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM trading_accounts WHERE provider=? ORDER BY account_name',
                    (provider,),
                ).fetchall()
        return [TradingAccount(**dict(row)) for row in rows]

    def get_account(self, account_id: str) -> TradingAccount | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM trading_accounts WHERE account_id=?', (account_id,)).fetchone()
        return TradingAccount(**dict(row)) if row else None


def reference_prop_profiles() -> tuple[ProviderRuleProfile, ...]:
    """Conservative editable seed profiles derived from the canonical project rules.

    These are configuration records, not a claim that provider rules never change.
    They must be reviewed before any future live activation.
    """
    return (
        ProviderRuleProfile('The5ers', 'default', None, None, None, None, None, None, True, False, True, False, False, None, None, 'Verify current program-specific rules before live use.'),
        ProviderRuleProfile('FundedNext', 'default', None, None, None, None, 120, None, True, False, True, True, False, None, None, 'Minimum holding and strategy rules vary by program; verify before live use.'),
        ProviderRuleProfile('E8', 'default', None, None, None, None, None, None, True, True, True, True, False, None, None, 'Order/request limits and program rules must be loaded in later rule-data updates.'),
        ProviderRuleProfile('FXIFY', 'default', 4.0, 10.0, None, 4, None, None, True, True, True, True, False, None, None, 'Example static risk fields from project context; verify exact program before live use.'),
        ProviderRuleProfile('SimFi', 'default', 2.5, None, None, None, None, None, True, True, True, True, False, None, None, 'Daily drawdown may include floating P/L; verify current program terms.'),
    )
