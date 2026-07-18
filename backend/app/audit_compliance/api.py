from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    AuditComplianceStatus, AuditEventCreate, AuditEventRecord, ComplianceRuleCreate,
    ComplianceRuleRecord, FindingRecord, FindingState, MetricsRecord, Mutation,
    ReportCreate, ReportRecord, ReportState,
)
from .service import audit_compliance_service as service

router = APIRouter(prefix="/v1/audit-compliance", tags=["audit-compliance"])


@router.get("/status", response_model=AuditComplianceStatus)
def get_status() -> AuditComplianceStatus:
    return service.status()


@router.post("/rules", response_model=ComplianceRuleRecord, status_code=status.HTTP_201_CREATED)
def create_rule(payload: ComplianceRuleCreate) -> ComplianceRuleRecord:
    try:
        return service.create_rule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/rules", response_model=list[ComplianceRuleRecord])
def list_rules(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ComplianceRuleRecord]:
    return service.list_rules(workspace_id)


@router.post("/events", response_model=AuditEventRecord, status_code=status.HTTP_201_CREATED)
def record_event(payload: AuditEventCreate) -> AuditEventRecord:
    return service.record_event(payload)


@router.get("/events", response_model=list[AuditEventRecord])
def list_events(
    workspace_id: str = Query(min_length=1, max_length=120),
    module: str | None = None,
) -> list[AuditEventRecord]:
    return service.list_events(workspace_id, module)


@router.get("/findings", response_model=list[FindingRecord])
def list_findings(
    workspace_id: str = Query(min_length=1, max_length=120),
    state: FindingState | None = None,
) -> list[FindingRecord]:
    return service.list_findings(workspace_id, state)


def _mutate_finding(finding_id: UUID, workspace_id: str, payload: Mutation, target: FindingState) -> FindingRecord:
    try:
        item = service.mutate_finding(finding_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return item


@router.post("/findings/{finding_id}/acknowledge", response_model=FindingRecord)
def acknowledge_finding(finding_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1)) -> FindingRecord:
    return _mutate_finding(finding_id, workspace_id, payload, FindingState.ACKNOWLEDGED)


@router.post("/findings/{finding_id}/resolve", response_model=FindingRecord)
def resolve_finding(finding_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1)) -> FindingRecord:
    return _mutate_finding(finding_id, workspace_id, payload, FindingState.RESOLVED)


@router.post("/findings/{finding_id}/archive", response_model=FindingRecord)
def archive_finding(finding_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1)) -> FindingRecord:
    return _mutate_finding(finding_id, workspace_id, payload, FindingState.ARCHIVED)


@router.post("/reports", response_model=ReportRecord, status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportCreate) -> ReportRecord:
    return service.create_report(payload)


@router.get("/reports", response_model=list[ReportRecord])
def list_reports(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ReportRecord]:
    return service.list_reports(workspace_id)


def _mutate_report(report_id: UUID, workspace_id: str, payload: Mutation, target: ReportState) -> ReportRecord:
    try:
        item = service.mutate_report(report_id, workspace_id, payload, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return item


@router.post("/reports/{report_id}/review", response_model=ReportRecord)
def review_report(report_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1)) -> ReportRecord:
    return _mutate_report(report_id, workspace_id, payload, ReportState.REVIEWED)


@router.post("/reports/{report_id}/approve", response_model=ReportRecord)
def approve_report(report_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1)) -> ReportRecord:
    return _mutate_report(report_id, workspace_id, payload, ReportState.APPROVED)


@router.post("/reports/{report_id}/archive", response_model=ReportRecord)
def archive_report(report_id: UUID, payload: Mutation, workspace_id: str = Query(min_length=1)) -> ReportRecord:
    return _mutate_report(report_id, workspace_id, payload, ReportState.ARCHIVED)


@router.get("/metrics", response_model=MetricsRecord)
def metrics(workspace_id: str = Query(min_length=1, max_length=120)) -> MetricsRecord:
    return service.metrics(workspace_id)


@router.get("/audit")
def audit(workspace_id: str = Query(min_length=1, max_length=120)):
    return service.list_audit(workspace_id)
