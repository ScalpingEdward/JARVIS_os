from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    CapitalMarketsRiskUpdate,
    ExecutiveInvestorPortfolio,
    InvestorAssessment,
    InvestorPortfolioCreate,
    InvestorStatusResponse,
    RiskSeverity,
)


class ExecutiveInvestorService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveInvestorPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: InvestorPortfolioCreate) -> ExecutiveInvestorPortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Executive investor-relations portfolio already exists")
        item = ExecutiveInvestorPortfolio(**payload.model_dump())
        self._portfolios[item.id] = item
        self._record(item.workspace_id, payload.executive_owner_id, "investor_portfolio_created", item.id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveInvestorPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveInvestorPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def update_risk(
        self,
        portfolio_id: UUID,
        workspace_id: str,
        payload: CapitalMarketsRiskUpdate,
    ) -> ExecutiveInvestorPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive investor-relations portfolio not found")
        risk = next((value for value in item.risks if value.risk_id == payload.risk_id), None)
        if risk is None:
            raise KeyError("Capital-markets risk not found")
        risk.remediation_progress = payload.remediation_progress
        if payload.response_readiness_score is not None:
            risk.response_readiness_score = payload.response_readiness_score
        item.updated_at = datetime.now(timezone.utc)
        self._record(
            workspace_id,
            payload.actor_id,
            "capital_markets_risk_updated",
            item.id,
            {"risk_id": payload.risk_id, "note": payload.note or ""},
        )
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveInvestorPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive investor-relations portfolio not found")

        segments = item.investor_segments
        analysts = item.analyst_coverage
        guidance = item.guidance_metrics
        risks = item.risks

        confidence = sum(value.confidence_score for value in segments) / len(segments)
        engagement = sum(value.engagement_score for value in segments) / len(segments)
        valuation = sum(value.valuation_alignment_score for value in segments) / len(segments)
        ownership_resilience = sum(
            (value.long_term_orientation_score + (100 - value.concentration_risk_score)) / 2
            for value in segments
        ) / len(segments)

        analyst_understanding = 100.0
        if analysts:
            analyst_understanding = sum(
                (value.model_understanding_score + value.access_quality_score + (100 - value.estimate_dispersion_score)) / 3
                for value in analysts
            ) / len(analysts)

        guidance_credibility = 100.0
        if guidance:
            guidance_credibility = sum(
                (
                    value.guidance_accuracy_score
                    + value.disclosure_clarity_score
                    + value.controllability_score
                    + max(0.0, 100 - abs(value.consensus_gap_percent) * 2)
                )
                / 4
                for value in guidance
            ) / len(guidance)

        risk_exposure = 0.0
        if risks:
            risk_exposure = sum(
                value.probability * value.impact_score * (1 - value.remediation_progress / 100)
                for value in risks
            ) / len(risks)

        vulnerable = [
            value.segment_id
            for value in segments
            if value.confidence_score < 60
            or value.engagement_score < 55
            or value.valuation_alignment_score < 55
            or value.concentration_risk_score > 75
        ]
        priority = [
            value.risk_id
            for value in risks
            if value.severity in {RiskSeverity.high, RiskSeverity.critical}
            and value.probability * value.impact_score >= 35
            and value.remediation_progress < 80
        ]

        actions: list[str] = []
        if vulnerable:
            actions.append("Launch targeted investor engagement and confidence-recovery plans for vulnerable segments")
        if guidance_credibility < 70:
            actions.append("Tighten guidance governance, disclosure clarity and consensus-expectation management")
        if analyst_understanding < 70:
            actions.append("Expand analyst education on the business model, value drivers and scenario sensitivities")
        if ownership_resilience < 65:
            actions.append("Improve long-term ownership quality and reduce investor concentration exposure")
        if priority:
            actions.append("Escalate priority capital-markets risks to executive, treasury and board oversight")
        if not actions:
            actions.append("Maintain current investor-relations governance and continue periodic capital-markets sensing")

        item.assessment = InvestorAssessment(
            investor_confidence_score=round(confidence, 2),
            engagement_quality_score=round(engagement, 2),
            valuation_alignment_score=round(valuation, 2),
            guidance_credibility_score=round(guidance_credibility, 2),
            analyst_understanding_score=round(analyst_understanding, 2),
            ownership_resilience_score=round(ownership_resilience, 2),
            capital_markets_risk_score=round(risk_exposure, 2),
            vulnerable_segments=vulnerable,
            priority_risks=priority,
            executive_actions=actions,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "investor_portfolio_assessed", item.id)
        return item

    def status(self, workspace_id: str) -> InvestorStatusResponse:
        items = self.list_portfolios(workspace_id)
        risks = [risk for item in items for risk in item.risks if risk.remediation_progress < 100]
        return InvestorStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            investor_segments=sum(len(item.investor_segments) for item in items),
            analysts=sum(len(item.analyst_coverage) for item in items),
            open_risks=len(risks),
            critical_risks=sum(risk.severity == RiskSeverity.critical for risk in risks),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _record(
        self,
        workspace_id: str,
        actor_id: str,
        action: str,
        resource_id: UUID,
        details: dict[str, object] | None = None,
    ) -> None:
        self._audit.append(
            AuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                resource_id=resource_id,
                details=details or {},
            )
        )


executive_investor_service = ExecutiveInvestorService()
