from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


class ResearchRealProviderAdapterContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchProviderEndpointBinding:
    capability: str
    method: str
    endpoint_template: str
    response_schema: str


@dataclass(frozen=True)
class ResearchCredentialResolverContract:
    credential_ref_scheme: str
    credential_scope: str
    resolver_output_type: str
    raw_secret_persistence_allowed: bool
    raw_secret_logging_allowed: bool


@dataclass(frozen=True)
class ResearchProviderAuditContract:
    persist_request_metadata: bool
    persist_status_code: bool
    persist_response_hash: bool
    persist_raw_credential: bool
    persist_raw_response_body: bool


@dataclass(frozen=True)
class ResearchRealProviderAdapterContract:
    contract_design_id: str
    provider_name: str
    provider_environment: str
    adapter_id: str
    vertical: str
    endpoint_bindings: tuple[ResearchProviderEndpointBinding, ...]
    credential_resolver: ResearchCredentialResolverContract
    audit: ResearchProviderAuditContract
    network_implementation_included: bool
    provider_client_included: bool
    write_methods_allowed: bool
    production_transport_allowed: bool


class ResearchRealProviderAdapterContractRegistry:
    """H9 design-only registry for a future Research read-only provider adapter.

    The registry defines provider identity, GET endpoint-to-capability mappings, normalized
    response-schema labels, secret-reference resolution constraints and audit semantics.
    It intentionally contains no HTTP client, credential resolver implementation or network call.
    """

    ALLOWED_CAPABILITIES=('search-readonly','inspect-source-metadata')

    def __init__(self, db_path: str | Path) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True); self._init_schema()

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS research_real_provider_adapter_contracts(
                contract_design_id TEXT PRIMARY KEY,provider_name TEXT NOT NULL,provider_environment TEXT NOT NULL,
                adapter_id TEXT NOT NULL,vertical TEXT NOT NULL,design_json TEXT NOT NULL)''')

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @classmethod
    def _validate_binding(cls, binding: ResearchProviderEndpointBinding) -> None:
        if binding.capability not in cls.ALLOWED_CAPABILITIES:
            raise ResearchRealProviderAdapterContractError('capability is not approved for Research read-only provider design')
        if binding.method.upper()!='GET':
            raise ResearchRealProviderAdapterContractError('only GET endpoint bindings are allowed')
        parsed=urlparse(binding.endpoint_template)
        if parsed.scheme!='https' or not parsed.netloc:
            raise ResearchRealProviderAdapterContractError('endpoint template must be absolute HTTPS')
        if not binding.response_schema.strip():
            raise ResearchRealProviderAdapterContractError('response schema label required')

    def register(self, *, provider_name: str, provider_environment: str, adapter_id: str,
                 endpoint_bindings: tuple[ResearchProviderEndpointBinding, ...],
                 credential_resolver: ResearchCredentialResolverContract,
                 audit: ResearchProviderAuditContract) -> ResearchRealProviderAdapterContract:
        if not provider_name.strip() or not adapter_id.strip():
            raise ResearchRealProviderAdapterContractError('provider name and adapter id required')
        if provider_environment.strip().lower() in ('production','prod','live'):
            raise ResearchRealProviderAdapterContractError('production environment is out of scope for H9')
        if not endpoint_bindings:
            raise ResearchRealProviderAdapterContractError('at least one endpoint binding required')
        for binding in endpoint_bindings: self._validate_binding(binding)
        capabilities=[b.capability for b in endpoint_bindings]
        if len(capabilities)!=len(set(capabilities)):
            raise ResearchRealProviderAdapterContractError('duplicate capability binding')
        if credential_resolver.credential_ref_scheme!='secretref://':
            raise ResearchRealProviderAdapterContractError('credential resolver must consume secretref:// references')
        if credential_resolver.credential_scope!='read-only':
            raise ResearchRealProviderAdapterContractError('credential scope must be read-only')
        if credential_resolver.raw_secret_persistence_allowed or credential_resolver.raw_secret_logging_allowed:
            raise ResearchRealProviderAdapterContractError('raw credential persistence/logging forbidden')
        if audit.persist_raw_credential or audit.persist_raw_response_body:
            raise ResearchRealProviderAdapterContractError('raw credentials/responses must not be persisted by audit contract')

        stable={'provider_name':provider_name.strip(),'provider_environment':provider_environment.strip(),
            'adapter_id':adapter_id.strip(),'vertical':'research','endpoint_bindings':[asdict(x) for x in endpoint_bindings],
            'credential_resolver':asdict(credential_resolver),'audit':asdict(audit)}
        design_id='research-provider-contract-'+self._hash(stable)[:24]
        contract=ResearchRealProviderAdapterContract(design_id,provider_name.strip(),provider_environment.strip(),adapter_id.strip(),
            'research',endpoint_bindings,credential_resolver,audit,False,False,False,False)
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_real_provider_adapter_contracts VALUES (?,?,?,?,?,?)',
                (design_id,contract.provider_name,contract.provider_environment,contract.adapter_id,contract.vertical,
                 json.dumps({'contract':asdict(contract)},sort_keys=True)))
        return contract

    def get(self, contract_design_id: str) -> ResearchRealProviderAdapterContract | None:
        with self._connect() as c:
            row=c.execute('SELECT design_json FROM research_real_provider_adapter_contracts WHERE contract_design_id=?',(contract_design_id,)).fetchone()
        if row is None: return None
        raw=json.loads(row['design_json'])['contract']
        bindings=tuple(ResearchProviderEndpointBinding(**x) for x in raw['endpoint_bindings'])
        resolver=ResearchCredentialResolverContract(**raw['credential_resolver']); audit=ResearchProviderAuditContract(**raw['audit'])
        return ResearchRealProviderAdapterContract(raw['contract_design_id'],raw['provider_name'],raw['provider_environment'],raw['adapter_id'],raw['vertical'],bindings,resolver,audit,
            raw['network_implementation_included'],raw['provider_client_included'],raw['write_methods_allowed'],raw['production_transport_allowed'])
