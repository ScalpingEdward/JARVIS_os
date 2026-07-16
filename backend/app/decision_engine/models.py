from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DecisionDomain(str, Enum):
    trading = "trading"
    business = "business"
    engineering = "engineering"
    operations = "operations"
    research = "research"


class DecisionState(str, Enum):
    recommended = "recommended"
    needs_review = "needs_review"
    rejected = "rejected"


class Criterion(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    weight: float = Field(gt=0, le=100)


class OptionInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    scores: dict[str, float] = Field(default_factory=dict)
    risk: float = Field(default=0, ge=0, le=100)
    evidence_quality: float = Field(default=50, ge=0, le=100)
    blockers: list[str] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    domain: DecisionDomain
    criteria: list[Criterion] = Field(min_length=1, max_length=20)
    options: list[OptionInput] = Field(min_length=2, max_length=20)
    minimum_confidence: float = Field(default=65, ge=0, le=100)
    maximum_risk: float = Field(default=70, ge=0, le=100)
    requires_human_approval: bool = True

    @model_validator(mode="after")
    def validate_scores(self):
        names = {item.name for item in self.criteria}
        if len(names) != len(self.criteria):
            raise ValueError("Criterion names must be unique")
        for option in self.options:
            unknown = set(option.scores) - names
            if unknown:
                raise ValueError(f"Unknown criteria: {sorted(unknown)}")
        return self


class RankedOption(BaseModel):
    name: str
    score: float
    confidence: float
    uncertainty: float
    risk: float
    blockers: list[str]
    reasons: list[str]


class DecisionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    domain: DecisionDomain
    state: DecisionState
    selected_option: str | None
    ranked_options: list[RankedOption]
    rationale: list[str]
    requires_human_approval: bool = True
    automatic_execution: bool = False
    approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionListResponse(BaseModel):
    items: list[DecisionRecord]
    count: int


class DecisionStatus(BaseModel):
    total: int
    recommended: int
    needs_review: int
    rejected: int
    automatic_execution: bool = False
    automatic_merge: bool = False
