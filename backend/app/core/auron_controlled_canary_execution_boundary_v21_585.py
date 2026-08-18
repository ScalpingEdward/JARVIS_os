from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.core.auron_controlled_provider_canary_contract_v21_584 import CanaryActivationDecision


class ControlledCanaryExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanaryExecutionRequest:
    authorization: CanaryActivationDecision
    action_key: str
    payload: dict
    kill_switch_active: bool
    reconciliation_ready: bool
    stop_control_ready: bool


@dataclass(frozen=True)
class CanaryExecutionRecord:
    execution_id: str
    activation_id: str
    vertical: str
    provider_id: str
    action_key: str
    ordinal: int
    action_allowance: int
    state: str
    provider_ref: str | None
    blockers: tuple[str, ...]
    payload_hash: str
    idempotency_key: str
    created_at: str
    external_calls_made: int


class CanaryExecutionTransport(Protocol):
    def execute_canary_action(self, *, vertical: str, provider_id: str, scope: str,
                              action_key: str, payload: dict, idempotency_key: str) -> str: ...


class DisabledCanaryExecutionTransport:
    def execute_canary_action(self, **kwargs) -> str:
        raise ControlledCanaryExecutionError('canary execution transport is disabled')


class ControlledCanaryExecutionService:
    """F2 bounded execution boundary for an F1 canary authorization artifact.

    Transport is adapter-separated and disabled by default. Every action rechecks kill switch,
    reconciliation/stop readiness, hard budget and idempotency before any adapter call.
    """

    def __init__(self, db_path: str | Path, transport: CanaryExecutionTransport | None = None) -> None:
        self.db_path = str(db_path)
        self.transport = transport or DisabledCanaryExecutionTransport()
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS canary_executions (
                execution_id TEXT PRIMARY KEY, activation_id TEXT NOT NULL,
                vertical TEXT NOT NULL, provider_id TEXT NOT NULL, action_key TEXT NOT NULL,
                ordinal INTEGER NOT NULL, action_allowance INTEGER NOT NULL,
                state TEXT NOT NULL, provider_ref TEXT, blockers_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL,
                UNIQUE(activation_id, ordinal))''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def execute(self, request: CanaryExecutionRequest, *, at: str | None = None) -> CanaryExecutionRecord:
        auth = request.authorization
        if not auth.activation_authorized:
            raise ControlledCanaryExecutionError('valid F1 authorization required')
        if auth.live_transport_enabled_by_contract:
            raise ControlledCanaryExecutionError('invalid F1 transport state')
        if not request.action_key.strip():
            raise ControlledCanaryExecutionError('action key is required')

        payload_hash = self._hash(request.payload)
        idempotency_key = 'canary-idem-' + self._hash({
            'activation_id': auth.activation_id,
            'action_key': request.action_key.strip(),
            'payload_hash': payload_hash,
        })[:32]

        with self._connect() as conn:
            row = conn.execute('SELECT * FROM canary_executions WHERE idempotency_key=?',(idempotency_key,)).fetchone()
            if row:
                return self._from_row(row)
            consumed = conn.execute('SELECT COUNT(*) AS n FROM canary_executions WHERE activation_id=? AND state IN (\'provider-submitted\',\'transport-disabled\',\'transport-error\')',(auth.activation_id,)).fetchone()['n']

        ordinal = int(consumed) + 1
        blockers: list[str] = []
        if ordinal > auth.action_allowance:
            blockers.append('canary-action-budget-exhausted')
        if not request.kill_switch_active:
            blockers.append('kill-switch-not-active')
        if not request.reconciliation_ready:
            blockers.append('reconciliation-not-ready')
        if not request.stop_control_ready:
            blockers.append('stop-control-not-ready')

        execution_id = 'canary-exec-' + self._hash({
            'activation_id': auth.activation_id,
            'ordinal': ordinal,
            'idempotency_key': idempotency_key,
        })[:24]
        provider_ref = None
        calls = 0

        if blockers:
            state = 'blocked'
        else:
            try:
                provider_ref = self.transport.execute_canary_action(
                    vertical=auth.vertical, provider_id=auth.provider_id, scope=auth.scope,
                    action_key=request.action_key.strip(), payload=request.payload,
                    idempotency_key=idempotency_key,
                )
                calls = 1
                if not provider_ref:
                    raise ControlledCanaryExecutionError('provider reference required')
                state = 'provider-submitted'
            except ControlledCanaryExecutionError:
                state = 'transport-disabled'
                blockers.append('canary-execution-transport-disabled')
            except Exception:
                calls = 1
                state = 'transport-error'
                blockers.append('canary-execution-transport-error')

        record = CanaryExecutionRecord(
            execution_id, auth.activation_id, auth.vertical, auth.provider_id,
            request.action_key.strip(), ordinal, auth.action_allowance, state, provider_ref,
            tuple(blockers), payload_hash, idempotency_key, at or self._now(), calls,
        )
        with self._connect() as conn:
            conn.execute('INSERT INTO canary_executions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                record.execution_id,record.activation_id,record.vertical,record.provider_id,
                record.action_key,record.ordinal,record.action_allowance,record.state,
                record.provider_ref,json.dumps(record.blockers),record.payload_hash,
                record.idempotency_key,record.created_at,record.external_calls_made))
        return record

    def list_for_activation(self, activation_id: str) -> tuple[CanaryExecutionRecord, ...]:
        with self._connect() as conn:
            rows=conn.execute('SELECT * FROM canary_executions WHERE activation_id=? ORDER BY ordinal',(activation_id,)).fetchall()
        return tuple(self._from_row(r) for r in rows)

    @staticmethod
    def _from_row(row) -> CanaryExecutionRecord:
        d=dict(row)
        d['blockers']=tuple(json.loads(d.pop('blockers_json')))
        return CanaryExecutionRecord(**d)
