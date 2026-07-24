from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class OperationalTrendState(str, Enum):
    BLOCKED="blocked"; EVIDENCE_READY="evidence-ready"; ASSESSED="assessed"; REVIEW_REQUIRED="review-required"; APPROVED="approved"; ACTIVE="active"; MONITORING="monitoring"; HEALTHY="healthy"; SUSPENDED="suspended"; REVOKED="revoked"; ARCHIVED="archived"

class OperationalTrendObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    window_id: str = Field(min_length=1, max_length=160)
    availability_trend: float = Field(ge=0, le=1); latency_trend: float = Field(ge=0, le=1); error_rate_trend: float = Field(ge=0, le=1)
    throughput_trend: float = Field(ge=0, le=1); business_kpi_trend: float = Field(ge=0, le=1); cost_efficiency: float = Field(ge=0, le=1)
    resource_efficiency: float = Field(ge=0, le=1); dependency_health: float = Field(ge=0, le=1); alert_quality: float = Field(ge=0, le=1)
    slo_posture: float = Field(ge=0, le=1); error_budget_posture: float = Field(ge=0, le=1); confidence: float = Field(ge=0, le=1); freshness: float = Field(ge=0, le=1)
    operator_interventions: int = Field(default=0, ge=0); sustained_degradation_events: int = Field(default=0, ge=0); dependency_incidents: int = Field(default=0, ge=0)
    criticality: float = Field(default=.5, ge=0, le=1)

class OperationalTrendCreate(BaseModel):
    workspace_id: str = Field(min_length=1); source_key: str = Field(min_length=1); requested_by: str = Field(min_length=1)
    observations: List[OperationalTrendObservation] = Field(min_length=1)
    min_performance: float = Field(default=.85, ge=0, le=1); min_efficiency: float = Field(default=.80, ge=0, le=1); max_residual_risk: float = Field(default=.30, ge=0, le=1)
    @model_validator(mode="after")
    def unique_windows(self):
        keys=[(o.agent_id,o.window_id) for o in self.observations]
        if len(keys)!=len(set(keys)): raise ValueError("duplicate agent/window observation")
        return self

class OperationalTrendDisposition(BaseModel):
    agent_id:str; agent_version:str; window_id:str; assurance:float=Field(ge=0,le=1); residual_risk:float=Field(ge=0,le=1); lifecycle_signal:str; required_actions:List[str]=Field(default_factory=list)

class OperationalTrendScores(BaseModel):
    performance_assurance:float=Field(ge=0,le=1); efficiency_assurance:float=Field(ge=0,le=1); dependency_assurance:float=Field(ge=0,le=1); slo_assurance:float=Field(ge=0,le=1); aggregate_assurance:float=Field(ge=0,le=1); aggregate_residual_risk:float=Field(ge=0,le=1); confidence:float=Field(ge=0,le=1)

class OperationalTrendRecord(BaseModel):
    record_id:str; workspace_id:str; source_key:str; state:OperationalTrendState; scores:OperationalTrendScores; dispositions:List[OperationalTrendDisposition]; risk_flags:List[str]=Field(default_factory=list); approved_by:Optional[str]=None; version:int=1

class OperationalTrendAction(BaseModel):
    workspace_id:str=Field(min_length=1); action:str=Field(min_length=1); actor:str=Field(min_length=1); operation_id:str=Field(min_length=1); reason:Optional[str]=None
