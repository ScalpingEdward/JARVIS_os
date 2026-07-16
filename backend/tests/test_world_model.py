from app.world_model.models import (
    EntityKind,
    EntityState,
    RelationCreate,
    RelationKind,
    WorldEntityCreate,
    WorldEventCreate,
)
from app.world_model.service import world_model_service


def setup_function() -> None:
    world_model_service.reset()


def test_world_model_propagates_critical_blocker() -> None:
    news = world_model_service.upsert_entity(
        WorldEntityCreate(kind=EntityKind.research_event, external_id="us-news", name="US High Impact News")
    )
    setup = world_model_service.upsert_entity(
        WorldEntityCreate(kind=EntityKind.trading_setup, external_id="xau-1", name="XAUUSD Setup")
    )
    world_model_service.add_relation(
        RelationCreate(source_id=news.id, target_id=setup.id, kind=RelationKind.blocks, reason="News risk")
    )

    event = world_model_service.ingest_event(
        WorldEventCreate(event_type="high_impact_news", entity_id=news.id, severity=5, summary="CPI in five minutes")
    )

    assert world_model_service.get_entity(news.id).state == EntityState.blocked
    assert world_model_service.get_entity(setup.id).state == EntityState.blocked
    assert any("XAUUSD Setup blocked" in item for item in event.consequences)


def test_world_snapshot_disables_automatic_execution() -> None:
    snapshot = world_model_service.snapshot()
    assert snapshot.automatic_order_execution is False
    assert snapshot.automatic_merge is False
