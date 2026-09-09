from __future__ import annotations

import os
from uuid import UUID

from app.account_intake.models import AccountIntakeRefusal
from app.account_intake.service import AccountIntakeError, account_intake_service
from app.approvals.models import ActorRole, ApprovalDecision, ApprovalStatus
from app.approvals.service import ApprovalError, approval_service
from app.orchestrator.models import TaskStatus
from app.orchestrator.service import orchestrator_service
from app.roadmap.service import roadmap_service

from .models import MobileCommand, MobileControlStatus, MobileReply, TelegramUpdate

#: Words that confirm a pending account proposal -- deliberately not a
#: MobileCommand (see MobileReply.command: MobileCommand | None -- these
#: replies are honestly reported as command=None, since they were never a
#: recognized fixed command).
_CONFIRMATION_WORDS = {"confirmed", "confirm", "yes", "ja", "bestätigt", "bestaetigt"}


class MobileControlError(ValueError):
    pass


class MobileControlService:
    """Processes authenticated Telegram commands without exposing secrets."""

    def __init__(self) -> None:
        self._paused = False
        self._override_users: set[int] | None = None
        #: telegram_user_id -> the most recent unconfirmed account
        #: proposal id for that user. One at a time, deliberately -- a
        #: second free-text account instruction before confirming the
        #: first just replaces it, same as any other single pending state
        #: in this codebase.
        self._pending_account_proposals: dict[int, UUID] = {}

    def reset(self) -> None:
        self._paused = False
        self._override_users = None
        self._pending_account_proposals = {}

    def set_authorized_users(self, users: set[int]) -> None:
        self._override_users = set(users)

    def authorized_users(self) -> set[int]:
        if self._override_users is not None:
            return set(self._override_users)
        raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
        return {int(value.strip()) for value in raw.split(",") if value.strip().isdigit()}

    def handle(self, update: TelegramUpdate) -> MobileReply:
        if update.telegram_user_id not in self.authorized_users():
            raise MobileControlError("Telegram user is not authorized")
        text = update.text.strip()
        parts = text.split()
        command_text = parts[0].lstrip("/").lower()

        if command_text in _CONFIRMATION_WORDS and update.telegram_user_id in self._pending_account_proposals:
            return self._confirm_pending_account(update.telegram_user_id)

        try:
            command = MobileCommand(command_text)
        except ValueError:
            return self._try_account_intake(text, update.telegram_user_id)

        if command == MobileCommand.help:
            return self._reply(command, "/status /today /approvals /approve ID /reject ID /pause /resume\n\nOr just tell me about a new trading account in plain text (broker, login, server, strategy) -- never a password, see /help.")
        if command == MobileCommand.status:
            status = self.status()
            return self._reply(command, f"Paused: {status.paused} | active: {status.active_tasks} | blocked: {status.blocked_tasks} | approvals: {status.pending_approvals}")
        if command == MobileCommand.today:
            plans = []
            for roadmap in list(roadmap_service._items.values()):
                plan = roadmap_service.today(roadmap.id, capacity_hours=8)
                plans.append(f"{roadmap.title}: {len(plan.task_ids)} task(s), {plan.estimated_hours}h")
            return self._reply(command, "\n".join(plans) if plans else "No roadmaps available")
        if command == MobileCommand.approvals:
            pending = approval_service.list(ApprovalStatus.pending)
            text = "\n".join(f"{item.id} | {item.action} | {item.risk}" for item in pending)
            return self._reply(command, text or "No pending approvals")
        if command in {MobileCommand.approve, MobileCommand.reject}:
            if len(parts) != 2:
                raise MobileControlError(f"Usage: /{command.value} APPROVAL_ID")
            try:
                approval_id = UUID(parts[1])
            except ValueError as exc:
                raise MobileControlError("Approval ID must be a valid UUID") from exc
            return self._decide(command, approval_id, update.telegram_user_id)
        if command == MobileCommand.pause:
            self._paused = True
            return self._reply(command, "Agent execution paused. Read-only status commands remain available.")
        if command == MobileCommand.resume:
            self._paused = False
            return self._reply(command, "Agent execution resumed.")
        raise MobileControlError("Unsupported command")

    def status(self) -> MobileControlStatus:
        tasks = orchestrator_service.list_tasks()
        return MobileControlStatus(
            paused=self._paused,
            authorized_users=len(self.authorized_users()),
            pending_approvals=len(approval_service.list(ApprovalStatus.pending)),
            active_tasks=sum(task.status in {TaskStatus.assigned, TaskStatus.in_progress} for task in tasks),
            blocked_tasks=sum(task.status == TaskStatus.blocked for task in tasks),
        )

    def execution_allowed(self) -> bool:
        return not self._paused

    def _decide(self, command: MobileCommand, approval_id: UUID, user_id: int) -> MobileReply:
        decision = ApprovalDecision(actor=f"telegram:{user_id}", role=ActorRole.admin, note="Decision from authorized Telegram control")
        try:
            if command == MobileCommand.approve:
                approval_service.approve(approval_id, decision)
                return self._reply(command, f"Approval {approval_id} approved. Confirmation token is intentionally not sent to Telegram.")
            approval_service.reject(approval_id, decision)
            return self._reply(command, f"Approval {approval_id} rejected.")
        except ApprovalError as exc:
            raise MobileControlError(str(exc)) from exc

    @staticmethod
    def _reply(command: MobileCommand, text: str) -> MobileReply:
        return MobileReply(ok=True, text=text, command=command, sensitive_data_redacted=True)

    def _try_account_intake(self, text: str, user_id: int) -> MobileReply:
        """Reached only when the message did not match any known /command
        -- tries it as a free-text trading-account instruction instead of
        immediately giving up. account_intake_service.propose() itself
        runs the credential-language check before anything else (see
        credential_guard.py); nothing here needs to repeat that.
        """
        requester_id = f"telegram:{user_id}"
        try:
            result = account_intake_service.propose(text, requester_id)
        except AccountIntakeError:
            # No AI extraction available right now (e.g. no API key
            # configured) -- degrade to the plain, original behavior
            # rather than a confusing internal error for what might just
            # be a typo'd command.
            raise MobileControlError("Unknown command. Use /help") from None

        if isinstance(result, AccountIntakeRefusal):
            return MobileReply(ok=False, text=result.reason, command=None, sensitive_data_redacted=True)

        fields = result.fields
        if not (fields.broker or fields.login or fields.server):
            # Nothing account-shaped was actually found -- this almost
            # certainly wasn't an account instruction at all; say so the
            # same way an unrecognized command always has.
            raise MobileControlError("Unknown command. Use /help")

        self._pending_account_proposals[user_id] = result.id
        lines = [
            f"Proposed account: {fields.label}",
            f"Broker: {fields.broker or '(missing)'}",
            f"Login: {fields.login or '(missing)'}",
            f"Server: {fields.server or '(missing)'}",
            f"Type: {fields.account_type}",
            f"Strategy: {fields.strategy_id or '(none)'}",
        ]
        if result.missing_fields:
            lines.append(f"\nMissing: {', '.join(result.missing_fields)} -- resend with these included.")
        else:
            lines.append("\nReply 'confirmed' to register this account. Nothing is registered yet.")
        return MobileReply(ok=True, text="\n".join(lines), command=None, sensitive_data_redacted=True)

    def _confirm_pending_account(self, user_id: int) -> MobileReply:
        proposal_id = self._pending_account_proposals.pop(user_id)
        try:
            record = account_intake_service.confirm(proposal_id, f"telegram:{user_id}")
        except AccountIntakeError as exc:
            raise MobileControlError(str(exc)) from exc
        return MobileReply(
            ok=True, command=None, sensitive_data_redacted=True,
            text=f"Account registered: {record.label} ({record.broker}, login {record.login}, {record.account_type.value}).",
        )


mobile_control_service = MobileControlService()
