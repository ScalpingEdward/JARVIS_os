from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.automation.auron_automation_catalog_read_health_v21_566 import AutomationCatalogReadHealthIntegration
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry

ApprovalState = Literal['pending', 'approved', 'revoked']
AuthorizationPurpose = Literal['simulation', 'execution']


class AutomationPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationWorkflowApproval:
    approval_id: str
    workflow_id: str
    operator_id: str
    provider_scope: tuple[str, ...]
    vertical_scope: tuple[str, ...]
    state: ApprovalState
    approved_at: str | None
    revoked_at: str | None


@dataclass(frozen=True)
class AutomationAuthorizationDecision:
    workflow_id: str
    purpose: AuthorizationPurpose
    allowed: bool
    blockers: tuple[str, ...]
    approval_id: str | None
    kill_switch_active: bool
    external_calls_made: int = 0


class AutomationWorkflowPolicy:
    """D20 fail-closed approval/scope/kill-switch boundary.

    D20 may authorize a later simulation but cannot authorize live execution yet.
    Every registered provider and target vertical must be explicitly covered by the
    operator approval and must still be present in the D19 certified catalog.
    """

    def __init__(self, db_path: str | Path, registry: AutomationWorkflowRegistry,
                 catalog: AutomationCatalogReadHealthIntegration) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.catalog = catalog
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _id(workflow_id: str, operator_id: str) -> str:
        return 'appr-' + hashlib.sha256(f'{workflow_id}\x1f{operator_id}'.encode()).hexdigest()[:24]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS automation_workflow_approvals (
                    approval_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
                    operator_id TEXT NOT NULL, provider_scope TEXT NOT NULL,
                    vertical_scope TEXT NOT NULL, state TEXT NOT NULL,
                    approved_at TEXT, revoked_at TEXT);
                CREATE TABLE IF NOT EXISTS automation_policy_controls (
                    workflow_id TEXT PRIMARY KEY, kill_switch_active INTEGER NOT NULL);
            ''')

    def approve(self, workflow_id: str, *, operator_id: str,
                provider_scope: tuple[str, ...], vertical_scope: tuple[str, ...] = (),
                at: str | None = None) -> AutomationWorkflowApproval:
        workflow = self.registry.get_workflow(workflow_id)
        if workflow is None:
            raise AutomationPolicyError('workflow not found')
        if workflow.state != 'ready-for-simulation':
            raise AutomationPolicyError('workflow is not ready for simulation')
        operator = operator_id.strip()
        providers = tuple(sorted(set(p.strip() for p in provider_scope if p.strip())))
        verticals = tuple(sorted(set(v.strip() for v in vertical_scope if v.strip())))
        if not operator or not providers:
            raise AutomationPolicyError('operator and provider scope are required')
        required_providers = {a.provider_id for a in self.registry.list_actions(workflow_id)}
        required_verticals = {a.target_vertical for a in self.registry.list_actions(workflow_id) if a.target_vertical}
        if not required_providers.issubset(set(providers)):
            raise AutomationPolicyError('approval provider scope is incomplete')
        if not required_verticals.issubset(set(verticals)):
            raise AutomationPolicyError('approval vertical scope is incomplete')
        blockers = self.catalog.validate_workflow_catalog(workflow_id)
        if blockers:
            raise AutomationPolicyError('workflow catalog validation failed')
        now = at or self._now()
        approval = AutomationWorkflowApproval(self._id(workflow_id, operator), workflow_id, operator,
                                               providers, verticals, 'approved', now, None)
        with self._connect() as conn:
            conn.execute('''INSERT INTO automation_workflow_approvals VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(approval_id) DO UPDATE SET provider_scope=excluded.provider_scope,
                vertical_scope=excluded.vertical_scope,state='approved',approved_at=excluded.approved_at,
                revoked_at=NULL''', (approval.approval_id, workflow_id, operator, ','.join(providers),
                ','.join(verticals), 'approved', now, None))
            conn.execute('INSERT OR IGNORE INTO automation_policy_controls VALUES (?,1)', (workflow_id,))
        return approval

    def revoke(self, workflow_id: str, *, operator_id: str, at: str | None = None) -> AutomationWorkflowApproval:
        approval = self.get_approval(workflow_id, operator_id)
        if approval is None:
            raise AutomationPolicyError('approval not found')
        now = at or self._now()
        with self._connect() as conn:
            conn.execute('UPDATE automation_workflow_approvals SET state=?,revoked_at=? WHERE approval_id=?',
                         ('revoked', now, approval.approval_id))
        return self.get_approval(workflow_id, operator_id)

    def set_kill_switch(self, workflow_id: str, *, active: bool) -> None:
        if self.registry.get_workflow(workflow_id) is None:
            raise AutomationPolicyError('workflow not found')
        with self._connect() as conn:
            conn.execute('''INSERT INTO automation_policy_controls VALUES (?,?)
                ON CONFLICT(workflow_id) DO UPDATE SET kill_switch_active=excluded.kill_switch_active''',
                (workflow_id, int(active)))

    def evaluate_authorization(self, workflow_id: str, *, operator_id: str,
                               purpose: AuthorizationPurpose = 'simulation') -> AutomationAuthorizationDecision:
        blockers: list[str] = []
        workflow = self.registry.get_workflow(workflow_id)
        approval = self.get_approval(workflow_id, operator_id)
        kill = self.kill_switch_active(workflow_id)
        if workflow is None:
            blockers.append('workflow-not-found')
        elif workflow.state != 'ready-for-simulation':
            blockers.append('workflow-not-ready-for-simulation')
        if kill:
            blockers.append('workflow-kill-switch-active')
        if approval is None or approval.state != 'approved':
            blockers.append('operator-approval-missing')
        if purpose == 'execution':
            blockers.append('D20-live-execution-not-authorized')
        if workflow is not None:
            blockers.extend(self.catalog.validate_workflow_catalog(workflow_id))
            if approval and approval.state == 'approved':
                providers = {a.provider_id for a in self.registry.list_actions(workflow_id)}
                verticals = {a.target_vertical for a in self.registry.list_actions(workflow_id) if a.target_vertical}
                if not providers.issubset(set(approval.provider_scope)):
                    blockers.append('provider-scope-mismatch')
                if not verticals.issubset(set(approval.vertical_scope)):
                    blockers.append('vertical-scope-mismatch')
        return AutomationAuthorizationDecision(workflow_id, purpose, not blockers,
                                               tuple(dict.fromkeys(blockers)),
                                               approval.approval_id if approval else None, kill, 0)

    def require_simulation_authorized(self, workflow_id: str, *, operator_id: str) -> AutomationAuthorizationDecision:
        decision = self.evaluate_authorization(workflow_id, operator_id=operator_id, purpose='simulation')
        if not decision.allowed:
            raise AutomationPolicyError('automation simulation is not authorized')
        return decision

    def kill_switch_active(self, workflow_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute('SELECT kill_switch_active FROM automation_policy_controls WHERE workflow_id=?',
                               (workflow_id,)).fetchone()
        return True if row is None else bool(row['kill_switch_active'])

    def get_approval(self, workflow_id: str, operator_id: str) -> AutomationWorkflowApproval | None:
        aid = self._id(workflow_id, operator_id.strip())
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_workflow_approvals WHERE approval_id=?',(aid,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data['provider_scope'] = tuple(filter(None, data['provider_scope'].split(',')))
        data['vertical_scope'] = tuple(filter(None, data['vertical_scope'].split(',')))
        return AutomationWorkflowApproval(**data)
