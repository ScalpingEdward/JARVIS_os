from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class HealthState(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    critical = "critical"
    unknown = "unknown"


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class ModuleSignal(BaseModel):
    module: str = Field(min_length=1, max_length=100)
    health: HealthState = HealthState.unknown
    readiness_score: float = Field(default=0, ge=0, le=100)
    open_items: int = Field(default=0, ge=0)
    blocked_items: int = Field(default=0, ge=0)
    pending_approvals: int = Field(default=0, ge=0)
    utilization_percent: float = Field(default=0, ge=0, le=100)
    risk_score: float = Field(default=0, ge=0, le=100)
    kpis: dict[str, float] = Field(default_factory=dict)
    dependency_modules: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OperationsSnapshotCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    signals: list[ModuleSignal] = Field(min_length=1)
    source_reference_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_modules(self):
        names = [signal.module for signal in self.signals]
        if len(names) != len(set(names)):
            raise ValueError("Module names must be unique within a snapshot")
        return self


class ExecutiveAlert(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    module: str
    severity: Severity
    code: str
    message: str
    recommended_action: str


class RiskCell(BaseModel):
    module: str
    risk_score: float
    blocked_items: int
    pending_approvals: int
    severity: Severity


class DependencyEdge(BaseModel):
    source_module: str
    target_module: str
    blocked: bool
    explanation: str


class ModuleSummary(BaseModel):
    module: str
    health: HealthState
    readiness_score: float
    open_items: int
    blocked_items: int
    pending_approvals: int
    utilization_percent: float
    risk_score: float


class OperationsAnalysis(BaseModel):
    analyzed_at: datetime
    overall_health: HealthState
    executive_score: float
    module_summaries: list[ModuleSummary]
    aggregated_kpis: dict[str, float]
    alerts: list[ExecutiveAlert]
    risk_heatmap: list[RiskCell]
    dependency_graph: list[DependencyEdge]
    governance_compliance_percent: float
    capacity_utilization_percent: float
    executive_recommendations: list[str]
    autonomous_actions_enabled: bool = False


class OperationsSnapshot(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    signals: list[ModuleSignal]
    source_reference_ids: list[UUID]
    analysis: OperationsAnalysis | None = None
    created_at: datetime
    updated_at: datetime


class OperationsStatus(BaseModel):
    version: str = "18.0"
    snapshots: int
    healthy_modules: int
    degraded_modules: int
    critical_modules: int
    active_alerts: int
    autonomous_actions_enabled: bool = False


class OperationsListResponse(BaseModel):
    items: list[OperationsSnapshot]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    snapshot_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
