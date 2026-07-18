from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class AssetKind(str, Enum):
    SERVER = "server"
    VPS = "vps"
    WORKSTATION = "workstation"
    CONTAINER = "container"
    VM = "vm"
    SERVICE = "service"
    DATABASE = "database"
    API = "api"
    STORAGE = "storage"
    BROKER = "broker"
    MT4 = "mt4"
    MT5 = "mt5"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    GITHUB = "github"
    AI_MODEL = "ai-model"
    AGENT = "agent"


class AssetState(str, Enum):
    DRAFT = "draft"
    REGISTERED = "registered"
    VALIDATED = "validated"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class Environment(str, Enum):
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Criticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RelationshipKind(str, Enum):
    HOSTS = "hosts"
    RUNS_ON = "runs-on"
    CONNECTS_TO = "connects-to"
    DEPENDS_ON = "depends-on"
    STORES_DATA_IN = "stores-data-in"
    MONITORS = "monitors"
    MANAGED_BY = "managed-by"
    BACKED_UP_TO = "backed-up-to"


class AssetCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    owner_id: str = Field(min_length=1, max_length=120)
    asset_key: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=300)
    kind: AssetKind
    environment: Environment
    criticality: Criticality = Criticality.MEDIUM
    version: str = Field(default="", max_length=200)
    operating_system: str = Field(default="", max_length=300)
    network_zone: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=300)
    responsible_party: str = Field(default="", max_length=300)
    maintenance_window: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)
    human_approved: bool = True
    automatic_discovery: bool = False
    apply_change: bool = False

    @model_validator(mode="after")
    def safety(self) -> "AssetCreate":
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.automatic_discovery:
            raise ValueError("automatic asset discovery is disabled")
        if self.apply_change:
            raise ValueError("asset records never apply system changes")
        return self


class AssetRecord(AssetCreate):
    id: UUID = Field(default_factory=uuid4)
    state: AssetState = AssetState.DRAFT
    revision: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RelationshipCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    requester_id: str = Field(min_length=1, max_length=120)
    source_asset_id: UUID
    target_asset_id: UUID
    kind: RelationshipKind
    description: str = Field(default="", max_length=4000)
    human_approved: bool = True
    execute_action: bool = False

    @model_validator(mode="after")
    def safety(self) -> "RelationshipCreate":
        if self.source_asset_id == self.target_asset_id:
            raise ValueError("self-relationships are not allowed")
        if not self.human_approved:
            raise ValueError("human approval is required")
        if self.execute_action:
            raise ValueError("CMDB relationships never execute actions")
        return self


class RelationshipRecord(RelationshipCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mutation(BaseModel):
    requester_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=4000)
    human_approved: bool = True

    @model_validator(mode="after")
    def require_human(self) -> "Mutation":
        if not self.human_approved:
            raise ValueError("human approval is required")
        return self


class MetricsRecord(BaseModel):
    workspace_id: str
    assets: int
    active_assets: int
    maintenance_assets: int
    retired_assets: int
    relationships: int
    critical_assets: int


class AssetCmdbStatus(BaseModel):
    version: str = "10.9"
    automatic_discovery: bool = False
    network_scanning: bool = False
    system_mutation: bool = False
    external_inventory: bool = False
    human_approval_required: bool = True
