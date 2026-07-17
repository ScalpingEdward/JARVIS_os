from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ComplianceStatus, ControlCreate, ControlRecord, ControlState, EvidenceCreate,
    EvidenceRecord, FindingCreate, FindingRecord, FindingState, Mutation,
    ReportCreate, ReportRecord, ReportState,
)
from .service import compliance_evidence_service


router = APIRouter(prefix="/v1/compliance-evidence", tags=["compliance-evidence"])


@router.get("/status", response_model=ComplianceStatus)
def get_status() -> ComplianceStatus:
    return compliance_evidence_service.status()


@router.post("/controls", response_model=ControlRecord, status_code=status.HTTP_201_CREATED)
def create_control(payload: ControlCreate) -> ControlRecord:
    try:
        return compliance_evidence_service.create_control(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/controls", response_model=list[ControlRecord])
def list_controls(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ControlRecord]:
    return compliance_evidence_service.list_controls(workspace_id)


def _set_control(control_id: UUID, workspace_id: str, payload: Mutation, state: ControlState) -> ControlRecord:
    item = compliance_evidence_service.set_control_state(control_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned control not found")
    return item


@router.post("/controls/{control_id}/activate", response_model=ControlRecord)
def activate_control(control_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ControlRecord:
    return _set_control(control_id, workspace_id, payload, ControlState.ACTIVE)


@router.post("/controls/{control_id}/retire", response_model=ControlRecord)
def retire_control(control_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ControlRecord:
    return _set_control(control_id, workspace_id, payload, ControlState.RETIRED)


@router.post("/evidence", response_model=EvidenceRecord, status_code=status.HTTP_201_CREATED)
def create_evidence(payload: EvidenceCreate) -> EvidenceRecord:
    try:
        return compliance_evidence_service.create_evidence(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/evidence", response_model=list[EvidenceRecord])
def list_evidence(workspace_id: str = Query(min_length=1, max_length=120), control_id: UUID | None = None) -> list[EvidenceRecord]:
    return compliance_evidence_service.list_evidence(workspace_id, control_id)


@router.post("/evidence/{evidence_id}/revoke", response_model=EvidenceRecord)
def revoke_evidence(evidence_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> EvidenceRecord:
    item = compliance_evidence_service.revoke_evidence(evidence_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned evidence not found")
    return item


@router.post("/findings", response_model=FindingRecord, status_code=status.HTTP_201_CREATED)
def create_finding(payload: FindingCreate) -> FindingRecord:
    try:
        return compliance_evidence_service.create_finding(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/findings", response_model=list[FindingRecord])
def list_findings(workspace_id: str = Query(min_length=1, max_length=120)) -> list[FindingRecord]:
    return compliance_evidence_service.list_findings(workspace_id)


def _set_finding(finding_id: UUID, workspace_id: str, payload: Mutation, state: FindingState) -> FindingRecord:
    item = compliance_evidence_service.set_finding_state(finding_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned finding not found")
    return item


@router.post("/findings/{finding_id}/accept", response_model=FindingRecord)
def accept_finding(finding_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FindingRecord:
    return _set_finding(finding_id, workspace_id, payload, FindingState.ACCEPTED)


@router.post("/findings/{finding_id}/remediation", response_model=FindingRecord)
def start_remediation(finding_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FindingRecord:
    return _set_finding(finding_id, workspace_id, payload, FindingState.REMEDIATION)


@router.post("/findings/{finding_id}/resolve", response_model=FindingRecord)
def resolve_finding(finding_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> FindingRecord:
    return _set_finding(finding_id, workspace_id, payload, FindingState.RESOLVED)


@router.post("/reports", response_model=ReportRecord, status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportCreate) -> ReportRecord:
    try:
        return compliance_evidence_service.create_report(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/reports", response_model=list[ReportRecord])
def list_reports(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ReportRecord]:
    return compliance_evidence_service.list_reports(workspace_id)


def _set_report(report_id: UUID, workspace_id: str, payload: Mutation, state: ReportState) -> ReportRecord:
    item = compliance_evidence_service.set_report_state(report_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=409, detail="Invalid report transition or ownership")
    return item


@router.post("/reports/{report_id}/approve", response_model=ReportRecord)
def approve_report(report_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ReportRecord:
    return _set_report(report_id, workspace_id, payload, ReportState.APPROVED)


@router.post("/reports/{report_id}/finalize", response_model=ReportRecord)
def finalize_report(report_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ReportRecord:
    return _set_report(report_id, workspace_id, payload, ReportState.FINAL)


@router.post("/reports/{report_id}/archive", response_model=ReportRecord)
def archive_report(report_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ReportRecord:
    return _set_report(report_id, workspace_id, payload, ReportState.ARCHIVED)


@router.get("/audit")
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return compliance_evidence_service.list_audit(workspace_id)
