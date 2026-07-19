from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, EsgIssueUpdate, EsgPillar, EsgPortfolioCreate, EsgStatusResponse, ExecutiveEsgPortfolio


class ExecutiveEsgService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveEsgPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: EsgPortfolioCreate) -> ExecutiveEsgPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._items.values()):
            raise ValueError("Executive ESG portfolio already exists")
        item = ExecutiveEsgPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._record(item.workspace_id, payload.actor_id, "esg_portfolio_created", item.portfolio_id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveEsgPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveEsgPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> EsgStatusResponse:
        items = self.list_portfolios(workspace_id)
        return EsgStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            assessed_portfolios=sum(item.assessed_at is not None for item in items),
            material_gaps=sum(len(item.material_gaps) for item in items),
        )

    def update_issue(self, portfolio_id: UUID, workspace_id: str, payload: EsgIssueUpdate) -> ExecutiveEsgPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive ESG portfolio not found")
        issue = next((value for value in item.issues if value.issue_id == payload.issue_id), None)
        if issue is None:
            raise KeyError("ESG issue not found")
        issue.remediation_progress = payload.remediation_progress
        self._record(workspace_id, payload.actor_id, "esg_issue_updated", portfolio_id)
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveEsgPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive ESG portfolio not found")

        def pillar_score(pillar: EsgPillar) -> float:
            metrics = [metric for metric in item.metrics if metric.pillar == pillar]
            if not metrics:
                return 0
            total_weight = sum(metric.weight for metric in metrics) or 1
            score = 0.0
            for metric in metrics:
                target = abs(metric.target_value) or 1
                achievement = max(0.0, min(1.0, metric.current_value / target))
                confidence = metric.data_quality / 100
                score += achievement * confidence * metric.weight
            return round(score / total_weight * 100, 2)

        item.environmental_score = pillar_score(EsgPillar.environmental)
        item.social_score = pillar_score(EsgPillar.social)
        item.governance_score = pillar_score(EsgPillar.governance)
        item.overall_esg_score = round((item.environmental_score + item.social_score + item.governance_score) / 3, 2)

        open_exposure = [issue.severity * (100 - issue.remediation_progress) / 100 for issue in item.issues]
        metric_exposure = [metric.regulatory_materiality * (100 - metric.data_quality) / 100 for metric in item.metrics]
        item.compliance_exposure = round((sum(open_exposure) + sum(metric_exposure)) / max(len(open_exposure) + len(metric_exposure), 1), 2)

        if item.initiatives:
            values = [
                initiative.impact_score * initiative.execution_readiness / 100 * (100 - initiative.delivery_risk) / 100
                for initiative in item.initiatives
            ]
            item.initiative_value_score = round(sum(values) / len(values), 2)
        else:
            item.initiative_value_score = 0

        item.material_gaps = [
            metric.metric_id
            for metric in item.metrics
            if metric.regulatory_materiality >= 70 and (metric.data_quality < 70 or abs(metric.current_value) < abs(metric.target_value) * 0.8)
        ]
        item.priority_initiatives = [
            initiative.initiative_id
            for initiative in item.initiatives
            if initiative.impact_score >= 70 and initiative.execution_readiness >= 60 and initiative.delivery_risk <= 50
        ]

        recommendations: list[str] = []
        if item.material_gaps:
            recommendations.append("Close material ESG performance and reporting gaps")
        if item.compliance_exposure >= 50:
            recommendations.append("Escalate ESG compliance remediation to executive governance")
        if item.priority_initiatives:
            recommendations.append("Prioritize high-impact sustainability initiatives with strong delivery readiness")
        if item.overall_esg_score < 60:
            recommendations.append("Rebalance the portfolio toward measurable environmental, social and governance outcomes")
        item.recommendations = recommendations or ["Maintain ESG controls and continue performance monitoring"]
        item.assessed_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "esg_portfolio_assessed", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, portfolio_id: UUID) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, portfolio_id=portfolio_id))


executive_esg_service = ExecutiveEsgService()
