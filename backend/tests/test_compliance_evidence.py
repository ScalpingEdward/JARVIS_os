from datetime import datetime,timedelta,timezone
import pytest
from app.compliance_evidence.models import *
from app.compliance_evidence.service import ComplianceEvidenceService

def active_control(s,w='w1'):
    c=s.create_control(ControlCreate(workspace_id=w,owner_id='owner',framework='ISO27001',control_key='A.5.1',title='Policies'))
    return s.set_control_state(c.id,w,Mutation(requester_id='owner'),ControlState.ACTIVE)

def test_lifecycle_and_report():
    s=ComplianceEvidenceService();c=active_control(s)
    e=s.create_evidence(EvidenceCreate(workspace_id='w1',owner_id='owner',control_id=c.id,source_module='policy_approval',evidence_type='snapshot',reference='internal://audit/1',checksum='abcdefgh12345678'))
    f=s.create_finding(FindingCreate(workspace_id='w1',owner_id='owner',control_id=c.id,title='Gap',description='Missing review',severity=FindingSeverity.HIGH,remediation_owner='owner',evidence_ids=[e.id]))
    assert s.set_finding_state(f.id,'w1',Mutation(requester_id='owner',reason='fixed'),FindingState.RESOLVED).state==FindingState.RESOLVED
    r=s.create_report(ReportCreate(workspace_id='w1',owner_id='owner',framework='ISO27001',title='Q3',control_ids=[c.id],period_start=datetime.now(timezone.utc)-timedelta(days=30),period_end=datetime.now(timezone.utc)))
    assert r.coverage_percent==100.0 and r.open_findings==0
    assert s.set_report_state(r.id,'w1',Mutation(requester_id='owner'),ReportState.APPROVED).state==ReportState.APPROVED
    assert s.set_report_state(r.id,'w1',Mutation(requester_id='owner'),ReportState.FINAL).state==ReportState.FINAL

def test_safety_isolation_and_stale_evidence():
    s=ComplianceEvidenceService();c=active_control(s)
    with pytest.raises(ValueError): EvidenceCreate(workspace_id='w1',owner_id='owner',control_id=c.id,source_module='x',evidence_type='x',reference='x',checksum='abcdefgh',raw_secret='secret')
    with pytest.raises(ValueError): FindingCreate(workspace_id='w1',owner_id='owner',control_id=c.id,title='x',description='x',severity=FindingSeverity.LOW,remediation_owner='owner',automatic_remediation=True)
    assert s.set_control_state(c.id,'w2',Mutation(requester_id='owner'),ControlState.RETIRED) is None
    p=EvidenceCreate(workspace_id='w1',owner_id='owner',control_id=c.id,source_module='x',evidence_type='snapshot',reference='internal://1',checksum='abcdefgh')
    e=s.create_evidence(p)
    with pytest.raises(ValueError): s.create_evidence(p)
    e.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert s.list_evidence('w1')[0].state==EvidenceState.STALE
