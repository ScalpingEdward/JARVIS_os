from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DashboardGovernanceStatus(BaseModel):
    module: str = "dashboard-governance"
    version: str = "11.4"
    status: str = "ready"
    automatic_actions_enabled: bool = False
    external_renderers_enabled: bool = False


class ViewState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class WidgetKind(str, Enum):
    KPI = "kpi"
    STATUS = "status"
    TABLE = "table"
    TIMELINE = "timeline"
    CHART = "chart"
    ALERT_LIST = "alert-list"
    DOMAIN_SUMMARY = "domain-summary"
    TEXT = "text"


class RefreshMode(str, Enum):
    MANUAL = "manual"
    INTERVAL = "interval"


class WidgetDefinition(BaseModel):
    widget_key: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=1, max_length=160)
    kind: WidgetKind
    data_source: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    refresh_mode: RefreshMode = RefreshMode.MANUAL
    refresh_seconds: int | None = Field(default=None, ge=30, le=86400)
    allowed_roles: list[str] = Field(default_factory=list, max_length=20)
    filters: dict[str, str] = Field(default_factory=dict)
    configuration: dict = Field(default_factory=dict)
    execute_action: bool = False

    @model_validator(mode="after")
    def validate_widget(self) -> "WidgetDefinition":
        if self.execute_action:
            raise ValueError("dashboard widgets cannot execute actions")
        if self.refresh_mode == RefreshMode.INTERVAL and self.refresh_seconds is None:
            raise ValueError("interval refresh requires refresh_seconds")
        if self.refresh_mode == RefreshMode.MANUAL and self.refresh_seconds is not None:
            raise ValueError("manual refresh cannot define refresh_seconds")
        return self


class GridPlacement(BaseModel):
    widget_key: str = Field(min_length=2, max_length=100)
    x: int = Field(ge=0, le=23)
    y: int = Field(ge=0, le=999)
    width: int = Field(ge=1, le=24)
    height: int = Field(ge=1, le=50)

    @model_validator(mode="after")
    def validate_bounds(self) -> "GridPlacement":
        if self.x + self.width > 24:
            raise ValueError("widget placement exceeds 24-column grid")
        return self


class DashboardViewCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    owner_id: str = Field(min_length=1, max_length=100)
    view_key: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    audience_roles: list[str] = Field(default_factory=list, max_length=20)
    widgets: list[WidgetDefinition] = Field(default_factory=list, max_length=50)
    layout: list[GridPlacement] = Field(default_factory=list, max_length=50)
    is_default: bool = False
    human_approval_required: bool = True
    execute_action: bool = False

    @model_validator(mode="after")
    def validate_view(self) -> "DashboardViewCreate":
        if self.execute_action:
            raise ValueError("dashboard views cannot execute actions")
        if not self.human_approval_required:
            raise ValueError("human approval must remain required")
        widget_keys = [item.widget_key for item in self.widgets]
        if len(widget_keys) != len(set(widget_keys)):
            raise ValueError("widget keys must be unique within a view")
        layout_keys = [item.widget_key for item in self.layout]
        if len(layout_keys) != len(set(layout_keys)):
            raise ValueError("layout widget keys must be unique")
        if set(layout_keys) != set(widget_keys):
            raise ValueError("layout must reference every widget exactly once")
        return self


class DashboardViewRecord(DashboardViewCreate):
    id: UUID = Field(default_factory=uuid4)
    state: ViewState = ViewState.DRAFT
    version: int = 1
    reviewed_by: str | None = None
    published_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DashboardViewUpdate(BaseModel):
    requester_id: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    audience_roles: list[str] | None = Field(default=None, max_length=20)
    widgets: list[WidgetDefinition] | None = Field(default=None, max_length=50)
    layout: list[GridPlacement] | None = Field(default=None, max_length=50)
    is_default: bool | None = None

    @model_validator(mode="after")
    def validate_update(self) -> "DashboardViewUpdate":
        if (self.widgets is None) != (self.layout is None):
            raise ValueError("widgets and layout must be updated together")
        if self.widgets is not None and self.layout is not None:
            widget_keys = [item.widget_key for item in self.widgets]
            layout_keys = [item.widget_key for item in self.layout]
            if len(widget_keys) != len(set(widget_keys)):
                raise ValueError("widget keys must be unique within a view")
            if len(layout_keys) != len(set(layout_keys)):
                raise ValueError("layout widget keys must be unique")
            if set(widget_keys) != set(layout_keys):
                raise ValueError("layout must reference every widget exactly once")
        return self


class ViewMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=100)


class DashboardGovernanceMetrics(BaseModel):
    workspace_id: str
    total_views: int
    draft_views: int
    review_views: int
    published_views: int
    archived_views: int
    total_widgets: int
    default_views: int
