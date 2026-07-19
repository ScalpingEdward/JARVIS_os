from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    ExecutiveReputationPortfolio,
    ReputationAssessment,
    ReputationIssueUpdate,
    ReputationPortfolioCreate,
    ReputationStatusResponse,
    Severity,
)


class ExecutiveReputationService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveReputationPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: ReputationPortfolioCreate) -> ExecutiveReputationPortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Executive reputation portfolio already exists")
        item = ExecutiveReputationPortfolio(**payload.model_dump())
        self._portfolios[item.id] = item
        self._record(item.workspace_id, payload.executive_owner_id, "reputation_portfolio_created", item.id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveReputationPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveReputationPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def update_issue(self, portfolio_id: UUID, workspace_id: str, payload: ReputationIssueUpdate) -> ExecutiveReputationPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive reputation portfolio not found")
        issue = next((value for value in item.issues if value.issue_id == payload.issue_id), None)
        if issue is None:
            raise KeyError("Reputation issue not found")
        issue.remediation_progress = payload.remediation_progress
        if payload.response_readiness_score is not None:
            issue.response_readiness_score = payload.response_readiness_score
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "reputation_issue_updated", item.id, {"issue_id": payload.issue_id, "note": payload.note or ""})
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveReputationPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive reputation portfolio not found")
        segments = item.stakeholder_segments
        issues = item.issues
        channels = item.channels
        trust = sum(value.trust_score for value in segments) / len(segments)
        alignment = sum(value.narrative_alignment_score for value in segments) / len(segments)
        engagement = sum(value.engagement_score for value in segments) / len(segments)
        sentiment = sum((value.sentiment_score + 100) / 2 for value in segments) / len(segments)
        issue_exposure = 0.0
        if issues:
            issue_exposure = sum(
                value.probability * value.velocity_score * (1 - value.remediation_progress / 100)
                for value in issues
            ) / len(issues)
        channel_readiness = 100.0
        if channels:
            channel_readiness = sum(
                (value.reach_score + value.credibility_score + value.response_speed_score + value.monitoring_coverage_score) / 4
                for value in channels
            ) / len(channels)
        issue_readiness = 100.0 if not issues else sum(value.response_readiness_score for value in issues) / len(issues)
        crisis_readiness = (channel_readiness + issue_readiness) / 2
        reputation_health = max(0.0, min(100.0, (trust + alignment + engagement + sentiment + (100 - issue_exposure)) / 5))
        vulnerable = [value.segment_id for value in segments if value.trust_score < 60 or value.sentiment_score < -10 or value.narrative_alignment_score < 55]
        priority = [value.issue_id for value in issues if value.severity in {Severity.high, Severity.critical} and value.probability * value.velocity_score >= 35 and value.remediation_progress < 80]
        actions: list[str] = []
        if vulnerable:
            actions.append("Launch targeted stakeholder listening and trust-recovery plans for vulnerable segments")
        if priority:
            actions.append("Escalate priority reputation issues to the executive crisis and communications team")
        if alignment < 70:
            actions.append("Align executive narratives, proof points and spokesperson guidance across channels")
        if crisis_readiness < 70:
            actions.append("Strengthen monitoring coverage, response playbooks and spokesperson readiness")
        if not actions:
            actions.append("Maintain current reputation governance and continue periodic stakeholder sensing")
        item.assessment = ReputationAssessment(
            reputation_health_score=round(reputation_health, 2),
            stakeholder_trust_score=round(trust, 2),
            narrative_alignment_score=round(alignment, 2),
            issue_exposure_score=round(issue_exposure, 2),
            crisis_readiness_score=round(crisis_readiness, 2),
            vulnerable_segments=vulnerable,
            priority_issues=priority,
            executive_actions=actions,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "reputation_portfolio_assessed", item.id)
        return item

    def status(self, workspace_id: str) -> ReputationStatusResponse:
        items = self.list_portfolios(workspace_id)
        issues = [issue for item in items for issue in item.issues if issue.remediation_progress < 100]
        return ReputationStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            stakeholder_segments=sum(len(item.stakeholder_segments) for item in items),
            open_issues=len(issues),
            critical_issues=sum(issue.severity == Severity.critical for issue in issues),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, resource_id=resource_id, details=details or {}))


executive_reputation_service = ExecutiveReputationService()
