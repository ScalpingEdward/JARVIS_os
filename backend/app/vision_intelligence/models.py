from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AssetType(str, Enum):
    IMAGE = "image"
    SCREENSHOT = "screenshot"
    CHART = "chart"
    DOCUMENT_PAGE = "document_page"
    UI_CAPTURE = "ui_capture"
    OTHER = "other"


class AnalysisType(str, Enum):
    CLASSIFY = "classify"
    DETECT_REGIONS = "detect_regions"
    EXTRACT_TEXT = "extract_text"
    ANALYZE_CHART = "analyze_chart"
    ANALYZE_UI = "analyze_ui"
    FULL = "full"


class AnalysisState(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class RegionKind(str, Enum):
    TEXT = "text"
    BUTTON = "button"
    INPUT = "input"
    TABLE = "table"
    CHART = "chart"
    AXIS = "axis"
    LEGEND = "legend"
    IMAGE = "image"
    ICON = "icon"
    PANEL = "panel"
    OTHER = "other"


class BoundingBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def remain_in_frame(self) -> "BoundingBox":
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("bounding box must remain inside normalized image bounds")
        return self


class VisualRegionInput(BaseModel):
    region_id: str = Field(min_length=1, max_length=160)
    kind: RegionKind
    label: str = Field(default="", max_length=1000)
    text: str = Field(default="", max_length=10000)
    confidence: float = Field(default=0.5, ge=0, le=1)
    bounding_box: BoundingBox
    attributes: dict[str, Any] = Field(default_factory=dict)
    sensitive: bool = False


class VisionAssetCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    asset_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=300)
    asset_type: AssetType
    source_reference: str | None = Field(default=None, max_length=2000)
    width: int = Field(ge=1, le=100000)
    height: int = Field(ge=1, le=100000)
    checksum: str = Field(min_length=8, max_length=160)
    supplied_regions: list[VisualRegionInput] = Field(default_factory=list, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_cloud_upload: bool = False
    external_vision_request: bool = False
    external_ocr_request: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "VisionAssetCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_cloud_upload:
            raise ValueError("automatic cloud uploads are disabled")
        if self.external_vision_request:
            raise ValueError("automatic external vision requests are disabled")
        if self.external_ocr_request:
            raise ValueError("automatic external OCR requests are disabled")
        return self


class VisionAssetRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    asset_key: str
    title: str
    asset_type: AssetType
    source_reference: str | None
    width: int
    height: int
    checksum: str
    supplied_regions: list[VisualRegionInput]
    metadata: dict[str, Any]
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    asset_id: UUID
    analysis_type: AnalysisType = AnalysisType.FULL
    objective: str = Field(default="", max_length=5000)
    human_approved: bool = True
    dry_run: bool = True
    use_external_ai: bool = False
    use_external_ocr: bool = False
    upload_asset: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "AnalysisRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run or self.use_external_ai:
            raise ValueError("v8.5 permits supplied-metadata analysis only")
        if self.use_external_ocr:
            raise ValueError("external OCR execution is disabled")
        if self.upload_asset:
            raise ValueError("asset upload to external services is disabled")
        return self


class VisualFinding(BaseModel):
    code: str
    category: str
    description: str
    confidence: float = Field(ge=0, le=1)
    region_id: str | None = None
    citation: str


class ChartInsight(BaseModel):
    chart_type: str = "unknown"
    title: str = ""
    axis_labels: list[str] = Field(default_factory=list)
    legend_labels: list[str] = Field(default_factory=list)
    visible_values: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)


class UIInsight(BaseModel):
    controls: list[str] = Field(default_factory=list)
    forms: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sensitive_regions: list[str] = Field(default_factory=list)


class VisionAnalysisRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    asset_id: UUID
    analysis_type: AnalysisType
    state: AnalysisState
    asset_classification: AssetType
    summary: str = ""
    extracted_text: list[str] = Field(default_factory=list)
    findings: list[VisualFinding] = Field(default_factory=list)
    chart: ChartInsight | None = None
    ui: UIInsight | None = None
    citations: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    external_ai_used: bool = False
    external_ocr_used: bool = False
    external_upload_performed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssetMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_approval(self) -> "AssetMutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VisionIntelligenceStatus(BaseModel):
    service: str = "vision-intelligence"
    version: str = "8.5"
    assets: int
    analyses: int
    completed_analyses: int
    blocked_analyses: int
    supplied_regions: int
    findings: int
    metadata_only_analysis: bool = True
    external_ai_execution: bool = False
    external_ocr_execution: bool = False
    automatic_cloud_uploads: bool = False
