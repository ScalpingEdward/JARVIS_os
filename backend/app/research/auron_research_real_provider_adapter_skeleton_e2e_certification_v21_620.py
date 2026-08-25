from __future__ import annotations
import hashlib,json,sqlite3
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from app.research.auron_research_real_provider_adapter_skeleton_v21_619 import ResearchRealProviderAdapterSkeleton,ResearchRealProviderAdapterSkeletonError

@dataclass(frozen=True)
class ResearchProviderSkeletonE2ECertification:
    certification_id:str; contract_design_id:str; status:str; blockers:tuple[str,...]; preview_verified:bool; normalization_verified:bool; audit_integrity_verified:bool; execution_fail_closed_verified:bool; resolver_calls:int; transport_calls:int; real_provider_transport_used:bool; certified_at:str

class ResearchRealProviderAdapterSkeletonE2ECertifier:
    """H12 certifies H11 deterministically; no real provider activation is permitted."""
    def __init__(self,db_path:str|Path,skeleton:ResearchRealProviderAdapterSkeleton):
        self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True); self.skeleton=skeleton; self._init()
    def _connect(self): c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self._connect() as c: c.execute('CREATE TABLE IF NOT EXISTS research_provider_skeleton_e2e_certifications(certification_id TEXT PRIMARY KEY,contract_design_id TEXT NOT NULL,status TEXT NOT NULL,blockers_json TEXT NOT NULL,evidence_json TEXT NOT NULL,certified_at TEXT NOT NULL)')
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    @staticmethod
    def _calls(obj): return int(getattr(obj,'calls',0)) if obj is not None and isinstance(getattr(obj,'calls',0),int) else len(getattr(obj,'calls',[])) if obj is not None else 0
    def certify(self,*,capability:str,path_params:dict[str,str]|None=None,status_code:int=200,response_payload:dict|None=None):
        blockers=[]; response_payload=response_payload or {'items':[{'id':'fixture-1'}]}
        before_r=self._calls(self.skeleton.resolver); before_t=self._calls(self.skeleton.transport)
        preview=self.skeleton.prepare_request_preview(capability=capability,path_params=path_params)
        preview_ok=preview.method=='GET' and preview.endpoint.startswith('https://') and preview.runtime_transport_enabled is False and preview.credential_reference_required is True
        if not preview_ok: blockers.append('request-preview-invariant-failed')
        normalized=self.skeleton.normalize_fixture(capability=capability,status_code=status_code,response_payload=response_payload)
        expected_hash=self._hash({'schema':normalized.response_schema,'data':response_payload})
        normalization_ok=normalized.response_hash==expected_hash and normalized.normalized_payload=={'schema':normalized.response_schema,'data':response_payload}
        if not normalization_ok: blockers.append('normalization-integrity-failed')
        audits=self.skeleton.audit_snapshot(); latest=audits[-1] if audits else None; audit_ok=False
        if latest:
            meta=json.loads(latest['metadata_json']); audit_ok=latest['response_hash']==expected_hash and meta.get('raw_response_body_persisted') is False and meta.get('raw_credential_persisted') is False and meta.get('credential_resolved') is False and meta.get('network_called') is False and meta.get('provider_write_performed') is False
        if not audit_ok: blockers.append('audit-integrity-failed')
        execution_blocked=False
        try: self.skeleton.execute_live_get(capability=capability)
        except ResearchRealProviderAdapterSkeletonError: execution_blocked=True
        if not execution_blocked: blockers.append('live-execution-not-fail-closed')
        after_r=self._calls(self.skeleton.resolver); after_t=self._calls(self.skeleton.transport); resolver_delta=after_r-before_r; transport_delta=after_t-before_t
        if resolver_delta: blockers.append('resolver-called')
        if transport_delta: blockers.append('transport-called')
        blockers=tuple(dict.fromkeys(blockers)); status='certified' if not blockers else 'blocked'; now=self._now(); cid='research-provider-skeleton-e2e-'+self._hash({'contract':self.skeleton.contract_design_id,'capability':capability,'blockers':blockers})[:24]
        evidence={'preview_verified':preview_ok,'normalization_verified':normalization_ok,'audit_integrity_verified':audit_ok,'execution_fail_closed_verified':execution_blocked,'resolver_calls':resolver_delta,'transport_calls':transport_delta,'real_provider_transport_used':False}
        with self._connect() as c: c.execute('INSERT OR IGNORE INTO research_provider_skeleton_e2e_certifications VALUES (?,?,?,?,?,?)',(cid,self.skeleton.contract_design_id,status,json.dumps(blockers),json.dumps(evidence,sort_keys=True),now))
        return ResearchProviderSkeletonE2ECertification(cid,self.skeleton.contract_design_id,status,blockers,preview_ok,normalization_ok,audit_ok,execution_blocked,resolver_delta,transport_delta,False,now)
