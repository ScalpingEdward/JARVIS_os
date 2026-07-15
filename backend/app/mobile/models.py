from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class MobileCommand(StrEnum):
    help = "help"
    status = "status"
    today = "today"
    approvals = "approvals"
    approve = "approve"
    reject = "reject"
    pause = "pause"
    resume = "resume"


class TelegramUpdate(BaseModel):
    telegram_user_id: int
    chat_id: int
    text: str = Field(min_length=1, max_length=2000)


class MobileReply(BaseModel):
    ok: bool
    text: str
    command: MobileCommand | None = None
    sensitive_data_redacted: bool = True


class MobileControlStatus(BaseModel):
    paused: bool
    authorized_users: int
    pending_approvals: int
    active_tasks: int
    blocked_tasks: int


class ApprovalCommand(BaseModel):
    approval_id: UUID
    note: str | None = Field(default=None, max_length=500)
