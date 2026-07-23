"""Governed lifecycle service for PHOENIX v21.67."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock

from .cross_asset_engine import CrossAssetEngine
from .cross_asset_models import CrossAssetRecord, CrossAssetScore, CrossAssetState


class GovernanceError(ValueError):
    pass


class CrossAssetGovernance:
    """Workspace-isolated in-memory governance boundary.

    The service deliberately exposes no broker, allocation or fund-movement API.
    """

    def __init__(self, engine: CrossAssetEngine | None = None) -> None:
        self._engine = engine or CrossAssetEngine()
        self._records: dict[tuple[str, str], CrossAssetRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._receipts: set[tuple[str, str]] = set()
        self._audit: list[dict[str, object]] = []
        self._lock = RLock()

    def create(self, record: CrossAssetRecord) -> CrossAssetRecord:
        key = (record.workspace_id, record.record_id)
        source_key = (record.workspace_id, record.source_key)
        with self._lock:
            if key in self._records:
                raise GovernanceError("duplicate record_id")
            if source_key in self._source_keys:
                raise GovernanceError("duplicate source_key")
            self._records[key] = record
            self._source_keys.add(source_key)
            self._log(record, "created")
            return record

    def get(self, workspace_id: str, record_id: str) -> CrossAssetRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise GovernanceError("record not found in workspace") from exc

    def score(self, workspace_id: str, record_id: str) -> CrossAssetScore:
        record = self.get(workspace_id, record_id)
        result = self._engine.score(record)
        with self._lock:
            updated = replace(record, state=result.recommended_state)
            self._records[(workspace_id, record_id)] = updated
            self._log(updated, "scored", {"recommended_state": result.recommended_state.value})
        return result

    def approve(self, workspace_id: str, record_id: str, actor: str, receipt: str) -> CrossAssetRecord:
        receipt_key = (workspace_id, receipt)
        with self._lock:
            if receipt_key in self._receipts:
                raise GovernanceError("operation receipt replay detected")
            record = self.get(workspace_id, record_id)
            if record.risk_blocked or record.state in {CrossAssetState.BLOCKED, CrossAssetState.ESCALATED}:
                raise GovernanceError("Risk Brain block is authoritative")
            if not actor.strip():
                raise GovernanceError("human approver is required")
            updated = replace(record, state=CrossAssetState.ACTIVE, approved_by=actor)
            self._records[(workspace_id, record_id)] = updated
            self._receipts.add(receipt_key)
            self._log(updated, "approved", {"actor": actor, "receipt": receipt})
            return updated

    def suspend(self, workspace_id: str, record_id: str, actor: str, receipt: str) -> CrossAssetRecord:
        receipt_key = (workspace_id, receipt)
        with self._lock:
            if receipt_key in self._receipts:
                raise GovernanceError("operation receipt replay detected")
            record = self.get(workspace_id, record_id)
            updated = replace(record, state=CrossAssetState.SUSPENDED)
            self._records[(workspace_id, record_id)] = updated
            self._receipts.add(receipt_key)
            self._log(updated, "suspended", {"actor": actor, "receipt": receipt})
            return updated

    def audit(self, workspace_id: str) -> list[dict[str, object]]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _log(self, record: CrossAssetRecord, event: str, details: dict[str, object] | None = None) -> None:
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "event": event,
            "state": record.state.value,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
