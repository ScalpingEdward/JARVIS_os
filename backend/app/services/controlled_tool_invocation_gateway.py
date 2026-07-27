from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.controlled_tool_invocation_gateway import (
    ToolInvocationCreate,
    ToolInvocationRecord,
    ToolInvocationResult,
    ToolInvocationScores,
    ToolInvocationState,
)


PROTECTED_OPERATIONS = {
    "fund-movement",
    "withdraw-funds",
    "order-submit",
    "trade-execute",
    "credential-mutation",
    "permission-escalation",
    "disable-safety-control",
}


class ControlledToolInvocationGatewayService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ToolInvocationRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "controlled-tool-invocation-gateway",
            "version": "21.118",
            "gateway_enabled": True,
            "dispatch_contract_enabled": True,
            "embedded_external_network_invocation_enabled": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "credential_mutation_enabled": False,
            "permission_escalation_enabled": False,
            "human_approval_required": True,
            "explicit_authorization_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ToolInvocationCreate) -> ToolInvocationRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        invocation = payload.invocation
        flags: List[str] = []
        policy_checks = 5
        passed = 0

        if invocation.tool_name in payload.allowed_tools:
            passed += 1
        else:
            flags.append("tool-not-allowed")

        if invocation.operation in payload.allowed_operations:
            passed += 1
        else:
            flags.append("operation-not-allowed")

        if invocation.operation in payload.denied_operations:
            flags.append("denied-operation")
        else:
            passed += 1

        if invocation.target_host and payload.allowed_hosts:
            if invocation.target_host not in payload.allowed_hosts:
                flags.append("host-not-allowed")
            else:
                passed += 1
        else:
            passed += 1

        if invocation.estimated_cost > payload.max_cost:
            flags.append("cost-limit-breach")
        elif invocation.timeout_seconds > payload.max_timeout_seconds:
            flags.append("timeout-limit-breach")
        else:
            passed += 1

        protected = invocation.operation in PROTECTED_OPERATIONS
        if protected:
            flags.extend(["protected-operation", "risk-brain-hard-block"])

        if invocation.side_effect_level in {"high", "critical"} and not invocation.human_approval_required:
            flags.append("missing-human-approval-requirement")

        if not invocation.dry_run_verified and invocation.side_effect_level != "read-only":
            flags.append("dry-run-not-verified")

        side_effect_assurance = 1.0
        if invocation.side_effect_level == "medium":
            side_effect_assurance = 0.8
        elif invocation.side_effect_level == "high":
            side_effect_assurance = 0.55
        elif invocation.side_effect_level == "critical":
            side_effect_assurance = 0.2

        residual = min(
            1.0,
            (1 - passed / policy_checks) * 0.45
            + (1 - side_effect_assurance) * 0.35
            + (0.2 if protected else 0.0),
        )
        scores = ToolInvocationScores(
            policy_coverage=round(passed / policy_checks, 4),
            authorization_assurance=1.0 if invocation.human_approval_required else 0.6,
            adapter_binding_assurance=1.0 if invocation.adapter_id else 0.0,
            side_effect_assurance=round(side_effect_assurance, 4),
            residual_risk=round(residual, 4),
        )

        state = ToolInvocationState.BLOCKED if "risk-brain-hard-block" in flags else ToolInvocationState.REVIEW_REQUIRED
        record = ToolInvocationRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            invocation=invocation,
            scores=scores,
            risk_flags=sorted(set(flags)),
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[ToolInvocationRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ToolInvocationRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> ToolInvocationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        if "risk-brain-hard-block" in record.risk_flags and action not in {"revoke", "archive", "cancel"}:
            raise ValueError("Risk Brain hard block is authoritative")

        if action == "approve":
            if record.risk_flags:
                raise ValueError("unresolved gateway findings block approval")
            updated = record.model_copy(update={"state": ToolInvocationState.APPROVED, "approved_by": actor, "version": record.version + 1})
        elif action == "authorize":
            if record.state != ToolInvocationState.APPROVED:
                raise ValueError("human approval required before authorization")
            updated = record.model_copy(update={"state": ToolInvocationState.AUTHORIZED, "authorized_by": actor, "version": record.version + 1})
        elif action == "prepare-dispatch":
            if record.state != ToolInvocationState.AUTHORIZED:
                raise ValueError("explicit authorization required before dispatch preparation")
            token = hashlib.sha256(f"{record.record_id}:{operation_id}:{uuid4()}".encode()).hexdigest()
            updated = record.model_copy(update={"state": ToolInvocationState.DISPATCH_READY, "dispatch_token": token, "version": record.version + 1})
        elif action == "mark-dispatched":
            if record.state != ToolInvocationState.DISPATCH_READY or not record.dispatch_token:
                raise ValueError("dispatch-ready contract required")
            updated = record.model_copy(update={"state": ToolInvocationState.DISPATCHED, "version": record.version + 1})
        elif action == "cancel":
            updated = record.model_copy(update={"state": ToolInvocationState.CANCELLED, "version": record.version + 1})
        elif action == "revoke":
            updated = record.model_copy(update={"state": ToolInvocationState.REVOKED, "version": record.version + 1})
        elif action == "archive":
            updated = record.model_copy(update={"state": ToolInvocationState.ARCHIVED, "version": record.version + 1})
        else:
            raise ValueError("unsupported action")

        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._audit_event(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def ingest_result(self, record_id: str, payload: ToolInvocationResult) -> ToolInvocationRecord:
        receipt = (payload.workspace_id, payload.operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")
        record = self.get(payload.workspace_id, record_id)
        if record.state != ToolInvocationState.DISPATCHED:
            raise ValueError("result accepted only for dispatched invocation")
        if payload.adapter_id != record.invocation.adapter_id:
            raise ValueError("adapter identity mismatch")

        state = {
            "succeeded": ToolInvocationState.SUCCEEDED,
            "failed": ToolInvocationState.FAILED,
            "timed-out": ToolInvocationState.TIMED_OUT,
        }[payload.status]
        updated = record.model_copy(update={
            "state": state,
            "result_status": payload.status,
            "result_digest": payload.output_digest,
            "version": record.version + 1,
        })
        self._records[(payload.workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._audit_event(updated, f"result:{payload.status}", payload.adapter_id, payload.operation_id, {"duration_ms": payload.duration_ms, "cost": payload.cost})
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [item for item in self._audit if item["workspace_id"] == workspace_id]

    def _audit_event(self, record: ToolInvocationRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append({
            "audit_id": str(uuid4()),
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        })


controlled_tool_invocation_gateway_service = ControlledToolInvocationGatewayService()
