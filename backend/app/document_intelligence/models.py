from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    CSV = "csv"
    JSON = "json"
    HTML = "html"
    IMAGE = "image"
    OTHER = "other"


class DocumentCategory(str, Enum):
    CONTRACT = "contract"
    INVOICE = "invoice"
    REPORT = "report"
    MANUAL = "manual"
    LEGAL = "legal"
    TRADING = "trading"
    BUSINESS = "business"
    PERSONAL = "personal"
    TECHNICAL = "technical"
    UNKNOWN = "unknown"


class AnalysisType(str, Enum):
    CLASSIFY = "classify"
    SUMMARIZE = "summarize"
    EXTRACT_FIELDS = "extract_fields"
    EXTRACT_TABLES = "extract_tables"
    FIND_RISKS = "find_risks"
    COMPARE = "compare"
    FULL = "full"


class AnalysisState(str, Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class DocumentCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    document_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=300)
    format: DocumentFormat
    version: str = Field(default="1", min_length=1, max_length=80)
    source_reference: str | None = Field(default=None, max_length=2000)
    text_content: str = Field(default="", max_length=2_000_000)
    page_count: int = Field(default=0, ge=0, le=100000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_cloud_upload: bool = False
    external_ocr_request: bool = False

    @model_validator(mode="after")
    def enforce_safety(self) -> "DocumentCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_cloud_upload:
            raise ValueError("automatic cloud uploads are disabled")
        if self.external_ocr_request:
            raise ValueError("automatic external OCR requests are disabled")
        return self


class DocumentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    owner_id: str
    document_key: str
    title: str
    format: DocumentFormat
    version: str
    source_reference: str | None
    text_content: str
    page_count: int
    metadata: dict[str, Any]
    content_hash: str
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FieldDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    required: bool = False


class AnalysisRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    document_id: UUID
    analysis_type: AnalysisType = AnalysisType.FULL
    field_schema: list[FieldDefinition] = Field(default_factory=list, max_length=200)
    comparison_document_id: UUID | None = None
    maximum_summary_sentences: int = Field(default=5, ge=1, le=50)
    human_approved: bool = True
    dry_run: bool = True
    use_external_ai: bool = False
    upload_document: bool = False

    @model_validator(mode="after")
    def enforce_analysis_safety(self) -> "AnalysisRequest":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if not self.dry_run:
            raise ValueError("live (non-dry-run) document mutation from an analysis request is not implemented")
        # use_external_ai was hard-blocked here ("v8.4 permits deterministic
        # local analysis only") with the field itself never wired to any real
        # behavior in service.py -- a fenced-off placeholder, not an active
        # capability. Deliberately unblocked 2026-08-31: AURON's own document
        # analysis may now use a real Anthropic call (ANTHROPIC_API_KEY),
        # same as captions/vision/research elsewhere in this build. The
        # deterministic local analysis remains the default and the fallback
        # when no API key is configured.
        if self.upload_document:
            raise ValueError("document upload to external services is disabled")
        if self.analysis_type == AnalysisType.COMPARE and self.comparison_document_id is None:
            raise ValueError("comparison analysis requires comparison_document_id")
        return self


class ExtractedField(BaseModel):
    name: str
    value: str
    confidence: float = Field(ge=0, le=1)
    confidence_level: ConfidenceLevel
    source_line: int | None = None
    source_excerpt: str = ""


class ExtractedTable(BaseModel):
    title: str = ""
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    source_start_line: int | None = None
    source_end_line: int | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class RiskFinding(BaseModel):
    code: str
    severity: str
    description: str
    source_line: int | None = None
    source_excerpt: str = ""


class DocumentDifference(BaseModel):
    kind: str
    old_text: str = ""
    new_text: str = ""
    old_line: int | None = None
    new_line: int | None = None


class AnalysisRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    requester_id: str
    document_id: UUID
    comparison_document_id: UUID | None = None
    analysis_type: AnalysisType
    state: AnalysisState
    category: DocumentCategory = DocumentCategory.UNKNOWN
    category_confidence: float = Field(default=0.0, ge=0, le=1)
    summary: str = ""
    extracted_fields: list[ExtractedField] = Field(default_factory=list)
    extracted_tables: list[ExtractedTable] = Field(default_factory=list)
    risks: list[RiskFinding] = Field(default_factory=list)
    differences: list[DocumentDifference] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    external_ai_used: bool = False
    external_upload_performed: bool = False
    ai_key_points: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentMutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    human_approved: bool = True
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_approval(self) -> "DocumentMutation":
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


class DocumentIntelligenceStatus(BaseModel):
    service: str = "document-intelligence"
    version: str = "8.4"
    documents: int
    analyses: int
    completed_analyses: int
    blocked_analyses: int
    extracted_fields: int
    extracted_tables: int
    risk_findings: int
    deterministic_local_analysis: bool = True
    external_ai_execution: bool = False
    automatic_cloud_uploads: bool = False
    external_ocr_execution: bool = False
