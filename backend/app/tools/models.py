from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ToolKind(StrEnum):
    github = "github"
    telegram = "telegram"
    gmail = "gmail"
    calendar = "calendar"
    ssh = "ssh"
    docker = "docker"
    filesystem = "filesystem"
    browser = "browser"
    mt5 = "mt5"
    tailscale = "tailscale"


class ToolRisk(StrEnum):
    read = "read"
    write = "write"
    privileged = "privileged"
    financial = "financial"


class ToolRegistration(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: ToolKind
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = False
    configured: bool = False


class ToolRecord(ToolRegistration):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolInvocation(BaseModel):
    tool_id: UUID
    action: str = Field(min_length=1, max_length=200)
    arguments: dict = Field(default_factory=dict)
    risk: ToolRisk = ToolRisk.read
    approved: bool = False
    requested_by: str = Field(default="jarvis", min_length=1, max_length=100)


class ToolRunRecord(ToolInvocation):
    id: UUID = Field(default_factory=uuid4)
    status: str
    output: dict | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class ToolListResponse(BaseModel):
    items: list[ToolRecord]
    count: int


class ToolRunListResponse(BaseModel):
    items: list[ToolRunRecord]
    count: int
