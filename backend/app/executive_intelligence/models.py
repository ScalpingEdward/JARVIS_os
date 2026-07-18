from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EventSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class TrendDirection(str, Enum):
    improving = "improving"
    stable = "stable"
    deteriorating = "deteriorating"


class IntelligenceEvent(BaseModel):
    event_key: str = Field(min_length=1, max_length=120)
    module: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=100)
    severity: EventSeverity = EventSeverity.info
    occurred_at: datetime
    metric_name: str | None = Field(default=None, max_length=100)
    metric_value: float | None = None
    baseline_value: float | None = None
    related_event_keys: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1, max_length=1000)


class BriefingCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    events: list[IntelligenceEvent] = Field(min_length=1)
    source_snapshot_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event_keys(self):
        keys = [event.event_key for event in self.events]
        if len(keys) != len(set(keys)):
            raise ValueError("Event keys must be unique within a briefing")
        known = set(keys)
        for event in self.events:
            missing = set(event.related_event_keys) - known
            if missing:
                raise ValueError(f"Unknown related event keys: {sorted(missing)}")
        return self


class Correlation(BaseModel):
    source_event_key: str
    target_event_key: str
    confidence: float = Field(ge=0, le=100)
    explanation: str


class TrendInsight(BaseModel):
    module: str
    metric_name: str
    direction: TrendDirection
    change_percent: float
    confidence: float = Field(ge=0, le=100)


class AnomalyInsight(BaseModel):
    event_key: str
    module: str
    severity: EventSeverity
    deviation_percent: float
    explanation: str


class PredictiveAlert(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    module: str
    severity: EventSeverity
    horizon: str
    message: str
    recommended_action: str


class DecisionImpact(BaseModel):
    module: str
    event_count: int
    critical_events: int
    impact_score: float = Field(ge=0, le=100)


class BriefingAnalysis(BaseModel):
    analyzed_at: datetime
    situation_summary: str
    executive_confidence: float = Field(ge=0, le=100)
    correlations: list[Correlation]
    trends: list[TrendInsight]
    anomalies: list[AnomalyInsight]
    predictive_alerts: list[PredictiveAlert]
    decision_impacts: list[DecisionImpact]
    root_cause_candidates: list[str]
    executive_recommendations: list[str]
    autonomous_actions_enabled: bool = False


class ExecutiveBriefing(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    title: str
    events: list[IntelligenceEvent]
    source_snapshot_ids: list[UUID]
    analysis: BriefingAnalysis | None = None
    created_at: datetime
    updated_at: datetime


class IntelligenceStatus(BaseModel):
    version: str = "18.1"
    briefings: int
    analyzed_briefings: int
    active_predictive_alerts: int
    critical_anomalies: int
    autonomous_actions_enabled: bool = False


class BriefingListResponse(BaseModel):
    items: list[ExecutiveBriefing]
    count: int


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    action: str
    actor_id: str
    briefing_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
