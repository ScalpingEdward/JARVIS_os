from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.automation.auron_automation_controlled_execution_v21_569 import ControlledAutomationExecutionService


class AutomationReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationActionResult:
    action_id: str
    provider_result_ref: str
    state: str
    idempotency_key: str
    observed_at: str
    external_calls_made: int = 1


@dataclass(frozen=True)
class AutomationReconciliationRecord:
    execution_id: str
    state: str
    blockers: tuple[str, ...]
    attempt_count: int
    retry_eligible: bool
    cancellation_requested: bool
    cancellation_state: str
    verified_actions: int
    failed_actions: int
    reconciled_at: str
    external_calls_made: int = 0


class AutomationResultReader(Protocol):
    def read_action_result(self, provider_result_ref: str) -> AutomationActionResult: ...


class AutomationCancellationTransport(Protocol):
    def cancel_action(self, *, provider_result_ref: str, idempotency_key: str) -> str: ...


class DisabledAutomationResultReader:
    def read_action_result(self, provider_result_ref: str) -> AutomationActionResult:
        raise AutomationReconciliationError('automation result reader is disabled')


class DisabledAutomationCancellationTransport:
    def cancel_action(self, **kwargs) -> str:
        raise AutomationReconciliationError('automation cancellation transport is disabled')


