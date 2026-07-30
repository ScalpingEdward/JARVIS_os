from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from datetime import datetime, timezone

from app.schemas.phoenix_demo1_approval_inbox_v21_228 import (
    ApprovalInboxCreate,
    ApprovalInboxRecord,
    DeferredRecoveryRequest,
    DeferredRecoveryResult,
    InboxStatus,
)


class ApprovalInboxError(ValueError):
    pass


class PersistentApprovalInbox:
    """Small durable Demo 1 inbox. Persistence is JSON-on-disk with atomic replacement."""

    def __init__(self, path: str | None = None) -> None:
        configured = path or os.getenv('PHOENIX_DEMO1_APPROVAL_INBOX_PATH', '.phoenix/demo1_approval_inbox.json')
        self.path = Path(configured)
        self._lock = RLock()
        self._items: dict[str, ApprovalInboxRecord] = {}
        self._load()

    def upsert(self, payload: ApprovalInboxCreate) -> ApprovalInboxRecord:
        with self._lock:
            existing = self._items.get(payload.approval_id)
            if existing is not None:
                same_identity = (
                    existing.session_id == payload.session_id
                    and existing.workspace_id == payload.workspace_id
                    and existing.operator_id == payload.operator_id
                    and existing.command == payload.command
                )
                if not same_identity:
                    raise ApprovalInboxError('approval_id reuse with different request identity')
                return existing
            now = datetime.now(timezone.utc)
            state = 'blocked' if payload.risk_brain_hard_block else payload.state
            data = payload.model_dump()
            data['state'] = state
            record = ApprovalInboxRecord(**data, updated_at=now)
            self._items[record.approval_id] = record
            self._persist()
            return record

    def list(self, state: str | None = None) -> list[ApprovalInboxRecord]:
        with self._lock:
            items = list(self._items.values())
            if state is not None:
                items = [item for item in items if item.state == state]
            return sorted(items, key=lambda item: item.created_at, reverse=True)

    def recover_deferred(self, req: DeferredRecoveryRequest) -> DeferredRecoveryResult:
        recovered: list[ApprovalInboxRecord] = []
        still_deferred: list[ApprovalInboxRecord] = []
        blocked: list[ApprovalInboxRecord] = []
        changed = False
        with self._lock:
            for record in self._items.values():
                if record.state != 'deferred':
                    continue
                if req.risk_brain_hard_block:
                    record.state = 'blocked'
                    record.updated_at = req.now
                    blocked.append(record)
                    changed = True
                    continue
                window_open = record.deferred_until is None or req.now >= record.deferred_until
                if req.interaction_available and window_open:
                    record.state = 'pending'
                    record.recovery_count += 1
                    record.updated_at = req.now
                    recovered.append(record)
                    changed = True
                else:
                    still_deferred.append(record)
            if changed:
                self._persist()
        return DeferredRecoveryResult(recovered=recovered, still_deferred=still_deferred, blocked=blocked)

    def resolve(self, approval_id: str) -> ApprovalInboxRecord:
        with self._lock:
            record = self._items.get(approval_id)
            if record is None:
                raise ApprovalInboxError('approval inbox record not found')
            if record.state == 'blocked':
                raise ApprovalInboxError('blocked approval inbox record cannot be resolved')
            record.state = 'resolved'
            record.updated_at = datetime.now(timezone.utc)
            self._persist()
            return record

    def status(self) -> InboxStatus:
        counts = {state: 0 for state in ('pending', 'deferred', 'resolved', 'blocked')}
        for item in self.list():
            counts[item.state] += 1
        return InboxStatus(
            persistent=True,
            storage_path=str(self.path),
            pending=counts['pending'], deferred=counts['deferred'],
            resolved=counts['resolved'], blocked=counts['blocked'],
        )

    def reset_for_tests(self) -> None:
        with self._lock:
            self._items.clear()
            if self.path.exists():
                self.path.unlink()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            self._items = {item['approval_id']: ApprovalInboxRecord.model_validate(item) for item in raw}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ApprovalInboxError(f'cannot load persistent approval inbox: {exc}') from exc

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        payload = [item.model_dump(mode='json') for item in self._items.values()]
        tmp.write_text(json.dumps(payload, sort_keys=True, separators=(',', ':')), encoding='utf-8')
        tmp.replace(self.path)


approval_inbox_service = PersistentApprovalInbox()
