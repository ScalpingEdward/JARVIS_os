from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    coordinator = "coordinator"
    planner = "planner"
    researcher = "researcher"
    analyst = "analyst"
    coder = "coder"
    reviewer = "reviewer"
    guardian = "guardian"
    vision = "vision"


class MissionState(StrEnum):
    proposed = "proposed"
    active = "active"
    waiting_consensus = "waiting_consensus"
    blocked = "blocked"
    completed = "completed"
    cancelled = "cancelled"


class VoteDecision(StrEnum):
    approve = "approve"
    reject = "reject"
    abstain = "abstain"


class MeshAgent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)
    role: AgentRole
    capabilities: list[str] = Field(default_factory=list)
    confidence_weight: float = Field(default=1, ge=0.1, le=2)
    available: bool = True


class MeshAgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: AgentRole
    capabilities: list[str] = Field(default_factory=list)
    confidence_weight: float = Field(default=1, ge=0.1, le=2)


class MissionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    objective: str = Field(min_length=1, max_length=3000)
    required_capabilities: list[str] = Field(default_factory=list)
    critical: bool = False
    consensus_threshold: float = Field(default=0.67, ge=0.5, le=1)


class AgentContribution(BaseModel):
    agent_id: UUID
    summary: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    recommendation: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsensusVote(BaseModel):
    agent_id: UUID
    decision: VoteDecision
    confidence: float = Field(default=0.5, ge=0, le=1)
    rationale: str = Field(default="", max_length=2000)


class CollaborationMission(MissionCreate):
    id: UUID = Field(default_factory=uuid4)
    state: MissionState = MissionState.proposed
    assigned_agent_ids: list[UUID] = Field(default_factory=list)
    contributions: list[AgentContribution] = Field(default_factory=list)
    votes: list[ConsensusVote] = Field(default_factory=list)
    consensus_score: float = Field(default=0, ge=0, le=1)
    conflicts: list[str] = Field(default_factory=list)
    final_recommendation: str | None = None
    human_approval_required: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MeshStatus(BaseModel):
    agents: int
    available_agents: int
    missions: int
    active_missions: int
    blocked_missions: int
    awaiting_consensus: int
    automatic_execution: bool = False
    automatic_order_execution: bool = False
    automatic_merge: bool = False
