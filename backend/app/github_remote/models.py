from pydantic import BaseModel, Field


class GitHubRemoteConfig(BaseModel):
    api_url: str = Field(default="https://api.github.com", min_length=8, max_length=500)
    token_env: str = Field(default="GITHUB_TOKEN", min_length=1, max_length=100)
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)


class RemoteExecutionResponse(BaseModel):
    success: bool
    message: str
    workspace_id: str
    branch_name: str
    commit_sha: str | None = None
    pull_request_number: int | None = None
    pull_request_url: str | None = None
    ci_state: str | None = None
