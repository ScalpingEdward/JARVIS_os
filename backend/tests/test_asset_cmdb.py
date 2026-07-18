import pytest

from app.asset_cmdb.models import (
    AssetCreate, AssetKind, AssetState, Criticality, Environment, Mutation,
    RelationshipCreate, RelationshipKind,
)
from app.asset_cmdb.service import AssetCmdbService


def asset(workspace: str, owner: str, key: str) -> AssetCreate:
    return AssetCreate(
        workspace_id=workspace,
        owner_id=owner,
        asset_key=key,
        name=key,
        kind=AssetKind.VPS,
        environment=Environment.PRODUCTION,
        criticality=Criticality.CRITICAL,
    )


def test_asset_lifecycle_and_metrics() -> None:
    service = AssetCmdbService()
    item = service.create_asset(asset("ws", "owner", "vps-1"))
    mutation = Mutation(requester_id="owner")
    assert service.set_state(item.id, "ws", mutation, AssetState.REGISTERED).state == AssetState.REGISTERED
    assert service.set_state(item.id, "ws", mutation, AssetState.VALIDATED).state == AssetState.VALIDATED
    assert service.set_state(item.id, "ws", mutation, AssetState.ACTIVE).state == AssetState.ACTIVE
    assert service.metrics("ws").active_assets == 1
    assert service.metrics("ws").critical_assets == 1


def test_relationship_requires_same_workspace_and_source_owner() -> None:
    service = AssetCmdbService()
    source = service.create_asset(asset("ws", "owner", "source"))
    target = service.create_asset(asset("ws", "other", "target"))
    relation = service.create_relationship(RelationshipCreate(
        workspace_id="ws",
        requester_id="owner",
        source_asset_id=source.id,
        target_asset_id=target.id,
        kind=RelationshipKind.HOSTS,
    ))
    assert relation.source_asset_id == source.id
    with pytest.raises(ValueError):
        service.create_relationship(RelationshipCreate(
            workspace_id="ws",
            requester_id="other",
            source_asset_id=source.id,
            target_asset_id=target.id,
            kind=RelationshipKind.CONNECTS_TO,
        ))


def test_workspace_isolation_and_duplicate_keys() -> None:
    service = AssetCmdbService()
    first = service.create_asset(asset("a", "owner", "shared"))
    service.create_asset(asset("b", "owner", "shared"))
    assert service.get_asset(first.id, "b") is None
    with pytest.raises(ValueError):
        service.create_asset(asset("a", "owner", "shared"))


def test_safety_controls() -> None:
    with pytest.raises(ValueError):
        AssetCreate(
            workspace_id="ws",
            owner_id="owner",
            asset_key="unsafe",
            name="unsafe",
            kind=AssetKind.VPS,
            environment=Environment.PRODUCTION,
            automatic_discovery=True,
        )
    with pytest.raises(ValueError):
        RelationshipCreate(
            workspace_id="ws",
            requester_id="owner",
            source_asset_id="00000000-0000-0000-0000-000000000001",
            target_asset_id="00000000-0000-0000-0000-000000000001",
            kind=RelationshipKind.DEPENDS_ON,
        )
