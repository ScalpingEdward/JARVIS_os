from datetime import datetime,timedelta,timezone
from uuid import UUID
from .models import *

class ComplianceEvidenceService:
    def __init__(self): self.controls={}; self.evidence={}; self.findings={}; self.reports={}; self.audit=[]
    def _audit(self,w,a,t,i,actor,**d): self.audit.append(AuditRecord(workspace_id=w,action=a,entity_type=t,entity_id=i,actor_id=actor,details=d))
    def _refresh(self):
        now=datetime.now(timezone.utc)
        for e in self.evidence.values():
            if e.state==EvidenceState.CURRENT and e.expires_at<=now: e.state=EvidenceState.STALE
    def status(self): self._refresh(); return ComplianceStatus(controls=len(self.controls),evidence_items=len(self.evidence),findings=len(self.findings),reports=len(self.reports))
    def create_control(self,p):
        if any(x.workspace_id==p.workspace_id and x.framework==p.framework and x.control_key==p.control_key and x.state!=ControlState.RETIRED for x in self.controls.values()): raise ValueError('active control already exists')
        x=ControlRecord(**p.model_dump()); self.controls[x.id]=x; self._audit(x.workspace_id,'control.created','control',x.id,x.owner_id); return x
    def list_controls(self,w): return [x for x in self.controls.values() if x.workspace_id==w]
    def set_control_state(self,i,w,p,s):
        x=self.controls.get(i)
        if not x or x.workspace_id!=w or x.owner_id!=p.requester_id:return None
        x.state=s;x.updated_at=datetime.now(timezone.utc);self._audit(w,f'control.{s.value}','control',x.id,p.requester_id,reason=p.reason);return x
    def create_evidence(self,p):
        c=self.controls.get(p.control_id)
        if not c or c.workspace_id!=p.workspace_id or c.state!=ControlState.ACTIVE: raise ValueError('active workspace control not found')
        if any(e.workspace_id==p.workspace_id and e.control_id==p.control_id and e.checksum==p.checksum and e.state!=EvidenceState.REVOKED for e in self.evidence.values()): raise ValueError('duplicate evidence checksum')
        d=p.model_dump(exclude={'valid_days','human_verified','raw_secret','external_upload'});x=EvidenceRecord(**d,expires_at=datetime.now(timezone.utc)+timedelta(days=p.valid_days));self.evidence[x.id]=x;self._audit(x.workspace_id,'evidence.created','evidence',x.id,x.owner_id);return x
    def list_evidence(self,w,c=None): self._refresh();return [x for x in self.evidence.values() if x.workspace_id==w and (c is None or x.control_id==c)]
    def revoke_evidence(self,i,w,p):
        x=self.evidence.get(i)
        if not x or x.workspace_id!=w or x.owner_id!=p.requester_id:return None
        x.state=EvidenceState.REVOKED;self._audit(w,'evidence.revoked','evidence',x.id,p.requester_id,reason=p.reason);return x
    def create_finding(self,p):
        c=self.controls.get(p.control_id)
        if not c or c.workspace_id!=p.workspace_id: raise ValueError('workspace control not found')
        if any(self.evidence.get(i) is None or self.evidence[i].workspace_id!=p.workspace_id for i in p.evidence_ids): raise ValueError('invalid evidence reference')
        x=FindingRecord(**p.model_dump());self.findings[x.id]=x;self._audit(x.workspace_id,'finding.created','finding',x.id,x.owner_id,severity=x.severity.value);return x
    def list_findings(self,w): return [x for x in self.findings.values() if x.workspace_id==w]
    def set_finding_state(self,i,w,p,s):
        x=self.findings.get(i)
        if not x or x.workspace_id!=w or x.owner_id!=p.requester_id:return None
        x.state=s;x.updated_at=datetime.now(timezone.utc)
        if s==FindingState.RESOLVED:x.resolution_note=p.reason
        self._audit(w,f'finding.{s.value}','finding',x.id,p.requester_id,reason=p.reason);return x
    def create_report(self,p):
        cs=[self.controls.get(i) for i in p.control_ids]
        if any(c is None or c.workspace_id!=p.workspace_id for c in cs): raise ValueError('invalid control selection')
        self._refresh();current={e.control_id for e in self.evidence.values() if e.workspace_id==p.workspace_id and e.state==EvidenceState.CURRENT};fs=[f for f in self.findings.values() if f.workspace_id==p.workspace_id and f.control_id in p.control_ids and f.state!=FindingState.RESOLVED];total=len(p.control_ids);covered=sum(i in current for i in p.control_ids)
        x=ReportRecord(workspace_id=p.workspace_id,owner_id=p.owner_id,framework=p.framework,title=p.title,control_ids=p.control_ids,period_start=p.period_start,period_end=p.period_end,controls_total=total,controls_with_current_evidence=covered,open_findings=len(fs),critical_findings=sum(f.severity==FindingSeverity.CRITICAL for f in fs),coverage_percent=round(covered/total*100 if total else 0,2));self.reports[x.id]=x;self._audit(x.workspace_id,'report.generated','report',x.id,x.owner_id,coverage=x.coverage_percent);return x
    def list_reports(self,w): return [x for x in self.reports.values() if x.workspace_id==w]
    def set_report_state(self,i,w,p,s):
        x=self.reports.get(i)
        if not x or x.workspace_id!=w or x.owner_id!=p.requester_id:return None
        if s==ReportState.FINAL and x.state!=ReportState.APPROVED:return None
        x.state=s
        if s==ReportState.APPROVED:x.approved_by=p.requester_id
        if s==ReportState.FINAL:x.finalized_at=datetime.now(timezone.utc)
        self._audit(w,f'report.{s.value}','report',x.id,p.requester_id,reason=p.reason);return x
    def list_audit(self,w): return [x for x in self.audit if x.workspace_id==w]

compliance_evidence_service=ComplianceEvidenceService()
