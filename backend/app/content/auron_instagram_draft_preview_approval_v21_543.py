from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_registry_calendar_v21_540 import InstagramContentRegistryCalendar
from app.content.auron_meta_instagram_read_health_v21_542 import MetaInstagramReadHealthAdapter


class ContentApprovalError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreviewArtifact:
    preview_id: str
    content_id: str
    account_id: str
    revision_version: int
    revision_hash: str
    caption: str
    hashtags: tuple[str, ...]
    asset_uris: tuple[str, ...]
    creative_notes: str
    generated_by: str
    generated_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class PublishApproval:
    approval_id: str
    content_id: str
    account_id: str
    preview_id: str
    revision_version: int
    revision_hash: str
    state: str
    approved_by: str
    reason: str
    approved_at: str
    revoked_at: str | None
    external_calls_made: int = 0


@dataclass(frozen=True)
class PublishAuthorizationDecision:
    content_id: str
    account_id: str
    state: str
    blockers: tuple[str, ...]
    approval_id: str | None
    preview_id: str | None
    external_calls_made: int = 0


class InstagramDraftPreviewApprovalPolicy:
    """C4 separates local content preparation/preview from publish authorization.

    A preview is immutable evidence of one exact C2 revision. Approval is explicit,
    actor-attributed and bound to that exact revision hash. Any later revision makes
    the old approval unusable. This module never publishes and never enables the
    Instagram account's provider-write flag.
    """

    def __init__(self, db_path: str | Path, registry: InstagramContentRegistryCalendar,
                 lifecycle: InstagramContentLifecycle,
                 provider_health: MetaInstagramReadHealthAdapter) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.lifecycle = lifecycle
        self.provider_health = provider_health
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
            conn.execute('''CREATE TABLE IF NOT EXISTS content_previews (
                preview_id TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                revision_version INTEGER NOT NULL,
                revision_hash TEXT NOT NULL,
                caption TEXT NOT NULL,
                hashtags_json TEXT NOT NULL,
                asset_uris_json TEXT NOT NULL,
                creative_notes TEXT NOT NULL,
                generated_by TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_content_previews_content ON content_previews(content_id, generated_at)')
            conn.execute('''CREATE TABLE IF NOT EXISTS content_publish_approvals (
                approval_id TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                preview_id TEXT NOT NULL,
                revision_version INTEGER NOT NULL,
                revision_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                reason TEXT NOT NULL,
                approved_at TEXT NOT NULL,
                revoked_at TEXT,
                external_calls_made INTEGER NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_content_approvals_content ON content_publish_approvals(content_id, approved_at)')

    @staticmethod
    def _preview_id(content_id: str, version: int, revision_hash: str) -> str:
        raw = f'{content_id}:{version}:{revision_hash}:preview'.encode()
        return 'preview:' + hashlib.sha256(raw).hexdigest()[:24]

    @staticmethod
    def _approval_id(content_id: str, preview_id: str, approved_by: str) -> str:
        raw = f'{content_id}:{preview_id}:{approved_by}'.encode()
        return 'approval:' + hashlib.sha256(raw).hexdigest()[:24]

    def generate_preview(self, content_id: str, *, actor: str) -> PreviewArtifact:
        if not actor.strip():
            raise ContentApprovalError('preview actor is required')
        entry = self.registry.get_calendar_entry(content_id)
        if entry is None:
            raise ContentApprovalError('content calendar entry not found')
        record = self.lifecycle.get(content_id)
        if record is None:
            raise ContentApprovalError('content lifecycle not initialized')
        if record.state not in {'draft', 'assets', 'review', 'approved', 'scheduled'}:
            raise ContentApprovalError('content state is not previewable')
        revision = self.lifecycle.get_revision(content_id, record.current_version)
        if revision is None:
            raise ContentApprovalError('current content revision not found')

        preview_id = self._preview_id(content_id, revision.version, revision.integrity_hash)
        existing = self.get_preview(preview_id)
        if existing is not None:
            return existing
        artifact = PreviewArtifact(
            preview_id=preview_id,
            content_id=content_id,
            account_id=entry.account_id,
            revision_version=revision.version,
            revision_hash=revision.integrity_hash,
            caption=revision.caption,
            hashtags=revision.hashtags,
            asset_uris=revision.asset_uris,
            creative_notes=revision.creative_notes,
            generated_by=actor.strip(),
            generated_at=self._now(),
            external_calls_made=0,
        )
        with self._connect() as conn:
            conn.execute('INSERT INTO content_previews VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                artifact.preview_id, artifact.content_id, artifact.account_id,
                artifact.revision_version, artifact.revision_hash, artifact.caption,
                json.dumps(artifact.hashtags), json.dumps(artifact.asset_uris), artifact.creative_notes,
                artifact.generated_by, artifact.generated_at, artifact.external_calls_made,
            ))
        return artifact

    def approve_for_publish(self, content_id: str, *, preview_id: str,
                            approved_by: str, reason: str) -> PublishApproval:
        if not approved_by.strip() or not reason.strip():
            raise ContentApprovalError('approved_by and reason are required')
        preview = self.get_preview(preview_id)
        if preview is None or preview.content_id != content_id:
            raise ContentApprovalError('preview does not belong to content')
        entry = self.registry.get_calendar_entry(content_id)
        record = self.lifecycle.get(content_id)
        if entry is None or record is None:
            raise ContentApprovalError('content state unavailable')
        if record.state not in {'approved', 'scheduled'}:
            raise ContentApprovalError('content must be approved or scheduled before publish authorization')
        revision = self.lifecycle.get_revision(content_id, record.current_version)
        if revision is None:
            raise ContentApprovalError('current revision unavailable')
        if preview.revision_version != revision.version or preview.revision_hash != revision.integrity_hash:
            raise ContentApprovalError('preview is stale; generate a new preview for the current revision')
        verification = self.provider_health.get_verification(entry.account_id)
        if verification is None or verification.state != 'verified-read-only':
            raise ContentApprovalError('provider account must be verified read-only before approval')

        approval_id = self._approval_id(content_id, preview_id, approved_by.strip())
        existing = self.get_approval(approval_id)
        if existing is not None:
            return existing
        approval = PublishApproval(
            approval_id=approval_id,
            content_id=content_id,
            account_id=entry.account_id,
            preview_id=preview.preview_id,
            revision_version=revision.version,
            revision_hash=revision.integrity_hash,
            state='approved-for-scheduler',
            approved_by=approved_by.strip(),
            reason=reason.strip(),
            approved_at=self._now(),
            revoked_at=None,
            external_calls_made=0,
        )
        with self._connect() as conn:
            conn.execute('INSERT INTO content_publish_approvals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                approval.approval_id, approval.content_id, approval.account_id, approval.preview_id,
                approval.revision_version, approval.revision_hash, approval.state,
                approval.approved_by, approval.reason, approval.approved_at,
                approval.revoked_at, approval.external_calls_made,
            ))
        return approval

    def revoke(self, approval_id: str) -> PublishApproval:
        current = self.get_approval(approval_id)
        if current is None:
            raise ContentApprovalError('approval not found')
        if current.state == 'revoked':
            return current
        revoked_at = self._now()
        with self._connect() as conn:
            conn.execute("UPDATE content_publish_approvals SET state='revoked', revoked_at=? WHERE approval_id=?",
                         (revoked_at, approval_id))
        result = self.get_approval(approval_id)
        if result is None:
            raise ContentApprovalError('approval revoke persistence failed')
        return result

    def evaluate_publish_authorization(self, content_id: str) -> PublishAuthorizationDecision:
        entry = self.registry.get_calendar_entry(content_id)
        record = self.lifecycle.get(content_id)
        blockers: list[str] = []
        if entry is None:
            return PublishAuthorizationDecision(content_id, '', 'blocked', ('content-calendar-entry-missing',), None, None, 0)
        if record is None:
            blockers.append('content-lifecycle-missing')
            return PublishAuthorizationDecision(content_id, entry.account_id, 'blocked', tuple(blockers), None, None, 0)
        if record.state not in {'approved', 'scheduled'}:
            blockers.append('content-not-approved-or-scheduled')
        revision = self.lifecycle.get_revision(content_id, record.current_version)
        if revision is None:
            blockers.append('current-revision-missing')
        verification = self.provider_health.get_verification(entry.account_id)
        if verification is None or verification.state != 'verified-read-only':
            blockers.append('provider-read-verification-missing')
        account = self.registry.get_account(entry.account_id)
        if account is None or account.status != 'active':
            blockers.append('instagram-account-not-active')

        approval = self.latest_active_approval(content_id)
        if approval is None:
            blockers.append('explicit-publish-approval-missing')
        elif revision is not None and (
            approval.revision_version != revision.version or approval.revision_hash != revision.integrity_hash
        ):
            blockers.append('publish-approval-stale-for-current-revision')

        state = 'approved-for-scheduler' if not blockers else 'blocked'
        return PublishAuthorizationDecision(
            content_id=content_id,
            account_id=entry.account_id,
            state=state,
            blockers=tuple(dict.fromkeys(blockers)),
            approval_id=approval.approval_id if approval else None,
            preview_id=approval.preview_id if approval else None,
            external_calls_made=0,
        )

    def get_preview(self, preview_id: str) -> PreviewArtifact | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_previews WHERE preview_id=?', (preview_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['hashtags'] = tuple(json.loads(data.pop('hashtags_json')))
        data['asset_uris'] = tuple(json.loads(data.pop('asset_uris_json')))
        return PreviewArtifact(**data)

    def get_approval(self, approval_id: str) -> PublishApproval | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_publish_approvals WHERE approval_id=?', (approval_id,)).fetchone()
        return PublishApproval(**dict(row)) if row else None

    def latest_active_approval(self, content_id: str) -> PublishApproval | None:
        with self._connect() as conn:
            row = conn.execute("SELECT approval_id FROM content_publish_approvals WHERE content_id=? AND state='approved-for-scheduler' ORDER BY approved_at DESC LIMIT 1", (content_id,)).fetchone()
        return self.get_approval(row['approval_id']) if row else None

    def snapshot(self, content_id: str) -> dict:
        decision = self.evaluate_publish_authorization(content_id)
        return {
            'publish_authorization': decision,
            'provider_write_available': False,
            'instagram_publishing_enabled': False,
            'external_calls_made': 0,
        }
