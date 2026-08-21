from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_network_transport_authorization_v21_613 import ResearchNetworkTransportAuthorizationDecision


class ResearchReadonlyNetworkBoundaryError(RuntimeError):
    pass


class CredentialReferenceResolver(Protocol):
    def resolve(self, credential_ref: str) -> str: ...


class ReadonlyHttpTransport(Protocol):
    def get(self, *, endpoint: str, headers: dict[str, str], timeout_seconds: int) -> dict: ...


@dataclass(frozen=True)
class ResearchNetworkActivation:
    activation_id: str
    decision_id: str
    contract_id: str
    requested_capability: str
    active: bool
    max_requests: int
    used_requests: int
    timeout_seconds: int
    activated_at: str


@dataclass(frozen=True)
class ResearchNetworkCallResult:
    call_id: str
    activation_id: str
    endpoint: str
    state: str
    status_code: int | None
    external_calls_made: int
    provider_write_performed: bool
    created_at: str


class ResearchReadonlyNetworkTransportBoundary:
    """H6 isolated read-only network boundary.

    The boundary is disabled by default. A positive H5 decision may be armed through an explicit
    activation record. Credentials are resolved only at call time through an injected resolver,
    only GET is available, a hard request budget is enforced, and stop/kill-switch state fails closed.
    This module does not provide a concrete provider transport implementation.
    """

    def __init__(self, db_path: str | Path, registry: ExternalProviderContractRegistry,
                 adapter: ResearchExternalReadonlySandboxAdapter,
                 resolver: CredentialReferenceResolver | None = None,
                 transport: ReadonlyHttpTransport | None = None) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        self.registry=registry; self.adapter=adapter; self.resolver=resolver; self.transport=transport
        self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS research_network_activations(
                    activation_id TEXT PRIMARY KEY,decision_id TEXT NOT NULL,contract_id TEXT NOT NULL,
                    requested_capability TEXT NOT NULL,active INTEGER NOT NULL,max_requests INTEGER NOT NULL,
                    used_requests INTEGER NOT NULL,timeout_seconds INTEGER NOT NULL,activated_at TEXT NOT NULL,
                    stopped_at TEXT,stop_reason TEXT);
                CREATE TABLE IF NOT EXISTS research_network_calls(
                    call_id TEXT PRIMARY KEY,activation_id TEXT NOT NULL,endpoint TEXT NOT NULL,
                    state TEXT NOT NULL,status_code INTEGER,external_calls_made INTEGER NOT NULL,
                    provider_write_performed INTEGER NOT NULL,created_at TEXT NOT NULL);
            ''')

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(v: dict) -> str:
        return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def arm(self, decision: ResearchNetworkTransportAuthorizationDecision, *, max_requests: int = 3,
            timeout_seconds: int = 10) -> ResearchNetworkActivation:
        if not decision.authorized or not decision.requires_separate_activation:
            raise ResearchReadonlyNetworkBoundaryError('positive H5 authorization decision required')
        if decision.network_transport_enabled or decision.credential_resolution_enabled or decision.provider_write_enabled or decision.production_transport_enabled:
            raise ResearchReadonlyNetworkBoundaryError('H5 decision must remain pre-activation safe')
        if max_requests < 1 or max_requests > 10:
            raise ResearchReadonlyNetworkBoundaryError('max_requests must be between 1 and 10')
        if timeout_seconds < 1 or timeout_seconds > 30:
            raise ResearchReadonlyNetworkBoundaryError('timeout_seconds must be between 1 and 30')

        contract=self.registry.require_secretless_sandbox(decision.contract_id); d=self.adapter.descriptor()
        if decision.contract_id != self.adapter.contract_id:
            raise ResearchReadonlyNetworkBoundaryError('adapter-contract mismatch')
        if (contract.vertical,contract.provider_id,contract.adapter_id,contract.environment)!=(d.vertical,d.provider_id,d.adapter_id,d.environment):
            raise ResearchReadonlyNetworkBoundaryError('contract identity mismatch')
        if decision.requested_capability not in contract.allowed_capabilities or decision.requested_capability not in d.allowed_actions:
            raise ResearchReadonlyNetworkBoundaryError('capability not bound')
        if contract.credential_ref is None:
            raise ResearchReadonlyNetworkBoundaryError('credential reference missing')
        if contract.provider_write_enabled or contract.production_transport_enabled or contract.network_transport_enabled:
            raise ResearchReadonlyNetworkBoundaryError('H1 contract must remain transport-disabled')

        aid='research-network-activation-'+self._hash({'decision':decision.decision_id,'contract':decision.contract_id,'capability':decision.requested_capability})[:24]
        now=self._now()
        with self._connect() as c:
            row=c.execute('SELECT * FROM research_network_activations WHERE activation_id=?',(aid,)).fetchone()
            if row is None:
                c.execute('INSERT INTO research_network_activations VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (aid,decision.decision_id,decision.contract_id,decision.requested_capability,1,max_requests,0,timeout_seconds,now,None,None))
            else:
                return self._activation_from_row(row)
        return ResearchNetworkActivation(aid,decision.decision_id,decision.contract_id,decision.requested_capability,True,max_requests,0,timeout_seconds,now)

    def stop(self, activation_id: str, *, reason: str='operator-stop') -> None:
        with self._connect() as c:
            cur=c.execute('UPDATE research_network_activations SET active=0,stopped_at=?,stop_reason=? WHERE activation_id=?',
                (self._now(),reason.strip() or 'operator-stop',activation_id))
            if cur.rowcount != 1:
                raise ResearchReadonlyNetworkBoundaryError('activation not found')

    def activation(self, activation_id: str) -> ResearchNetworkActivation | None:
        with self._connect() as c:
            row=c.execute('SELECT * FROM research_network_activations WHERE activation_id=?',(activation_id,)).fetchone()
        return None if row is None else self._activation_from_row(row)

    @staticmethod
    def _activation_from_row(row: sqlite3.Row) -> ResearchNetworkActivation:
        return ResearchNetworkActivation(row['activation_id'],row['decision_id'],row['contract_id'],row['requested_capability'],
            bool(row['active']),int(row['max_requests']),int(row['used_requests']),int(row['timeout_seconds']),row['activated_at'])

    def execute_get(self, *, activation_id: str, endpoint: str, kill_switch_active: bool = True) -> ResearchNetworkCallResult:
        activation=self.activation(activation_id)
        if activation is None or not activation.active:
            raise ResearchReadonlyNetworkBoundaryError('activation is not active')
        if not kill_switch_active:
            self.stop(activation_id,reason='kill-switch-open')
            raise ResearchReadonlyNetworkBoundaryError('kill switch is not active')
        if activation.used_requests >= activation.max_requests:
            self.stop(activation_id,reason='request-budget-exhausted')
            raise ResearchReadonlyNetworkBoundaryError('request budget exhausted')
        endpoint=endpoint.strip()
        if not endpoint.startswith('https://'):
            raise ResearchReadonlyNetworkBoundaryError('HTTPS endpoint required')
        if self.resolver is None or self.transport is None:
            raise ResearchReadonlyNetworkBoundaryError('credential resolver and read-only transport must be explicitly injected')

        contract=self.registry.require_secretless_sandbox(activation.contract_id)
        secret=self.resolver.resolve(contract.credential_ref or '')
        if not secret:
            raise ResearchReadonlyNetworkBoundaryError('credential resolution returned empty material')
        headers={'Authorization':f'Bearer {secret}','Accept':'application/json'}
        response=self.transport.get(endpoint=endpoint,headers=headers,timeout_seconds=activation.timeout_seconds)
        status=response.get('status_code')
        if not isinstance(status,int):
            raise ResearchReadonlyNetworkBoundaryError('transport response missing status_code')

        now=self._now(); cid='research-network-call-'+self._hash({'activation':activation_id,'endpoint':endpoint,'used':activation.used_requests})[:24]
        with self._connect() as c:
            c.execute('UPDATE research_network_activations SET used_requests=used_requests+1 WHERE activation_id=?',(activation_id,))
            c.execute('INSERT INTO research_network_calls VALUES (?,?,?,?,?,?,?,?)',
                (cid,activation_id,endpoint,'completed',status,1,0,now))
        return ResearchNetworkCallResult(cid,activation_id,endpoint,'completed',status,1,False,now)
