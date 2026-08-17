from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.automation.auron_automation_policy_approval_v21_567 import AutomationWorkflowPolicy
from app.automation.auron_automation_simulation_dry_run_v21_568 import AutomationSimulationDryRunService
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry


class AutomationExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationExecutionScope:
    workflow_id: str
    enabled: bool
    operator_enabled: bool
    kill_switch: bool
    updated_at: str


@dataclass(frozen=True)
class AutomationExecutionDecision:
    execution_id: str
    plan_id: str
    workflow_id: str
    operator_id: str
    approval_id: str
    plan_hash: str
    state: str
    blockers: tuple[str, ...]
    provider_results_json: str
    created_at: str
    external_calls_made: int = 0
    cross_vertical_actions_made: int = 0


class AutomationExecutionTransport(Protocol):
    def execute_action(self, *, provider_id: str, capability: str, target_vertical: str | None,
                       config: dict, idempotency_key: str) -> str: ...


class DisabledAutomationExecutionTransport:
    def execute_action(self, **kwargs) -> str:
        raise AutomationExecutionError('automation execution transport is disabled')


class ControlledAutomationExecutionService:
    """D22 controlled execution boundary.

    Successful D21 simulation, current D20 simulation authorization, exact workflow/action
    integrity, explicit workflow execution scope, operator enablement and a clear D22 kill
    switch are all required. The default transport cannot execute provider or cross-vertical
    actions. A future transport must route target_vertical actions through that vertical's
    governed public boundary rather than directly to its provider transport.
    """

    def __init__(self, db_path: str | Path, registry: AutomationWorkflowRegistry,
                 policy: AutomationWorkflowPolicy, simulation: AutomationSimulationDryRunService,
                 transport: AutomationExecutionTransport | None = None) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.policy = policy
        self.simulation = simulation
        self.transport = transport or DisabledAutomationExecutionTransport()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _execution_id(plan_id: str) -> str:
        return 'autoexec-' + hashlib.sha256(plan_id.encode()).hexdigest()[:24]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS automation_execution_scopes (
                    workflow_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,
                    operator_enabled INTEGER NOT NULL, kill_switch INTEGER NOT NULL,
                    updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS automation_execution_decisions (
                    execution_id TEXT PRIMARY KEY, plan_id TEXT UNIQUE NOT NULL,
                    workflow_id TEXT NOT NULL, operator_id TEXT NOT NULL,
                    approval_id TEXT NOT NULL, plan_hash TEXT NOT NULL,
                    state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                    provider_results_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    external_calls_made INTEGER NOT NULL,
                    cross_vertical_actions_made INTEGER NOT NULL);
            ''')

    def configure_scope(self, workflow_id: str, *, enabled: bool = False,
                        operator_enabled: bool = False, kill_switch: bool = True) -> AutomationExecutionScope:
        if self.registry.get_workflow(workflow_id) is None:
            raise AutomationExecutionError('workflow not found')
        at = self._now()
        with self._connect() as conn:
            conn.execute('''INSERT INTO automation_execution_scopes VALUES (?,?,?,?,?)
                ON CONFLICT(workflow_id) DO UPDATE SET enabled=excluded.enabled,
                operator_enabled=excluded.operator_enabled,kill_switch=excluded.kill_switch,
                updated_at=excluded.updated_at''',
                (workflow_id, int(enabled), int(operator_enabled), int(kill_switch), at))
        scope = self.get_scope(workflow_id)
        if scope is None:
            raise AutomationExecutionError('execution scope persistence failed')
        return scope

    def get_scope(self, workflow_id: str) -> AutomationExecutionScope | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_execution_scopes WHERE workflow_id=?', (workflow_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        for key in ('enabled', 'operator_enabled', 'kill_switch'):
            data[key] = bool(data[key])
        return AutomationExecutionScope(**data)

    def evaluate(self, plan_id: str) -> AutomationExecutionDecision:
        existing = self.get_decision_by_plan(plan_id)
        if existing is not None:
            return existing
        plan = self.simulation.get_plan(plan_id)
        if plan is None:
            raise AutomationExecutionError('D21 simulation plan not found')
        blockers: list[str] = []
        if plan.state != 'simulated-success':
            blockers.append('successful-d21-simulation-required')

        authorization = self.policy.evaluate_authorization(
            plan.workflow_id, operator_id=plan.operator_id, purpose='simulation')
        if not authorization.allowed or authorization.approval_id != plan.approval_id:
            blockers.append('current-d20-authorization-required')

        workflow = self.registry.get_workflow(plan.workflow_id)
        if workflow is None or workflow.integrity_hash != plan.workflow_integrity_hash:
            blockers.append('workflow-integrity-mismatch')

        sim_actions = self.simulation.list_actions(plan_id)
        current_actions = self.registry.list_actions(plan.workflow_id)
        current_shape = [(a.action_id,a.ordinal,a.provider_id,a.capability,a.target_vertical,a.config_json) for a in current_actions]
        simulated_shape = [(a.action_id,a.ordinal,a.provider_id,a.capability,a.target_vertical,a.config_json) for a in sim_actions]
        if current_shape != simulated_shape:
            blockers.append('action-plan-integrity-mismatch')

        scope = self.get_scope(plan.workflow_id)
        if scope is None:
            blockers.append('execution-scope-missing')
        else:
            if not scope.enabled:
                blockers.append('execution-scope-disabled')
            if not scope.operator_enabled:
                blockers.append('operator-enablement-required')
            if scope.kill_switch:
                blockers.append('execution-kill-switch-active')

        decision = AutomationExecutionDecision(
            self._execution_id(plan_id), plan_id, plan.workflow_id, plan.operator_id,
            plan.approval_id, plan.plan_hash,
            'ready-for-controlled-execution' if not blockers else 'blocked',
            tuple(dict.fromkeys(blockers)), '{}', self._now(), 0, 0)
        self._persist(decision)
        return decision

    def execute(self, plan_id: str) -> AutomationExecutionDecision:
        decision = self.evaluate(plan_id)
        if decision.state != 'ready-for-controlled-execution':
            return decision
        actions = self.simulation.list_actions(plan_id)
        results: dict[str, str] = {}
        calls = 0
        cross = 0
        for action in actions:
            try:
                result = self.transport.execute_action(
                    provider_id=action.provider_id,
                    capability=action.capability,
                    target_vertical=action.target_vertical,
                    config=json.loads(action.config_json),
                    idempotency_key=f'{decision.execution_id}:{action.ordinal}',
                )
                calls += 1
                if action.target_vertical:
                    cross += 1
                results[action.action_id] = result
            except AutomationExecutionError:
                return self._replace(decision, 'execution-transport-disabled',
                                     ('execution-transport-disabled',), results, calls, cross)
            except Exception:
                calls += 1
                return self._replace(decision, 'execution-transport-error',
                                     ('execution-transport-error',), results, calls, cross)
        return self._replace(decision, 'submitted-for-reconciliation', (), results, calls, cross)

    def _persist(self, decision: AutomationExecutionDecision) -> None:
        with self._connect() as conn:
            conn.execute('INSERT INTO automation_execution_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                decision.execution_id, decision.plan_id, decision.workflow_id, decision.operator_id,
                decision.approval_id, decision.plan_hash, decision.state,
                json.dumps(decision.blockers), decision.provider_results_json, decision.created_at,
                decision.external_calls_made, decision.cross_vertical_actions_made))

    def _replace(self, old: AutomationExecutionDecision, state: str, blockers: tuple[str, ...],
                 results: dict[str, str], calls: int, cross: int) -> AutomationExecutionDecision:
        updated = AutomationExecutionDecision(
            old.execution_id, old.plan_id, old.workflow_id, old.operator_id, old.approval_id,
            old.plan_hash, state, blockers, json.dumps(results, sort_keys=True), old.created_at, calls, cross)
        with self._connect() as conn:
            conn.execute('''UPDATE automation_execution_decisions SET state=?,blockers_json=?,
                provider_results_json=?,external_calls_made=?,cross_vertical_actions_made=? WHERE execution_id=?''',
                (state, json.dumps(blockers), updated.provider_results_json, calls, cross, old.execution_id))
        return updated

    def get_decision_by_plan(self, plan_id: str) -> AutomationExecutionDecision | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_execution_decisions WHERE plan_id=?', (plan_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['blockers'] = tuple(json.loads(data.pop('blockers_json')))
        return AutomationExecutionDecision(**data)
