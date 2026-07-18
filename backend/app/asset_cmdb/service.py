from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AssetCmdbStatus, AssetCreate, AssetRecord, AssetState, Criticality,
    MetricsRecord, Mutation, RelationshipCreate, RelationshipRecord,
)


class AssetCmdbService:
    def __init__(self) -> None:
        self.assets: dict[UUID, AssetRecord] = {}
        self.relationships: dict[UUID, RelationshipRecord] = {}
        self.audit: list[dict] = []

    def status(self) -> AssetCmdbStatus:
        return AssetCmdbStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "entity_id": str(entity_id) if entity_id else None,
            "created_at": datetime.now(timezone.utc),
        })

    def create_asset(self, payload: AssetCreate) -> AssetRecord:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.asset_key == payload.asset_key
            for item in self.assets.values()
        )
        if duplicate:
            raise ValueError("asset key already exists in workspace")
        item = AssetRecord(**payload.model_dump())
        self.assets[item.id] = item
        self._audit(item.workspace_id, "asset.created", item.owner_id, item.id)
        return item

    def list_assets(self, workspace_id: str, state: AssetState | None = None) -> list[AssetRecord]:
        return [
            item for item in self.assets.values()
            if item.workspace_id == workspace_id and (state is None or item.state == state)
        ]

    def get_asset(self, asset_id: UUID, workspace_id: str) -> AssetRecord | None:
        item = self.assets.get(asset_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_state(self, asset_id: UUID, workspace_id: str, payload: Mutation, target: AssetState) -> AssetRecord | None:
        item = self.get_asset(asset_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        allowed = {
            AssetState.DRAFT: {AssetState.REGISTERED, AssetState.RETIRED},
            AssetState.REGISTERED: {AssetState.VALIDATED, AssetState.RETIRED},
            AssetState.VALIDATED: {AssetState.ACTIVE, AssetState.RETIRED},
            AssetState.ACTIVE: {AssetState.MAINTENANCE, AssetState.RETIRED},
            AssetState.MAINTENANCE: {AssetState.ACTIVE, AssetState.RETIRED},
            AssetState.RETIRED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid asset lifecycle transition")
        item.state = target
        item.revision += 1
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"asset.{target.value}", payload.requester_id, item.id)
        return item

    def create_relationship(self, payload: RelationshipCreate) -> RelationshipRecord:
        source = self.get_asset(payload.source_asset_id, payload.workspace_id)
        target = self.get_asset(payload.target_asset_id, payload.workspace_id)
        if source is None or target is None:
            raise ValueError("both assets must exist in the same workspace")
        if source.owner_id != payload.requester_id:
            raise ValueError("relationship requester must own the source asset")
        duplicate = any(
            item.workspace_id == payload.workspace_id
            and item.source_asset_id == payload.source_asset_id
            and item.target_asset_id == payload.target_asset_id
            and item.kind == payload.kind
            for item in self.relationships.values()
        )
        if duplicate:
            raise ValueError("asset relationship already exists")
        item = RelationshipRecord(**payload.model_dump())
        self.relationships[item.id] = item
        self._audit(payload.workspace_id, "relationship.created", payload.requester_id, item.id)
        return item

    def list_relationships(self, workspace_id: str, asset_id: UUID | None = None) -> list[RelationshipRecord]:
        return [
            item for item in self.relationships.values()
            if item.workspace_id == workspace_id
            and (asset_id is None or item.source_asset_id == asset_id or item.target_asset_id == asset_id)
        ]

    def metrics(self, workspace_id: str) -> MetricsRecord:
        assets = self.list_assets(workspace_id)
        relationships = self.list_relationships(workspace_id)
        return MetricsRecord(
            workspace_id=workspace_id,
            assets=len(assets),
            active_assets=sum(item.state == AssetState.ACTIVE for item in assets),
            maintenance_assets=sum(item.state == AssetState.MAINTENANCE for item in assets),
            retired_assets=sum(item.state == AssetState.RETIRED for item in assets),
            relationships=len(relationships),
            critical_assets=sum(item.criticality == Criticality.CRITICAL for item in assets),
        )

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [item for item in self.audit if item["workspace_id"] == workspace_id]


asset_cmdb_service = AssetCmdbService()
