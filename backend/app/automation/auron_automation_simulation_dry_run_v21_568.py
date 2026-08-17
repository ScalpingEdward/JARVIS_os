from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.automation.auron_automation_policy_approval_v21_567 import AutomationWorkflowPolicy
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry


class AutomationSimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationSimulationAction:
    simulation_action_id: str
    plan_id: str
    action_id: str
    ordinal: int
    provider_id: str
    capability: str
    target_vertical: str | None
    config_json: str
    state: str = 'simulated-not-executed'


@dataclass(frozen=True)
class AutomationSimulationPlan:
    plan_id: str
    workflow_id: str
    operator_id: str
    approval_id: str
    workflow_integrity_hash: str
    plan_hash: str
    state: str
    created_at: str
    external_calls_made: int = 0
    cross_vertical_actions_made: int = 0


class AutomationSimulationDryRunService:
    """D21 deterministic, inspectable workflow simulation with zero execution.

    A valid D20 authorization is required when a plan is created and again when it is
    simulated. The resulting ordered action plan is persisted and integrity-bound, but
    no provider or cross-vertical execution method exists in this service.
    """

    def __init__(self, db_path: str | Path, registry: AutomationWorkflowRegistry,
                 policy: AutomationWorkflowPolicy) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.policy = policy
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: object) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        raw = '\x1f'.join(parts).encode('utf-8')
        return f'{prefix}-' + hashlib.sha256(raw).hexdigest()[:24]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS automation_simulation_plans (
                    plan_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
                    operator_id TEXT NOT NULL, approval_id TEXT NOT NULL,
                    workflow_integrity_hash TEXT NOT NULL, plan_hash TEXT NOT NULL,
                    state TEXT NOT NULL, created_at TEXT NOT NULL,
                    external_calls_made INTEGER NOT NULL,
                    cross_vertical_actions_made INTEGER NOT NULL,
                    UNIQUE(workflow_id, operator_id, workflow_integrity_hash, approval_id));
                CREATE TABLE IF NOT EXISTS automation_simulation_actions (
                    simulation_action_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL,
                    action_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
                    provider_id TEXT NOT NULL, capability TEXT NOT NULL,
                    target_vertical TEXT, config_json TEXT NOT NULL,
                    state TEXT NOT NULL, UNIQUE(plan_id, ordinal));
            ''')

    def create_plan(self, workflow_id: str, *, operator_id: str,
                    created_at: str | None = None) -> AutomationSimulationPlan:
        authorization = self.policy.require_simulation_authorized(workflow_id, operator_id=operator_id)
        workflow = self.registry.get_workflow(workflow_id)
        if workflow is None:
            raise AutomationSimulationError('workflow not found')
        actions = self.registry.list_actions(workflow_id)
        if not actions:
            raise AutomationSimulationError('workflow has no actions')
        approval_id = authorization.approval_id
        if not approval_id:
            raise AutomationSimulationError('approval id missing')

        canonical_actions = [
            {
                'action_id': a.action_id, 'ordinal': a.ordinal, 'provider_id': a.provider_id,
                'capability': a.capability, 'target_vertical': a.target_vertical,
                'config_json': a.config_json,
            } for a in actions
        ]
        payload = {
            'workflow_id': workflow_id,
            'operator_id': operator_id,
            'approval_id': approval_id,
            'workflow_integrity_hash': workflow.integrity_hash,
            'actions': canonical_actions,
        }
        plan_hash = self._hash(payload)
        plan_id = self._stable_id('sim', workflow_id, operator_id, approval_id, workflow.integrity_hash, plan_hash)
        at = created_at or self._now()
        plan = AutomationSimulationPlan(plan_id, workflow_id, operator_id, approval_id,
                                        workflow.integrity_hash, plan_hash, 'planned', at, 0, 0)
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_simulation_plans WHERE plan_id=?', (plan_id,)).fetchone()
            if row:
                return AutomationSimulationPlan(**dict(row))
            conn.execute('INSERT INTO automation_simulation_plans VALUES (?,?,?,?,?,?,?,?,?,?)', tuple(plan.__dict__.values()))
            for action in actions:
                sim_action = AutomationSimulationAction(
                    self._stable_id('simact', plan_id, action.action_id), plan_id,
                    action.action_id, action.ordinal, action.provider_id, action.capability,
                    action.target_vertical, action.config_json,
                )
                conn.execute('INSERT INTO automation_simulation_actions VALUES (?,?,?,?,?,?,?,?,?)', tuple(sim_action.__dict__.values()))
        return plan

    def simulate(self, plan_id: str) -> AutomationSimulationPlan:
        plan = self.get_plan(plan_id)
        if plan is None:
            raise AutomationSimulationError('simulation plan not found')
        authorization = self.policy.evaluate_authorization(plan.workflow_id, operator_id=plan.operator_id, purpose='simulation')
        if not authorization.allowed or authorization.approval_id != plan.approval_id:
            return self._set_state(plan, 'blocked-policy-drift')
        workflow = self.registry.get_workflow(plan.workflow_id)
        if workflow is None or workflow.integrity_hash != plan.workflow_integrity_hash:
            return self._set_state(plan, 'blocked-workflow-drift')

        actions = self.list_actions(plan_id)
        current = self.registry.list_actions(plan.workflow_id)
        if [(a.action_id,a.ordinal,a.provider_id,a.capability,a.target_vertical,a.config_json) for a in current] != [
            (a.action_id,a.ordinal,a.provider_id,a.capability,a.target_vertical,a.config_json) for a in actions
        ]:
            return self._set_state(plan, 'blocked-action-drift')
        return self._set_state(plan, 'simulated-success')

    def _set_state(self, plan: AutomationSimulationPlan, state: str) -> AutomationSimulationPlan:
        with self._connect() as conn:
            conn.execute('UPDATE automation_simulation_plans SET state=? WHERE plan_id=?', (state, plan.plan_id))
        result = self.get_plan(plan.plan_id)
        if result is None:
            raise AutomationSimulationError('simulation plan persistence failed')
        return result

    def get_plan(self, plan_id: str) -> AutomationSimulationPlan | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_simulation_plans WHERE plan_id=?', (plan_id,)).fetchone()
        return AutomationSimulationPlan(**dict(row)) if row else None

    def list_actions(self, plan_id: str) -> tuple[AutomationSimulationAction, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM automation_simulation_actions WHERE plan_id=? ORDER BY ordinal,simulation_action_id', (plan_id,)).fetchall()
        return tuple(AutomationSimulationAction(**dict(row)) for row in rows)

    def inspect(self, plan_id: str) -> dict:
        plan = self.get_plan(plan_id)
        if plan is None:
            raise AutomationSimulationError('simulation plan not found')
        return {
            'plan': plan,
            'actions': self.list_actions(plan_id),
            'provider_writes_made': 0,
            'cross_vertical_actions_made': 0,
            'execution_enabled': False,
        }
