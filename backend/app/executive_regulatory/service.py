from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    ComplianceIssueUpdate,
    ExecutiveRegulatoryPortfolio,
    ObligationStatus,
    RegulatoryAssessment,
    RegulatoryPortfolioCreate,
    RegulatoryStatusResponse,
)


class ExecutiveRegulatoryService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveRegulatoryPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: RegulatoryPortfolioCreate) -> ExecutiveRegulatoryPortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Executive regulatory portfolio already exists")
        portfolio = ExecutiveRegulatoryPortfolio(**payload.model_dump())
        self._portfolios[portfolio.id] = portfolio
        self._audit.append(AuditRecord(workspace_id=portfolio.workspace_id, actor_id=portfolio.executive_owner_id, action="regulatory_portfolio_created", resource_id=portfolio.id))
        return portfolio

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveRegulatoryPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveRegulatoryPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> RegulatoryStatusResponse:
        items = self.list_portfolios(workspace_id)
        obligations = [obligation for item in items for obligation in item.obligations]
        return RegulatoryStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            obligations=len(obligations),
            obligations_at_risk=sum(item.status == ObligationStatus.at_risk for item in obligations),
            overdue_obligations=sum(item.status == ObligationStatus.overdue or item.days_to_deadline < 0 for item in obligations),
        )

    def update_issue(self, portfolio_id: UUID, workspace_id: str, payload: ComplianceIssueUpdate) -> ExecutiveRegulatoryPortfolio:
        portfolio = self.get(portfolio_id, workspace_id)
        if portfolio is None:
            raise KeyError("Executive regulatory portfolio not found")
        issue = next((item for item in portfolio.issues if item.issue_id == payload.issue_id), None)
        if issue is None:
            raise KeyError("Compliance issue not found")
        issue.remediation_progress = payload.remediation_progress
        portfolio.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=payload.actor_id, action="compliance_issue_updated", resource_id=portfolio.id, details={"issue_id": payload.issue_id, "note": payload.note or ""}))
        return portfolio

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveRegulatoryPortfolio:
        portfolio = self.get(portfolio_id, workspace_id)
        if portfolio is None:
            raise KeyError("Executive regulatory portfolio not found")
        obligations = portfolio.obligations
        issues = portfolio.issues
        weights = [max(item.materiality, 0.01) for item in obligations]
        total_weight = sum(weights)
        control = sum(item.control_coverage * weight for item, weight in zip(obligations, weights)) / total_weight
        evidence = sum(item.evidence_readiness * weight for item, weight in zip(obligations, weights)) / total_weight
        progress = sum(item.implementation_progress * weight for item, weight in zip(obligations, weights)) / total_weight
        issue_exposure = sum(item.severity * (1 - item.remediation_progress) for item in issues) / max(len(issues), 1)
        deadline_pressure = sum(1 if item.days_to_deadline <= 30 else 0.5 if item.days_to_deadline <= 90 else 0 for item in obligations) / len(obligations)
        at_risk = [item.obligation_id for item in obligations if item.status in {ObligationStatus.at_risk, ObligationStatus.overdue} or item.control_coverage < 0.6]
        overdue = [item.obligation_id for item in obligations if item.status == ObligationStatus.overdue or item.days_to_deadline < 0]
        priority = [item.issue_id for item in issues if item.severity >= 0.7 and item.remediation_progress < 0.7]
        actions: list[str] = []
        if overdue:
            actions.append("Escalate overdue regulatory obligations to executive owners immediately.")
        if evidence < 0.7:
            actions.append("Strengthen evidence collection and audit-readiness controls.")
        if issue_exposure >= 0.4:
            actions.append("Accelerate remediation of high-severity compliance issues.")
        if not actions:
            actions.append("Maintain regulatory monitoring and scheduled control validation.")
        portfolio.assessment = RegulatoryAssessment(
            compliance_readiness_score=round(progress * 100, 2),
            control_coverage_score=round(control * 100, 2),
            evidence_readiness_score=round(evidence * 100, 2),
            regulatory_exposure_score=round(issue_exposure * 100, 2),
            deadline_pressure_score=round(deadline_pressure * 100, 2),
            obligations_at_risk=at_risk,
            overdue_obligations=overdue,
            priority_issues=priority,
            executive_actions=actions,
        )
        portfolio.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action="regulatory_portfolio_assessed", resource_id=portfolio.id))
        return portfolio

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_regulatory_service = ExecutiveRegulatoryService()
