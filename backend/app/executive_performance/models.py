from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PerformanceStatus(str, Enum):
    draft = "draft"
    analyzed = "analyzed"
    on_track = "on_track"
    at_risk = "at_risk"
    off_track = "off_track"


class TrendDirection(str, Enum):
    improving = "improving"
    stable = "stable"
    declining = "declining"


class KPI(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    target: float
    current: float
    baseline: float = 0
    weight: float = Field(gt=0, le=100)
    higher_is_better: bool = True
    owner_id: str = Field(min_length=1, max_length=100)
    objective_key: str | None = Field(default=None, max_length=100)


class PerformanceRisk(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    probability: float = Field(ge=0, le=100)
    impact: float = Field(ge=0, le=100)
    mitigation: str = Field(default="", max_length=1000)


class ScorecardCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    strategy_plan_id: UUID | None = None
    review_period: str = Field(min_length=1, max_length=100)
    kpis: list[KPI] = Field(min_length=1)
    risks: list[PerformanceRisk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scorecard(self):
        keys = [item.key for item in self.kpis]
        if len(keys) != len(set(keys)):
            raise ValueError("KPI keys must be unique")
        if abs(sum(item.weight for item in self.kpis) - 100.0) > 0.01:
            raise ValueError("KPI weights must total 100")
        risk_keys = [item.key for item in self.risks]
        if len(risk_keys) != len(set(risk_keys)):
            raise ValueError("Risk keys must be unique")
        return self


class KPIResult(BaseModel):
    key: str
    attainment: float = Field(ge=0, le=200)
    weighted_score: float = Field(ge=0, le=200)
    variance: float
    trend: TrendDirection
    status: PerformanceStatus


class PerformanceAlert(BaseModel):
    severity: str
    source_key: str
    message: str


class PerformanceAnalysis(BaseModel):
    analyzed_at: datetime
    overall_score: float = Field(ge=0, le=200)
    alignment_score: float = Field(ge=0, le=100)
    forecast_score: float = Field(ge=0, le=200)
    status: PerformanceStatus
    kpi_results: list[KPIResult]
    risk_exposure: float = Field(ge=0, le=10000)
    alerts: list[PerformanceAlert]
    executive_summary: str
    recommendations: list[str]
    autonomous_actions_enabled: bool = False


class Scorecard(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    strategy_plan_id: UUID | None
    review_period: str
    kpis: list[KPI]
    risks: list[PerformanceRisk]
    status: PerformanceStatus = PerformanceStatus.draft
    analysis: PerformanceAnalysis | None = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


class MeasurementUpdate(BaseModel):
    actor_id: str = Field(min_length=1, max_length=100)
    values: dict[str, float] = Field(min_length=1)


class ScorecardList(BaseModel):
    items: list[Scorecard]
    count: int


class PerformanceStatusResponse(BaseModel):
    version: str = "18.4"
    scorecards: int
    analyzed_scorecards: int
    at_risk_scorecards: int
    off_track_scorecards: int
    autonomous_actions_enabled: bool = False


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    scorecard_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
