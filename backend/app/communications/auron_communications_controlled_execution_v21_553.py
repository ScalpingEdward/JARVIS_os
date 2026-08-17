from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.communications.auron_communications_policy_approval_v21_551 import CommunicationsPolicyApprovalService
from app.communications.auron_communications_registry_state_v21_549 import CommunicationsRegistryStateStore
from app.communications.auron_communications_simulation_dry_run_v21_552 import CommunicationsSimulationDryRunService


class CommunicationsExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsExecutionScope:
    channel_id: str
    enabled: bool
    operator_enabled: bool
    kill_switch: bool
    updated_at: str


@dataclass(frozen=True)
class CommunicationsExecutionDecision:
    execution_id: str
    plan_id: str
    intent_id: str
    channel_id: str
    approval_id: str
    payload_hash: str
    state: str
    blockers: tuple[str, ...]
    provider_message_ref: str | None
    created_at: str
    external_calls_made: int = 0


class CommunicationsProviderWriter(Protocol):
    def send(self, *, channel_id: str, conversation_id: str | None, recipients: tuple[str, ...],
             subject: str, body_text: str, idempotency_key: str) -> str: ...


class DisabledCommunicationsProviderWriter:
    def send(self, **kwargs) -> str:
        raise CommunicationsExecutionError('communications provider writer is disabled')


