from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_draft_preview_approval_v21_543 import InstagramDraftPreviewApprovalPolicy
from app.content.auron_instagram_registry_calendar_v21_540 import InstagramContentRegistryCalendar


class ContentSchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class DryRunExecutionPlan:
    plan_id: str
    content_id: str
    account_id: str
    approval_id: str
    revision_version: int
    revision_hash: str
    scheduled_for: str
    state: str
    payload_hash: str
    created_at: str
    external_calls_made: int = 0


class InstagramSchedulerDryRun:
    """C5 deterministic scheduler and dry-run queue.

    Only a currently valid C4 authorization may enter the queue. Plans are bound
    to the exact approved revision and schedule. No Meta/Instagram write exists.
    """

    def __init__(self, db_path: str | Path, registry: InstagramContentRegistryCalendar,
                 lifecycle: InstagramContentLifecycle,
                 approvals: InstagramDraftPreviewApprovalPolicy) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.lifecycle = lifecycle
        self.approvals = approvals
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS content_dry_run_plans (
                plan_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, account_id TEXT NOT NULL,
                approval_id TEXT NOT NULL, revision_version INTEGER NOT NULL,
                revision_hash TEXT NOT NULL, scheduled_for TEXT NOT NULL, state TEXT NOT NULL,
                payload_hash TEXT NOT NULL, created_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL,
                UNIQUE(content_id, revision_version, scheduled_for)
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_dry_run_due ON content_dry_run_plans(state, scheduled_for)')

    @staticmethod
    def _ids(content_id: str, account_id: str, approval_id: str, version: int,
             revision_hash: str, scheduled_for: str) -> tuple[str, str]:
        payload = json.dumps({
            'content_id': content_id, 'account_id': account_id, 'approval_id': approval_id,
            'revision_version': version, 'revision_hash': revision_hash,
            'scheduled_for': scheduled_for,
        }, sort_keys=True, separators=(',', ':'))
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()
        return 'dryrun:' + payload_hash[:24], payload_hash

    def schedule(self, content_id: str) -> DryRunExecutionPlan:
        entry = self.registry.get_calendar_entry(content_id)
        record = self.lifecycle.get(content_id)
        if entry is None or record is None:
            raise ContentSchedulerError('content registry/lifecycle state unavailable')
        if record.state != 'scheduled' or not record.scheduled_for:
            raise ContentSchedulerError('content must be in scheduled lifecycle state')
        authorization = self.approvals.evaluate_publish_authorization(content_id)
        if authorization.state != 'approved-for-scheduler' or authorization.blockers:
            raise ContentSchedulerError('current C4 publish authorization is required')
        revision = self.lifecycle.get_revision(content_id, record.current_version)
        if revision is None:
            raise ContentSchedulerError('current content revision unavailable')
        approval = self.approvals.get_approval(authorization.approval_id)
        if approval is None:
            raise ContentSchedulerError('approval evidence unavailable')
        if approval.revision_version != revision.version or approval.revision_hash != revision.integrity_hash:
            raise ContentSchedulerError('approval no longer matches current revision')

        plan_id, payload_hash = self._ids(content_id, entry.account_id, approval.approval_id,
                                          revision.version, revision.integrity_hash, record.scheduled_for)
        existing = self.get_plan(plan_id)
        if existing is not None:
            return existing
        plan = DryRunExecutionPlan(plan_id, content_id, entry.account_id, approval.approval_id,
                                   revision.version, revision.integrity_hash, record.scheduled_for,
                                   'scheduled-dry-run', payload_hash, self._now(), 0)
        with self._connect() as conn:
            conn.execute('INSERT INTO content_dry_run_plans VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                plan.plan_id, plan.content_id, plan.account_id, plan.approval_id,
                plan.revision_version, plan.revision_hash, plan.scheduled_for, plan.state,
                plan.payload_hash, plan.created_at, plan.external_calls_made))
        return plan

    def due(self, at: datetime | None = None) -> tuple[DryRunExecutionPlan, ...]:
        at = at or datetime.now(timezone.utc)
        cutoff = at.astimezone(timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute('''SELECT plan_id FROM content_dry_run_plans
                                   WHERE state='scheduled-dry-run' AND scheduled_for<=?
                                   ORDER BY scheduled_for, plan_id''', (cutoff,)).fetchall()
        return tuple(self.get_plan(row['plan_id']) for row in rows)

    def simulate(self, plan_id: str, *, at: datetime | None = None) -> DryRunExecutionPlan:
        plan = self.get_plan(plan_id)
        if plan is None:
            raise ContentSchedulerError('dry-run plan not found')
        if plan.state == 'simulated-success':
            return plan
        now = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if datetime.fromisoformat(plan.scheduled_for).astimezone(timezone.utc) > now:
            raise ContentSchedulerError('plan is not due yet')
        authorization = self.approvals.evaluate_publish_authorization(plan.content_id)
        record = self.lifecycle.get(plan.content_id)
        if authorization.state != 'approved-for-scheduler' or authorization.approval_id != plan.approval_id:
            return self._set_state(plan_id, 'blocked-authorization-changed')
        if record is None or record.current_version != plan.revision_version:
            return self._set_state(plan_id, 'blocked-revision-changed')
        revision = self.lifecycle.get_revision(plan.content_id, plan.revision_version)
        if revision is None or revision.integrity_hash != plan.revision_hash:
            return self._set_state(plan_id, 'blocked-integrity-mismatch')
        return self._set_state(plan_id, 'simulated-success')

    def _set_state(self, plan_id: str, state: str) -> DryRunExecutionPlan:
        with self._connect() as conn:
            conn.execute('UPDATE content_dry_run_plans SET state=? WHERE plan_id=?', (state, plan_id))
        result = self.get_plan(plan_id)
        if result is None:
            raise ContentSchedulerError('dry-run plan persistence failed')
        return result

    def get_plan(self, plan_id: str) -> DryRunExecutionPlan | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_dry_run_plans WHERE plan_id=?', (plan_id,)).fetchone()
        return DryRunExecutionPlan(**dict(row)) if row else None

    def list_plans(self, *, state: str | None = None) -> tuple[DryRunExecutionPlan, ...]:
        with self._connect() as conn:
            if state is None:
                rows = conn.execute('SELECT plan_id FROM content_dry_run_plans ORDER BY scheduled_for, plan_id').fetchall()
            else:
                rows = conn.execute('SELECT plan_id FROM content_dry_run_plans WHERE state=? ORDER BY scheduled_for, plan_id', (state,)).fetchall()
        return tuple(self.get_plan(row['plan_id']) for row in rows)
