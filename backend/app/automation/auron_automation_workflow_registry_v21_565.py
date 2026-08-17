from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

WorkflowState = Literal['draft', 'disabled', 'ready-for-simulation']
TriggerKind = Literal['manual', 'schedule', 'event', 'condition']
ActionState = Literal['registered', 'disabled']


class AutomationWorkflowRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationWorkflow:
    workflow_id: str
    name: str
    description: str
    state: WorkflowState
    created_by: str
    created_at: str
    updated_at: str
    integrity_hash: str


@dataclass(frozen=True)
class AutomationTrigger:
    trigger_id: str
    workflow_id: str
    kind: TriggerKind
    provider_id: str | None
    config_json: str
    enabled: bool
    created_at: str
    integrity_hash: str


@dataclass(frozen=True)
class AutomationAction:
    action_id: str
    workflow_id: str
    ordinal: int
    provider_id: str
    capability: str
    target_vertical: str | None
    config_json: str
    state: ActionState
    created_at: str
    integrity_hash: str


class AutomationWorkflowRegistry:
    """D18 persistent provider-neutral workflow state with zero execution.

    Workflows, triggers and actions are normalized and integrity-bound. Actions are only
    registered metadata at this stage; no provider execution method exists here.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        raw = '\x1f'.join(parts).encode('utf-8')
        return f'{prefix}-' + hashlib.sha256(raw).hexdigest()[:24]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS automation_workflows (
                    workflow_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    description TEXT NOT NULL, state TEXT NOT NULL,
                    created_by TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, integrity_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS automation_triggers (
                    trigger_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
                    kind TEXT NOT NULL, provider_id TEXT, config_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL, created_at TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    FOREIGN KEY(workflow_id) REFERENCES automation_workflows(workflow_id));
                CREATE TABLE IF NOT EXISTS automation_actions (
                    action_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL, provider_id TEXT NOT NULL,
                    capability TEXT NOT NULL, target_vertical TEXT,
                    config_json TEXT NOT NULL, state TEXT NOT NULL,
                    created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL,
                    FOREIGN KEY(workflow_id) REFERENCES automation_workflows(workflow_id),
                    UNIQUE(workflow_id, ordinal));
            ''')

    def create_workflow(self, *, name: str, description: str = '', created_by: str,
                        workflow_id: str | None = None, now: str | None = None) -> AutomationWorkflow:
        clean_name, actor = name.strip(), created_by.strip()
        if not clean_name or not actor:
            raise AutomationWorkflowRegistryError('workflow name and creator are required')
        created_at = now or self._now()
        wid = workflow_id or self._stable_id('wf', actor, clean_name, created_at)
        payload = {
            'workflow_id': wid, 'name': clean_name, 'description': description.strip(),
            'state': 'draft', 'created_by': actor, 'created_at': created_at,
        }
        workflow = AutomationWorkflow(
            wid, clean_name, description.strip(), 'draft', actor, created_at, created_at,
            self._hash(payload),
        )
        with self._connect() as conn:
            existing = conn.execute('SELECT * FROM automation_workflows WHERE workflow_id=?', (wid,)).fetchone()
            if existing:
                stored = AutomationWorkflow(**dict(existing))
                if stored.integrity_hash != workflow.integrity_hash:
                    raise AutomationWorkflowRegistryError('workflow id collision with different payload')
                return stored
            conn.execute('INSERT INTO automation_workflows VALUES (?,?,?,?,?,?,?,?)', tuple(workflow.__dict__.values()))
        return workflow

    def add_trigger(self, workflow_id: str, *, kind: TriggerKind, config: dict,
                    provider_id: str | None = None, enabled: bool = False,
                    trigger_id: str | None = None, now: str | None = None) -> AutomationTrigger:
        if self.get_workflow(workflow_id) is None:
            raise AutomationWorkflowRegistryError('workflow not found')
        if kind not in {'manual', 'schedule', 'event', 'condition'}:
            raise AutomationWorkflowRegistryError('unsupported trigger kind')
        config_json = json.dumps(config, sort_keys=True, separators=(',', ':'))
        created_at = now or self._now()
        tid = trigger_id or self._stable_id('trg', workflow_id, kind, provider_id or '', config_json)
        payload = {
            'trigger_id': tid, 'workflow_id': workflow_id, 'kind': kind,
            'provider_id': provider_id, 'config_json': config_json,
            'enabled': bool(enabled), 'created_at': created_at,
        }
        trigger = AutomationTrigger(
            tid, workflow_id, kind, provider_id, config_json, bool(enabled), created_at,
            self._hash(payload),
        )
        with self._connect() as conn:
            existing = conn.execute('SELECT * FROM automation_triggers WHERE trigger_id=?', (tid,)).fetchone()
            if existing:
                data = dict(existing); data['enabled'] = bool(data['enabled'])
                stored = AutomationTrigger(**data)
                if stored.integrity_hash != trigger.integrity_hash:
                    raise AutomationWorkflowRegistryError('trigger id collision with different payload')
                return stored
            conn.execute('INSERT INTO automation_triggers VALUES (?,?,?,?,?,?,?,?)', (
                trigger.trigger_id, trigger.workflow_id, trigger.kind, trigger.provider_id,
                trigger.config_json, int(trigger.enabled), trigger.created_at, trigger.integrity_hash,
            ))
        return trigger

    def add_action(self, workflow_id: str, *, ordinal: int, provider_id: str,
                   capability: str, config: dict, target_vertical: str | None = None,
                   state: ActionState = 'registered', action_id: str | None = None,
                   now: str | None = None) -> AutomationAction:
        if self.get_workflow(workflow_id) is None:
            raise AutomationWorkflowRegistryError('workflow not found')
        provider, cap = provider_id.strip(), capability.strip()
        if ordinal < 1 or not provider or not cap:
            raise AutomationWorkflowRegistryError('valid ordinal, provider and capability are required')
        if state not in {'registered', 'disabled'}:
            raise AutomationWorkflowRegistryError('unsupported action state')
        config_json = json.dumps(config, sort_keys=True, separators=(',', ':'))
        created_at = now or self._now()
        aid = action_id or self._stable_id('act', workflow_id, str(ordinal), provider, cap, target_vertical or '')
        payload = {
            'action_id': aid, 'workflow_id': workflow_id, 'ordinal': ordinal,
            'provider_id': provider, 'capability': cap, 'target_vertical': target_vertical,
            'config_json': config_json, 'state': state, 'created_at': created_at,
        }
        action = AutomationAction(
            aid, workflow_id, ordinal, provider, cap, target_vertical, config_json,
            state, created_at, self._hash(payload),
        )
        with self._connect() as conn:
            existing = conn.execute('SELECT * FROM automation_actions WHERE action_id=?', (aid,)).fetchone()
            if existing:
                stored = AutomationAction(**dict(existing))
                if stored.integrity_hash != action.integrity_hash:
                    raise AutomationWorkflowRegistryError('action id collision with different payload')
                return stored
            try:
                conn.execute('INSERT INTO automation_actions VALUES (?,?,?,?,?,?,?,?,?,?)', tuple(action.__dict__.values()))
            except sqlite3.IntegrityError as exc:
                raise AutomationWorkflowRegistryError('workflow action ordinal already exists') from exc
        return action

    def set_workflow_state(self, workflow_id: str, state: WorkflowState) -> AutomationWorkflow:
        if state not in {'draft', 'disabled', 'ready-for-simulation'}:
            raise AutomationWorkflowRegistryError('unsupported workflow state')
        current = self.get_workflow(workflow_id)
        if current is None:
            raise AutomationWorkflowRegistryError('workflow not found')
        if state == 'ready-for-simulation':
            if not self.list_triggers(workflow_id):
                raise AutomationWorkflowRegistryError('workflow requires at least one trigger')
            actions = self.list_actions(workflow_id)
            if not actions or any(action.state != 'registered' for action in actions):
                raise AutomationWorkflowRegistryError('workflow requires registered actions')
        updated_at = self._now()
        payload = {
            'workflow_id': current.workflow_id, 'name': current.name,
            'description': current.description, 'state': state,
            'created_by': current.created_by, 'created_at': current.created_at,
        }
        with self._connect() as conn:
            conn.execute('UPDATE automation_workflows SET state=?,updated_at=?,integrity_hash=? WHERE workflow_id=?',
                         (state, updated_at, self._hash(payload), workflow_id))
        result = self.get_workflow(workflow_id)
        if result is None:
            raise AutomationWorkflowRegistryError('workflow persistence failed')
        return result

    def get_workflow(self, workflow_id: str) -> AutomationWorkflow | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_workflows WHERE workflow_id=?', (workflow_id,)).fetchone()
        return AutomationWorkflow(**dict(row)) if row else None

    def list_workflows(self) -> tuple[AutomationWorkflow, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM automation_workflows ORDER BY created_at,workflow_id').fetchall()
        return tuple(AutomationWorkflow(**dict(row)) for row in rows)

    def list_triggers(self, workflow_id: str) -> tuple[AutomationTrigger, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM automation_triggers WHERE workflow_id=? ORDER BY created_at,trigger_id', (workflow_id,)).fetchall()
        out = []
        for row in rows:
            data = dict(row); data['enabled'] = bool(data['enabled']); out.append(AutomationTrigger(**data))
        return tuple(out)

    def list_actions(self, workflow_id: str) -> tuple[AutomationAction, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM automation_actions WHERE workflow_id=? ORDER BY ordinal,action_id', (workflow_id,)).fetchall()
        return tuple(AutomationAction(**dict(row)) for row in rows)

    def snapshot(self, workflow_id: str) -> dict:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise AutomationWorkflowRegistryError('workflow not found')
        return {
            'workflow': workflow,
            'triggers': self.list_triggers(workflow_id),
            'actions': self.list_actions(workflow_id),
            'execution_enabled': False,
            'external_calls_made': 0,
        }
