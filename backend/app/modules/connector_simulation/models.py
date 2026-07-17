from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AdapterType(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    GMAIL = "gmail"
    CALENDAR = "calendar"
    BROWSER = "browser"
    DOCUMENTS = "documents"
    TELEGRAM = "telegram"
    GENERIC = "generic"


class ScenarioState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"


class SimulationState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AdapterAction(BaseModel):
    key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.:-]+$")
    description: str = Field(default="", max_length=500)
    required_fields: list[str] = Field(default_factory=list, max_length=100)
    optional_fields: list[str] = Field(default_factory=list, max_length=100)
    produces_fields: list[str] = Field(default_factory=list, max_length=100)
    external_side_effect: bool = False

    @model_validator(mode="after")
    def block_side_effects(self) -> "AdapterAction":
        if self.external_side_effect:
            raise ValueError("v8.1 adapters may not declare external side effects")
        return self


class AdapterRegister(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    adapter_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.-]+$")
    adapter_type: AdapterType
    display_name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1.0", min_length=1, max_length=40)
    actions: list[AdapterAction] = Field(min_length=1, max_length=100)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "AdapterRegister":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class AdapterRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    adapter_key: str
    adapter_type: AdapterType
    display_name: str
    version: str
    actions: list[AdapterAction]
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScenarioStep(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    adapter_id: UUID
    action: str = Field(min_length=1, max_length=160)
    input: dict[str, Any] = Field(default_factory=dict)
    expected_output: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, max_length=100)


class ScenarioCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    steps: list[ScenarioStep] = Field(min_length=1, max_length=200)
    human_approved: bool = True
    external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "ScenarioCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_action:
            raise ValueError("external actions are disabled")
        return self


class ScenarioRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    name: str
    description: str
    steps: list[ScenarioStep]
    state: ScenarioState = ScenarioState.DRAFT
    validation_errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScenarioValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)


class ScenarioMutation(BaseModel):
    human_approved: bool = True

    @model_validator(mode="after")
    def require_approval(self) -> "ScenarioMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class SimulationCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    seed: int = Field(default=1, ge=0, le=2_147_483_647)
    context: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    external_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "SimulationCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_action:
            raise ValueError("external actions are disabled")
        return self


class StepResult(BaseModel):
    step_key: str
    adapter_id: UUID
    action: str
    state: SimulationState
    input: dict[str, Any]
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SimulationRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    scenario_id: UUID
    scenario_version: int = 1
    seed: int
    context: dict[str, Any]
    state: SimulationState = SimulationState.PENDING
    step_results: list[StepResult] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SimulationLabStatus(BaseModel):
    service: str = "connector-simulation"
    version: str = "8.1"
    registered_adapters: int
    ready_scenarios: int
    total_simulations: int
    passed_simulations: int
    failed_simulations: int
    deterministic_dry_run: bool = True
    external_actions_enabled: bool = False
