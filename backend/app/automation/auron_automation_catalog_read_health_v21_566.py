from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.automation.auron_automation_adapter_onboarding_v21_564 import (
    AutomationAdapterOnboardingPolicy,
    AutomationOnboardingDecision,
    AutomationProviderBoundary,
)
from app.automation.auron_automation_workflow_registry_v21_565 import AutomationWorkflowRegistry


class AutomationCatalogReadHealthError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutomationCatalogAction:
    provider_id: str
    capability: str
    display_name: str
    input_schema: dict
    target_verticals: tuple[str, ...] = ()
    supports_simulation: bool = True


@dataclass(frozen=True)
class NormalizedAutomationCatalogAction:
    catalog_action_id: str
    provider_id: str
    capability: str
    display_name: str
    input_schema_json: str
    target_verticals_json: str
    supports_simulation: bool
    observed_at: str
    integrity_hash: str


@dataclass(frozen=True)
class AutomationProviderReadState:
    provider_id: str
    onboarding_accepted: bool
    reachable: bool
    authenticated: bool
    identity_verified: bool
    catalog_available: bool
    permissions_scoped: bool
    catalog_action_count: int
    observed_at: str
    external_calls_made: int
    execution_enabled: bool = False


class AutomationCatalogReadProvider(AutomationProviderBoundary, Protocol):
    def read_catalog(self) -> tuple[AutomationCatalogAction, ...]: ...


