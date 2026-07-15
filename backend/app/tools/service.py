from datetime import datetime, timezone
from uuid import UUID

from .models import ToolInvocation, ToolRecord, ToolRegistration, ToolRisk, ToolRunRecord


class ToolError(ValueError):
    pass


class ToolGatewayService:
    def __init__(self) -> None:
        self._tools: dict[UUID, ToolRecord] = {}
        self._runs: dict[UUID, ToolRunRecord] = {}
        self._seed_defaults()

    def reset(self) -> None:
        self._tools.clear()
        self._runs.clear()
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        defaults = [
            ("GitHub", "github", ["repositories", "issues", "pull_requests"]),
            ("Telegram", "telegram", ["messages", "notifications"]),
            ("Gmail", "gmail", ["email_read", "email_send"]),
            ("Google Calendar", "calendar", ["events_read", "events_write"]),
            ("SSH", "ssh", ["remote_commands"]),
            ("Docker", "docker", ["containers", "images"]),
            ("Filesystem", "filesystem", ["files_read", "files_write"]),
            ("Browser", "browser", ["web_navigation"]),
            ("MT5", "mt5", ["market_data", "trade_execution"]),
            ("Tailscale", "tailscale", ["private_network"]),
        ]
        for name, kind, capabilities in defaults:
            record = ToolRecord(name=name, kind=kind, capabilities=capabilities)
            self._tools[record.id] = record

    def register(self, payload: ToolRegistration) -> ToolRecord:
        record = ToolRecord(**payload.model_dump())
        self._tools[record.id] = record
        return record

    def list_tools(self) -> list[ToolRecord]:
        return sorted(self._tools.values(), key=lambda item: item.name)

    def get(self, tool_id: UUID) -> ToolRecord:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolError("Tool not found")
        return tool

    def set_enabled(self, tool_id: UUID, enabled: bool) -> ToolRecord:
        tool = self.get(tool_id)
        if enabled and not tool.configured:
            raise ToolError("Tool cannot be enabled before configuration")
        tool.enabled = enabled
        return tool

    def invoke(self, payload: ToolInvocation) -> ToolRunRecord:
        tool = self.get(payload.tool_id)
        if not tool.configured or not tool.enabled:
            raise ToolError("Tool is not configured and enabled")
        if payload.risk != ToolRisk.read and not payload.approved:
            run = ToolRunRecord(**payload.model_dump(), status="approval_required")
            self._runs[run.id] = run
            return run

        run = ToolRunRecord(**payload.model_dump(), status="completed")
        run.output = {
            "mode": "adapter_stub",
            "tool": tool.kind.value,
            "action": payload.action,
            "message": "Adapter contract accepted; provider execution is not configured yet.",
        }
        run.finished_at = datetime.now(timezone.utc)
        self._runs[run.id] = run
        return run

    def list_runs(self) -> list[ToolRunRecord]:
        return sorted(self._runs.values(), key=lambda item: item.created_at, reverse=True)


tool_gateway_service = ToolGatewayService()
