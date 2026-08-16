from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.core.auron_capability_adapter_contract_v21_525 import ExecutionContext, ExecutionResult, assert_result_accounting

LedgerStatus = Literal['received', 'simulated', 'executed', 'blocked', 'failed']
ReconciliationState = Literal['pending', 'matched', 'mismatched', 'not-applicable']


class LedgerInvariantError(RuntimeError):
    pass


@dataclass(frozen=True)
class LedgerRecord:
    request_id: str
    capability: str
    mode: str
    status: LedgerStatus
    payload_json: str
    result_json: str | None
    provider_reference: str | None
    external_calls_made: int
    reconciliation_state: ReconciliationState
    created_at: str
    updated_at: str


class ExecutionAuditLedger:
    """SQLite-backed execution ledger shared by future capability adapters.

    The ledger persists across process restarts, enforces request-id idempotency,
    and keeps reconciliation state separate from execution state.
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
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS execution_ledger (
                    request_id TEXT PRIMARY KEY,
                    capability TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    provider_reference TEXT,
                    external_calls_made INTEGER NOT NULL DEFAULT 0 CHECK (external_calls_made >= 0),
                    reconciliation_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS reconciliation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    expected_reference TEXT,
                    observed_reference TEXT,
                    state TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES execution_ledger(request_id)
                )
                '''
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

    def record_intent(self, context: ExecutionContext, payload: dict[str, Any]) -> LedgerRecord:
        payload_json = self._canonical(payload)
        existing = self.get(context.request_id)
        if existing is not None:
            if existing.capability != context.capability or existing.mode != context.mode or existing.payload_json != payload_json:
                raise LedgerInvariantError('Idempotency key reuse attempted with different execution intent')
            return existing

        now = self._now()
        reconciliation_state: ReconciliationState = 'not-applicable' if context.mode == 'simulation' else 'pending'
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO execution_ledger (
                    request_id, capability, mode, status, payload_json, result_json,
                    provider_reference, external_calls_made, reconciliation_state, created_at, updated_at
                ) VALUES (?, ?, ?, 'received', ?, NULL, NULL, 0, ?, ?, ?)
                ''',
                (context.request_id, context.capability, context.mode, payload_json, reconciliation_state, now, now),
            )
        record = self.get(context.request_id)
        if record is None:
            raise LedgerInvariantError('Ledger failed to persist execution intent')
        return record

    def record_result(self, result: ExecutionResult) -> LedgerRecord:
        assert_result_accounting(result)
        existing = self.get(result.request_id)
        if existing is None:
            raise LedgerInvariantError('Execution result cannot be recorded before execution intent')
        if existing.capability != result.capability or existing.mode != result.mode:
            raise LedgerInvariantError('Execution result does not match persisted execution intent')

        result_json = self._canonical(asdict(result))
        status: LedgerStatus = result.status
        reconciliation_state: ReconciliationState
        if result.mode == 'simulation':
            reconciliation_state = 'not-applicable'
        elif result.status == 'executed':
            reconciliation_state = 'pending'
        else:
            reconciliation_state = existing.reconciliation_state

        with self._connect() as conn:
            conn.execute(
                '''
                UPDATE execution_ledger
                SET status = ?, result_json = ?, provider_reference = ?, external_calls_made = ?,
                    reconciliation_state = ?, updated_at = ?
                WHERE request_id = ?
                ''',
                (
                    status,
                    result_json,
                    result.provider_reference,
                    result.external_calls_made,
                    reconciliation_state,
                    self._now(),
                    result.request_id,
                ),
            )
        record = self.get(result.request_id)
        if record is None:
            raise LedgerInvariantError('Ledger result update failed')
        return record

    def reconcile(
        self,
        request_id: str,
        observed_provider_reference: str | None,
        *,
        detail: str = '',
    ) -> LedgerRecord:
        existing = self.get(request_id)
        if existing is None:
            raise LedgerInvariantError('Cannot reconcile an unknown request')
        if existing.mode == 'simulation':
            raise LedgerInvariantError('Simulation records do not require provider reconciliation')
        if existing.status != 'executed':
            raise LedgerInvariantError('Only executed live records can be reconciled')

        expected = existing.provider_reference
        state: ReconciliationState = 'matched' if expected and expected == observed_provider_reference else 'mismatched'
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                'UPDATE execution_ledger SET reconciliation_state = ?, updated_at = ? WHERE request_id = ?',
                (state, now, request_id),
            )
            conn.execute(
                '''
                INSERT INTO reconciliation_events (
                    request_id, expected_reference, observed_reference, state, detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (request_id, expected, observed_provider_reference, state, detail, now),
            )
        record = self.get(request_id)
        if record is None:
            raise LedgerInvariantError('Ledger reconciliation update failed')
        return record

    def get(self, request_id: str) -> LedgerRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM execution_ledger WHERE request_id = ?', (request_id,)).fetchone()
        return LedgerRecord(**dict(row)) if row is not None else None

    def list_recent(self, capability: str | None = None, limit: int = 100) -> list[LedgerRecord]:
        if limit < 1 or limit > 1000:
            raise ValueError('limit must be between 1 and 1000')
        with self._connect() as conn:
            if capability is None:
                rows = conn.execute(
                    'SELECT * FROM execution_ledger ORDER BY created_at DESC LIMIT ?', (limit,)
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM execution_ledger WHERE capability = ? ORDER BY created_at DESC LIMIT ?',
                    (capability, limit),
                ).fetchall()
        return [LedgerRecord(**dict(row)) for row in rows]

    def reconciliation_history(self, request_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM reconciliation_events WHERE request_id = ? ORDER BY id ASC', (request_id,)
            ).fetchall()
        return [dict(row) for row in rows]
