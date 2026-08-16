from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.trading.auron_mt5_broker_adapter_v21_536 import MT5BrokerReadOnlyPaperAdapter, PaperExecution
from app.trading.auron_multi_account_allocation_v21_534 import AccountChildIntent
from app.trading.auron_trading_account_state_v21_531 import TradingAccountStateStore
from app.trading.auron_trading_registry_v21_530 import TradingAccountRegistry

ReconciliationState = Literal['matched', 'mismatched', 'blocked']
CertificationState = Literal['canary-certified', 'not-certified']


class TradingReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReconciliationRecord:
    reconciliation_id: str
    child_intent_id: str
    paper_execution_id: str
    account_id: str
    state: ReconciliationState
    checks: tuple[str, ...]
    blockers: tuple[str, ...]
    observed_state_source: str | None
    observed_at: str | None
    integrity_hash: str
    reconciled_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class CanaryCertification:
    certification_id: str
    account_id: str
    state: CertificationState
    matched_reconciliations: int
    blockers: tuple[str, ...]
    certified_at: str | None
    live_execution_enabled: bool = False
    external_calls_made: int = 0


class TradingReconciliationCanaryService:
    """B8 proves consistency before any live trading path exists.

    It reconciles B5 child intents against B7 persistent paper executions and the
    latest normalized read-only account state. A canary certificate only means the
    account has passed the configured proof threshold; it does not enable live orders.
    """

    def __init__(
        self,
        db_path: str | Path,
        registry: TradingAccountRegistry,
        states: TradingAccountStateStore,
        adapter: MT5BrokerReadOnlyPaperAdapter,
        *,
        required_matches: int = 3,
    ) -> None:
        if required_matches < 1:
            raise TradingReconciliationError('required_matches must be >= 1')
        self.db_path = str(db_path)
        self.registry = registry
        self.states = states
        self.adapter = adapter
        self.required_matches = required_matches
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trading_reconciliations (
                    reconciliation_id TEXT PRIMARY KEY,
                    child_intent_id TEXT UNIQUE NOT NULL,
                    paper_execution_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    checks_json TEXT NOT NULL,
                    blockers_json TEXT NOT NULL,
                    observed_state_source TEXT,
                    observed_at TEXT,
                    integrity_hash TEXT NOT NULL,
                    reconciled_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trading_canary_certifications (
                    certification_id TEXT PRIMARY KEY,
                    account_id TEXT UNIQUE NOT NULL,
                    state TEXT NOT NULL,
                    matched_reconciliations INTEGER NOT NULL,
                    blockers_json TEXT NOT NULL,
                    certified_at TEXT,
                    live_execution_enabled INTEGER NOT NULL
                )
            ''')

    @staticmethod
    def _expected_execution_hash(intent: AccountChildIntent) -> str:
        payload = {
            'child_intent_id': intent.child_intent_id,
            'account_id': intent.account_id,
            'symbol': intent.symbol,
            'side': intent.side,
            'lot': intent.calculated_lot,
            'reference_price': intent.reference_price,
            'stop_loss': intent.stop_loss,
            'take_profit': intent.take_profit,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    @staticmethod
    def _reconciliation_id(child_intent_id: str) -> str:
        return 'recon:' + hashlib.sha256(child_intent_id.encode()).hexdigest()[:24]

    def reconcile(self, intent: AccountChildIntent) -> ReconciliationRecord:
        existing = self.get_reconciliation(intent.child_intent_id)
        if existing is not None:
            return existing

        blockers: list[str] = []
        checks: list[str] = []
        account = self.registry.get_account(intent.account_id)
        if account is None:
            blockers.append('account-not-registered')
        elif account.status != 'active':
            blockers.append('account-not-active')
        else:
            checks.append('account-active')

        execution = self.adapter.get_paper_execution(intent.child_intent_id)
        if execution is None:
            blockers.append('paper-execution-missing')
        else:
            if execution.account_id != intent.account_id:
                blockers.append('paper-account-mismatch')
            else:
                checks.append('paper-account-matched')
            if execution.state != 'paper-filled':
                blockers.append('paper-execution-not-filled')
            else:
                checks.append('paper-filled')
            expected_hash = self._expected_execution_hash(intent)
            if execution.integrity_hash != expected_hash:
                blockers.append('paper-integrity-mismatch')
            else:
                checks.append('paper-integrity-matched')
            if execution.symbol != intent.symbol or execution.side != intent.side:
                blockers.append('paper-direction-mismatch')
            else:
                checks.append('paper-direction-matched')
            if execution.lot != intent.calculated_lot:
                blockers.append('paper-lot-mismatch')
            else:
                checks.append('paper-lot-matched')

        state = self.states.get_snapshot(intent.account_id)
        if state is None:
            blockers.append('normalized-account-state-missing')
        else:
            if not state.source.strip():
                blockers.append('account-state-source-missing')
            else:
                checks.append('account-state-source-present')
            if state.equity <= 0:
                blockers.append('account-equity-non-positive')
            else:
                checks.append('account-equity-positive')

        result_state: ReconciliationState = 'matched' if not blockers else 'mismatched'
        execution_id = execution.paper_execution_id if execution is not None else 'missing'
        observed_source = state.source if state is not None else None
        observed_at = state.observed_at if state is not None else None
        reconciled_at = datetime.now(timezone.utc).isoformat()
        integrity_payload = {
            'child_intent_id': intent.child_intent_id,
            'paper_execution_id': execution_id,
            'account_id': intent.account_id,
            'state': result_state,
            'checks': checks,
            'blockers': blockers,
            'observed_state_source': observed_source,
            'observed_at': observed_at,
        }
        integrity_hash = hashlib.sha256(json.dumps(integrity_payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        record = ReconciliationRecord(
            reconciliation_id=self._reconciliation_id(intent.child_intent_id),
            child_intent_id=intent.child_intent_id,
            paper_execution_id=execution_id,
            account_id=intent.account_id,
            state=result_state,
            checks=tuple(checks),
            blockers=tuple(dict.fromkeys(blockers)),
            observed_state_source=observed_source,
            observed_at=observed_at,
            integrity_hash=integrity_hash,
            reconciled_at=reconciled_at,
            external_calls_made=0,
        )
        with self._connect() as conn:
            conn.execute('''
                INSERT INTO trading_reconciliations VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                record.reconciliation_id, record.child_intent_id, record.paper_execution_id,
                record.account_id, record.state, json.dumps(record.checks), json.dumps(record.blockers),
                record.observed_state_source, record.observed_at, record.integrity_hash, record.reconciled_at,
            ))
        return record

    def get_reconciliation(self, child_intent_id: str) -> ReconciliationRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM trading_reconciliations WHERE child_intent_id=?', (child_intent_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        return ReconciliationRecord(
            reconciliation_id=data['reconciliation_id'],
            child_intent_id=data['child_intent_id'],
            paper_execution_id=data['paper_execution_id'],
            account_id=data['account_id'],
            state=data['state'],
            checks=tuple(json.loads(data['checks_json'])),
            blockers=tuple(json.loads(data['blockers_json'])),
            observed_state_source=data['observed_state_source'],
            observed_at=data['observed_at'],
            integrity_hash=data['integrity_hash'],
            reconciled_at=data['reconciled_at'],
            external_calls_made=0,
        )

    def certify_canary(self, account_id: str) -> CanaryCertification:
        account = self.registry.get_account(account_id)
        blockers: list[str] = []
        if account is None:
            blockers.append('account-not-registered')
        elif account.status != 'active':
            blockers.append('account-not-active')

        with self._connect() as conn:
            rows = conn.execute(
                'SELECT state FROM trading_reconciliations WHERE account_id=? ORDER BY reconciled_at ASC',
                (account_id,),
            ).fetchall()
        matched = sum(1 for row in rows if row['state'] == 'matched')
        mismatched = sum(1 for row in rows if row['state'] != 'matched')
        if matched < self.required_matches:
            blockers.append('insufficient-matched-reconciliations')
        if mismatched:
            blockers.append('reconciliation-mismatches-present')
        if not MT5BrokerReadOnlyPaperAdapter.live_execution_available() is False:
            blockers.append('unexpected-live-execution-path-present')

        state: CertificationState = 'canary-certified' if not blockers else 'not-certified'
        certification_id = 'canary:' + hashlib.sha256(account_id.encode()).hexdigest()[:24]
        certified_at = datetime.now(timezone.utc).isoformat() if state == 'canary-certified' else None
        certificate = CanaryCertification(
            certification_id=certification_id,
            account_id=account_id,
            state=state,
            matched_reconciliations=matched,
            blockers=tuple(dict.fromkeys(blockers)),
            certified_at=certified_at,
            live_execution_enabled=False,
            external_calls_made=0,
        )
        with self._connect() as conn:
            conn.execute('''
                INSERT INTO trading_canary_certifications VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET
                    state=excluded.state,matched_reconciliations=excluded.matched_reconciliations,
                    blockers_json=excluded.blockers_json,certified_at=excluded.certified_at,
                    live_execution_enabled=excluded.live_execution_enabled
            ''', (
                certificate.certification_id, certificate.account_id, certificate.state,
                certificate.matched_reconciliations, json.dumps(certificate.blockers),
                certificate.certified_at, 0,
            ))
        return certificate

    def get_canary_certification(self, account_id: str) -> CanaryCertification | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM trading_canary_certifications WHERE account_id=?', (account_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        return CanaryCertification(
            certification_id=data['certification_id'], account_id=data['account_id'], state=data['state'],
            matched_reconciliations=data['matched_reconciliations'], blockers=tuple(json.loads(data['blockers_json'])),
            certified_at=data['certified_at'], live_execution_enabled=bool(data['live_execution_enabled']), external_calls_made=0,
        )
