import json
import os
from pathlib import Path
from threading import RLock
from uuid import UUID

from .models import WorkflowRecord


class WorkflowStore:
    """Atomic JSON persistence for execution workflows."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("JARVIS_WORKFLOW_STORE", "data/workflows.json")
        self.path = Path(configured)
        self._lock = RLock()

    def load(self) -> dict[UUID, WorkflowRecord]:
        with self._lock:
            if not self.path.exists():
                return {}
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            records = [WorkflowRecord.model_validate(item) for item in raw]
            return {record.id: record for record in records}

    def save(self, workflows: dict[UUID, WorkflowRecord]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            payload = [
                item.model_dump(mode="json")
                for item in sorted(workflows.values(), key=lambda value: value.created_at)
            ]
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(self.path)

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
