from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.communications.auron_communications_policy_approval_v21_551 import (
    CommunicationsPolicyApprovalService,
)
from app.communications.auron_communications_registry_state_v21_549 import (
    CommunicationsRegistryStateStore,
)


class CommunicationsSimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommunicationsDryRunPlan:
    plan_id: str
    intent_id: str
    channel_id: str
    approval_id: str
    content_hash: str
    kind: str
    conversation_id: str | None
    recipients: tuple[str, ...]
    subject: str
    payload_hash: str
    state: str
    created_at: str
    external_calls_made: int = 0


@dataclass(frozen=True)
class CommunicationsSimulationResult:
    plan_id: str
    intent_id: str
    state: str
    blockers: tuple[str, ...]
    simulated_sender: str
    simulated_recipients: tuple[str, ...]
    rendered_subject: str
    rendered_body: str
    payload_hash: str
    simulated_at: str
    outbound_execution_enabled: bool = False
    external_calls_made: int = 0


class CommunicationsSimulationDryRunService:
    """D5 deterministic dry-run consuming only currently valid D4 approvals.

    Plans are bound to the exact approval, content hash and normalized outbound payload.
    Simulation revalidates approval and channel/conversation state immediately before
    producing a result. This module has no provider write/send/reply boundary.
    """

    def __init__(self, db_path: str | Path, store: CommunicationsRegistryStateStore,
                 approvals: CommunicationsPolicyApprovalService) -> None:
        self.db_path = str(db_path)
        self.store = store
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
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_dry_run_plans (
                plan_id TEXT PRIMARY KEY, intent_id TEXT UNIQUE NOT NULL,
                channel_id TEXT NOT NULL, approval_id TEXT NOT NULL,
                content_hash TEXT NOT NULL, kind TEXT NOT NULL,
                conversation_id TEXT, recipients_json TEXT NOT NULL,
                subject TEXT NOT NULL, payload_hash TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL,
                external_calls_made INTEGER NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS communications_simulation_results (
                plan_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, state TEXT NOT NULL,
                blockers_json TEXT NOT NULL, simulated_sender TEXT NOT NULL,
                simulated_recipients_json TEXT NOT NULL, rendered_subject TEXT NOT NULL,
                rendered_body TEXT NOT NULL, payload_hash TEXT NOT NULL,
                simulated_at TEXT NOT NULL, outbound_execution_enabled INTEGER NOT NULL,
                external_calls_made INTEGER NOT NULL)''')

    @staticmethod
    def _payload_hash(intent, approval_id: str) -> str:
        payload = json.dumps({
            'intent_id': intent.intent_id,
            'channel_id': intent.channel_id,
            'approval_id': approval_id,
            'content_hash': intent.content_hash,
            'kind': intent.kind,
            'conversation_id': intent.conversation_id,
            'recipients': intent.recipients,
            'subject': intent.subject,
            'body_text': intent.body_text,
        }, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _plan_id(intent_id: str, payload_hash: str) -> str:
        return 'comms-dryrun:' + hashlib.sha256(f'{intent_id}:{payload_hash}'.encode()).hexdigest()[:24]

    def create_plan(self, intent_id: str) -> CommunicationsDryRunPlan:
        decision = self.approvals.evaluate(intent_id)
        if decision.state != 'ready-for-simulation' or decision.blockers or not decision.approval_id:
            raise CommunicationsSimulationError('current D4 approval is required')
        intent = self.approvals.get_intent(intent_id)
        if intent is None:
            raise CommunicationsSimulationError('outbound intent not found')
        channel = self.store.get_channel(intent.channel_id)
        if channel is None or channel.status != 'active':
            raise CommunicationsSimulationError('active communications channel required')
        if intent.kind == 'reply' and (
            not intent.conversation_id or self.store.get_conversation(intent.conversation_id) is None
        ):
            raise CommunicationsSimulationError('reply conversation unavailable')

        payload_hash = self._payload_hash(intent, decision.approval_id)
        plan_id = self._plan_id(intent.intent_id, payload_hash)
        existing = self.get_plan_by_intent(intent.intent_id)
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise CommunicationsSimulationError('existing dry-run plan is stale for current payload')
            return existing

        plan = CommunicationsDryRunPlan(
            plan_id=plan_id,
            intent_id=intent.intent_id,
            channel_id=intent.channel_id,
            approval_id=decision.approval_id,
            content_hash=intent.content_hash,
            kind=intent.kind,
            conversation_id=intent.conversation_id,
            recipients=intent.recipients,
            subject=intent.subject,
            payload_hash=payload_hash,
            state='planned',
            created_at=self._now(),
            external_calls_made=0,
        )
        with self._connect() as conn:
            conn.execute('INSERT INTO communications_dry_run_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                plan.plan_id, plan.intent_id, plan.channel_id, plan.approval_id,
                plan.content_hash, plan.kind, plan.conversation_id,
                json.dumps(plan.recipients), plan.subject, plan.payload_hash,
                plan.state, plan.created_at, plan.external_calls_made,
            ))
        return plan

    def simulate(self, plan_id: str) -> CommunicationsSimulationResult:
        existing_result = self.get_result(plan_id)
        if existing_result is not None:
            return existing_result
        plan = self.get_plan(plan_id)
        if plan is None:
            raise CommunicationsSimulationError('dry-run plan not found')

        blockers: list[str] = []
        decision = self.approvals.evaluate(plan.intent_id)
        intent = self.approvals.get_intent(plan.intent_id)
        channel = self.store.get_channel(plan.channel_id)

        if decision.state != 'ready-for-simulation' or decision.blockers:
            blockers.append('current-d4-approval-required')
        if decision.approval_id != plan.approval_id:
            blockers.append('approval-changed')
        if intent is None:
            blockers.append('intent-missing')
        else:
            if intent.content_hash != plan.content_hash:
                blockers.append('content-hash-changed')
            current_payload_hash = self._payload_hash(intent, plan.approval_id)
            if current_payload_hash != plan.payload_hash:
                blockers.append('payload-integrity-mismatch')
        if channel is None or channel.status != 'active':
            blockers.append('channel-not-active')
        if plan.kind == 'reply' and (
            not plan.conversation_id or self.store.get_conversation(plan.conversation_id) is None
        ):
            blockers.append('reply-conversation-missing')

        sender = channel.address if channel else ''
        recipients = intent.recipients if intent else plan.recipients
        subject = intent.subject if intent else plan.subject
        body = intent.body_text if intent else ''
        state = 'simulated-success' if not blockers else 'blocked'
        result = CommunicationsSimulationResult(
            plan_id=plan.plan_id,
            intent_id=plan.intent_id,
            state=state,
            blockers=tuple(dict.fromkeys(blockers)),
            simulated_sender=sender,
            simulated_recipients=recipients,
            rendered_subject=subject,
            rendered_body=body,
            payload_hash=plan.payload_hash,
            simulated_at=self._now(),
            outbound_execution_enabled=False,
            external_calls_made=0,
        )
        with self._connect() as conn:
            conn.execute('INSERT INTO communications_simulation_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                result.plan_id, result.intent_id, result.state, json.dumps(result.blockers),
                result.simulated_sender, json.dumps(result.simulated_recipients),
                result.rendered_subject, result.rendered_body, result.payload_hash,
                result.simulated_at, int(result.outbound_execution_enabled),
                result.external_calls_made,
            ))
            conn.execute('UPDATE communications_dry_run_plans SET state=? WHERE plan_id=?',
                         (result.state, plan.plan_id))
        return result

    def get_plan(self, plan_id: str) -> CommunicationsDryRunPlan | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_dry_run_plans WHERE plan_id=?', (plan_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['recipients'] = tuple(json.loads(data.pop('recipients_json')))
        return CommunicationsDryRunPlan(**data)

    def get_plan_by_intent(self, intent_id: str) -> CommunicationsDryRunPlan | None:
        with self._connect() as conn:
            row = conn.execute('SELECT plan_id FROM communications_dry_run_plans WHERE intent_id=?', (intent_id,)).fetchone()
        return self.get_plan(row['plan_id']) if row else None

    def get_result(self, plan_id: str) -> CommunicationsSimulationResult | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM communications_simulation_results WHERE plan_id=?', (plan_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['blockers'] = tuple(json.loads(data.pop('blockers_json')))
        data['simulated_recipients'] = tuple(json.loads(data.pop('simulated_recipients_json')))
        data['outbound_execution_enabled'] = bool(data['outbound_execution_enabled'])
        return CommunicationsSimulationResult(**data)
