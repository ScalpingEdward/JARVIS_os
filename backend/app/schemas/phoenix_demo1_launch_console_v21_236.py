from pydantic import BaseModel, Field


class LaunchConsoleRequest(BaseModel):
    workspace_id: str = Field(default='demo', min_length=1, max_length=100)
    operator_id: str = Field(default='operator', min_length=1, max_length=100)
    scenario: str = Field(default='operator-readiness', min_length=1, max_length=100)
    risk_brain_hard_block: bool = False


class LaunchConsoleCheck(BaseModel):
    check_id: str
    passed: bool
    detail: str


class LaunchConsoleResult(BaseModel):
    version: str = 'v21.236'
    state: str
    release_candidate: str
    checks: list[LaunchConsoleCheck]
    passed: int
    failed: int
    startup_command: str
    health_endpoint: str
    launch_endpoint: str
    operator_dashboard: str
    demo1_launch_ready: bool
    autonomous_high_risk_execution_enabled: bool = False
    next_action: str
    reasons: list[str] = Field(default_factory=list)
