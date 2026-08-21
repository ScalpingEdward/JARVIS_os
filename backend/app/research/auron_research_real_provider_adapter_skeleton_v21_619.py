from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from app.research.auron_research_real_provider_adapter_contract_v21_617 import (
    ResearchRealProviderAdapterContract,
    ResearchRealProviderAdapterContractRegistry,
)
from app.research.auron_research_real_provider_adapter_contract_certification_v21_618 import (
    ResearchRealProviderAdapterContractCertification,
)


class ResearchRealProviderAdapterSkeletonError(RuntimeError):
    pass


class ResearchCredentialResolver(Protocol):
    def resolve(self, credential_ref: str) -> str: ...


class ResearchReadonlyTransport(Protocol):
    def get(self, *, endpoint: str, headers: dict[str, str], timeout_seconds: int) -> dict: ...


@dataclass(frozen=True)
class ResearchNormalizedProviderResponse:
    capability: str
    response_schema: str
    status_code: int
    normalized_payload: dict
    response_hash: str


@dataclass(frozen=True)
class ResearchProviderRequestPreview:
    capability: str
    method: str
    endpoint: str
    response_schema: str
    credential_reference_required: bool
    runtime_transport_enabled: bool


class ResearchRealProviderAdapterSkeleton:
    """H11 provider-specific adapter skeleton with normalization/audit plumbing only.

    The skeleton is bound to a clean H10-certified H9 contract. It can prepare deterministic
    GET request previews and normalize supplied response fixtures into audit-safe evidence.
    It never resolves credentials and never calls an injected transport because runtime transport
    is deliberately disabled in H11.
    """

    def __init__(self, db_path: str | Path, registry: ResearchRealProviderAdapterContractRegistry,
                 contract_design_id: str, certification: ResearchRealProviderAdapterContractCertification,
                 *, resolver: ResearchCredentialResolver | None = None,
                 transport: ResearchReadonlyTransport | None = None) -> None:
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        self.registry=registry; self.contract_design_id=contract_design_id; self.certification=certification
        self.resolver=resolver; self.transport=transport; self.runtime_transport_enabled=False
        self.contract=self._require_certified_contract(); self._init_schema()

    def _require_certified_contract(self) -> ResearchRealProviderAdapterContract:
        if self.certification.status!='certified' or self.certification.blockers:
            raise ResearchRealProviderAdapterSkeletonError('clean H10 certification required')
        if self.certification.contract_design_id!=self.contract_design_id:
            raise ResearchRealProviderAdapterSkeletonError('H10 certification contract mismatch')
        if any((self.certification.real_network_enabled,self.certification.credential_resolution_enabled,
                self.certification.provider_write_enabled,self.certification.production_transport_enabled)):
            raise ResearchRealProviderAdapterSkeletonError('H10 certification must remain pre-activation safe')
        if not self.certification.requires_separate_adapter_implementation:
            raise ResearchRealProviderAdapterSkeletonError('separate adapter implementation must be required')
        contract=self.registry.get(self.contract_design_id)
        if contract is None: raise ResearchRealProviderAdapterSkeletonError('H9 contract missing')
        if any((contract.network_implementation_included,contract.provider_client_included,
                contract.write_methods_allowed,contract.production_transport_allowed)):
            raise ResearchRealProviderAdapterSkeletonError('H9 design-only safety boundary violated')
        return contract

    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c

    def _init_schema(self):
        with self._connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS research_provider_adapter_previews(
                    preview_id TEXT PRIMARY KEY,capability TEXT NOT NULL,endpoint TEXT NOT NULL,
                    response_schema TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_provider_adapter_normalized_audit(
                    audit_id TEXT PRIMARY KEY,capability TEXT NOT NULL,response_schema TEXT NOT NULL,
                    status_code INTEGER NOT NULL,response_hash TEXT NOT NULL,metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL);
            ''')

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(value) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def _binding(self, capability: str):
        matches=[b for b in self.contract.endpoint_bindings if b.capability==capability]
        if len(matches)!=1: raise ResearchRealProviderAdapterSkeletonError('capability binding missing or ambiguous')
        b=matches[0]
        if b.method.upper()!='GET': raise ResearchRealProviderAdapterSkeletonError('only GET is allowed')
        return b

    def prepare_request_preview(self, *, capability: str, path_params: dict[str,str] | None=None) -> ResearchProviderRequestPreview:
        b=self._binding(capability); endpoint=b.endpoint_template
        for key,value in (path_params or {}).items():
            endpoint=endpoint.replace('{'+key+'}',quote(str(value),safe=''))
        if '{' in endpoint or '}' in endpoint:
            raise ResearchRealProviderAdapterSkeletonError('unresolved endpoint template parameter')
        if not endpoint.startswith('https://'):
            raise ResearchRealProviderAdapterSkeletonError('HTTPS endpoint required')
        now=self._now(); pid='research-provider-preview-'+self._hash({'capability':capability,'endpoint':endpoint})[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_provider_adapter_previews VALUES (?,?,?,?,?)',
                (pid,capability,endpoint,b.response_schema,now))
        return ResearchProviderRequestPreview(capability,'GET',endpoint,b.response_schema,True,False)

    def normalize_fixture(self, *, capability: str, status_code: int, response_payload: dict) -> ResearchNormalizedProviderResponse:
        b=self._binding(capability)
        if not isinstance(status_code,int): raise ResearchRealProviderAdapterSkeletonError('integer status code required')
        if not isinstance(response_payload,dict): raise ResearchRealProviderAdapterSkeletonError('response payload must be a mapping')
        normalized={'schema':b.response_schema,'data':response_payload}
        response_hash=self._hash(normalized); now=self._now()
        audit_metadata={'capability':capability,'response_schema':b.response_schema,'status_code':status_code,
            'response_hash':response_hash,'raw_response_body_persisted':False,'raw_credential_persisted':False,
            'credential_resolved':False,'network_called':False,'provider_write_performed':False}
        aid='research-provider-audit-'+self._hash(audit_metadata)[:24]
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_provider_adapter_normalized_audit VALUES (?,?,?,?,?,?,?)',
                (aid,capability,b.response_schema,status_code,response_hash,json.dumps(audit_metadata,sort_keys=True),now))
        return ResearchNormalizedProviderResponse(capability,b.response_schema,status_code,normalized,response_hash)

    def execute_live_get(self, *args, **kwargs):
        raise ResearchRealProviderAdapterSkeletonError('H11 runtime transport is disabled; activation is a separate later gate')

    def audit_snapshot(self) -> tuple[dict,...]:
        with self._connect() as c:
            rows=c.execute('SELECT * FROM research_provider_adapter_normalized_audit ORDER BY created_at,audit_id').fetchall()
        return tuple(dict(r) for r in rows)
