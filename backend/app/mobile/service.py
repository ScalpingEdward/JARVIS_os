from __future__ import annotations

import os
from uuid import UUID

from app.approvals.models import ActorRole, ApprovalDecision, ApprovalStatus
from app.approvals.service import ApprovalError, approval_service
from app.orchestrator.models import TaskStatus
from app.orchestrator.service import orchestrator_service
from app.roadmap.service import roadmap_service

from .models import MobileCommand, MobileControlStatus, MobileReply, TelegramUpdate


class MobileControlError(ValueError):
    pass


class MobileControlService:
    """Processes authenticated Telegram commands without exposing secrets."""

    def __init__(self) -> None:
        self._paused = False
        self._override_users: set[int] | None = None

    def reset(self) -> None:
        self._paused = False
        self._override_users = None

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
        parts = update.text.strip().split()
        command_text = parts[0].lstrip("/").lower()
        try:
            command = MobileCommand(command_text)
        except ValueError as exc:
            raise MobileControlError("Unknown command. Use /help") from exc

        if command == MobileCommand.help:
            return self._reply(command, "/status /today /approvals /approve ID /reject ID /pause /resume")
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


mobile_control_service = MobileControlService()
