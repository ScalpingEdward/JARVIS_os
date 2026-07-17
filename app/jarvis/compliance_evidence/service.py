from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AuditRecord, ComplianceStatus, ControlCreate, ControlRecord, ControlState,
    EvidenceCreate, EvidenceRecord, EvidenceState, FindingCreate, FindingRecord,
    FindingSeverity, FindingState, Mutation, ReportCreate, ReportRecord, ReportState,
)


class ComplianceEvidenceService:
    def __init__(self) -> None:
        self.controls: dict[UUID, ControlRecord] = {}
        self.evidence: dict[UUID, EvidenceRecord] = {}
        self.findings: dict[UUID, FindingRecord] = {}
        self.reports: dict[UUID, ReportRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id, details=details))

    def _refresh(self) -> None:
        now = datetime.now(timezone.utc)
        for item in self.evidence.values():
            if item.state == EvidenceState.CURRENT and item.expires_at <= now:
                item.state = EvidenceState.STALE

    def status(self) -> ComplianceStatus:
        self._refresh()
        return ComplianceStatus(controls=len(self.controls), evidence_items=len(self.evidence), findings=len(self.findings), reports=len(self.reports))

    def create_control(self, payload: ControlCreate) -> ControlRecord:
        if any(c.workspace_id == payload.workspace_id and c.framework == payload.framework and c.control_key == payload.control_key and c.state != ControlState.RETIRED for c in self.controls.values()):
            raise ValueError("active control already exists")
        item = ControlRecord(**payload.model_dump())
        self.controls[item.id] = item
        self._audit(item.workspace_id, "control.created", "control", item.id, item.owner_id)
        return item

    def list_controls(self, workspace_id: str) -> list[ControlRecord]:
        return [x for x in self.controls.values() if x.workspace_id == workspace_id]

    def set_control_state(self, control_id: UUID, workspace_id: str, payload: Mutation, state: ControlState) -> ControlRecord | None:
        item = self.controls.get(control_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"control.{state.value}", "control", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_evidence(self, payload: EvidenceCreate) -> EvidenceRecord:
        control = self.controls.get(payload.control_id)
        if not control or control.workspace_id != payload.workspace_id or control.state != ControlState.ACTIVE:
            raise ValueError("active workspace control not found")
        if any(e.workspace_id == payload.workspace_id and e.control_id == payload.control_id and e.checksum == payload.checksum and e.state != EvidenceState.REVOKED for e in self.evidence.values()):
            raise ValueError("duplicate evidence checksum")
        data = payload.model_dump(exclude={"valid_days", "human_verified", "raw_secret", "external_upload"})
        item = EvidenceRecord(**data, expires_at=datetime.now(timezone.utc) + timedelta(days=payload.valid_days))
        self.evidence[item.id] = item
        self._audit(item.workspace_id, "evidence.created", "evidence", item.id, item.owner_id, control_id=str(item.control_id))
        return item

    def list_evidence(self, workspace_id: str, control_id: UUID | None = None) -> list[EvidenceRecord]:
        self._refresh()
        return [x for x in self.evidence.values() if x.workspace_id == workspace_id and (control_id is None or x.control_id == control_id)]

    def revoke_evidence(self, evidence_id: UUID, workspace_id: str, payload: Mutation) -> EvidenceRecord | None:
        item = self.evidence.get(evidence_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = EvidenceState.REVOKED
        self._audit(workspace_id, "evidence.revoked", "evidence", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_finding(self, payload: FindingCreate) -> FindingRecord:
        control = self.controls.get(payload.control_id)
        if not control or control.workspace_id != payload.workspace_id:
            raise ValueError("workspace control not found")
        if any(self.evidence.get(i) is None or self.evidence[i].workspace_id != payload.workspace_id for i in payload.evidence_ids):
            raise ValueError("invalid evidence reference")
        item = FindingRecord(**payload.model_dump())
        self.findings[item.id] = item
        self._audit(item.workspace_id, "finding.created", "finding", item.id, item.owner_id, severity=item.severity.value)
        return item

    def list_findings(self, workspace_id: str) -> list[FindingRecord]:
        return [x for x in self.findings.values() if x.workspace_id == workspace_id]

    def set_finding_state(self, finding_id: UUID, workspace_id: str, payload: Mutation, state: FindingState) -> FindingRecord | None:
        item = self.findings.get(finding_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        if state == FindingState.RESOLVED:
            item.resolution_note = payload.reason
        self._audit(workspace_id, f"finding.{state.value}", "finding", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_report(self, payload: ReportCreate) -> ReportRecord:
        controls = [self.controls.get(i) for i in payload.control_ids]
        if any(c is None or c.workspace_id != payload.workspace_id for c in controls):
            raise ValueError("invalid control selection")
        self._refresh()
        current_controls = {e.control_id for e in self.evidence.values() if e.workspace_id == payload.workspace_id and e.state == EvidenceState.CURRENT}
        open_findings = [f for f in self.findings.values() if f.workspace_id == payload.workspace_id and f.control_id in payload.control_ids and f.state != FindingState.RESOLVED]
        total = len(payload.control_ids)
        covered = sum(1 for i in payload.control_ids if i in current_controls)
        item = ReportRecord(
            workspace_id=payload.workspace_id, owner_id=payload.owner_id, framework=payload.framework,
            title=payload.title, control_ids=payload.control_ids, period_start=payload.period_start,
            period_end=payload.period_end, controls_total=total, controls_with_current_evidence=covered,
            open_findings=len(open_findings), critical_findings=sum(1 for f in open_findings if f.severity == FindingSeverity.CRITICAL),
            coverage_percent=round((covered / total * 100) if total else 0.0, 2),
        )
        self.reports[item.id] = item
        self._audit(item.workspace_id, "report.generated", "report", item.id, item.owner_id, coverage=item.coverage_percent)
        return item

    def list_reports(self, workspace_id: str) -> list[ReportRecord]:
        return [x for x in self.reports.values() if x.workspace_id == workspace_id]

    def set_report_state(self, report_id: UUID, workspace_id: str, payload: Mutation, state: ReportState) -> ReportRecord | None:
        item = self.reports.get(report_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        if state == ReportState.FINAL and item.state != ReportState.APPROVED:
            return None
        item.state = state
        if state == ReportState.APPROVED:
            item.approved_by = payload.requester_id
        if state == ReportState.FINAL:
            item.finalized_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"report.{state.value}", "report", item.id, payload.requester_id, reason=payload.reason)
        return item

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [x for x in self.audit if x.workspace_id == workspace_id]


compliance_evidence_service = ComplianceEvidenceService()
