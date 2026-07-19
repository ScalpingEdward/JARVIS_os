from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    BoardAssessment,
    BoardPortfolioCreate,
    BoardStatusResponse,
    ExecutiveBoardPortfolio,
    GovernanceIssueUpdate,
    Severity,
)


class ExecutiveBoardService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveBoardPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: BoardPortfolioCreate) -> ExecutiveBoardPortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Executive board portfolio already exists")
        item = ExecutiveBoardPortfolio(**payload.model_dump())
        self._portfolios[item.id] = item
        self._record(item.workspace_id, payload.executive_owner_id, "board_portfolio_created", item.id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveBoardPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveBoardPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def update_issue(self, portfolio_id: UUID, workspace_id: str, payload: GovernanceIssueUpdate) -> ExecutiveBoardPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive board portfolio not found")
        issue = next((value for value in item.issues if value.issue_id == payload.issue_id), None)
        if issue is None:
            raise KeyError("Governance issue not found")
        issue.remediation_progress = payload.remediation_progress
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "governance_issue_updated", item.id, {"issue_id": payload.issue_id, "note": payload.note or ""})
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveBoardPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive board portfolio not found")
        members = item.members
        committees = item.committees
        issues = item.issues
        independence = 100 * sum(member.independent for member in members) / len(members)
        skill = sum(member.skill_coverage_score for member in members) / len(members)
        attendance = sum(member.attendance_score for member in members) / len(members)
        challenge = sum(member.challenge_effectiveness_score for member in members) / len(members)
        succession = sum(member.succession_readiness_score for member in members) / len(members)
        agenda = sum(value.agenda_quality_score for value in committees) / len(committees)
        information = sum(value.information_quality_score for value in committees) / len(committees)
        closure = sum(value.action_closure_score for value in committees) / len(committees)
        cycle = sum(value.decision_cycle_days for value in committees) / len(committees)
        cycle_score = max(0.0, 100 - min(cycle, 100))
        decision = (agenda + information + closure + cycle_score + challenge) / 5
        issue_exposure = 0.0
        if issues:
            issue_exposure = sum(
                value.probability * value.impact_score * (1 - value.remediation_progress / 100)
                for value in issues
            ) / len(issues)
        governance_health = max(0.0, min(100.0, (independence + skill + attendance + decision + succession + (100 - issue_exposure)) / 6))
        vulnerable = [
            value.committee_id for value in committees
            if value.agenda_quality_score < 65 or value.information_quality_score < 65 or value.action_closure_score < 65 or value.decision_cycle_days > 45
        ]
        priority = [
            value.issue_id for value in issues
            if value.severity in {Severity.high, Severity.critical}
            and value.probability * value.impact_score >= 35
            and value.remediation_progress < 80
        ]
        actions: list[str] = []
        if vulnerable:
            actions.append("Strengthen agenda design, decision materials and action ownership for vulnerable committees")
        if independence < 60:
            actions.append("Review board composition and independence against governance requirements")
        if skill < 70:
            actions.append("Close critical board skill gaps through succession, education or targeted appointments")
        if succession < 70:
            actions.append("Accelerate chair, committee and executive succession readiness plans")
        if priority:
            actions.append("Escalate priority governance issues with named owners, deadlines and board oversight")
        if not actions:
            actions.append("Maintain current board governance cadence and continue periodic effectiveness reviews")
        item.assessment = BoardAssessment(
            governance_health_score=round(governance_health, 2),
            independence_score=round(independence, 2),
            skill_coverage_score=round(skill, 2),
            decision_effectiveness_score=round(decision, 2),
            action_closure_score=round(closure, 2),
            succession_readiness_score=round(succession, 2),
            issue_exposure_score=round(issue_exposure, 2),
            vulnerable_committees=vulnerable,
            priority_issues=priority,
            executive_actions=actions,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "board_portfolio_assessed", item.id)
        return item

    def status(self, workspace_id: str) -> BoardStatusResponse:
        items = self.list_portfolios(workspace_id)
        issues = [issue for item in items for issue in item.issues if issue.remediation_progress < 100]
        return BoardStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            members=sum(len(item.members) for item in items),
            committees=sum(len(item.committees) for item in items),
            open_issues=len(issues),
            critical_issues=sum(issue.severity == Severity.critical for issue in issues),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, resource_id=resource_id, details=details or {}))


executive_board_service = ExecutiveBoardService()
