from pydantic import BaseModel, Field


class DemoStep(BaseModel):
    step_id: str
    title: str
    endpoint: str
    expected_state: str
    recovery_hint: str | None = None


class RecoveryCase(BaseModel):
    case_id: str
    trigger: str
    expected_response: str
    operator_action: str


class OperatorAcceptanceRequest(BaseModel):
    workspace_id: str = Field(default='demo', min_length=1, max_length=100)
    operator_id: str = Field(default='operator', min_length=1, max_length=100)
    scenario: str = Field(default='guided-demo', min_length=1, max_length=100)
    risk_brain_hard_block: bool = False


class OperatorAcceptanceResult(BaseModel):
    version: str = 'v21.233'
    state: str
    workspace_id: str
    operator_id: str
    scenario: str
    script: list[DemoStep]
    recovery_cases: list[RecoveryCase]
    integration_acceptance_ready: bool
    operator_acceptance_ready: bool
    release_packaging_ready: bool = False
    autonomous_high_risk_execution_enabled: bool = False
    reasons: list[str] = Field(default_factory=list)
