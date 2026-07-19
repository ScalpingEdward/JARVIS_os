from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    CultureAssessment,
    CultureIssueUpdate,
    CulturePortfolioCreate,
    CultureStatusResponse,
    ExecutiveCulturePortfolio,
)


class ExecutiveCultureService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveCulturePortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: CulturePortfolioCreate) -> ExecutiveCulturePortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._items.values()):
            raise ValueError("Executive culture portfolio already exists")
        item = ExecutiveCulturePortfolio(**payload.model_dump())
        self._items[item.id] = item
        self._record(payload.workspace_id, payload.executive_owner_id, "culture_portfolio_created", item.id)
        return item

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveCulturePortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveCulturePortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> CultureStatusResponse:
        items = self.list_portfolios(workspace_id)
        return CultureStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            segments=sum(len(item.segments) for item in items),
            active_initiatives=sum(sum(i.state.value != "complete" for i in item.initiatives) for item in items),
            critical_issues=sum(sum(issue.risk.value == "critical" for issue in item.issues) for item in items),
        )

    def update_issue(self, portfolio_id: UUID, workspace_id: str, payload: CultureIssueUpdate) -> ExecutiveCulturePortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive culture portfolio not found")
        issue = next((issue for issue in item.issues if issue.issue_id == payload.issue_id), None)
        if issue is None:
            raise KeyError("Culture issue not found")
        issue.remediation_progress = payload.remediation_progress
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "culture_issue_updated", portfolio_id, {"issue_id": payload.issue_id})
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveCulturePortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive culture portfolio not found")
        segments = item.segments
        average = lambda values: round(sum(values) / len(values), 2) if values else 0.0
        culture_health = average([(s.psychological_safety + s.collaboration_score + s.accountability_score + s.trust_score) / 4 for s in segments])
        leadership = average([s.leadership_alignment for s in segments])
        fatigue = average([s.change_fatigue for s in segments])
        initiative_readiness = average([(i.sponsor_commitment + i.communication_reach + i.manager_enablement + i.adoption_progress + (100 - i.resistance_level)) / 5 for i in item.initiatives]) if item.initiatives else culture_health
        readiness = round((culture_health * 0.35) + (leadership * 0.25) + (initiative_readiness * 0.4), 2)
        adoption_risk = round(100 - initiative_readiness, 2)
        vulnerable = [s.segment_id for s in segments if s.trust_score < 55 or s.psychological_safety < 55 or s.change_fatigue > 70]
        at_risk = [i.initiative_id for i in item.initiatives if i.resistance_level > 60 or i.communication_reach < 55 or i.manager_enablement < 55]
        priority = [issue.issue_id for issue in item.issues if issue.risk.value in {"high", "critical"} and issue.probability >= 0.5 and issue.remediation_progress < 70]
        actions: list[str] = []
        if vulnerable:
            actions.append("Launch targeted listening, trust-rebuilding and psychological-safety interventions for vulnerable segments.")
        if at_risk:
            actions.append("Strengthen sponsorship, manager enablement and communication for at-risk change initiatives.")
        if fatigue > 65:
            actions.append("Reduce concurrent change load and sequence initiatives to lower change-fatigue exposure.")
        if priority:
            actions.append("Escalate priority cultural risks with named owners, milestones and executive review cadence.")
        item.assessment = CultureAssessment(
            culture_health_score=culture_health,
            change_readiness_score=readiness,
            leadership_alignment_score=leadership,
            adoption_risk_score=adoption_risk,
            fatigue_exposure_score=fatigue,
            vulnerable_segments=vulnerable,
            at_risk_initiatives=at_risk,
            priority_issues=priority,
            executive_actions=actions,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "culture_portfolio_assessed", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, resource_id=resource_id, details=details or {}))


executive_culture_service = ExecutiveCultureService()