class AutomationCatalogReadHealthIntegration:
    """D19 certified read-only catalog/health integration.

    The integration can inspect provider health and catalog metadata, validate D18 action
    registrations against that catalog and persist normalized metadata. It exposes no
    execute/schedule/cancel provider method and cannot perform workflow actions.
    """

    def __init__(self, db_path: str | Path, registry: AutomationWorkflowRegistry,
                 onboarding: AutomationAdapterOnboardingPolicy | None = None) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.onboarding = onboarding or AutomationAdapterOnboardingPolicy()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    @staticmethod
    def _id(provider_id: str, capability: str) -> str:
        return 'cat-' + hashlib.sha256(f'{provider_id}\x1f{capability}'.encode()).hexdigest()[:24]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS automation_provider_read_state (
                    provider_id TEXT PRIMARY KEY, onboarding_accepted INTEGER NOT NULL,
                    reachable INTEGER NOT NULL, authenticated INTEGER NOT NULL,
                    identity_verified INTEGER NOT NULL, catalog_available INTEGER NOT NULL,
                    permissions_scoped INTEGER NOT NULL, catalog_action_count INTEGER NOT NULL,
                    observed_at TEXT NOT NULL, external_calls_made INTEGER NOT NULL,
                    execution_enabled INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS automation_catalog_actions (
                    catalog_action_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL,
                    capability TEXT NOT NULL, display_name TEXT NOT NULL,
                    input_schema_json TEXT NOT NULL, target_verticals_json TEXT NOT NULL,
                    supports_simulation INTEGER NOT NULL, observed_at TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL, UNIQUE(provider_id, capability));
            ''')

    def sync(self, provider: AutomationCatalogReadProvider, *, observed_at: str | None = None) -> AutomationProviderReadState:
        decision = self.onboarding.evaluate(provider)
        self.onboarding.require_onboarded(decision)
        descriptor = provider.descriptor()
        health = provider.read_health()
        if health.provider_id != descriptor.provider_id:
            raise AutomationCatalogReadHealthError('provider identity mismatch')
        catalog = provider.read_catalog()
        at = observed_at or self._now()
        normalized: list[NormalizedAutomationCatalogAction] = []
        seen: set[str] = set()
        for item in catalog:
            if item.provider_id != descriptor.provider_id:
                raise AutomationCatalogReadHealthError('catalog provider identity mismatch')
            capability = item.capability.strip()
            if not capability or capability in seen:
                raise AutomationCatalogReadHealthError('catalog capability missing or duplicated')
            if capability not in descriptor.capabilities:
                raise AutomationCatalogReadHealthError('catalog capability not declared by provider')
            if not item.supports_simulation:
                raise AutomationCatalogReadHealthError('catalog action lacks simulation support')
            seen.add(capability)
            schema_json = json.dumps(item.input_schema, sort_keys=True, separators=(',', ':'))
            targets_json = json.dumps(sorted(set(item.target_verticals)), separators=(',', ':'))
            payload = {'provider_id': descriptor.provider_id, 'capability': capability,
                       'display_name': item.display_name.strip(), 'input_schema_json': schema_json,
                       'target_verticals_json': targets_json, 'supports_simulation': True}
            normalized.append(NormalizedAutomationCatalogAction(
                self._id(descriptor.provider_id, capability), descriptor.provider_id, capability,
                item.display_name.strip(), schema_json, targets_json, True, at, self._hash(payload)))
        with self._connect() as conn:
            for item in normalized:
                conn.execute('''INSERT INTO automation_catalog_actions VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(catalog_action_id) DO UPDATE SET display_name=excluded.display_name,
                    input_schema_json=excluded.input_schema_json,target_verticals_json=excluded.target_verticals_json,
                    supports_simulation=excluded.supports_simulation,observed_at=excluded.observed_at,
                    integrity_hash=excluded.integrity_hash''', (
                    item.catalog_action_id,item.provider_id,item.capability,item.display_name,
                    item.input_schema_json,item.target_verticals_json,int(item.supports_simulation),
                    item.observed_at,item.integrity_hash))
            state = AutomationProviderReadState(
                descriptor.provider_id, decision.accepted, health.reachable, health.authenticated,
                health.identity_verified, health.catalog_available, health.permissions_scoped,
                len(normalized), at, decision.external_calls_made + health.external_calls_made, False)
            conn.execute('''INSERT INTO automation_provider_read_state VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(provider_id) DO UPDATE SET onboarding_accepted=excluded.onboarding_accepted,
                reachable=excluded.reachable,authenticated=excluded.authenticated,
                identity_verified=excluded.identity_verified,catalog_available=excluded.catalog_available,
                permissions_scoped=excluded.permissions_scoped,catalog_action_count=excluded.catalog_action_count,
                observed_at=excluded.observed_at,external_calls_made=excluded.external_calls_made,
                execution_enabled=0''', (
                state.provider_id,int(state.onboarding_accepted),int(state.reachable),int(state.authenticated),
                int(state.identity_verified),int(state.catalog_available),int(state.permissions_scoped),
                state.catalog_action_count,state.observed_at,state.external_calls_made,0))
        return state

    def validate_workflow_catalog(self, workflow_id: str) -> tuple[str, ...]:
        blockers: list[str] = []
        for action in self.registry.list_actions(workflow_id):
            item = self.get_catalog_action(action.provider_id, action.capability)
            if item is None:
                blockers.append(f'action-not-in-provider-catalog:{action.action_id}')
                continue
            targets = tuple(json.loads(item.target_verticals_json))
            if action.target_vertical and targets and action.target_vertical not in targets:
                blockers.append(f'target-vertical-not-supported:{action.action_id}')
            if not item.supports_simulation:
                blockers.append(f'action-not-simulation-capable:{action.action_id}')
        return tuple(blockers)

    def get_catalog_action(self, provider_id: str, capability: str) -> NormalizedAutomationCatalogAction | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_catalog_actions WHERE provider_id=? AND capability=?',
                               (provider_id, capability)).fetchone()
        if not row:
            return None
        data = dict(row); data['supports_simulation'] = bool(data['supports_simulation'])
        return NormalizedAutomationCatalogAction(**data)

    def list_catalog(self, provider_id: str) -> tuple[NormalizedAutomationCatalogAction, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM automation_catalog_actions WHERE provider_id=? ORDER BY capability',
                                (provider_id,)).fetchall()
        out = []
        for row in rows:
            data = dict(row); data['supports_simulation'] = bool(data['supports_simulation']); out.append(NormalizedAutomationCatalogAction(**data))
        return tuple(out)

    def get_provider_state(self, provider_id: str) -> AutomationProviderReadState | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM automation_provider_read_state WHERE provider_id=?',(provider_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        for key in ('onboarding_accepted','reachable','authenticated','identity_verified','catalog_available','permissions_scoped','execution_enabled'):
            data[key] = bool(data[key])
        return AutomationProviderReadState(**data)
