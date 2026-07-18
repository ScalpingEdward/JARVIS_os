from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AccountabilityAssessment,
    AuditRecord,
    ControlResult,
    ControlSeverity,
    ControlUpdate,
    ExecutiveGovernanceFramework,
    GovernanceFrameworkCreate,
    GovernanceStatus,
    GovernanceStatusResponse,
    GovernanceViolation,
)


class ExecutiveGovernanceService:
    def __init__(self) -> None:
        self._frameworks: dict[UUID, ExecutiveGovernanceFramework] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, framework_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, framework_id=framework_id, details=details or {}, created_at=self._now()))

    def create(self, payload: GovernanceFrameworkCreate) -> ExecutiveGovernanceFramework:
        now = self._now()
        record = ExecutiveGovernanceFramework(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._frameworks.values()):
                raise ValueError("A governance framework with this title already exists in the workspace")
            self._frameworks[record.id] = record
            self._write_audit(payload.workspace_id, "executive-governance-created", payload.owner_id, record.id, {"controls": len(payload.controls), "roles": len(payload.roles)})
        return record

    def list_frameworks(self, workspace_id: str) -> list[ExecutiveGovernanceFramework]:
        with self._lock:
            return [item for item in self._frameworks.values() if item.workspace_id == workspace_id]

    def get(self, framework_id: UUID, workspace_id: str) -> ExecutiveGovernanceFramework | None:
        with self._lock:
            record = self._frameworks.get(framework_id)
            return record if record is not None and record.workspace_id == workspace_id else None

    def update_control(self, framework_id: UUID, workspace_id: str, payload: ControlUpdate) -> ExecutiveGovernanceFramework:
        with self._lock:
            record = self._frameworks.get(framework_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Executive governance framework not found")
            controls = []
            found = False
            for control in record.controls:
                if control.control_key == payload.control_key:
                    found = True
                    controls.append(control.model_copy(update={"passed": payload.passed, "evidence_refs": payload.evidence_refs}))
                else:
                    controls.append(control)
            if not found:
                raise ValueError("Governance control not found")
            updated = record.model_copy(update={"controls": controls, "assessment": None, "status": GovernanceStatus.draft, "version": record.version + 1, "updated_at": self._now()})
            self._frameworks[framework_id] = updated
            self._write_audit(workspace_id, "executive-governance-control-updated", payload.actor_id, framework_id, {"control_key": payload.control_key, "passed": payload.passed})
            return updated

    def assess(self, framework_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveGovernanceFramework:
        with self._lock:
            record = self._frameworks.get(framework_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Executive governance framework not found")

            severity_weight = {ControlSeverity.low: 1, ControlSeverity.medium: 2, ControlSeverity.high: 4, ControlSeverity.critical: 8}
            results: list[ControlResult] = []
            violations: list[GovernanceViolation] = []
            total_weight = 0
            passed_weight = 0
            for control in record.controls:
                weight = severity_weight[control.severity]
                total_weight += weight
                passed = control.passed is True
                if passed:
                    passed_weight += weight
                results.append(ControlResult(control_key=control.control_key, passed=passed, blocking=control.required, severity=control.severity, explanation="Control passed with evidence" if passed else "Required control is not satisfied"))
                if not passed:
                    rule = next((item for item in record.escalation_rules if item.severity == control.severity), None)
                    violations.append(GovernanceViolation(
                        violation_key=f"{control.control_key}:failure",
                        control_key=control.control_key,
                        severity=control.severity,
                        owner_id=control.owner_id,
                        escalation_owner_id=rule.escalation_owner_id if rule else None,
                        response_sla_hours=rule.response_sla_hours if rule else None,
                        explanation=f"{control.title} failed or has not been evidenced",
                    ))

            compliance = 100.0 if total_weight == 0 else passed_weight / total_weight * 100.0
            accountable_areas = {area for role in record.roles for area in role.accountable_for}
            rights_coverage = sum(bool(role.decision_rights) for role in record.roles) / len(record.roles) * 100.0
            role_coverage = min(100.0, len(accountable_areas) * 15.0 + rights_coverage * 0.55)
            now = self._now()
            ready_reviews = 0
            cycles = []
            for cycle in record.review_cycles:
                next_review = cycle.next_review_at or (cycle.last_reviewed_at + timedelta(days=cycle.frequency_days) if cycle.last_reviewed_at else now)
                if next_review >= now:
                    ready_reviews += 1
                cycles.append(cycle.model_copy(update={"next_review_at": next_review}))
            review_score = 100.0 if not cycles else ready_reviews / len(cycles) * 100.0
            accountability = compliance * 0.55 + role_coverage * 0.25 + review_score * 0.20
            blocking = [item for item in results if item.blocking and not item.passed]
            status = GovernanceStatus.compliant if not blocking else GovernanceStatus.non_compliant
            recommendations = []
            if violations:
                recommendations.append("Resolve failed controls according to severity and escalation SLA")
            if role_coverage < 80:
                recommendations.append("Close accountability or decision-right coverage gaps")
            if review_score < 100:
                recommendations.append("Schedule overdue governance reviews")
            if not recommendations:
                recommendations.append("Maintain current governance cadence and evidence quality")
            assessment = AccountabilityAssessment(
                assessed_at=now,
                accountability_score=round(accountability, 2),
                governance_compliance_score=round(compliance, 2),
                role_coverage_score=round(role_coverage, 2),
                review_readiness_score=round(review_score, 2),
                control_results=results,
                violations=violations,
                escalation_queue=[item for item in violations if item.severity in {ControlSeverity.high, ControlSeverity.critical}],
                recommendations=recommendations,
                executive_summary=f"Governance is {status.value} with an accountability score of {accountability:.2f}. Human remediation remains mandatory.",
            )
            updated = record.model_copy(update={"review_cycles": cycles, "assessment": assessment, "status": status, "version": record.version + 1, "updated_at": now})
            self._frameworks[framework_id] = updated
            self._write_audit(workspace_id, "executive-governance-assessed", actor_id, framework_id, {"status": status.value, "violations": len(violations), "score": assessment.accountability_score})
            return updated

    def status(self, workspace_id: str) -> GovernanceStatusResponse:
        records = self.list_frameworks(workspace_id)
        return GovernanceStatusResponse(
            frameworks=len(records),
            assessed_frameworks=sum(item.assessment is not None for item in records),
            compliant_frameworks=sum(item.status == GovernanceStatus.compliant for item in records),
            open_violations=sum(len(item.assessment.violations) for item in records if item.assessment is not None),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_governance_service = ExecutiveGovernanceService()
