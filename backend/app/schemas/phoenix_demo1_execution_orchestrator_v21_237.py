from typing import Literal

from pydantic import BaseModel, Field


class ExecutionOrchestratorRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(default='demo', min_length=1, max_length=100)
    operator_id: str = Field(default='operator', min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=4000)
    memory_query: str | None = Field(default=None, max_length=500)
    risk_brain_hard_block: bool = False


class ExecutionStepResult(BaseModel):
    step_id: str
    adapter_id: str
    capability: str
    state: str
    summary: str
    output: dict | None = None
    reasons: list[str] = Field(default_factory=list)


class ExecutionOrchestratorResult(BaseModel):
    version: str = 'v21.237'
    state: Literal['completed', 'partial', 'blocked', 'failed']
    session_id: str
    workspace_id: str
    operator_id: str
    requested_command: str
    steps: list[ExecutionStepResult]
    completed_steps: int
    failed_steps: int
    operator_summary: str
    approval_required: bool = False
    autonomous_high_risk_execution_enabled: bool = False
    audit_digest: str
    reasons: list[str] = Field(default_factory=list)
