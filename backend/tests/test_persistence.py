from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.persistence import PersistenceRepository


def test_memory_persists_between_sessions(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'jarvis-test.db'}")
    Base.metadata.create_all(engine)
    created_at = datetime.now(timezone.utc)

    with Session(engine) as first_session:
        PersistenceRepository(first_session).save_memory(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "content": "Trade only approved setups.",
                "category": "trading",
                "tags": ["risk"],
                "priority": 90,
                "created_at": created_at,
            }
        )

    with Session(engine) as second_session:
        items = PersistenceRepository(second_session).list_memories()
        assert len(items) == 1
        assert items[0].content == "Trade only approved setups."
        assert items[0].category == "trading"


def test_memory_delete_is_persistent(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'jarvis-delete.db'}")
    Base.metadata.create_all(engine)
    memory_id = "00000000-0000-0000-0000-000000000002"

    with Session(engine) as session:
        repository = PersistenceRepository(session)
        repository.save_memory(
            {
                "id": memory_id,
                "content": "Temporary",
                "category": "project",
                "tags": [],
                "priority": 50,
                "created_at": datetime.now(timezone.utc),
            }
        )
        assert repository.delete_memory(memory_id) is True
        assert repository.list_memories() == []
