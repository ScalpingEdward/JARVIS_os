from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.communications.auron_communications_controlled_execution_v21_553 import ControlledCommunicationsExecutionService
from app.communications.auron_communications_policy_approval_v21_551 import CommunicationsPolicyApprovalService
from app.communications.auron_communications_reconciliation_retries_v21_554 import CommunicationsReconciliationRetryService
from app.communications.auron_communications_registry_state_v21_549 import CommunicationsRegistryStateStore
from app.communications.auron_communications_simulation_dry_run_v21_552 import CommunicationsSimulationDryRunService


class CommunicationsCommandCentreError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandJournalEntry:
    command_id: int
    actor: str
    command_text: str
    state: str
    created_at: str


class CommunicationsCommandCentre:
    """D8 operational read model and safe controls for the Communications vertical."""

    def __init__(self, db_path: str | Path, store: CommunicationsRegistryStateStore,
                 approvals: CommunicationsPolicyApprovalService,
                 dryrun: CommunicationsSimulationDryRunService,
                 execution: ControlledCommunicationsExecutionService,
                 reconciliation: CommunicationsReconciliationRetryService) -> None:
        self.db_path = str(db_path)
        self.store = store
        self.approvals = approvals
        self.dryrun = dryrun
        self.execution = execution
        self.reconciliation = reconciliation
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
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_command_journal (
                command_id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL,
                command_text TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL)''')

    @staticmethod
    def _read_rows(db_path: str, sql: str) -> tuple[dict, ...]:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql).fetchall()
            return tuple(dict(row) for row in rows)
        except sqlite3.OperationalError:
            return ()
        finally:
            conn.close()

    def snapshot(self) -> dict:
        accounts = tuple(asdict(x) for x in self.store.list_accounts())
        channels = tuple(asdict(x) for x in self.store.list_channels())
        conversations = tuple(asdict(x) for x in self.store.list_conversations())
        unread_total = sum(x['unread_count'] for x in conversations)

        intents = self._read_rows(
            self.approvals.db_path,
            "SELECT intent_id,channel_id,conversation_id,kind,recipients_json,subject,state,created_by,updated_at FROM communications_outbound_intents ORDER BY updated_at DESC",
        )
        approvals = self._read_rows(
            self.approvals.db_path,
            "SELECT approval_id,intent_id,approved_by,reason,approved_at,revoked FROM communications_intent_approvals ORDER BY approved_at DESC",
        )
        simulations = self._read_rows(
            self.dryrun.db_path,
            "SELECT plan_id,intent_id,state,created_at,external_calls_made FROM communications_dry_run_plans ORDER BY created_at DESC",
        )
        executions = self._read_rows(
            self.execution.db_path,
            "SELECT execution_id,plan_id,intent_id,channel_id,state,provider_message_ref,created_at,external_calls_made FROM communications_execution_decisions ORDER BY created_at DESC",
        )
        reconciliations = self._read_rows(
            self.reconciliation.db_path,
            "SELECT execution_id,provider_message_ref,state,blockers_json,attempt_count,retry_eligible,verified_at,external_calls_made FROM communications_reconciliation ORDER BY verified_at DESC",
        )
        scopes = self._read_rows(
            self.execution.db_path,
            "SELECT channel_id,enabled,operator_enabled,kill_switch,updated_at FROM communications_execution_scopes ORDER BY channel_id",
        )

        alerts: list[dict] = []
        if unread_total:
            alerts.append({'kind': 'unread', 'severity': 'info', 'count': unread_total})
        for item in executions:
            if item['state'] in {'blocked', 'provider-error', 'provider-write-disabled'}:
                alerts.append({'kind': 'execution', 'severity': 'warning', 'execution_id': item['execution_id'], 'state': item['state']})
        for item in reconciliations:
            if item['state'] not in {'verified-sent', 'verified-delivered'}:
                alerts.append({'kind': 'reconciliation', 'severity': 'warning', 'execution_id': item['execution_id'], 'state': item['state']})

        return {
            'workspace': 'communications',
            'command_field_enabled': True,
            'accounts': accounts,
            'channels': channels,
            'conversations': conversations,
            'unread_total': unread_total,
            'intents': intents,
            'approvals': approvals,
            'simulations': simulations,
            'executions': executions,
            'reconciliations': reconciliations,
            'execution_scopes': scopes,
            'alerts': tuple(alerts),
            'outbound_enabled_by_default': False,
        }

    def set_channel_kill_switch(self, channel_id: str, *, active: bool) -> dict:
        current = self.execution.get_scope(channel_id)
        if current is None:
            scope = self.execution.configure_scope(channel_id, enabled=False, operator_enabled=False, kill_switch=active)
        else:
            scope = self.execution.configure_scope(
                channel_id,
                enabled=current.enabled,
                operator_enabled=current.operator_enabled,
                kill_switch=active,
            )
        return asdict(scope)

    def record_command(self, command_text: str, *, actor: str) -> CommandJournalEntry:
        if not command_text.strip() or not actor.strip():
            raise CommunicationsCommandCentreError('command text and actor are required')
        with self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO communications_command_journal(actor,command_text,state,created_at) VALUES (?,?,?,?)',
                (actor.strip(), command_text.strip(), 'recorded-not-executed', self._now()),
            )
            command_id = int(cur.lastrowid)
        return self.get_command(command_id)

    def get_command(self, command_id: int) -> CommandJournalEntry:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_command_journal WHERE command_id=?', (command_id,)).fetchone()
        if row is None:
            raise CommunicationsCommandCentreError('command journal entry not found')
        return CommandJournalEntry(**dict(row))

    def list_commands(self) -> tuple[CommandJournalEntry, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM communications_command_journal ORDER BY command_id DESC').fetchall()
        return tuple(CommandJournalEntry(**dict(row)) for row in rows)
