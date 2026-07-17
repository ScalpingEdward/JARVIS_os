import pytest
from pydantic import ValidationError

from app.memory_engine.models import (
    MemoryCreate,
    MemoryQuery,
    MemoryState,
    MemoryStateChange,
    MemoryType,
    MemoryUpdate,
    MemoryVisibility,
)
from app.memory_engine.service import MemoryEngineService


def payload(**overrides) -> MemoryCreate:
    values = {
        "workspace_id": "brano-workspace",
        "owner_id": "brano",
        "title": "XAUUSD risk preference",
        "content": "Use one percent risk only for premium XAUUSD setups.",
        "memory_type": MemoryType.PREFERENCE,
        "visibility": MemoryVisibility.PRIVATE,
        "tags": ["Trading", "XAUUSD", "risk"],
        "source": "manual",
        "importance": 0.9,
        "confidence": 1.0,
    }
    values.update(overrides)
    return MemoryCreate(**values)


def test_create_normalizes_memory_and_reports_status() -> None:
    service = MemoryEngineService()
    record = service.create(payload())
    assert record.tags == ["risk", "trading", "xauusd"]
    assert record.workspace_id == "brano-workspace"
    assert service.status().active_memories == 1


def test_search_ranks_relevant_memory_and_tracks_access() -> None:
    service = MemoryEngineService()
    preferred = service.create(payload())
    service.create(
        payload(
            title="Instagram cadence",
            content="Prepare four posts per day.",
            tags=["instagram", "content"],
            importance=0.4,
        )
    )
    results = service.search(
        MemoryQuery(
            workspace_id="brano-workspace",
            requester_id="brano",
            query="XAUUSD premium risk",
            tags=["risk"],
        )
    )
    assert results[0].memory.id == preferred.id
    assert results[0].relevance_score > 0.5
    assert preferred.access_count == 1


def test_private_memory_is_isolated_by_owner_and_workspace() -> None:
    service = MemoryEngineService()
    record = service.create(payload())
    assert service.get(record.id, "other-workspace", "brano") is None
    assert service.get(record.id, "brano-workspace", "other-user") is None
    assert service.get(record.id, "brano-workspace", "brano") == record


def test_workspace_memory_can_be_read_but_only_owner_can_update() -> None:
    service = MemoryEngineService()
    record = service.create(payload(visibility=MemoryVisibility.WORKSPACE))
    assert service.get(record.id, "brano-workspace", "team-member") == record
    assert service.update(
        record.id,
        "brano-workspace",
        "team-member",
        MemoryUpdate(title="Unauthorized change"),
    ) is None
    updated = service.update(
        record.id,
        "brano-workspace",
        "brano",
        MemoryUpdate(title="Updated risk preference"),
    )
    assert updated is not None
    assert updated.title == "Updated risk preference"


def test_related_archive_restore_and_delete_lifecycle() -> None:
    service = MemoryEngineService()
    first = service.create(payload())
    second = service.create(
        payload(
            title="Risk lesson",
            content="Reduce exposure after daily drawdown.",
            related_memory_ids=[first.id],
            memory_type=MemoryType.LESSON,
        )
    )
    related = service.related(second.id, "brano-workspace", "brano")
    assert related == [first]
    archived = service.archive(
        first.id,
        "brano-workspace",
        "brano",
        MemoryStateChange(reason="Temporarily inactive"),
    )
    assert archived is not None and archived.state == MemoryState.ARCHIVED
    restored = service.restore(
        first.id,
        "brano-workspace",
        "brano",
        MemoryStateChange(reason="Needed again"),
    )
    assert restored is not None and restored.state == MemoryState.ACTIVE
    deleted = service.delete(
        first.id,
        "brano-workspace",
        "brano",
        MemoryStateChange(reason="User requested deletion"),
    )
    assert deleted is not None and deleted.state == MemoryState.DELETED
    assert deleted.content == "[deleted]"
    assert service.get(first.id, "brano-workspace", "brano") is None


def test_unsafe_or_unapproved_mutations_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload(automatic_external_action=True)
    with pytest.raises(ValidationError):
        payload(human_approved=False)
    with pytest.raises(ValidationError):
        MemoryUpdate(title="Blocked", human_approved=False)
    with pytest.raises(ValidationError):
        MemoryStateChange(reason="Blocked", human_approved=False)
