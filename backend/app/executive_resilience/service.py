from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    ContinuityState,
    ContinuityUpdate,
    Criticality,
    ExecutiveResiliencePlan,
    ResilienceAssessment,
    ResiliencePlanCreate,
    ResilienceStatusResponse,
)


class ExecutiveResilienceService:
    def __init__(self) -> None:
        self._plans: dict[UUID, ExecutiveResiliencePlan] = {}
        self._audit: list[AuditRecord] = []

    def status(self, workspace_id: str) -> ResilienceStatusResponse:
        plans = self.list_plans(workspace_id)
        services = [service for plan in plans for service in plan.services]
        return ResilienceStatusResponse(
            workspace_id=workspace_id,
            plans=len(plans),
            critical_services=sum(service.criticality == Criticality.critical for service in services),
            disrupted_services=sum(service.current_state == ContinuityState.disrupted for service in services),
            untested_services=sum(not service.tested for service in services),
        )

    def create(self, payload: ResiliencePlanCreate) -> ExecutiveResiliencePlan:
        if any(plan.workspace_id == payload.workspace_id and plan.name == payload.name for plan in self._plans.values()):
            raise ValueError("A resilience plan with this name already exists in the workspace")
        self._validate_acyclic(payload.services)
        plan = ExecutiveResiliencePlan(**payload.model_dump())
        self._plans[plan.id] = plan
        self._record(payload.workspace_id, payload.executive_owner_id, "resilience_plan.created", plan.id)
        return plan

    def list_plans(self, workspace_id: str) -> list[ExecutiveResiliencePlan]:
        return [plan for plan in self._plans.values() if plan.workspace_id == workspace_id]

    def get(self, plan_id: UUID, workspace_id: str) -> ExecutiveResiliencePlan | None:
        plan = self._plans.get(plan_id)
        return plan if plan and plan.workspace_id == workspace_id else None

    def update_continuity(self, plan_id: UUID, workspace_id: str, payload: ContinuityUpdate) -> ExecutiveResiliencePlan:
        plan = self.get(plan_id, workspace_id)
        if plan is None:
            raise KeyError("Executive resilience plan not found")
        service = next((item for item in plan.services if item.service_id == payload.service_id), None)
        if service is None:
            raise KeyError("Critical service not found")
        service.current_state = payload.state
        if payload.tested is not None:
            service.tested = payload.tested
        plan.assessment = None
        plan.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "continuity.updated", plan.id, {"service_id": payload.service_id, "state": payload.state.value})
        return plan

    def assess(self, plan_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveResiliencePlan:
        plan = self.get(plan_id, workspace_id)
        if plan is None:
            raise KeyError("Executive resilience plan not found")
        self._validate_acyclic(plan.services)
        plan.assessment = self._build_assessment(plan)
        plan.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "resilience.assessed", plan.id, {"score": plan.assessment.resilience_score})
        return plan

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _build_assessment(self, plan: ExecutiveResiliencePlan) -> ResilienceAssessment:
        services = plan.services
        tested_ratio = sum(service.tested for service in services) / len(services)
        healthy_weights = {
            ContinuityState.ready: 1.0,
            ContinuityState.recovering: 0.65,
            ContinuityState.degraded: 0.4,
            ContinuityState.disrupted: 0.0,
        }
        state_score = sum(healthy_weights[service.current_state] for service in services) / len(services) * 100
        recovery_score = sum(
            max(0.0, 1 - service.recovery_time_objective_minutes / service.maximum_tolerable_downtime_minutes)
            for service in services
        ) / len(services) * 100
        role_score = 100.0 if plan.crisis_roles and all(role.backup_owner_id for role in plan.crisis_roles) else (60.0 if plan.crisis_roles else 0.0)
        exposure = sum(item.probability * item.impact * (1 - item.mitigation_strength) for item in plan.scenarios)
        exposure_score = min(100.0, exposure / max(1, len(plan.scenarios)) * 100) if plan.scenarios else 0.0
        dependency_counts = Counter(dep for service in services for dep in service.dependencies)
        concentration = max(dependency_counts.values(), default=0) / max(1, len(services)) * 100
        single_points = sorted(dep for dep, count in dependency_counts.items() if count >= 2)
        at_risk = sorted(
            service.service_id
            for service in services
            if service.current_state != ContinuityState.ready or not service.tested
        )
        resilience = max(0.0, min(100.0, state_score * 0.35 + tested_ratio * 100 * 0.2 + recovery_score * 0.2 + role_score * 0.15 + (100 - exposure_score) * 0.1))
        actions: list[str] = []
        if at_risk:
            actions.append("Prioritize continuity exercises and recovery remediation for at-risk critical services")
        if single_points:
            actions.append("Reduce dependency concentration and establish alternate service paths")
        if role_score < 100:
            actions.append("Assign primary and backup owners for every crisis-management role")
        if exposure_score >= 40:
            actions.append("Strengthen mitigations for the highest residual-risk scenarios")
        if not actions:
            actions.append("Maintain the current testing cadence and executive resilience review cycle")
        return ResilienceAssessment(
            resilience_score=round(resilience, 2),
            recovery_readiness_score=round((recovery_score + tested_ratio * 100) / 2, 2),
            crisis_role_coverage_score=round(role_score, 2),
            scenario_exposure_score=round(exposure_score, 2),
            dependency_concentration_score=round(concentration, 2),
            critical_services_at_risk=at_risk,
            single_points_of_failure=single_points,
            executive_actions=actions,
        )

    @staticmethod
    def _validate_acyclic(services: list) -> None:
        graph = {service.service_id: service.dependencies for service in services}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("Critical service dependency graph contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, resource_id=resource_id, details=details or {}))


executive_resilience_service = ExecutiveResilienceService()
