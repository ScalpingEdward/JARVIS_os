from pydantic import BaseModel, Field


class PackagingReadinessRequest(BaseModel):
    workspace_id: str = Field(default='demo', min_length=1, max_length=100)
    operator_id: str = Field(default='operator', min_length=1, max_length=100)
    scenario: str = Field(default='operator-readiness', min_length=1, max_length=100)
    risk_brain_hard_block: bool = False


class StartupCheck(BaseModel):
    check_id: str
    passed: bool
    detail: str
    required: bool = True


class PackagingReadinessResult(BaseModel):
    version: str = 'v21.234'
    state: str
    workspace_id: str
    operator_id: str
    checks: list[StartupCheck]
    passed: int
    failed: int
    package_manifest: dict[str, str]
    startup_command: str
    health_endpoint: str
    environment: str
    operator_acceptance_ready: bool
    release_packaging_ready: bool
    autonomous_high_risk_execution_enabled: bool = False
    reasons: list[str] = Field(default_factory=list)
