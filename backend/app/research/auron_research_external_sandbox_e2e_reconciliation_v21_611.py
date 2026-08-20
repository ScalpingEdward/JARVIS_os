from __future__ import annotations
import hashlib,json,sqlite3
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from pathlib import Path
from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter

class ResearchExternalSandboxCertificationError(RuntimeError): pass
@dataclass(frozen=True)
class ResearchExternalSandboxCertification:
    certification_id:str; contract_id:str; provider_ref:str; action_key:str; status:str; blockers:tuple[str,...]; external_calls_made:int; certified_at:str

class ResearchExternalSandboxE2EReconciler:
    """H3 certifies the H1->H2 path without authorizing credential resolution or transport."""
    def __init__(self,db_path:str|Path,registry:ExternalProviderContractRegistry,adapter:ResearchExternalReadonlySandboxAdapter):
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True); self.registry=registry; self.adapter=adapter; self._init_schema()
    def _connect(self): c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def _init_schema(self):
        with self._connect() as c: c.execute('CREATE TABLE IF NOT EXISTS research_external_sandbox_certifications(certification_id TEXT PRIMARY KEY,contract_id TEXT NOT NULL,provider_ref TEXT NOT NULL UNIQUE,action_key TEXT NOT NULL,status TEXT NOT NULL,blockers_json TEXT NOT NULL,external_calls_made INTEGER NOT NULL,evidence_json TEXT NOT NULL,certified_at TEXT NOT NULL)')
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def certify(self,*,contract_id:str,provider_ref:str,action_key:str)->ResearchExternalSandboxCertification:
        blockers=[]; evidence={}
        try: contract=self.registry.require_secretless_sandbox(contract_id)
        except Exception: contract=None; blockers.append('contract-not-secretless-sandbox-safe')
        if contract_id!=self.adapter.contract_id: blockers.append('adapter-contract-mismatch')
        d=self.adapter.descriptor()
        if contract is not None:
            if (contract.vertical,contract.provider_id,contract.adapter_id,contract.environment)!=(d.vertical,d.provider_id,d.adapter_id,d.environment): blockers.append('contract-identity-mismatch')
            if action_key not in contract.allowed_capabilities or action_key not in d.allowed_actions: blockers.append('capability-not-bound')
            if contract.network_transport_enabled or contract.provider_write_enabled or contract.production_transport_enabled: blockers.append('transport-or-write-enabled')
        try:
            result=self.adapter.read_result(provider_ref=provider_ref); preview=self.adapter.preview(provider_ref)
            evidence={'result':asdict(result),'preview':preview}
            if result.external_calls_made!=0 or preview.get('external_calls_made')!=0: blockers.append('external-call-observed')
            if preview.get('credential_resolved') is not False: blockers.append('credential-resolution-observed')
            if preview.get('network_called') is not False: blockers.append('network-call-observed')
            if preview.get('provider_write_performed') is not False: blockers.append('provider-write-observed')
            if preview.get('contract_id')!=contract_id: blockers.append('evidence-contract-mismatch')
            if preview.get('action_key')!=action_key: blockers.append('evidence-action-mismatch')
        except Exception:
            result=None; blockers.append('provider-evidence-missing')
        blockers=tuple(dict.fromkeys(blockers)); status='certified' if not blockers else 'blocked'; external_calls=0 if result is None else result.external_calls_made
        identity={'contract_id':contract_id,'provider_ref':provider_ref,'action_key':action_key}; cid='research-external-cert-'+self._hash(identity)[:24]; now=self._now()
        with self._connect() as c:
            existing=c.execute('SELECT * FROM research_external_sandbox_certifications WHERE provider_ref=?',(provider_ref,)).fetchone()
            if existing: return self._from_row(existing)
            c.execute('INSERT INTO research_external_sandbox_certifications VALUES (?,?,?,?,?,?,?,?,?)',(cid,contract_id,provider_ref,action_key,status,json.dumps(blockers),external_calls,json.dumps(evidence,sort_keys=True),now))
        return ResearchExternalSandboxCertification(cid,contract_id,provider_ref,action_key,status,blockers,external_calls,now)
    def get(self,certification_id:str):
        with self._connect() as c: row=c.execute('SELECT * FROM research_external_sandbox_certifications WHERE certification_id=?',(certification_id,)).fetchone()
        return None if row is None else self._from_row(row)
    @staticmethod
    def _from_row(r): return ResearchExternalSandboxCertification(r['certification_id'],r['contract_id'],r['provider_ref'],r['action_key'],r['status'],tuple(json.loads(r['blockers_json'])),int(r['external_calls_made']),r['certified_at'])
