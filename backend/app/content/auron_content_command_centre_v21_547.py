from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.content.auron_instagram_content_lifecycle_v21_541 import InstagramContentLifecycle
from app.content.auron_instagram_controlled_publish_v21_545 import ControlledInstagramPublishService
from app.content.auron_instagram_draft_preview_approval_v21_543 import InstagramDraftPreviewApprovalPolicy
from app.content.auron_instagram_publish_reconciliation_v21_546 import InstagramPublishReconciliationService
from app.content.auron_instagram_registry_calendar_v21_540 import InstagramContentRegistryCalendar
from app.content.auron_instagram_scheduler_dry_run_v21_544 import InstagramSchedulerDryRun
from app.content.auron_meta_instagram_read_health_v21_542 import InMemoryMetaInstagramReadSource, MetaInstagramReadHealthAdapter


@dataclass(frozen=True)
class RecurringAutomationPolicy:
    automation_id: str
    account_id: str
    enabled: bool
    operator_approved: bool
    cadence: str
    action: str
    created_at: str
    updated_at: str


class ContentCommandCentreService:
    """C8 operational content workspace plus explicitly authorized automation policy.

    Automation policy records permission and cadence only. It never bypasses C4-C7,
    never injects a provider writer, and cannot publish by itself.
    """

    def __init__(self, db_path: str | Path, registry: InstagramContentRegistryCalendar,
                 lifecycle: InstagramContentLifecycle,
                 approvals: InstagramDraftPreviewApprovalPolicy,
                 scheduler: InstagramSchedulerDryRun,
                 publish: ControlledInstagramPublishService,
                 reconciliation: InstagramPublishReconciliationService) -> None:
        self.db_path = str(db_path)
        self.registry = registry
        self.lifecycle = lifecycle
        self.approvals = approvals
        self.scheduler = scheduler
        self.publish = publish
        self.reconciliation = reconciliation
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
            conn.execute('''CREATE TABLE IF NOT EXISTS content_recurring_automation_policies (
                automation_id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                enabled INTEGER NOT NULL, operator_approved INTEGER NOT NULL,
                cadence TEXT NOT NULL, action TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')

    def configure_automation(self, automation_id: str, account_id: str, *, cadence: str,
                             action: str = 'prepare-and-schedule', enabled: bool = False,
                             operator_approved: bool = False) -> RecurringAutomationPolicy:
        if self.registry.get_account(account_id) is None:
            raise KeyError('Instagram account not found')
        if not automation_id.strip() or not cadence.strip():
            raise ValueError('automation_id and cadence are required')
        if action not in {'prepare-only', 'prepare-and-schedule'}:
            raise ValueError('automation action cannot include direct provider publishing')
        now = self._now()
        existing = self.get_automation(automation_id)
        created_at = existing.created_at if existing else now
        with self._connect() as conn:
            conn.execute('''INSERT INTO content_recurring_automation_policies VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(automation_id) DO UPDATE SET account_id=excluded.account_id,
                enabled=excluded.enabled,operator_approved=excluded.operator_approved,
                cadence=excluded.cadence,action=excluded.action,updated_at=excluded.updated_at''',
                (automation_id, account_id, int(enabled), int(operator_approved), cadence.strip(),
                 action, created_at, now))
        result = self.get_automation(automation_id)
        if result is None:
            raise RuntimeError('automation policy persistence failed')
        return result

    def get_automation(self, automation_id: str) -> RecurringAutomationPolicy | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM content_recurring_automation_policies WHERE automation_id=?',
                               (automation_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['enabled'] = bool(data['enabled'])
        data['operator_approved'] = bool(data['operator_approved'])
        return RecurringAutomationPolicy(**data)

    def list_automations(self) -> tuple[RecurringAutomationPolicy, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT automation_id FROM content_recurring_automation_policies ORDER BY automation_id').fetchall()
        return tuple(self.get_automation(row['automation_id']) for row in rows)

    def account_view(self, account_id: str) -> dict:
        account = self.registry.get_account(account_id)
        if account is None:
            raise KeyError('Instagram account not found')
        verification = self.approvals.provider_health.get_verification(account_id)
        scope = self.publish.get_scope(account_id)
        entries = self.registry.list_calendar(account_id=account_id)
        content = []
        alerts: list[str] = []
        for entry in entries:
            lifecycle = self.lifecycle.get(entry.content_id)
            plans = [asdict(p) for p in self.scheduler.list_plans() if p.content_id == entry.content_id]
            publish_decisions = []
            for plan in plans:
                decision = self.publish.get_decision_by_plan(plan['plan_id'])
                if decision:
                    recon = self.reconciliation.get(decision.publish_id)
                    publish_decisions.append({
                        'decision': asdict(decision),
                        'reconciliation': asdict(recon) if recon else None,
                    })
            content.append({
                'calendar': asdict(entry),
                'lifecycle': asdict(lifecycle) if lifecycle else None,
                'dry_run_plans': plans,
                'publish': publish_decisions,
            })
        if verification is None or verification.state != 'verified-read-only':
            alerts.append('provider-read-verification-missing')
        if scope is None:
            alerts.append('publish-scope-missing')
        elif scope.kill_switch:
            alerts.append('publish-kill-switch-active')
        return {
            'account': asdict(account),
            'provider_verification': asdict(verification) if verification else None,
            'publish_scope': asdict(scope) if scope else None,
            'content': content,
            'alerts': alerts,
            'external_calls_made': 0,
        }

    def snapshot(self) -> dict:
        return {
            'brands': [asdict(x) for x in self.registry.list_brands()],
            'accounts': [self.account_view(x.account_id) for x in self.registry.list_accounts()],
            'calendar': [asdict(x) for x in self.registry.list_calendar()],
            'automations': [asdict(x) for x in self.list_automations()],
            'command_input_available': True,
            'provider_write_enabled_by_default': False,
            'recurring_automation_bypasses_approval': False,
            'external_calls_made': 0,
        }


def build_default_content_command_centre() -> ContentCommandCentreService:
    registry = InstagramContentRegistryCalendar(Path(os.getenv('AURON_CONTENT_REGISTRY_DB', '/tmp/auron_content_registry.sqlite3')))
    lifecycle = InstagramContentLifecycle(Path(os.getenv('AURON_CONTENT_LIFECYCLE_DB', '/tmp/auron_content_lifecycle.sqlite3')), registry)
    health = MetaInstagramReadHealthAdapter(Path(os.getenv('AURON_CONTENT_HEALTH_DB', '/tmp/auron_content_health.sqlite3')), registry, InMemoryMetaInstagramReadSource({}))
    approvals = InstagramDraftPreviewApprovalPolicy(Path(os.getenv('AURON_CONTENT_APPROVAL_DB', '/tmp/auron_content_approval.sqlite3')), registry, lifecycle, health)
    scheduler = InstagramSchedulerDryRun(Path(os.getenv('AURON_CONTENT_SCHEDULER_DB', '/tmp/auron_content_scheduler.sqlite3')), registry, lifecycle, approvals)
    publish = ControlledInstagramPublishService(Path(os.getenv('AURON_CONTENT_PUBLISH_DB', '/tmp/auron_content_publish.sqlite3')), lifecycle, approvals, scheduler)
    reconciliation = InstagramPublishReconciliationService(Path(os.getenv('AURON_CONTENT_RECON_DB', '/tmp/auron_content_recon.sqlite3')), publish)
    return ContentCommandCentreService(Path(os.getenv('AURON_CONTENT_COMMAND_DB', '/tmp/auron_content_command.sqlite3')), registry, lifecycle, approvals, scheduler, publish, reconciliation)
