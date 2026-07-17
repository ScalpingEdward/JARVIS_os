from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class SessionState(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class ActionType(str, Enum):
    OBSERVE = "observe"
    FOCUS_WINDOW = "focus_window"
    MOVE_POINTER = "move_pointer"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    DRAG = "drag"
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    SAVE = "save"
    DELETE = "delete"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ElementKind(str, Enum):
    WINDOW = "window"
    BUTTON = "button"
    INPUT = "input"
    MENU = "menu"
    TAB = "tab"
    TABLE = "table"
    DIALOG = "dialog"
    ICON = "icon"
    TEXT = "text"
    OTHER = "other"


class DesktopElement(BaseModel):
    element_id: str = Field(min_length=1, max_length=160)
    kind: ElementKind
    label: str = Field(default="", max_length=1000)
    app_name: str = Field(default="", max_length=300)
    window_title: str = Field(default="", max_length=1000)
    visible: bool = True
    enabled: bool = True
    sensitive: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class DesktopSessionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    session_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    allowed_applications: list[str] = Field(min_length=1, max_length=100)
    maximum_steps: int = Field(default=50, ge=1, le=1000)
    human_approved: bool = True
    dry_run: bool = True
    execute_desktop: bool = False
    capture_credentials: bool = False
    persist_clipboard: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "DesktopSessionCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run or self.execute_desktop:
            raise ValueError("v8.6 permits planning and analysis only")
        if self.capture_credentials or self.persist_clipboard:
            raise ValueError("credential capture and clipboard persistence are disabled")
        return self


class DesktopSessionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    session_key: str
    allowed_applications: list[str]
    maximum_steps: int
    state: SessionState = SessionState.PLANNED
    step_count: int = 0
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DesktopSnapshotCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    session_id: UUID
    active_application: str = Field(min_length=1, max_length=300)
    active_window_title: str = Field(default="", max_length=1000)
    screenshot_reference: str | None = Field(default=None, max_length=2000)
    snapshot_hash: str = Field(min_length=8, max_length=160)
    elements: list[DesktopElement] = Field(default_factory=list, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    live_capture_performed: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "DesktopSnapshotCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.live_capture_performed:
            raise ValueError("live desktop capture is disabled in v8.6")
        return self


class DesktopSnapshotRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    session_id: UUID
    active_application: str
    active_window_title: str
    screenshot_reference: str | None
    snapshot_hash: str
    elements: list[DesktopElement]
    metadata: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DesktopActionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    session_id: UUID
    action: ActionType
    target_application: str = Field(default="", max_length=300)
    target_element_id: str | None = Field(default=None, max_length=160)
    value_preview: str | None = Field(default=None, max_length=2000)
    rationale: str = Field(default="", max_length=5000)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_human_approval: bool = True
    human_approved: bool = False
    dry_run: bool = True
    execute_action: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "DesktopActionCreate":
        if not self.dry_run or self.execute_action:
            raise ValueError("real desktop actions are disabled in v8.6")
        return self


class DesktopActionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    session_id: UUID
    action: ActionType
    target_application: str
    target_element_id: str | None
    value_preview: str | None
    rationale: str
    risk_level: RiskLevel
    requires_human_approval: bool
    approved: bool = False
    executed: bool = False
    blocked_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequest(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    approved: bool
    reason: str = Field(default="", max_length=1000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "ApprovalRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class SessionMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_human(self) -> "SessionMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class DesktopAuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DesktopIntelligenceStatus(BaseModel):
    service: str = "desktop-intelligence"
    version: str = "8.6"
    sessions: int
    snapshots: int
    actions: int
    approved_actions: int
    blocked_actions: int
    planning_only: bool = True
    real_desktop_execution: bool = False
    credential_capture: bool = False
    clipboard_persistence: bool = False
