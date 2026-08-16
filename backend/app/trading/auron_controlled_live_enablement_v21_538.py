from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_guards_v21_535 import GuardDecision
from app.trading.auron_trading_reconciliation_canary_v21_537 import TradingReconciliationCanaryService
from app.trading.auron_trading_registry_v21_530 import TradingAccountRegistry


class LiveEnablementError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveEnablementScope:
    account_id: str
    provider: str
    mode: str
    operator_approved: bool
    global_kill_switch: bool
    account_kill_switch: bool
    enabled: bool
    updated_at: str


@dataclass(frozen=True)
class LiveExecutionDecision:
    execution_id: str
    child_intent_id: str
    account_id: str
    state: str
    blockers: tuple[str, ...]
    provider_order_id: str | None
    created_at: str
    external_calls_made: int


class LiveBrokerWriteBoundary(Protocol):
    """Explicit provider-write boundary. Implementations must be injected deliberately."""
    def place_order(self, intent: AccountChildIntent, idempotency_key: str) -> str: ...


class DisabledLiveBrokerWriteBoundary:
    """Default B9 boundary: fail closed. No provider call is possible."""
    def place_order(self, intent: AccountChildIntent, idempotency_key: str) -> str:
        raise LiveEnablementError('live provider write boundary is disabled')


class ControlledLiveEnablementService:
    """B9 gate for deliberate canary/live activation.

    Live execution is never default. An account must be active, canary-certified,
    explicitly scoped, operator-approved, kill switches clear, and the B6 guard must
    still approve the exact child intent. The default provider boundary cannot write.
    """

    def __init__(self, db_path: str | Path, registry: TradingAccountRegistry,
                 reconciliation: TradingReconciliationCanaryService,
                 writer: LiveBrokerWriteBoundary | None = None) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.reconciliation = reconciliation
        self.writer = writer or DisabledLiveBrokerWriteBoundary()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS live_enablement_scopes (
                account_id TEXT PRIMARY KEY, provider TEXT NOT NULL, mode TEXT NOT NULL,
                operator_approved INTEGER NOT NULL, global_kill_switch INTEGER NOT NULL,
                account_kill_switch INTEGER NOT NULL, enabled INTEGER NOT NULL, updated_at TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS live_execution_decisions (
                execution_id TEXT PRIMARY KEY, child_intent_id TEXT UNIQUE NOT NULL,
                account_id TEXT NOT NULL, state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                provider_order_id TEXT, created_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL)''')

    def configure_scope(self, account_id: str, provider: str, *, mode: str = 'canary',
                        operator_approved: bool = False, global_kill_switch: bool = True,
                        account_kill_switch: bool = True, enabled: bool = False) -> LiveEnablementScope:
        if mode not in {'canary', 'multi-account-live'}:
            raise LiveEnablementError('unsupported live mode')
        if self.registry.get_account(account_id) is None:
            raise LiveEnablementError('account must be registered')
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute('''INSERT INTO live_enablement_scopes VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET provider=excluded.provider,mode=excluded.mode,
                operator_approved=excluded.operator_approved,global_kill_switch=excluded.global_kill_switch,
                account_kill_switch=excluded.account_kill_switch,enabled=excluded.enabled,updated_at=excluded.updated_at''',
                (account_id, provider, mode, int(operator_approved), int(global_kill_switch),
                 int(account_kill_switch), int(enabled), now))
        return self.get_scope(account_id)

    def get_scope(self, account_id: str) -> LiveEnablementScope | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM live_enablement_scopes WHERE account_id=?', (account_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        for key in ('operator_approved', 'global_kill_switch', 'account_kill_switch', 'enabled'):
            d[key] = bool(d[key])
        return LiveEnablementScope(**d)

    @staticmethod
    def _execution_id(child_intent_id: str) -> str:
        return 'live:' + hashlib.sha256(child_intent_id.encode()).hexdigest()[:24]

    def evaluate(self, intent: AccountChildIntent, guard: GuardDecision) -> LiveExecutionDecision:
        existing = self.get_decision(intent.child_intent_id)
        if existing is not None:
            return existing
        blockers: list[str] = []
        account = self.registry.get_account(intent.account_id)
        if account is None or account.status != 'active': blockers.append('account-not-active')
        certificate = self.reconciliation.get_canary_certification(intent.account_id)
        if certificate is None or certificate.state != 'canary-certified': blockers.append('canary-certification-required')
        scope = self.get_scope(intent.account_id)
        if scope is None: blockers.append('live-scope-missing')
        else:
            if not scope.enabled: blockers.append('live-scope-disabled')
            if not scope.operator_approved: blockers.append('operator-approval-required')
            if scope.global_kill_switch: blockers.append('global-kill-switch-active')
            if scope.account_kill_switch: blockers.append('account-kill-switch-active')
        if guard.account_id != intent.account_id or guard.child_intent_id != intent.child_intent_id:
            blockers.append('guard-intent-mismatch')
        elif guard.state != 'ready-for-paper-execution' or guard.blockers:
            blockers.append('current-guard-approval-required')
        if intent.state != 'ready-for-guard-evaluation' or intent.blockers:
            blockers.append('child-intent-not-ready')
        state = 'ready-for-controlled-live' if not blockers else 'blocked'
        decision = LiveExecutionDecision(self._execution_id(intent.child_intent_id), intent.child_intent_id,
            intent.account_id, state, tuple(dict.fromkeys(blockers)), None,
            datetime.now(timezone.utc).isoformat(), 0)
        self._persist(decision)
        return decision

    def execute_controlled(self, intent: AccountChildIntent, guard: GuardDecision) -> LiveExecutionDecision:
        decision = self.evaluate(intent, guard)
        if decision.state != 'ready-for-controlled-live':
            return decision
        # The provider write is behind one explicit boundary and an idempotency key.
        try:
            provider_order_id = self.writer.place_order(intent, decision.execution_id)
        except LiveEnablementError:
            return self._replace(decision, 'provider-write-disabled', ('provider-write-disabled',), None, 0)
        except Exception:
            return self._replace(decision, 'provider-error', ('provider-write-error',), None, 1)
        return self._replace(decision, 'live-submitted', (), provider_order_id, 1)

    def _replace(self, old: LiveExecutionDecision, state: str, blockers: tuple[str, ...],
                 provider_order_id: str | None, calls: int) -> LiveExecutionDecision:
        result = LiveExecutionDecision(old.execution_id, old.child_intent_id, old.account_id, state,
            blockers, provider_order_id, old.created_at, calls)
        with self._connect() as conn:
            conn.execute('''UPDATE live_execution_decisions SET state=?,blockers_json=?,provider_order_id=?,external_calls_made=?
                            WHERE child_intent_id=?''',
                         (state, json.dumps(blockers), provider_order_id, calls, old.child_intent_id))
        return result

    def _persist(self, decision: LiveExecutionDecision) -> None:
        with self._connect() as conn:
            conn.execute('INSERT INTO live_execution_decisions VALUES (?,?,?,?,?,?,?,?)',
                (decision.execution_id, decision.child_intent_id, decision.account_id, decision.state,
                 json.dumps(decision.blockers), decision.provider_order_id, decision.created_at,
                 decision.external_calls_made))

    def get_decision(self, child_intent_id: str) -> LiveExecutionDecision | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM live_execution_decisions WHERE child_intent_id=?', (child_intent_id,)).fetchone()
        if row is None: return None
        d = dict(row); d['blockers'] = tuple(json.loads(d.pop('blockers_json')))
        return LiveExecutionDecision(**d)
