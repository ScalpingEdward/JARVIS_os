from __future__ import annotations
import hashlib,json,sqlite3
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from app.research.auron_research_real_provider_activation_boundary_design_v21_621 import ResearchRealProviderActivationDesign

@dataclass(frozen=True)
class ResearchRealProviderActivationBoundaryCertification:
    certification_id:str; design_id:str; status:str; blockers:tuple[str,...]; identity_pinning_verified:bool; expiry_budget_verified:bool; safety_controls_verified:bool; zero_transport_verified:bool; certified_at:str

class ResearchRealProviderActivationBoundaryCertifier:
    """H14 certifies H13 design state only; it has no activation/transport capability."""
    def __init__(self,db_path:str|Path): self.db_path=str(db_path); Path(self.db_path).parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self): c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self._connect() as c: c.execute('CREATE TABLE IF NOT EXISTS research_real_provider_activation_certifications(certification_id TEXT PRIMARY KEY,design_id TEXT NOT NULL UNIQUE,status TEXT NOT NULL,blockers_json TEXT NOT NULL,evidence_json TEXT NOT NULL,certified_at TEXT NOT NULL)')
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
    @staticmethod
    def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def certify(self,design:ResearchRealProviderActivationDesign,*,expected_skeleton_certification_id:str,expected_provider_id:str,expected_environment:str,expected_capability:str,allowed_endpoints:tuple[str,...],expected_credential_ref:str,now:str|None=None):
        blockers=[]; t=datetime.fromisoformat((now or self._now()).replace('Z','+00:00')); expiry=datetime.fromisoformat(design.expires_at.replace('Z','+00:00'))
        identity=(design.skeleton_certification_id==expected_skeleton_certification_id and design.provider_id==expected_provider_id and design.environment==expected_environment and design.capability==expected_capability and design.endpoint in allowed_endpoints and design.credential_ref==expected_credential_ref)
        if not identity: blockers.append('identity-or-pinning-mismatch')
        p=urlparse(design.endpoint)
        if p.scheme!='https' or not p.netloc or p.username or p.password: blockers.append('unsafe-endpoint')
        expiry_budget=expiry>t and 1<=design.max_requests<=10 and design.environment.lower() not in {'production','prod','live'} and design.capability in {'search-readonly','inspect-source-metadata'}
        if not expiry_budget: blockers.append('expiry-budget-or-scope-unsafe')
        controls=design.one_shot and design.kill_switch_required and design.rollback_required and design.operator_reapproval_required and bool(design.operator_id)
        if not controls: blockers.append('mandatory-safety-controls-missing')
        zero_transport=not any((design.network_enabled,design.credential_resolution_enabled,design.provider_write_enabled,design.production_transport_enabled))
        if not zero_transport: blockers.append('transport-or-write-enabled')
        blockers=tuple(dict.fromkeys(blockers)); status='certified' if not blockers else 'blocked'; nowv=self._now(); cid='research-real-activation-cert-'+self._hash({'design':design.design_id,'expected_cert':expected_skeleton_certification_id})[:24]
        evidence={'identity_pinning_verified':identity,'expiry_budget_verified':expiry_budget,'safety_controls_verified':controls,'zero_transport_verified':zero_transport,'real_provider_calls_made':0,'credential_resolution_performed':False,'provider_writes_performed':False}
        with self._connect() as c: c.execute('INSERT OR IGNORE INTO research_real_provider_activation_certifications VALUES (?,?,?,?,?,?)',(cid,design.design_id,status,json.dumps(blockers),json.dumps(evidence,sort_keys=True),nowv))
        return ResearchRealProviderActivationBoundaryCertification(cid,design.design_id,status,blockers,identity,expiry_budget,controls,zero_transport,nowv)
