from pydantic import BaseModel, Field


class DemoScenarioRequest(BaseModel):
    scenario: str = Field(default='operator-readiness', min_length=1, max_length=100)
    workspace_id: str = Field(default='demo', min_length=1, max_length=100)
    operator_id: str = Field(default='operator', min_length=1, max_length=100)
    risk_brain_hard_block: bool = False


class ScenarioCheck(BaseModel):
    check_id: str
    passed: bool
    detail: str


class DemoScenarioResult(BaseModel):
    version: str = 'v21.232'
    state: str
    scenario: str
    workspace_id: str
    operator_id: str
    checks: list[ScenarioCheck]
    passed: int
    failed: int
    acceptance_ready: bool
    autonomous_high_risk_execution_enabled: bool = False
