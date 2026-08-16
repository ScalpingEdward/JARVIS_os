from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_draft_preview_approval_v21_543 import InstagramDraftPreviewApprovalPolicy
from app.content.auron_instagram_scheduler_dry_run_v21_544 import InstagramSchedulerDryRun


class ControlledPublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishScope:
    account_id: str
    enabled: bool
    operator_approved: bool
    kill_switch: bool
    updated_at: str


@dataclass(frozen=True)
class PublishDecision:
    publish_id: str
    plan_id: str
    content_id: str
    account_id: str
    revision_version: int
    revision_hash: str
    state: str
    blockers: tuple[str, ...]
    provider_media_id: str | None
    created_at: str
    external_calls_made: int = 0


class InstagramProviderWriteBoundary(Protocol):
    def publish(self, *, content_id: str, account_id: str, revision_version: int,
                revision_hash: str, idempotency_key: str) -> str: ...


class DisabledInstagramProviderWriteBoundary:
    def publish(self, **kwargs) -> str:
        raise ControlledPublishError('Instagram provider write boundary is disabled')


class ControlledInstagramPublishService:
    """C6 explicit provider-write boundary after a successful C5 dry run.

    Default construction cannot publish. A real writer must be deliberately injected,
    while current C4 authorization, exact revision, explicit scope and kill switch are
    revalidated immediately before the provider boundary.
    """

    def __init__(self, db_path: str | Path, lifecycle: InstagramContentLifecycle,
                 approvals: InstagramDraftPreviewApprovalPolicy,
                 scheduler: InstagramSchedulerDryRun,
                 writer: InstagramProviderWriteBoundary | None = None) -> None:
        self.db_path = str(db_path)
        self.lifecycle = lifecycle
        self.approvals = approvals
        self.scheduler = scheduler
        self.writer = writer or DisabledInstagramProviderWriteBoundary()
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
            conn.execute('''CREATE TABLE IF NOT EXISTS instagram_publish_scopes (
                account_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,
                operator_approved INTEGER NOT NULL, kill_switch INTEGER NOT NULL,
                updated_at TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS instagram_publish_decisions (
                publish_id TEXT PRIMARY KEY, plan_id TEXT UNIQUE NOT NULL,
                content_id TEXT NOT NULL, account_id TEXT NOT NULL,
                revision_version INTEGER NOT NULL, revision_hash TEXT NOT NULL,
                state TEXT NOT NULL, blockers_json TEXT NOT NULL,
                provider_media_id TEXT, created_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL)''')

    def configure_scope(self, account_id: str, *, enabled: bool = False,
                        operator_approved: bool = False,
                        kill_switch: bool = True) -> PublishScope:
        now = self._now()
        with self._connect() as conn:
            conn.execute('''INSERT INTO instagram_publish_scopes VALUES (?,?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET enabled=excluded.enabled,
                operator_approved=excluded.operator_approved,
                kill_switch=excluded.kill_switch,updated_at=excluded.updated_at''',
                (account_id, int(enabled), int(operator_approved), int(kill_switch), now))
        return self.get_scope(account_id)

    def get_scope(self, account_id: str) -> PublishScope | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM instagram_publish_scopes WHERE account_id=?', (account_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        for key in ('enabled', 'operator_approved', 'kill_switch'):
            data[key] = bool(data[key])
        return PublishScope(**data)

    @staticmethod
    def _publish_id(plan_id: str) -> str:
        return 'publish:' + hashlib.sha256(plan_id.encode()).hexdigest()[:24]

    def evaluate(self, plan_id: str) -> PublishDecision:
        existing = self.get_decision_by_plan(plan_id)
        if existing is not None:
            return existing
        plan = self.scheduler.get_plan(plan_id)
        if plan is None:
            raise ControlledPublishError('C5 dry-run plan not found')
        blockers: list[str] = []
        if plan.state != 'simulated-success':
            blockers.append('successful-dry-run-required')
        authorization = self.approvals.evaluate_publish_authorization(plan.content_id)
        if authorization.state != 'approved-for-scheduler' or authorization.approval_id != plan.approval_id:
            blockers.append('current-publish-authorization-required')
        record = self.lifecycle.get(plan.content_id)
        if record is None or record.state != 'scheduled':
            blockers.append('content-not-scheduled')
        elif record.current_version != plan.revision_version:
            blockers.append('content-revision-changed')
        revision = self.lifecycle.get_revision(plan.content_id, plan.revision_version)
        if revision is None or revision.integrity_hash != plan.revision_hash:
            blockers.append('content-integrity-mismatch')
        scope = self.get_scope(plan.account_id)
        if scope is None:
            blockers.append('publish-scope-missing')
        else:
            if not scope.enabled:
                blockers.append('publish-scope-disabled')
            if not scope.operator_approved:
                blockers.append('operator-approval-required')
            if scope.kill_switch:
                blockers.append('publish-kill-switch-active')
        state = 'ready-for-controlled-publish' if not blockers else 'blocked'
        decision = PublishDecision(
            self._publish_id(plan.plan_id), plan.plan_id, plan.content_id, plan.account_id,
            plan.revision_version, plan.revision_hash, state, tuple(dict.fromkeys(blockers)),
            None, self._now(), 0,
        )
        self._persist(decision)
        return decision

    def execute(self, plan_id: str) -> PublishDecision:
        decision = self.evaluate(plan_id)
        if decision.state != 'ready-for-controlled-publish':
            return decision
        try:
            provider_media_id = self.writer.publish(
                content_id=decision.content_id,
                account_id=decision.account_id,
                revision_version=decision.revision_version,
                revision_hash=decision.revision_hash,
                idempotency_key=decision.publish_id,
            )
        except ControlledPublishError:
            return self._replace(decision, 'provider-write-disabled', ('provider-write-disabled',), None, 0)
        except Exception:
            return self._replace(decision, 'provider-error', ('provider-write-error',), None, 1)
        return self._replace(decision, 'provider-submitted', (), provider_media_id, 1)

    def _persist(self, decision: PublishDecision) -> None:
        with self._connect() as conn:
            conn.execute('INSERT INTO instagram_publish_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                decision.publish_id, decision.plan_id, decision.content_id, decision.account_id,
                decision.revision_version, decision.revision_hash, decision.state,
                json.dumps(decision.blockers), decision.provider_media_id,
                decision.created_at, decision.external_calls_made,
            ))

    def _replace(self, old: PublishDecision, state: str, blockers: tuple[str, ...],
                 provider_media_id: str | None, calls: int) -> PublishDecision:
        result = PublishDecision(old.publish_id, old.plan_id, old.content_id, old.account_id,
                                 old.revision_version, old.revision_hash, state, blockers,
                                 provider_media_id, old.created_at, calls)
        with self._connect() as conn:
            conn.execute('''UPDATE instagram_publish_decisions SET state=?,blockers_json=?,
                provider_media_id=?,external_calls_made=? WHERE publish_id=?''',
                (state, json.dumps(blockers), provider_media_id, calls, old.publish_id))
        return result

    def get_decision_by_plan(self, plan_id: str) -> PublishDecision | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM instagram_publish_decisions WHERE plan_id=?', (plan_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['blockers'] = tuple(json.loads(data.pop('blockers_json')))
        return PublishDecision(**data)
