from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from app.core.auron_execution_ledger_v21_526 import ExecutionAuditLedger
from app.core.auron_integration_readiness_v21_527 import get_integration_readiness
from app.core.auron_policy_gate_v21_527 import CentralPolicyGate, PolicyState

ApprovalState = Literal['pending', 'approved', 'rejected']


@dataclass(frozen=True)
class CommandRecord:
    command_id: str
    text: str
    actor: str
    state: str
    created_at: str


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    request_id: str
    capability: str
    action: str
    actor: str
    state: ApprovalState
    decided_by: str | None
    created_at: str
    decided_at: str | None


class CommandCentreStore:
    """Persistent local Command Centre state. No provider execution is performed here."""

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
                CREATE TABLE IF NOT EXISTS command_centre_commands (
                    command_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS command_centre_approvals (
                    approval_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    state TEXT NOT NULL,
                    decided_by TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )
            ''')

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def submit_command(self, text: str, actor: str) -> CommandRecord:
        text = text.strip()
        actor = actor.strip()
        if not text:
            raise ValueError('Command text is required')
        if not actor:
            raise ValueError('Actor is required')
        record = CommandRecord(str(uuid4()), text, actor, 'received-non-executing', self._now())
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO command_centre_commands(command_id,text,actor,state,created_at) VALUES(?,?,?,?,?)',
                (record.command_id, record.text, record.actor, record.state, record.created_at),
            )
        return record

    def recent_commands(self, limit: int = 50) -> list[CommandRecord]:
        if limit < 1 or limit > 500:
            raise ValueError('limit must be between 1 and 500')
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM command_centre_commands ORDER BY created_at DESC LIMIT ?', (limit,)
            ).fetchall()
        return [CommandRecord(**dict(row)) for row in rows]

    def request_approval(self, request_id: str, capability: str, action: str, actor: str) -> ApprovalRecord:
        values = [request_id.strip(), capability.strip(), action.strip(), actor.strip()]
        if not all(values):
            raise ValueError('request_id, capability, action and actor are required')
        record = ApprovalRecord(str(uuid4()), values[0], values[1], values[2], values[3], 'pending', None, self._now(), None)
        with self._connect() as conn:
            conn.execute(
                '''INSERT INTO command_centre_approvals(
                    approval_id,request_id,capability,action,actor,state,decided_by,created_at,decided_at
                ) VALUES(?,?,?,?,?,?,?,?,?)''',
                (record.approval_id, record.request_id, record.capability, record.action, record.actor, record.state, None, record.created_at, None),
            )
        return record

    def decide_approval(self, approval_id: str, decision: Literal['approved', 'rejected'], decided_by: str) -> ApprovalRecord:
        existing = self.get_approval(approval_id)
        if existing is None:
            raise KeyError('Approval not found')
        if existing.state != 'pending':
            return existing
        decided_by = decided_by.strip()
        if not decided_by:
            raise ValueError('decided_by is required')
        decided_at = self._now()
        with self._connect() as conn:
            conn.execute(
                'UPDATE command_centre_approvals SET state=?, decided_by=?, decided_at=? WHERE approval_id=?',
                (decision, decided_by, decided_at, approval_id),
            )
        result = self.get_approval(approval_id)
        if result is None:
            raise RuntimeError('Approval decision persistence failed')
        return result

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM command_centre_approvals WHERE approval_id=?', (approval_id,)).fetchone()
        return ApprovalRecord(**dict(row)) if row else None

    def pending_approvals(self, limit: int = 100) -> list[ApprovalRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM command_centre_approvals WHERE state='pending' ORDER BY created_at ASC LIMIT ?", (limit,)
            ).fetchall()
        return [ApprovalRecord(**dict(row)) for row in rows]


class CommandCentreService:
    def __init__(self, store: CommandCentreStore, ledger: ExecutionAuditLedger, policy: CentralPolicyGate | None = None) -> None:
        self.store = store
        self.ledger = ledger
        self.policy = policy or CentralPolicyGate()

    def snapshot(self) -> dict:
        readiness = get_integration_readiness()
        recent = [asdict(item) for item in self.ledger.list_recent(limit=50)]
        pending = [asdict(item) for item in self.store.pending_approvals()]
        commands = [asdict(item) for item in self.store.recent_commands(limit=20)]
        return {
            'readiness': readiness,
            'policy': self.policy.snapshot(),
            'pending_approvals': pending,
            'audit_timeline': recent,
            'recent_commands': commands,
            'command_input_available': True,
            'command_execution_enabled': False,
            'external_calls_made': 0,
        }


def build_default_command_centre() -> CommandCentreService:
    state_path = Path(os.getenv('AURON_COMMAND_CENTRE_DB', '/tmp/auron_command_centre.sqlite3'))
    ledger_path = Path(os.getenv('AURON_EXECUTION_LEDGER_DB', '/tmp/auron_execution_ledger.sqlite3'))
    return CommandCentreService(
        store=CommandCentreStore(state_path),
        ledger=ExecutionAuditLedger(ledger_path),
        policy=CentralPolicyGate(PolicyState()),
    )
