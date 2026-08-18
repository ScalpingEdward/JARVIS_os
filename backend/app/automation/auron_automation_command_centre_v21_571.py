from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.automation.auron_automation_controlled_execution_v21_569 import ControlledAutomationExecutionService
from app.automation.auron_automation_policy_approval_v21_567 import AutomationWorkflowPolicy
from app.automation.auron_automation_reconciliation_retries_cancellation_v21_570 import (
    AutomationReconciliationRetryCancellationService,
)
from app.automation.auron_automation_simulation_dry_run_v21_568 import AutomationSimulationDryRunService
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry


class AutomationCommandCentreError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationCommandJournalEntry:
    command_id: int
    actor: str
    command_text: str
    state: str
    created_at: str


class AutomationCommandCentre:
    """D24 operational read model and governed controls for Automation.

    The Command Centre exposes workflows, provider/catalog state, approvals, deterministic
    simulations, controlled execution, reconciliation/retry/cancellation state and alerts.
    Text commands are persisted as operator intent only and never execute provider or
    cross-vertical actions directly.
    """

    def __init__(self, db_path: str | Path, registry: AutomationWorkflowRegistry,
                 policy: AutomationWorkflowPolicy,
                 simulation: AutomationSimulationDryRunService,
                 execution: ControlledAutomationExecutionService,
                 reconciliation: AutomationReconciliationRetryCancellationService) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.policy = policy
        self.simulation = simulation
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
            conn.execute('''CREATE TABLE IF NOT EXISTS automation_command_journal (
                command_id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL, command_text TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL)''')

    @staticmethod
    def _read_rows(db_path: str, sql: str) -> tuple[dict, ...]:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            return tuple(dict(row) for row in conn.execute(sql).fetchall())
        except sqlite3.OperationalError:
            return ()
        finally:
            conn.close()

    def snapshot(self) -> dict:
        workflows = self._read_rows(
            self.registry.db_path,
            '''SELECT workflow_id,name,description,state,created_by,created_at,updated_at,integrity_hash
               FROM automation_workflows ORDER BY updated_at DESC,workflow_id''',
        )
        triggers = self._read_rows(
            self.registry.db_path,
            '''SELECT trigger_id,workflow_id,kind,provider_id,config_json,enabled,created_at,integrity_hash
               FROM automation_triggers ORDER BY created_at DESC,trigger_id''',
        )
        actions = self._read_rows(
            self.registry.db_path,
            '''SELECT action_id,workflow_id,ordinal,provider_id,capability,target_vertical,
                      config_json,state,created_at,integrity_hash
               FROM automation_actions ORDER BY workflow_id,ordinal,action_id''',
        )
        approvals = self._read_rows(
            self.policy.db_path,
            '''SELECT approval_id,workflow_id,operator_id,provider_scope,vertical_scope,state,
                      approved_at,revoked_at FROM automation_workflow_approvals
               ORDER BY approved_at DESC,approval_id''',
        )
        policy_controls = self._read_rows(
            self.policy.db_path,
            '''SELECT workflow_id,kill_switch_active FROM automation_policy_controls
               ORDER BY workflow_id''',
        )
        provider_state = self._read_rows(
            self.policy.catalog.db_path,
            '''SELECT provider_id,onboarding_accepted,reachable,authenticated,identity_verified,
                      catalog_available,permissions_scoped,catalog_action_count,observed_at,
                      external_calls_made,execution_enabled
               FROM automation_provider_read_state ORDER BY provider_id''',
        )
        catalog_actions = self._read_rows(
            self.policy.catalog.db_path,
            '''SELECT catalog_action_id,provider_id,capability,display_name,input_schema_json,
                      target_verticals_json,supports_simulation,observed_at,integrity_hash
               FROM automation_catalog_actions ORDER BY provider_id,capability''',
        )
        simulations = self._read_rows(
            self.simulation.db_path,
            '''SELECT plan_id,workflow_id,operator_id,approval_id,workflow_integrity_hash,
                      plan_hash,state,created_at,external_calls_made,cross_vertical_actions_made
               FROM automation_simulation_plans ORDER BY created_at DESC''',
        )
        simulation_actions = self._read_rows(
            self.simulation.db_path,
            '''SELECT simulation_action_id,plan_id,action_id,ordinal,provider_id,capability,
                      target_vertical,config_json,state
               FROM automation_simulation_actions ORDER BY plan_id,ordinal''',
        )
        execution_scopes = self._read_rows(
            self.execution.db_path,
            '''SELECT workflow_id,enabled,operator_enabled,kill_switch,updated_at
               FROM automation_execution_scopes ORDER BY workflow_id''',
        )
        executions = self._read_rows(
            self.execution.db_path,
            '''SELECT execution_id,plan_id,workflow_id,operator_id,approval_id,plan_hash,state,
                      blockers_json,provider_results_json,created_at,external_calls_made,
                      cross_vertical_actions_made
               FROM automation_execution_decisions ORDER BY created_at DESC''',
        )
        reconciliations = self._read_rows(
            self.reconciliation.db_path,
            '''SELECT execution_id,state,blockers_json,attempt_count,retry_eligible,
                      cancellation_requested,cancellation_state,verified_actions,failed_actions,
                      reconciled_at,external_calls_made
               FROM automation_reconciliation ORDER BY reconciled_at DESC''',
        )

        alerts: list[dict] = []
        for workflow in workflows:
            if workflow['state'] == 'disabled':
                alerts.append({'kind': 'workflow', 'severity': 'info',
                               'workflow_id': workflow['workflow_id'], 'state': 'disabled'})
        for item in simulations:
            if item['state'].startswith('blocked-'):
                alerts.append({'kind': 'simulation', 'severity': 'warning',
                               'plan_id': item['plan_id'], 'state': item['state']})
        for item in executions:
            if item['state'] in {'blocked', 'execution-transport-disabled', 'execution-transport-error'}:
                alerts.append({'kind': 'execution', 'severity': 'warning',
                               'execution_id': item['execution_id'], 'state': item['state']})
        for item in reconciliations:
            if item['state'] in {'retry-eligible', 'retry-exhausted', 'blocked'}:
                alerts.append({'kind': 'reconciliation', 'severity': 'warning',
                               'execution_id': item['execution_id'], 'state': item['state']})
            if item['cancellation_requested'] and item['cancellation_state'] not in {'cancelled', 'not-requested'}:
                alerts.append({'kind': 'cancellation', 'severity': 'warning',
                               'execution_id': item['execution_id'],
                               'state': item['cancellation_state']})

        return {
            'workspace': 'automation',
            'command_field_enabled': True,
            'workflows': workflows,
            'triggers': triggers,
            'actions': actions,
            'provider_state': provider_state,
            'catalog_actions': catalog_actions,
            'approvals': approvals,
            'policy_controls': policy_controls,
            'simulations': simulations,
            'simulation_actions': simulation_actions,
            'execution_scopes': execution_scopes,
            'executions': executions,
            'reconciliations': reconciliations,
            'alerts': tuple(alerts),
            'automation_execution_enabled_by_default': False,
            'cross_vertical_execution_enabled_by_default': False,
            'recorded_commands_execute_directly': False,
        }

    def set_policy_kill_switch(self, workflow_id: str, *, active: bool) -> dict:
        if self.registry.get_workflow(workflow_id) is None:
            raise AutomationCommandCentreError('workflow not found')
        self.policy.set_kill_switch(workflow_id, active=active)
        return {'workflow_id': workflow_id, 'policy_kill_switch_active': self.policy.kill_switch_active(workflow_id)}

    def set_execution_kill_switch(self, workflow_id: str, *, active: bool) -> dict:
        scope = self.execution.get_scope(workflow_id)
        if scope is None:
            raise AutomationCommandCentreError('execution scope not configured')
        updated = self.execution.configure_scope(
            workflow_id,
            enabled=scope.enabled,
            operator_enabled=scope.operator_enabled,
            kill_switch=active,
        )
        return asdict(updated)

    def retry_status(self, execution_id: str) -> dict:
        try:
            record = self.reconciliation.retry_authorization(execution_id)
        except Exception as exc:
            raise AutomationCommandCentreError('retry is not authorized') from exc
        return asdict(record)

    def request_cancellation(self, plan_id: str) -> dict:
        try:
            record = self.reconciliation.request_cancellation(plan_id)
        except Exception as exc:
            raise AutomationCommandCentreError('cancellation request failed') from exc
        return asdict(record)

    def record_command(self, command_text: str, *, actor: str) -> AutomationCommandJournalEntry:
        command, operator = command_text.strip(), actor.strip()
        if not command or not operator:
            raise AutomationCommandCentreError('command text and actor are required')
        with self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO automation_command_journal(actor,command_text,state,created_at) VALUES (?,?,?,?)',
                (operator, command, 'recorded-not-executed', self._now()),
            )
            command_id = int(cur.lastrowid)
        return self.get_command(command_id)

    def get_command(self, command_id: int) -> AutomationCommandJournalEntry:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_command_journal WHERE command_id=?', (command_id,)).fetchone()
        if row is None:
            raise AutomationCommandCentreError('automation command journal entry not found')
        return AutomationCommandJournalEntry(**dict(row))

    def list_commands(self) -> tuple[AutomationCommandJournalEntry, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM automation_command_journal ORDER BY command_id DESC').fetchall()
        return tuple(AutomationCommandJournalEntry(**dict(row)) for row in rows)
