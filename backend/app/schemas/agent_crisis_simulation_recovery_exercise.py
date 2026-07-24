from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class CrisisExerciseState(str, Enum):
    BLOCKED = "blocked"
    EVIDENCE_READY = "evidence-ready"
    ASSESSED = "assessed"
    REVIEW_REQUIRED = "review-required"
    APPROVED = "approved"
    ACTIVE = "active"
    MONITORING = "monitoring"
    VERIFIED = "verified"
    SCENARIO_ALERT = "scenario-alert"
    COMMAND_ALERT = "command-alert"
    RECOVERY_ALERT = "recovery-alert"
    COMMUNICATION_ALERT = "communication-alert"
    LESSONS_ALERT = "lessons-alert"
    ESCALATED = "escalated"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class CrisisExerciseObservation(BaseModel):
    agent_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=80)
    exercise_id: str = Field(min_length=1, max_length=160)
    scenario_coverage: float = Field(ge=0.0, le=1.0)
    severity_realism: float = Field(ge=0.0, le=1.0)
    incident_command_readiness: float = Field(ge=0.0, le=1.0)
    decision_timing_quality: float = Field(ge=0.0, le=1.0)
    communication_readiness: float = Field(ge=0.0, le=1.0)
    recovery_sequence_quality: float = Field(ge=0.0, le=1.0)
    rto_attainment: float = Field(ge=0.0, le=1.0)
    rpo_attainment: float = Field(ge=0.0, le=1.0)
    dependency_coordination: float = Field(ge=0.0, le=1.0)
    runbook_effectiveness: float = Field(ge=0.0, le=1.0)
    evidence_capture: float = Field(ge=0.0, le=1.0)
    lessons_learned_quality: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(ge=0.0, le=1.0)
    failed_command_decisions: int = Field(default=0, ge=0)
    missed_recovery_objectives: int = Field(default=0, ge=0)
    communication_failures: int = Field(default=0, ge=0)
    unresolved_lessons: int = Field(default=0, ge=0)
    business_criticality: float = Field(default=0.5, ge=0.0, le=1.0)


class CrisisExerciseCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    source_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    observations: List[CrisisExerciseObservation] = Field(min_length=1)
    min_scenario_coverage: float = Field(default=0.85, ge=0.0, le=1.0)
    min_command_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    min_recovery_quality: float = Field(default=0.90, ge=0.0, le=1.0)
    min_communication_readiness: float = Field(default=0.90, ge=0.0, le=1.0)
    max_residual_risk: float = Field(default=0.30, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_exercises(self):
        keys = [(o.agent_id, o.exercise_id) for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate agent/exercise observation")
        return self


class CrisisExerciseDisposition(BaseModel):
    agent_id: str
    agent_version: str
    exercise_id: str
    assurance: float = Field(ge=0.0, le=1.0)
    residual_risk: float = Field(ge=0.0, le=1.0)
    lifecycle_signal: str
    required_actions: List[str] = Field(default_factory=list)


class CrisisExerciseScores(BaseModel):
    scenario_assurance: float = Field(ge=0.0, le=1.0)
    command_assurance: float = Field(ge=0.0, le=1.0)
    recovery_assurance: float = Field(ge=0.0, le=1.0)
    communication_assurance: float = Field(ge=0.0, le=1.0)
    runbook_assurance: float = Field(ge=0.0, le=1.0)
    learning_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_assurance: float = Field(ge=0.0, le=1.0)
    aggregate_residual_risk: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class CrisisExerciseRecord(BaseModel):
    record_id: str
    workspace_id: str
    source_key: str
    state: CrisisExerciseState
    scores: CrisisExerciseScores
    dispositions: List[CrisisExerciseDisposition]
    risk_flags: List[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    version: int = 1


class CrisisExerciseAction(BaseModel):
    workspace_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    reason: Optional[str] = None
