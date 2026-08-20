from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry


class ResearchExternalReadonlySandboxAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchExternalReadonlySandboxDescriptor:
    adapter_id: str = 'research-external-readonly-sandbox-v1'
    vertical: str = 'research'
    provider_id: str = 'research-external-readonly-sandbox'
    environment: str = 'sandbox'
    allowed_actions: tuple[str, ...] = ('search-readonly','inspect-source-metadata')
    read_only: bool = True
    credential_resolution_enabled: bool = False
    network_transport_enabled: bool = False
    provider_write_enabled: bool = False
    production_transport_enabled: bool = False


@dataclass(frozen=True)
class ResearchSandboxResult:
    provider_ref: str
    state: str
    external_calls_made: int
    updated_at: str


class ResearchExternalReadonlySandboxAdapter:
    """H2 contract-bound adapter. It persists sandbox intent/evidence but cannot call a provider."""

    FORBIDDEN_PAYLOAD_KEYS=('api_key','api_secret','access_token','refresh_token','password','secret','private_key','client_secret','authorization','bearer','write','delete','update','mutate','publish')

    def __init__(self, db_path: str | Path, registry: ExternalProviderContractRegistry, contract_id: str) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        self.registry=registry; self.contract_id=contract_id
        contract=registry.require_secretless_sandbox(contract_id); d=self.descriptor()
        if (contract.vertical!=d.vertical or contract.provider_id!=d.provider_id or contract.adapter_id!=d.adapter_id
                or contract.environment!=d.environment):
            raise ResearchExternalReadonlySandboxAdapterError('provider contract identity mismatch')
        if not set(d.allowed_actions).issubset(set(contract.allowed_capabilities)):
            raise ResearchExternalReadonlySandboxAdapterError('provider contract lacks required read-only capabilities')
        if contract.credential_ref is not None and not contract.credential_ref.startswith('secretref://'):
            raise ResearchExternalReadonlySandboxAdapterError('credential reference must remain opaque')
        self._init_schema()

    @staticmethod
    def descriptor(): return ResearchExternalReadonlySandboxDescriptor()
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
    @staticmethod
    def _hash(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def _connect(self): c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def _init_schema(self):
        with self._connect() as c: c.executescript('''CREATE TABLE IF NOT EXISTS research_external_sandbox_actions(provider_ref TEXT PRIMARY KEY,contract_id TEXT NOT NULL,action_key TEXT NOT NULL,payload_hash TEXT NOT NULL,state TEXT NOT NULL,preview_json TEXT NOT NULL,external_calls_made INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS research_external_sandbox_stops(activation_id TEXT PRIMARY KEY,reason TEXT NOT NULL,stopped_at TEXT NOT NULL);''')

    def execute_canary_action(self,*,vertical:str,provider_id:str,scope:str,action_key:str,payload:dict,idempotency_key:str)->str:
        d=self.descriptor()
        if vertical!=d.vertical or provider_id!=d.provider_id: raise ResearchExternalReadonlySandboxAdapterError('vertical/provider mismatch')
        if action_key not in d.allowed_actions: raise ResearchExternalReadonlySandboxAdapterError('action is not read-only sandbox allowed')
        lowered={str(k).lower() for k in payload}
        if any(marker in key for key in lowered for marker in self.FORBIDDEN_PAYLOAD_KEYS): raise ResearchExternalReadonlySandboxAdapterError('secret/write material forbidden')
        identity={'contract_id':self.contract_id,'scope':scope,'action_key':action_key,'payload':payload,'idempotency_key':idempotency_key}
        ref='research-external-sandbox-'+self._hash(identity)[:24]; now=self._now()
        preview={'contract_id':self.contract_id,'action_key':action_key,'scope':scope,'payload_hash':self._hash(payload),'state':'transport-disabled-preview','credential_resolved':False,'network_called':False,'provider_write_performed':False,'external_calls_made':0}
        with self._connect() as c:
            existing=c.execute('SELECT provider_ref FROM research_external_sandbox_actions WHERE provider_ref=?',(ref,)).fetchone()
            if existing: return ref
            c.execute('INSERT INTO research_external_sandbox_actions VALUES (?,?,?,?,?,?,?,?,?)',(ref,self.contract_id,action_key,self._hash(payload),'completed',json.dumps(preview,sort_keys=True),0,now,now))
        return ref

    def read_result(self,*,provider_ref:str)->ResearchSandboxResult:
        with self._connect() as c: row=c.execute('SELECT * FROM research_external_sandbox_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None: raise ResearchExternalReadonlySandboxAdapterError('provider ref not found')
        return ResearchSandboxResult(provider_ref,row['state'],int(row['external_calls_made']),row['updated_at'])

    def preview(self,provider_ref:str)->dict:
        with self._connect() as c: row=c.execute('SELECT preview_json FROM research_external_sandbox_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None: raise ResearchExternalReadonlySandboxAdapterError('provider ref not found')
        return json.loads(row['preview_json'])

    def stop_canary(self,*,activation_id:str,reason:str)->None:
        with self._connect() as c: c.execute('INSERT OR REPLACE INTO research_external_sandbox_stops VALUES (?,?,?)',(activation_id,reason,self._now()))
    def is_stopped(self,activation_id:str)->bool:
        with self._connect() as c: return c.execute('SELECT 1 FROM research_external_sandbox_stops WHERE activation_id=?',(activation_id,)).fetchone() is not None
