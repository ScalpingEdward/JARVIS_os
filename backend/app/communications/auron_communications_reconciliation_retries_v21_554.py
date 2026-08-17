from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.communications.auron_communications_controlled_execution_v21_553 import ControlledCommunicationsExecutionService


class CommunicationsReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderMessageResult:
    provider_message_ref: str
    channel_id: str
    state: str
    idempotency_key: str
    observed_at: str
    external_calls_made: int = 1


@dataclass(frozen=True)
class CommunicationsReconciliationRecord:
    execution_id: str
    provider_message_ref: str | None
    state: str
    blockers: tuple[str, ...]
    attempt_count: int
    retry_eligible: bool
    verified_at: str
    external_calls_made: int = 0


class CommunicationsProviderResultReader(Protocol):
    def read_result(self, provider_message_ref: str) -> ProviderMessageResult: ...


class DisabledCommunicationsProviderResultReader:
    def read_result(self, provider_message_ref: str) -> ProviderMessageResult:
        raise CommunicationsReconciliationError('communications provider result reader is disabled')


class CommunicationsReconciliationRetryService:
    """D7 verifies provider results and bounds retries.

    Reconciliation never treats provider submission as delivery proof. Provider reference,
    channel and idempotency key must match the D6 execution. Retries are policy decisions
    only; this service does not silently resend a message.
    """

    RETRYABLE_PROVIDER_STATES = {'pending', 'temporary-failure', 'rate-limited'}
    TERMINAL_SUCCESS_STATES = {'sent', 'delivered'}

    def __init__(self, db_path: str | Path, execution: ControlledCommunicationsExecutionService,
                 reader: CommunicationsProviderResultReader | None = None, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError('max_attempts must be >= 1')
        self.db_path = str(db_path)
        self.execution = execution
        self.reader = reader or DisabledCommunicationsProviderResultReader()
        self.max_attempts = max_attempts
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_reconciliation (
                execution_id TEXT PRIMARY KEY, provider_message_ref TEXT,
                state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                attempt_count INTEGER NOT NULL, retry_eligible INTEGER NOT NULL,
                verified_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_reconciliation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT NOT NULL,
                state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                attempt_count INTEGER NOT NULL, retry_eligible INTEGER NOT NULL,
                verified_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL)''')

    def reconcile(self, plan_id: str) -> CommunicationsReconciliationRecord:
        decision = self.execution.get_decision_by_plan(plan_id)
        if decision is None:
            raise CommunicationsReconciliationError('D6 execution decision not found')
        previous = self.get(decision.execution_id)
        attempts = (previous.attempt_count if previous else 0) + 1
        blockers: list[str] = []
        calls = 0
        provider_state = None

        if decision.state != 'provider-submitted' or not decision.provider_message_ref:
            blockers.append('provider-submission-required')
        else:
            try:
                result = self.reader.read_result(decision.provider_message_ref)
                calls = result.external_calls_made
                provider_state = result.state
                if result.provider_message_ref != decision.provider_message_ref:
                    blockers.append('provider-message-ref-mismatch')
                if result.channel_id != decision.channel_id:
                    blockers.append('provider-channel-mismatch')
                if result.idempotency_key != decision.execution_id:
                    blockers.append('provider-idempotency-key-mismatch')
            except CommunicationsReconciliationError:
                blockers.append('provider-result-reader-disabled')
            except Exception:
                blockers.append('provider-result-read-error')
                calls = 1

        if not blockers and provider_state in self.TERMINAL_SUCCESS_STATES:
            state = 'verified-delivered' if provider_state == 'delivered' else 'verified-sent'
            retry = False
        elif not blockers and provider_state in self.RETRYABLE_PROVIDER_STATES:
            retry = attempts < self.max_attempts
            state = 'retry-eligible' if retry else 'retry-exhausted'
        elif not blockers:
            state = 'provider-result-unverified'
            retry = False
            blockers.append('unsupported-provider-result-state')
        else:
            retryable_blockers = {'provider-result-read-error'}
            retry = bool(set(blockers) & retryable_blockers) and attempts < self.max_attempts
            state = 'retry-eligible' if retry else 'blocked'

        record = CommunicationsReconciliationRecord(
            decision.execution_id, decision.provider_message_ref, state,
            tuple(dict.fromkeys(blockers)), attempts, retry, self._now(), calls,
        )
        self._persist(record)
        return record

    def retry_authorization(self, execution_id: str) -> CommunicationsReconciliationRecord:
        record = self.get(execution_id)
        if record is None:
            raise CommunicationsReconciliationError('reconciliation record not found')
        if not record.retry_eligible or record.attempt_count >= self.max_attempts:
            raise CommunicationsReconciliationError('retry is not authorized')
        return record

    def _persist(self, record: CommunicationsReconciliationRecord) -> None:
        values = (
            record.execution_id, record.provider_message_ref, record.state,
            json.dumps(record.blockers), record.attempt_count, int(record.retry_eligible),
            record.verified_at, record.external_calls_made,
        )
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_reconciliation VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(execution_id) DO UPDATE SET provider_message_ref=excluded.provider_message_ref,
                state=excluded.state,blockers_json=excluded.blockers_json,
                attempt_count=excluded.attempt_count,retry_eligible=excluded.retry_eligible,
                verified_at=excluded.verified_at,external_calls_made=excluded.external_calls_made''', values)
            conn.execute('''INSERT INTO communications_reconciliation_history
                (execution_id,state,blockers_json,attempt_count,retry_eligible,verified_at,external_calls_made)
                VALUES (?,?,?,?,?,?,?)''', (
                record.execution_id, record.state, json.dumps(record.blockers), record.attempt_count,
                int(record.retry_eligible), record.verified_at, record.external_calls_made,
            ))

    def get(self, execution_id: str) -> CommunicationsReconciliationRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_reconciliation WHERE execution_id=?', (execution_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['blockers'] = tuple(json.loads(data.pop('blockers_json')))
        data['retry_eligible'] = bool(data['retry_eligible'])
        return CommunicationsReconciliationRecord(**data)

    def history(self, execution_id: str) -> tuple[dict, ...]:
        with self._connect() as conn:
            rows = conn.execute('''SELECT state,blockers_json,attempt_count,retry_eligible,
                verified_at,external_calls_made FROM communications_reconciliation_history
                WHERE execution_id=? ORDER BY id''', (execution_id,)).fetchall()
        return tuple({**dict(row), 'blockers': tuple(json.loads(row['blockers_json']))} for row in rows)
