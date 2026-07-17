from uuid import UUID
from fastapi import APIRouter,HTTPException,Query,status
from .models import *
from .service import compliance_evidence_service as service
router=APIRouter(prefix='/v1/compliance-evidence',tags=['compliance-evidence'])
@router.get('/status',response_model=ComplianceStatus)
def get_status(): return service.status()
@router.post('/controls',response_model=ControlRecord,status_code=status.HTTP_201_CREATED)
def create_control(p:ControlCreate):
    try:return service.create_control(p)
    except ValueError as e:raise HTTPException(409,str(e))
@router.get('/controls',response_model=list[ControlRecord])
def list_controls(workspace_id:str=Query(min_length=1,max_length=120)):return service.list_controls(workspace_id)
def _control(i,w,p,s):
    x=service.set_control_state(i,w,p,s)
    if x is None:raise HTTPException(404,'Owned control not found')
    return x
@router.post('/controls/{control_id}/activate',response_model=ControlRecord)
def activate(control_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _control(control_id,workspace_id,p,ControlState.ACTIVE)
@router.post('/controls/{control_id}/retire',response_model=ControlRecord)
def retire(control_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _control(control_id,workspace_id,p,ControlState.RETIRED)
@router.post('/evidence',response_model=EvidenceRecord,status_code=status.HTTP_201_CREATED)
def create_evidence(p:EvidenceCreate):
    try:return service.create_evidence(p)
    except ValueError as e:raise HTTPException(409,str(e))
@router.get('/evidence',response_model=list[EvidenceRecord])
def list_evidence(workspace_id:str=Query(min_length=1,max_length=120),control_id:UUID|None=None):return service.list_evidence(workspace_id,control_id)
@router.post('/evidence/{evidence_id}/revoke',response_model=EvidenceRecord)
def revoke(evidence_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):
    x=service.revoke_evidence(evidence_id,workspace_id,p)
    if x is None:raise HTTPException(404,'Owned evidence not found')
    return x
@router.post('/findings',response_model=FindingRecord,status_code=status.HTTP_201_CREATED)
def create_finding(p:FindingCreate):
    try:return service.create_finding(p)
    except ValueError as e:raise HTTPException(409,str(e))
@router.get('/findings',response_model=list[FindingRecord])
def list_findings(workspace_id:str=Query(min_length=1,max_length=120)):return service.list_findings(workspace_id)
def _finding(i,w,p,s):
    x=service.set_finding_state(i,w,p,s)
    if x is None:raise HTTPException(404,'Owned finding not found')
    return x
@router.post('/findings/{finding_id}/accept',response_model=FindingRecord)
def accept(finding_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _finding(finding_id,workspace_id,p,FindingState.ACCEPTED)
@router.post('/findings/{finding_id}/remediation',response_model=FindingRecord)
def remediation(finding_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _finding(finding_id,workspace_id,p,FindingState.REMEDIATION)
@router.post('/findings/{finding_id}/resolve',response_model=FindingRecord)
def resolve(finding_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _finding(finding_id,workspace_id,p,FindingState.RESOLVED)
@router.post('/reports',response_model=ReportRecord,status_code=status.HTTP_201_CREATED)
def create_report(p:ReportCreate):
    try:return service.create_report(p)
    except ValueError as e:raise HTTPException(409,str(e))
@router.get('/reports',response_model=list[ReportRecord])
def list_reports(workspace_id:str=Query(min_length=1,max_length=120)):return service.list_reports(workspace_id)
def _report(i,w,p,s):
    x=service.set_report_state(i,w,p,s)
    if x is None:raise HTTPException(409,'Invalid report transition or ownership')
    return x
@router.post('/reports/{report_id}/approve',response_model=ReportRecord)
def approve_report(report_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _report(report_id,workspace_id,p,ReportState.APPROVED)
@router.post('/reports/{report_id}/finalize',response_model=ReportRecord)
def finalize_report(report_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _report(report_id,workspace_id,p,ReportState.FINAL)
@router.post('/reports/{report_id}/archive',response_model=ReportRecord)
def archive_report(report_id:UUID,p:Mutation,workspace_id:str=Query(min_length=1,max_length=120)):return _report(report_id,workspace_id,p,ReportState.ARCHIVED)
@router.get('/audit')
def audit(workspace_id:str=Query(min_length=1,max_length=120)):return service.list_audit(workspace_id)