class AutomationReconciliationRetryCancellationService:
    """D23 result verification, bounded retries and explicit cancellation semantics.

    Retry authorization is policy only; no blind action replay occurs here. Cancellation is
    explicit and best-effort against provider result refs already returned by D22. Every
    provider result must match the original action id and D22 idempotency key.
    """

    SUCCESS_STATES = {'completed', 'succeeded'}
    RETRYABLE_STATES = {'pending', 'temporary-failure', 'rate-limited'}
    CANCELLABLE_STATES = {'pending', 'running'}

    def __init__(self, db_path: str | Path, execution: ControlledAutomationExecutionService,
                 reader: AutomationResultReader | None = None,
                 cancellation: AutomationCancellationTransport | None = None,
                 max_attempts: int = 3) -> None:
        if not 1 <= max_attempts <= 5:
            raise ValueError('max_attempts must be between 1 and 5')
        self.db_path = str(db_path)
        self.execution = execution
        self.reader = reader or DisabledAutomationResultReader()
        self.cancellation = cancellation or DisabledAutomationCancellationTransport()
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
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS automation_reconciliation (
                    execution_id TEXT PRIMARY KEY, state TEXT NOT NULL,
                    blockers_json TEXT NOT NULL, attempt_count INTEGER NOT NULL,
                    retry_eligible INTEGER NOT NULL, cancellation_requested INTEGER NOT NULL,
                    cancellation_state TEXT NOT NULL, verified_actions INTEGER NOT NULL,
                    failed_actions INTEGER NOT NULL, reconciled_at TEXT NOT NULL,
                    external_calls_made INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS automation_reconciliation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT NOT NULL,
                    state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL, retry_eligible INTEGER NOT NULL,
                    cancellation_requested INTEGER NOT NULL, cancellation_state TEXT NOT NULL,
                    verified_actions INTEGER NOT NULL, failed_actions INTEGER NOT NULL,
                    reconciled_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL);
            ''')

    def reconcile(self, plan_id: str) -> AutomationReconciliationRecord:
        decision = self.execution.get_decision_by_plan(plan_id)
        if decision is None:
            raise AutomationReconciliationError('D22 execution decision not found')
        previous = self.get(decision.execution_id)
        attempts = (previous.attempt_count if previous else 0) + 1
        blockers: list[str] = []
        verified = 0
        failed = 0
        calls = 0
        retryable = False

        if decision.state != 'submitted-for-reconciliation':
            blockers.append('submitted-d22-execution-required')
        results = json.loads(decision.provider_results_json or '{}')
        simulated_actions = self.execution.simulation.list_actions(decision.plan_id)
        action_map = {a.action_id: a for a in simulated_actions}
        if not results:
            blockers.append('provider-results-missing')

        for action_id, provider_ref in results.items():
            action = action_map.get(action_id)
            if action is None:
                blockers.append(f'unknown-action-result:{action_id}')
                failed += 1
                continue
            try:
                result = self.reader.read_action_result(provider_ref)
                calls += result.external_calls_made
            except AutomationReconciliationError:
                blockers.append('result-reader-disabled')
                failed += 1
                continue
            except Exception:
                blockers.append(f'result-read-error:{action_id}')
                failed += 1
                retryable = True
                calls += 1
                continue

            expected_key = f'{decision.execution_id}:{action.ordinal}'
            if result.action_id != action_id:
                blockers.append(f'action-id-mismatch:{action_id}')
                failed += 1
                continue
            if result.provider_result_ref != provider_ref:
                blockers.append(f'provider-result-ref-mismatch:{action_id}')
                failed += 1
                continue
            if result.idempotency_key != expected_key:
                blockers.append(f'idempotency-key-mismatch:{action_id}')
                failed += 1
                continue
            if result.state in self.SUCCESS_STATES:
                verified += 1
            elif result.state in self.RETRYABLE_STATES:
                failed += 1
                retryable = True
            else:
                blockers.append(f'unsupported-result-state:{action_id}')
                failed += 1

        if not blockers and failed == 0 and verified == len(action_map):
            state = 'verified-complete'
            retry = False
        elif retryable and attempts < self.max_attempts:
            state = 'retry-eligible'
            retry = True
        elif retryable:
            state = 'retry-exhausted'
            retry = False
        else:
            state = 'blocked'
            retry = False

        record = AutomationReconciliationRecord(
            execution_id=decision.execution_id, state=state,
            blockers=tuple(dict.fromkeys(blockers)), attempt_count=attempts,
            retry_eligible=retry,
            cancellation_requested=previous.cancellation_requested if previous else False,
            cancellation_state=previous.cancellation_state if previous else 'not-requested',
            verified_actions=verified, failed_actions=failed,
            reconciled_at=self._now(), external_calls_made=calls,
        )
        self._persist(record)
        return record

    def retry_authorization(self, execution_id: str) -> AutomationReconciliationRecord:
        record = self.get(execution_id)
        if record is None:
            raise AutomationReconciliationError('reconciliation record not found')
        if not record.retry_eligible or record.attempt_count >= self.max_attempts:
            raise AutomationReconciliationError('retry is not authorized')
        return record

    def request_cancellation(self, plan_id: str) -> AutomationReconciliationRecord:
        decision = self.execution.get_decision_by_plan(plan_id)
        if decision is None:
            raise AutomationReconciliationError('D22 execution decision not found')
        current = self.get(decision.execution_id) or self.reconcile(plan_id)
        if decision.state != 'submitted-for-reconciliation':
            raise AutomationReconciliationError('only submitted executions can be cancelled')
        results = json.loads(decision.provider_results_json or '{}')
        if not results:
            raise AutomationReconciliationError('provider results missing')

        calls = current.external_calls_made
        cancel_states: list[str] = []
        for action in self.execution.simulation.list_actions(plan_id):
            provider_ref = results.get(action.action_id)
            if not provider_ref:
                continue
            try:
                result = self.reader.read_action_result(provider_ref)
                calls += result.external_calls_made
            except Exception:
                cancel_states.append('result-unavailable')
                continue
            if result.state not in self.CANCELLABLE_STATES:
                cancel_states.append('not-cancellable')
                continue
            try:
                state = self.cancellation.cancel_action(
                    provider_result_ref=provider_ref,
                    idempotency_key=f'{decision.execution_id}:{action.ordinal}:cancel',
                )
                calls += 1
                cancel_states.append(state)
            except AutomationReconciliationError:
                cancel_states.append('cancellation-transport-disabled')
            except Exception:
                calls += 1
                cancel_states.append('cancellation-error')

        if cancel_states and all(state in {'cancelled', 'already-cancelled'} for state in cancel_states):
            cancellation_state = 'cancelled'
        elif 'cancellation-transport-disabled' in cancel_states:
            cancellation_state = 'transport-disabled'
        elif 'cancellation-error' in cancel_states:
            cancellation_state = 'error'
        elif cancel_states and all(state == 'not-cancellable' for state in cancel_states):
            cancellation_state = 'not-cancellable'
        else:
            cancellation_state = 'partial-or-pending'

        updated = AutomationReconciliationRecord(
            current.execution_id, current.state, current.blockers, current.attempt_count,
            current.retry_eligible, True, cancellation_state, current.verified_actions,
            current.failed_actions, self._now(), calls,
        )
        self._persist(updated)
        return updated

    def _persist(self, record: AutomationReconciliationRecord) -> None:
        values = (
            record.execution_id, record.state, json.dumps(record.blockers), record.attempt_count,
            int(record.retry_eligible), int(record.cancellation_requested), record.cancellation_state,
            record.verified_actions, record.failed_actions, record.reconciled_at,
            record.external_calls_made,
        )
        with self._connect() as conn:
            conn.execute('''INSERT INTO automation_reconciliation VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(execution_id) DO UPDATE SET state=excluded.state,
                blockers_json=excluded.blockers_json,attempt_count=excluded.attempt_count,
                retry_eligible=excluded.retry_eligible,cancellation_requested=excluded.cancellation_requested,
                cancellation_state=excluded.cancellation_state,verified_actions=excluded.verified_actions,
                failed_actions=excluded.failed_actions,reconciled_at=excluded.reconciled_at,
                external_calls_made=excluded.external_calls_made''', values)
            conn.execute('''INSERT INTO automation_reconciliation_history
                (execution_id,state,blockers_json,attempt_count,retry_eligible,cancellation_requested,
                 cancellation_state,verified_actions,failed_actions,reconciled_at,external_calls_made)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''', values)

    def get(self, execution_id: str) -> AutomationReconciliationRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_reconciliation WHERE execution_id=?',(execution_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['blockers'] = tuple(json.loads(data.pop('blockers_json')))
        data['retry_eligible'] = bool(data['retry_eligible'])
        data['cancellation_requested'] = bool(data['cancellation_requested'])
        return AutomationReconciliationRecord(**data)

    def history(self, execution_id: str) -> tuple[dict, ...]:
        with self._connect() as conn:
            rows = conn.execute('''SELECT state,blockers_json,attempt_count,retry_eligible,
                cancellation_requested,cancellation_state,verified_actions,failed_actions,
                reconciled_at,external_calls_made FROM automation_reconciliation_history
                WHERE execution_id=? ORDER BY id''',(execution_id,)).fetchall()
        return tuple({**dict(row), 'blockers': tuple(json.loads(row['blockers_json']))} for row in rows)
