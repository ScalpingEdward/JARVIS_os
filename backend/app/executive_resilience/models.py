from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Criticality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ContinuityState(str, Enum):
    ready = "ready"
    degraded = "degraded"
    disrupted = "disrupted"
    recovering = "recovering"


class CriticalService(BaseModel):
    service_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    owner_id: str = Field(min_length=1, max_length=100)
    criticality: Criticality = Criticality.medium
    recovery_time_objective_minutes: int = Field(gt=0, le=10080)
    recovery_point_objective_minutes: int = Field(ge=0, le=10080)
    maximum_tolerable_downtime_minutes: int = Field(gt=0, le=20160)
    dependencies: list[str] = Field(default_factory=list)
    tested: bool = False
    current_state: ContinuityState = ContinuityState.ready

    @model_validator(mode="after")
    def validate_recovery_targets(self) -> "CriticalService":
        if self.recovery_time_objective_minutes > self.maximum_tolerable_downtime_minutes:
            raise ValueError("Recovery time objective cannot exceed maximum tolerable downtime")
        if self.service_id in self.dependencies:
            raise ValueError("Service cannot depend on itself")
        return self


class ResilienceScenario(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    probability: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=1)
    affected_service_ids: list[str] = Field(default_factory=list)
    mitigation_strength: float = Field(default=0, ge=0, le=1)


class CrisisRole(BaseModel):
    role_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    owner_id: str = Field(min_length=1, max_length=100)
    backup_owner_id: str | None = Field(default=None, max_length=100)
    decision_authority: list[str] = Field(default_factory=list)


class ResiliencePlanCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    executive_owner_id: str = Field(min_length=1, max_length=100)
    governance_framework_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    services: list[CriticalService] = Field(min_length=1)
    scenarios: list[ResilienceScenario] = Field(default_factory=list)
    crisis_roles: list[CrisisRole] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "ResiliencePlanCreate":
        service_ids = [item.service_id for item in self.services]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("Duplicate service IDs are not allowed")
        scenario_ids = [item.scenario_id for item in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("Duplicate scenario IDs are not allowed")
        known = set(service_ids)
        for service in self.services:
            missing = set(service.dependencies) - known
            if missing:
                raise ValueError(f"Unknown service dependencies: {sorted(missing)}")
        for scenario in self.scenarios:
            missing = set(scenario.affected_service_ids) - known
            if missing:
                raise ValueError(f"Unknown affected services: {sorted(missing)}")
        return self


class ContinuityUpdate(BaseModel):
    service_id: str = Field(min_length=1, max_length=100)
    state: ContinuityState
    tested: bool | None = None
    actor_id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class ResilienceAssessment(BaseModel):
    resilience_score: float = Field(ge=0, le=100)
    recovery_readiness_score: float = Field(ge=0, le=100)
    crisis_role_coverage_score: float = Field(ge=0, le=100)
    scenario_exposure_score: float = Field(ge=0, le=100)
    dependency_concentration_score: float = Field(ge=0, le=100)
    critical_services_at_risk: list[str] = Field(default_factory=list)
    single_points_of_failure: list[str] = Field(default_factory=list)
    executive_actions: list[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutiveResiliencePlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    name: str
    executive_owner_id: str
    governance_framework_id: UUID | None = None
    transformation_portfolio_id: UUID | None = None
    services: list[CriticalService]
    scenarios: list[ResilienceScenario]
    crisis_roles: list[CrisisRole]
    assessment: ResilienceAssessment | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResilienceStatusResponse(BaseModel):
    workspace_id: str
    plans: int
    critical_services: int
    disrupted_services: int
    untested_services: int
    autonomous_actions_enabled: bool = False


class ResilienceListResponse(BaseModel):
    items: list[ExecutiveResiliencePlan]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_id: UUID
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
