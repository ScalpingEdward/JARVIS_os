from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AdapterMode(StrEnum):
    contribution = "contribution"
    review = "review"


class AgentAdapterDescriptor(BaseModel):
    provider: str
    model_provider: str
    available: bool
    supports_contributions: bool = True
    supports_reviews: bool = True


class ContributionDispatch(BaseModel):
    session_id: UUID
    participant_name: str
    instructions: str = Field(default="", max_length=10000)
    artifacts: list[str] = Field(default_factory=list)


class ReviewDispatch(BaseModel):
    session_id: UUID
    contribution_id: UUID
    reviewer_name: str
    instructions: str = Field(default="", max_length=10000)


class AdapterExecutionResult(BaseModel):
    provider: str
    model: str
    runtime_run_id: UUID
    session_id: UUID
    contribution_id: UUID | None = None
    approved: bool | None = None
    content: str
