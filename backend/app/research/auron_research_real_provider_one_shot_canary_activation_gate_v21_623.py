from __future__ import annotations
import hashlib,json,sqlite3
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from pathlib import Path
from app.research.auron_research_real_provider_activation_boundary_certification_v21_622 import ResearchRealProviderActivationBoundaryCertification
from app.research.auron_research_real_provider_activation_boundary_design_v21_621 import ResearchRealProviderActivationDesign

class ResearchRealProviderCanaryActivationGateError(RuntimeError): pass

@dataclass(frozen=True)
class ResearchRealProviderCanaryActivationToken:
    token_id:str; certification_id:str; design_id:str; operator_id:str; provider_id:str; capability:str; endpoint:str; request_budget:int; state:str; issued_at:str; expires_at:str; network_execution_enabled:bool; credential_resolution_enabled:bool; provider_write_enabled:bool; production_transport_enabled:bool

class ResearchRealProviderOneShotCanaryActivationGate:
    """H15 emits a short-lived one-shot activation token only. It cannot execute provider traffic."""
    def __init__(self,db_path:str|Path): self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self): c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self._connect() as c: c.execute('''CREATE TABLE IF NOT EXISTS research_real_provider_canary_tokens(token_id TEXT PRIMARY KEY,certification_id TEXT NOT NULL UNIQUE,design_id TEXT NOT NULL,operator_id TEXT NOT NULL,provider_id TEXT NOT NULL,capability TEXT NOT NULL,endpoint TEXT NOT NULL,request_budget INTEGER NOT NULL,state TEXT NOT NULL,issued_at TEXT NOT NULL,expires_at TEXT NOT NULL,network_execution_enabled INTEGER NOT NULL,credential_resolution_enabled INTEGER NOT NULL,provider_write_enabled INTEGER NOT NULL,production_transport_enabled INTEGER NOT NULL)''')
    @staticmethod
    def _now(): return datetime.now(timezone.utc)
    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def issue(self,certification:ResearchRealProviderActivationBoundaryCertification,design:ResearchRealProviderActivationDesign,*,operator_id:str,operator_reapproved:bool,kill_switch_ready:bool,rollback_ready:bool,ttl_seconds:int=300):
        if certification.status!='certified' or certification.blockers: raise ResearchRealProviderCanaryActivationGateError('clean H14 certification required')
        if not all((certification.identity_pinning_verified,certification.expiry_budget_verified,certification.safety_controls_verified,certification.zero_transport_verified)): raise ResearchRealProviderCanaryActivationGateError('H14 certification invariants incomplete')
        if certification.design_id!=design.design_id: raise ResearchRealProviderCanaryActivationGateError('H14 design mismatch')
        if operator_id!=design.operator_id or not operator_reapproved: raise ResearchRealProviderCanaryActivationGateError('explicit operator re-approval required')
        if not kill_switch_ready or not rollback_ready: raise ResearchRealProviderCanaryActivationGateError('kill-switch and rollback must be ready')
        if not design.one_shot or not design.operator_reapproval_required or not design.kill_switch_required or not design.rollback_required: raise ResearchRealProviderCanaryActivationGateError('H13 mandatory controls missing')
        if any((design.network_enabled,design.credential_resolution_enabled,design.provider_write_enabled,design.production_transport_enabled)): raise ResearchRealProviderCanaryActivationGateError('design must remain zero-transport')
        if not isinstance(ttl_seconds,int) or not 1<=ttl_seconds<=600: raise ResearchRealProviderCanaryActivationGateError('token ttl must be 1..600 seconds')
        now=self._now(); design_expiry=datetime.fromisoformat(design.expires_at.replace('Z','+00:00'))
        if design_expiry<=now: raise ResearchRealProviderCanaryActivationGateError('activation design expired')
        expiry=min(now+timedelta(seconds=ttl_seconds),design_expiry)
        tid='research-real-canary-token-'+self._hash({'certification':certification.certification_id,'design':design.design_id,'operator':operator_id})[:24]
        state='armed-not-executable'; values=(tid,certification.certification_id,design.design_id,operator_id,design.provider_id,design.capability,design.endpoint,design.max_requests,state,now.isoformat(),expiry.isoformat(),0,0,0,0)
        with self._connect() as c:
            c.execute('INSERT OR IGNORE INTO research_real_provider_canary_tokens VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',values)
            row=c.execute('SELECT * FROM research_real_provider_canary_tokens WHERE certification_id=?',(certification.certification_id,)).fetchone()
        return self._from_row(row)
    def revoke(self,token_id:str,*,operator_id:str):
        with self._connect() as c:
            row=c.execute('SELECT * FROM research_real_provider_canary_tokens WHERE token_id=?',(token_id,)).fetchone()
            if row is None: raise ResearchRealProviderCanaryActivationGateError('token not found')
            if row['operator_id']!=operator_id: raise ResearchRealProviderCanaryActivationGateError('operator mismatch')
            c.execute("UPDATE research_real_provider_canary_tokens SET state='revoked' WHERE token_id=?",(token_id,))
            row=c.execute('SELECT * FROM research_real_provider_canary_tokens WHERE token_id=?',(token_id,)).fetchone()
        return self._from_row(row)
    def get(self,token_id:str):
        with self._connect() as c: row=c.execute('SELECT * FROM research_real_provider_canary_tokens WHERE token_id=?',(token_id,)).fetchone()
        return None if row is None else self._from_row(row)
    @staticmethod
    def _from_row(r):
        d=dict(r)
        for k in ('network_execution_enabled','credential_resolution_enabled','provider_write_enabled','production_transport_enabled'): d[k]=bool(d[k])
        return ResearchRealProviderCanaryActivationToken(**d)
