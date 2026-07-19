from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    EventStatus,
    ExecutiveGeopoliticalPortfolio,
    GeopoliticalAssessment,
    GeopoliticalEventUpdate,
    GeopoliticalPortfolioCreate,
    GeopoliticalStatusResponse,
    Severity,
)


class ExecutiveGeopoliticalService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveGeopoliticalPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: GeopoliticalPortfolioCreate) -> ExecutiveGeopoliticalPortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Executive geopolitical portfolio already exists")
        item = ExecutiveGeopoliticalPortfolio(**payload.model_dump())
        self._portfolios[item.id] = item
        self._record(item.workspace_id, payload.executive_owner_id, "geopolitical_portfolio_created", item.id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveGeopoliticalPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveGeopoliticalPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def update_event(self, portfolio_id: UUID, workspace_id: str, payload: GeopoliticalEventUpdate) -> ExecutiveGeopoliticalPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive geopolitical portfolio not found")
        event = next((value for value in item.events if value.event_id == payload.event_id), None)
        if event is None:
            raise KeyError("Geopolitical event not found")
        event.mitigation_progress = payload.mitigation_progress
        if payload.status is not None:
            event.status = payload.status
        if payload.response_readiness_score is not None:
            event.response_readiness_score = payload.response_readiness_score
        item.updated_at = datetime.now(timezone.utc)
        self._record(
            workspace_id,
            payload.actor_id,
            "geopolitical_event_updated",
            item.id,
            {"event_id": payload.event_id, "note": payload.note or ""},
        )
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveGeopoliticalPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive geopolitical portfolio not found")
        exposures = item.exposures
        events = item.events
        options = item.continuity_options
        total_value = sum(value.annual_value for value in exposures)

        def weighted(field: str) -> float:
            if total_value <= 0:
                return sum(getattr(value, field) for value in exposures) / len(exposures)
            return sum(getattr(value, field) * value.annual_value for value in exposures) / total_value

        stability = weighted("political_stability_score")
        sanctions = weighted("sanctions_exposure_score")
        transfer = weighted("fx_transfer_risk_score")
        dependency = weighted("supply_dependency_score")
        continuity = weighted("continuity_readiness_score")
        substitutability = weighted("substitutability_score")
        supply_continuity = max(0.0, min(100.0, (continuity + substitutability + (100 - dependency)) / 3))

        event_exposure = 0.0
        if events:
            event_exposure = sum(
                value.probability
                * value.velocity_score
                * (1 - value.mitigation_progress / 100)
                * (1.2 if value.severity == Severity.critical else 1.0)
                for value in events
                if value.status != EventStatus.closed
            ) / len(events)
            event_exposure = min(100.0, event_exposure)

        event_readiness = 100.0 if not events else sum(value.response_readiness_score for value in events) / len(events)
        option_readiness = 100.0
        if options:
            option_readiness = sum(
                (value.activation_readiness_score + value.capacity_coverage_score) / 2 for value in options
            ) / len(options)
        response_readiness = (event_readiness + option_readiness) / 2
        resilience = max(
            0.0,
            min(
                100.0,
                (stability + (100 - sanctions) + (100 - transfer) + supply_continuity + response_readiness + (100 - event_exposure)) / 6,
            ),
        )
        vulnerable = [
            value.exposure_id
            for value in exposures
            if value.strategic_criticality >= 70
            and (
                value.political_stability_score < 55
                or value.sanctions_exposure_score > 55
                or value.fx_transfer_risk_score > 60
                or value.supply_dependency_score > 70
                or value.continuity_readiness_score < 55
            )
        ]
        priority = [
            value.event_id
            for value in events
            if value.status in {EventStatus.monitoring, EventStatus.active}
            and value.severity in {Severity.high, Severity.critical}
            and value.probability * value.velocity_score >= 35
            and value.mitigation_progress < 80
        ]
        actions: list[str] = []
        if vulnerable:
            actions.append("Reduce concentration and establish country-specific continuity plans for vulnerable exposures")
        if priority:
            actions.append("Escalate priority geopolitical events to the executive risk and crisis forum")
        if sanctions > 45:
            actions.append("Strengthen sanctions screening, legal review and counterparty controls")
        if supply_continuity < 65:
            actions.append("Qualify alternative suppliers, routes and operating locations for critical dependencies")
        if response_readiness < 70:
            actions.append("Increase scenario exercises, trigger definitions and continuity-option activation readiness")
        if not actions:
            actions.append("Maintain current geopolitical controls and continue periodic country-risk sensing")
        item.assessment = GeopoliticalAssessment(
            geopolitical_resilience_score=round(resilience, 2),
            political_stability_score=round(stability, 2),
            sanctions_exposure_score=round(sanctions, 2),
            transfer_risk_score=round(transfer, 2),
            supply_continuity_score=round(supply_continuity, 2),
            event_exposure_score=round(event_exposure, 2),
            response_readiness_score=round(response_readiness, 2),
            vulnerable_exposures=vulnerable,
            priority_events=priority,
            executive_actions=actions,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "geopolitical_portfolio_assessed", item.id)
        return item

    def status(self, workspace_id: str) -> GeopoliticalStatusResponse:
        items = self.list_portfolios(workspace_id)
        events = [
            event
            for item in items
            for event in item.events
            if event.status not in {EventStatus.closed, EventStatus.contained}
        ]
        return GeopoliticalStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            country_exposures=sum(len(item.exposures) for item in items),
            active_events=len(events),
            critical_events=sum(event.severity == Severity.critical for event in events),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(
            AuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                resource_id=resource_id,
                details=details or {},
            )
        )


executive_geopolitical_service = ExecutiveGeopoliticalService()
