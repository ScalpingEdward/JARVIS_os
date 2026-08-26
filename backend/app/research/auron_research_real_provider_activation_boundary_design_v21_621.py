from __future__ import annotations
import hashlib,json,sqlite3
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse

class ResearchRealProviderActivationDesignError(RuntimeError): pass

@dataclass(frozen=True)
class ResearchRealProviderActivationDesign:
    design_id:str; skeleton_certification_id:str; provider_id:str; environment:str; capability:str; endpoint:str; credential_ref:str; operator_id:str; max_requests:int; expires_at:str; one_shot:bool; kill_switch_required:bool; rollback_required:bool; operator_reapproval_required:bool; network_enabled:bool; credential_resolution_enabled:bool; provider_write_enabled:bool; production_transport_enabled:bool; created_at:str

class ResearchRealProviderActivationBoundaryDesignRegistry:
    """H13 persists activation designs only. It cannot resolve credentials or execute traffic."""
    def __init__(self,db_path:str|Path): self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self): c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self._connect() as c: c.execute('''CREATE TABLE IF NOT EXISTS research_real_provider_activation_designs(design_id TEXT PRIMARY KEY,skeleton_certification_id TEXT NOT NULL,provider_id TEXT NOT NULL,environment TEXT NOT NULL,capability TEXT NOT NULL,endpoint TEXT NOT NULL,credential_ref TEXT NOT NULL,operator_id TEXT NOT NULL,max_requests INTEGER NOT NULL,expires_at TEXT NOT NULL,one_shot INTEGER NOT NULL,kill_switch_required INTEGER NOT NULL,rollback_required INTEGER NOT NULL,operator_reapproval_required INTEGER NOT NULL,network_enabled INTEGER NOT NULL,credential_resolution_enabled INTEGER NOT NULL,provider_write_enabled INTEGER NOT NULL,production_transport_enabled INTEGER NOT NULL,created_at TEXT NOT NULL)''')
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def register(self,*,skeleton_certification_id:str,provider_id:str,environment:str,capability:str,endpoint:str,credential_ref:str,operator_id:str,max_requests:int,expires_at:str,one_shot:bool=True,kill_switch_required:bool=True,rollback_required:bool=True,operator_reapproval_required:bool=True):
        if not skeleton_certification_id: raise ResearchRealProviderActivationDesignError('H12 certification reference required')
        if environment.lower() in {'production','prod','live'}: raise ResearchRealProviderActivationDesignError('production environment forbidden')
        p=urlparse(endpoint)
        if p.scheme!='https' or not p.netloc or p.username or p.password: raise ResearchRealProviderActivationDesignError('safe HTTPS endpoint required')
        if capability not in {'search-readonly','inspect-source-metadata'}: raise ResearchRealProviderActivationDesignError('read-only capability required')
        if not credential_ref.startswith('secretref://'): raise ResearchRealProviderActivationDesignError('opaque secretref credential reference required')
        if not operator_id: raise ResearchRealProviderActivationDesignError('operator identity required')
        if not isinstance(max_requests,int) or not 1<=max_requests<=10: raise ResearchRealProviderActivationDesignError('request budget must be 1..10')
        try: expiry=datetime.fromisoformat(expires_at.replace('Z','+00:00'))
        except ValueError as e: raise ResearchRealProviderActivationDesignError('valid expiry required') from e
        if expiry.tzinfo is None or expiry<=datetime.now(timezone.utc): raise ResearchRealProviderActivationDesignError('future timezone-aware expiry required')
        if not all((one_shot,kill_switch_required,rollback_required,operator_reapproval_required)): raise ResearchRealProviderActivationDesignError('one-shot kill rollback and reapproval are mandatory')
        identity={'cert':skeleton_certification_id,'provider':provider_id,'environment':environment,'capability':capability,'endpoint':endpoint,'credential_ref':credential_ref,'operator':operator_id,'budget':max_requests,'expiry':expires_at}
        did='research-real-activation-design-'+self._hash(identity)[:24]; now=self._now()
        values=(did,skeleton_certification_id,provider_id,environment,capability,endpoint,credential_ref,operator_id,max_requests,expires_at,1,1,1,1,0,0,0,0,now)
        with self._connect() as c: c.execute('INSERT OR IGNORE INTO research_real_provider_activation_designs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',values)
        return ResearchRealProviderActivationDesign(did,skeleton_certification_id,provider_id,environment,capability,endpoint,credential_ref,operator_id,max_requests,expires_at,True,True,True,True,False,False,False,False,now)
    def get(self,design_id:str):
        with self._connect() as c: r=c.execute('SELECT * FROM research_real_provider_activation_designs WHERE design_id=?',(design_id,)).fetchone()
        if r is None:return None
        d=dict(r)
        for k in ('one_shot','kill_switch_required','rollback_required','operator_reapproval_required','network_enabled','credential_resolution_enabled','provider_write_enabled','production_transport_enabled'): d[k]=bool(d[k])
        return ResearchRealProviderActivationDesign(**d)
