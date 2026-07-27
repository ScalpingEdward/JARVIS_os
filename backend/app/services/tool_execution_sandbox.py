from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.tool_execution_sandbox import (
    SandboxExecutionState,
    SideEffectLevel,
    ToolExecutionReceipt,
    ToolExecutionRecord,
    ToolExecutionRequest,
    ToolExecutionResult,
)


class ToolExecutionSandboxService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ToolExecutionRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []
        self._kill_switch_engaged = False

    def status(self) -> dict:
        return {
            "module": "tool-execution-sandbox",
            "version": "21.116",
            "sandbox_enabled": True,
            "external_adapter_execution_enabled": False,
            "dry_run_default": True,
            "kill_switch_supported": True,
            "kill_switch_engaged": self._kill_switch_engaged,
            "human_approval_required_for_mutation": True,
            "trading_execution_enabled": False,
            "fund_movement_enabled": False,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ToolExecutionRequest) -> ToolExecutionRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        flags = self._risk_flags(payload)
        state = SandboxExecutionState.BLOCKED if "risk-brain-hard-block" in flags else SandboxExecutionState.REVIEW_REQUIRED
        record = ToolExecutionRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, request=payload, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[ToolExecutionRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ToolExecutionRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> ToolExecutionRecord:
        self._reject_replay(workspace_id, operation_id)
        record = self.get(workspace_id, record_id)
        if self._kill_switch_engaged and action not in {"cancel", "revoke", "archive"}:
            raise ValueError("sandbox kill switch engaged")
        if action == "approve":
            if record.risk_flags:
                raise ValueError("unresolved sandbox findings block approval")
            record = record.model_copy(update={"state": SandboxExecutionState.APPROVED, "approved_by": actor, "version": record.version + 1})
        elif action == "authorize":
            if record.state != SandboxExecutionState.APPROVED:
                raise ValueError("human approval required before authorization")
            record = record.model_copy(update={"state": SandboxExecutionState.READY, "authorization_token_id": str(uuid4()), "version": record.version + 1})
        elif action == "start":
            if record.state != SandboxExecutionState.READY:
                raise ValueError("execution record is not ready")
            if not record.request.dry_run:
                raise ValueError("external adapter execution is not enabled in v21.116")
            receipt = ToolExecutionReceipt(
                receipt_id=str(uuid4()), record_id=record.record_id, tool_name=record.request.tool_name,
                operation=record.request.operation, status="running", started_at=datetime.now(timezone.utc).isoformat(),
                dry_run=True,
            )
            record = record.model_copy(update={"state": SandboxExecutionState.RUNNING, "receipt": receipt, "version": record.version + 1})
        elif action == "cancel":
            record = record.model_copy(update={"state": SandboxExecutionState.CANCELLED, "version": record.version + 1})
        elif action == "revoke":
            record = record.model_copy(update={"state": SandboxExecutionState.REVOKED, "authorization_token_id": None, "version": record.version + 1})
        elif action == "archive":
            record = record.model_copy(update={"state": SandboxExecutionState.ARCHIVED, "version": record.version + 1})
        elif action == "engage-kill-switch":
            self._kill_switch_engaged = True
            record = record.model_copy(update={"state": SandboxExecutionState.BLOCKED, "version": record.version + 1})
        else:
            raise ValueError("unsupported action")
        self._records[(workspace_id, record_id)] = record
        self._operations.add((workspace_id, operation_id))
        self._audit_event(record, action, actor, operation_id, {"reason": reason} if reason else {})
        return record

    def record_result(self, record_id: str, result: ToolExecutionResult) -> ToolExecutionRecord:
        self._reject_replay(result.workspace_id, result.operation_id)
        record = self.get(result.workspace_id, record_id)
        if record.state != SandboxExecutionState.RUNNING or record.receipt is None:
            raise ValueError("record is not running")
        if result.call_count > record.request.max_calls:
            raise ValueError("tool call limit exceeded")
        if result.budget_used > record.request.budget_units:
            raise ValueError("sandbox budget exceeded")
        status_map = {
            "succeeded": SandboxExecutionState.SUCCEEDED,
            "failed": SandboxExecutionState.FAILED,
            "timed-out": SandboxExecutionState.TIMED_OUT,
        }
        if result.status not in status_map:
            raise ValueError("unsupported result status")
        receipt = record.receipt.model_copy(update={
            "status": result.status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "call_count": result.call_count,
            "budget_used": result.budget_used,
            "output_digest": result.output_digest,
            "error": result.error,
        })
        updated = record.model_copy(update={"state": status_map[result.status], "receipt": receipt, "version": record.version + 1})
        self._records[(result.workspace_id, record_id)] = updated
        self._operations.add((result.workspace_id, result.operation_id))
        self._audit_event(updated, f"result:{result.status}", "sandbox-adapter", result.operation_id)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _risk_flags(self, payload: ToolExecutionRequest) -> List[str]:
        flags: List[str] = []
        if payload.confidence < 0.70:
            flags.append("confidence-below-threshold")
        if payload.side_effect_level in {SideEffectLevel.HIGH, SideEffectLevel.CRITICAL}:
            flags.append("high-side-effect-review-required")
        if payload.max_calls > 25:
            flags.append("excessive-tool-call-limit")
        if payload.timeout_seconds > 300:
            flags.append("extended-timeout-review")
        forbidden = {"move-funds", "submit-order", "execute-trade", "modify-credentials", "disable-safety-controls"}
        if payload.operation in forbidden:
            flags.append("risk-brain-hard-block")
        if payload.side_effect_level == SideEffectLevel.CRITICAL and payload.confidence < 0.90:
            flags.append("risk-brain-hard-block")
        return sorted(set(flags))

    def _reject_replay(self, workspace_id: str, operation_id: str) -> None:
        if (workspace_id, operation_id) in self._operations:
            raise ValueError("operation replay detected")

    def _audit_event(self, record: ToolExecutionRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append({
            "audit_id": str(uuid4()), "workspace_id": record.workspace_id, "record_id": record.record_id,
            "action": action, "actor": actor, "operation_id": operation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(), "metadata": metadata or {},
        })


tool_execution_sandbox_service = ToolExecutionSandboxService()