class ControlledCommunicationsExecutionService:
    """D6 controlled outbound boundary.

    A successful D5 simulation is necessary but insufficient. Current D4 approval,
    exact payload integrity, explicit channel scope, operator enablement and a clear
    kill switch are revalidated immediately before the provider writer is invoked.
    The default writer cannot send anything.
    """

    def __init__(self, db_path: str | Path, store: CommunicationsRegistryStateStore,
                 approvals: CommunicationsPolicyApprovalService,
                 dryrun: CommunicationsSimulationDryRunService,
                 writer: CommunicationsProviderWriter | None = None) -> None:
        self.db_path = str(db_path)
        self.store = store
        self.approvals = approvals
        self.dryrun = dryrun
        self.writer = writer or DisabledCommunicationsProviderWriter()
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
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_execution_scopes (
                channel_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,
                operator_enabled INTEGER NOT NULL, kill_switch INTEGER NOT NULL,
                updated_at TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_execution_decisions (
                execution_id TEXT PRIMARY KEY, plan_id TEXT UNIQUE NOT NULL,
                intent_id TEXT NOT NULL, channel_id TEXT NOT NULL,
                approval_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
                state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                provider_message_ref TEXT, created_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL)''')

    def configure_scope(self, channel_id: str, *, enabled: bool = False,
                        operator_enabled: bool = False,
                        kill_switch: bool = True) -> CommunicationsExecutionScope:
        channel = self.store.get_channel(channel_id)
        if channel is None:
            raise CommunicationsExecutionError('communications channel not found')
        now = self._now()
        with self._connect() as conn:
            conn.execute('''INSERT INTO communications_execution_scopes VALUES (?,?,?,?,?)
                ON CONFLICT(channel_id) DO UPDATE SET enabled=excluded.enabled,
                operator_enabled=excluded.operator_enabled,kill_switch=excluded.kill_switch,
                updated_at=excluded.updated_at''',
                (channel_id, int(enabled), int(operator_enabled), int(kill_switch), now))
        scope = self.get_scope(channel_id)
        if scope is None:
            raise CommunicationsExecutionError('scope persistence failed')
        return scope

    def get_scope(self, channel_id: str) -> CommunicationsExecutionScope | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_execution_scopes WHERE channel_id=?', (channel_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        for key in ('enabled', 'operator_enabled', 'kill_switch'):
            data[key] = bool(data[key])
        return CommunicationsExecutionScope(**data)

    @staticmethod
    def _execution_id(plan_id: str) -> str:
        return 'comms-exec:' + hashlib.sha256(plan_id.encode()).hexdigest()[:24]

    def evaluate(self, plan_id: str) -> CommunicationsExecutionDecision:
        existing = self.get_decision_by_plan(plan_id)
        if existing is not None:
            return existing
        plan = self.dryrun.get_plan(plan_id)
        simulation = self.dryrun.get_result(plan_id)
        if plan is None:
            raise CommunicationsExecutionError('D5 dry-run plan not found')
        blockers: list[str] = []
        if simulation is None or simulation.state != 'simulated-success':
            blockers.append('successful-d5-simulation-required')
        elif simulation.payload_hash != plan.payload_hash:
            blockers.append('simulation-payload-mismatch')
        authorization = self.approvals.evaluate(plan.intent_id)
        if authorization.state != 'ready-for-simulation' or authorization.approval_id != plan.approval_id:
            blockers.append('current-d4-approval-required')
        intent = self.approvals.get_intent(plan.intent_id)
        if intent is None:
            blockers.append('intent-missing')
        else:
            if intent.content_hash != plan.content_hash:
                blockers.append('content-hash-changed')
            current_hash = self.dryrun._payload_hash(intent, plan.approval_id)
            if current_hash != plan.payload_hash:
                blockers.append('payload-integrity-mismatch')
        channel = self.store.get_channel(plan.channel_id)
        if channel is None or channel.status != 'active':
            blockers.append('channel-not-active')
        scope = self.get_scope(plan.channel_id)
        if scope is None:
            blockers.append('execution-scope-missing')
        else:
            if not scope.enabled:
                blockers.append('execution-scope-disabled')
            if not scope.operator_enabled:
                blockers.append('operator-enablement-required')
            if scope.kill_switch:
                blockers.append('execution-kill-switch-active')
        state = 'ready-for-controlled-execution' if not blockers else 'blocked'
        decision = CommunicationsExecutionDecision(
            self._execution_id(plan.plan_id), plan.plan_id, plan.intent_id, plan.channel_id,
            plan.approval_id, plan.payload_hash, state, tuple(dict.fromkeys(blockers)),
            None, self._now(), 0,
        )
        self._persist(decision)
        return decision

    def execute(self, plan_id: str) -> CommunicationsExecutionDecision:
        decision = self.evaluate(plan_id)
        if decision.state != 'ready-for-controlled-execution':
            return decision
        plan = self.dryrun.get_plan(plan_id)
        intent = self.approvals.get_intent(decision.intent_id)
        if plan is None or intent is None:
            return self._replace(decision, 'blocked', ('intent-or-plan-missing',), None, 0)
        try:
            provider_ref = self.writer.send(
                channel_id=decision.channel_id,
                conversation_id=intent.conversation_id,
                recipients=intent.recipients,
                subject=intent.subject,
                body_text=intent.body_text,
                idempotency_key=decision.execution_id,
            )
        except CommunicationsExecutionError:
            return self._replace(decision, 'provider-write-disabled', ('provider-write-disabled',), None, 0)
        except Exception:
            return self._replace(decision, 'provider-error', ('provider-write-error',), None, 1)
        return self._replace(decision, 'provider-submitted', (), provider_ref, 1)

    def _persist(self, decision: CommunicationsExecutionDecision) -> None:
        with self._connect() as conn:
            conn.execute('INSERT INTO communications_execution_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                decision.execution_id, decision.plan_id, decision.intent_id, decision.channel_id,
                decision.approval_id, decision.payload_hash, decision.state,
                json.dumps(decision.blockers), decision.provider_message_ref,
                decision.created_at, decision.external_calls_made,
            ))

    def _replace(self, old: CommunicationsExecutionDecision, state: str, blockers: tuple[str, ...],
                 provider_ref: str | None, calls: int) -> CommunicationsExecutionDecision:
        result = CommunicationsExecutionDecision(
            old.execution_id, old.plan_id, old.intent_id, old.channel_id, old.approval_id,
            old.payload_hash, state, blockers, provider_ref, old.created_at, calls,
        )
        with self._connect() as conn:
            conn.execute('''UPDATE communications_execution_decisions SET state=?,blockers_json=?,
                provider_message_ref=?,external_calls_made=? WHERE execution_id=?''',
                (state, json.dumps(blockers), provider_ref, calls, old.execution_id))
        return result

    def get_decision_by_plan(self, plan_id: str) -> CommunicationsExecutionDecision | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_execution_decisions WHERE plan_id=?', (plan_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['blockers'] = tuple(json.loads(data.pop('blockers_json')))
        return CommunicationsExecutionDecision(**data)
