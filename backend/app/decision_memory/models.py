from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DecisionDomain(str, Enum):
    trading = "trading"
    business = "business"
    engineering = "engineering"
    research = "research"
    finance = "finance"
    health = "health"
    legal = "legal"
    personal = "personal"


class DecisionOutcome(str, Enum):
    successful = "successful"
    mixed = "mixed"
    unsuccessful = "unsuccessful"
    pending = "pending"


class ConfidenceBand(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DecisionRecordCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    domain: DecisionDomain
    recommendation: str = Field(min_length=2, max_length=2000)
    selected_action: str = Field(min_length=2, max_length=2000)
    predicted_confidence: float = Field(ge=0.0, le=1.0)
    outcome: DecisionOutcome = DecisionOutcome.pending
    outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_tags: list[str] = Field(default_factory=list, max_length=30)
    context_tags: list[str] = Field(default_factory=list, max_length=30)
    learning_consent: bool = False


class DecisionRecord(DecisionRecordCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PatternType(str, Enum):
    strength = "strength"
    risk = "risk"
    bias = "bias"
    calibration = "calibration"


class DecisionPattern(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    domain: DecisionDomain
    pattern_type: PatternType
    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    sample_size: int = Field(ge=1)
    evidence: list[str] = Field(default_factory=list)


class CalibrationReport(BaseModel):
    domain: DecisionDomain | None = None
    sample_size: int
    average_predicted_confidence: float
    average_outcome_score: float
    calibration_gap: float
    status: str


class DecisionMemoryStatus(BaseModel):
    owner_name: str = "MASTER Brano"
    records: int
    learning_records: int
    patterns: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False


class DecisionMemoryList(BaseModel):
    items: list[DecisionRecord]
    count: int


class PatternList(BaseModel):
    items: list[DecisionPattern]
    count: int
