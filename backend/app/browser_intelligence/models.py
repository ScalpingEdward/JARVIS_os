from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, model_validator


class SessionState(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    READ = "read"
    EXTRACT = "extract"
    SCREENSHOT = "screenshot"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    SUBMIT = "submit"
    DOWNLOAD = "download"
    UPLOAD = "upload"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ElementKind(str, Enum):
    LINK = "link"
    BUTTON = "button"
    INPUT = "input"
    SELECT = "select"
    TEXTAREA = "textarea"
    FORM = "form"
    TABLE = "table"
    IMAGE = "image"
    TEXT = "text"
    OTHER = "other"


class BrowserSessionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    session_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    start_url: HttpUrl
    allowed_domains: list[str] = Field(min_length=1, max_length=100)
    maximum_steps: int = Field(default=25, ge=1, le=500)
    human_approved: bool = True
    dry_run: bool = True
    execute_browser: bool = False
    persist_cookies: bool = False
    store_credentials: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "BrowserSessionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run or self.execute_browser:
            raise ValueError("v8.3 permits planning and analysis only")
        if self.persist_cookies or self.store_credentials:
            raise ValueError("cookie persistence and credential storage are disabled")
        return self


class BrowserSessionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    session_key: str
    start_url: str
    current_url: str
    allowed_domains: list[str]
    maximum_steps: int
    state: SessionState = SessionState.PLANNED
    step_count: int = 0
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_approval(self) -> "SessionMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class ElementDescriptor(BaseModel):
    element_id: str = Field(min_length=1, max_length=160)
    kind: ElementKind
    label: str = Field(default="", max_length=1000)
    selector_hint: str = Field(default="", max_length=1000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    visible: bool = True
    enabled: bool = True
    sensitive: bool = False


class PageSnapshotCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    session_id: UUID
    url: HttpUrl
    title: str = Field(default="", max_length=1000)
    text_content: str = Field(default="", max_length=500_000)
    dom_hash: str = Field(min_length=8, max_length=160)
    elements: list[ElementDescriptor] = Field(default_factory=list, max_length=5000)
    screenshot_reference: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    external_fetch_performed: bool = False

    @model_validator(mode="after")
    def enforce_snapshot_safety(self) -> "PageSnapshotCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.external_fetch_performed:
            raise ValueError("external browser fetching is disabled in v8.3")
        return self


class PageSnapshotRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    session_id: UUID
    url: str
    title: str
    text_content: str
    dom_hash: str
    elements: list[ElementDescriptor]
    screenshot_reference: str | None
    metadata: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NavigationStepCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    session_id: UUID
    action: ActionType
    target_url: HttpUrl | None = None
    element_id: str | None = Field(default=None, max_length=160)
    value_preview: str | None = Field(default=None, max_length=2000)
    rationale: str = Field(default="", max_length=5000)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_human_approval: bool = True
    human_approved: bool = False
    dry_run: bool = True
    execute_action: bool = False

    @model_validator(mode="after")
    def enforce_action_safety(self) -> "NavigationStepCreate":
        if not self.dry_run or self.execute_action:
            raise ValueError("real browser actions are disabled in v8.3")
        if self.action in {ActionType.TYPE, ActionType.SUBMIT, ActionType.UPLOAD, ActionType.DOWNLOAD}:
            self.requires_human_approval = True
        return self


class NavigationStepRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    session_id: UUID
    ordinal: int
    action: ActionType
    target_url: str | None
    element_id: str | None
    value_preview: str | None
    rationale: str
    risk_level: RiskLevel
    requires_human_approval: bool
    human_approved: bool
    executed: bool = False
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StepApproval(BaseModel):
    approved: bool
    approved_by: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=1000)


class PageAnalysisRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    snapshot_id: UUID
    objective: str = Field(min_length=1, max_length=5000)
    human_approved: bool = True
    invoke_external_ai: bool = False

    @model_validator(mode="after")
    def enforce_analysis_safety(self) -> "PageAnalysisRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.invoke_external_ai:
            raise ValueError("automatic external AI analysis is disabled")
        return self


class PageAnalysisRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    snapshot_id: UUID
    requester_id: str
    objective: str
    summary: str
    detected_forms: int
    detected_tables: int
    detected_sensitive_elements: int
    suggested_element_ids: list[str] = Field(default_factory=list)
    external_ai_invoked: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrowserAuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: UUID
    detail: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrowserIntelligenceStatus(BaseModel):
    service: str = "browser-intelligence"
    version: str = "8.3"
    sessions: int
    active_sessions: int
    snapshots: int
    planned_steps: int
    approved_steps: int
    analyses: int
    dry_run_only: bool = True
    real_browser_execution: bool = False
    credential_storage: bool = False
    cookie_persistence: bool = False
    automatic_external_ai: bool = False
