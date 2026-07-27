from __future__ import annotations

from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.tool_adapter_registry import (
    ToolAdapterMatch,
    ToolAdapterMatchRequest,
    ToolAdapterRegistryCreate,
    ToolAdapterRegistryRecord,
    ToolAdapterState,
)


class ToolAdapterRegistryService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ToolAdapterRegistryRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "tool-adapter-registry-controlled-connector-runtime",
            "version": "21.117",
            "registry_enabled": True,
            "adapter_matching_enabled": True,
            "connector_invocation_enabled": False,
            "credential_material_exposure_enabled": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ToolAdapterRegistryCreate) -> ToolAdapterRegistryRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        flags: List[str] = []
        adapter = payload.adapter
        if adapter.health_score < payload.min_health_score:
            flags.append("adapter-health-below-threshold")
        if adapter.reliability_score < payload.min_reliability_score:
            flags.append("adapter-reliability-below-threshold")
        if adapter.side_effect_level != "read-only" and not adapter.requires_human_approval:
            flags.append("mutable-adapter-without-human-approval")
        if adapter.credential_reference and any(x.lower() in adapter.credential_reference.lower() for x in ["password=", "secret=", "token="]):
            flags.append("credential-material-must-not-be-inline")
        protected = {"fund-movement", "order-submit", "trade-execute", "credential-mutation", "disable-safety-controls"}
        if protected & set(adapter.supported_operations):
            flags.append("risk-brain-hard-block")

        state = ToolAdapterState.BLOCKED if "risk-brain-hard-block" in flags else ToolAdapterState.REVIEW_REQUIRED
        record = ToolAdapterRegistryRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, adapter=adapter, risk_flags=sorted(set(flags)),
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit.append({"workspace_id": payload.workspace_id, "record_id": record.record_id, "action": "create", "actor": payload.requested_by})
        return record

    def list(self, workspace_id: str) -> List[ToolAdapterRegistryRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ToolAdapterRegistryRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> ToolAdapterRegistryRecord:
        op = (workspace_id, operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "approve": ToolAdapterState.APPROVED,
            "activate": ToolAdapterState.ACTIVE,
            "degrade": ToolAdapterState.DEGRADED,
            "suspend": ToolAdapterState.SUSPENDED,
            "revoke": ToolAdapterState.REVOKED,
            "archive": ToolAdapterState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved adapter findings block approval")
        if action == "activate" and record.state != ToolAdapterState.APPROVED:
            raise ValueError("human approval required before activation")
        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operations.add(op)
        self._audit.append({"workspace_id": workspace_id, "record_id": record_id, "action": action, "actor": actor, "operation_id": operation_id, "reason": reason})
        return updated

    def match(self, request: ToolAdapterMatchRequest) -> List[ToolAdapterMatch]:
        matches: List[ToolAdapterMatch] = []
        for record in self.list(request.workspace_id):
            reasons: List[str] = []
            adapter = record.adapter
            if record.state != ToolAdapterState.ACTIVE:
                reasons.append("adapter-not-active")
            if request.tool not in adapter.supported_tools:
                reasons.append("tool-not-supported")
            if request.operation not in adapter.supported_operations:
                reasons.append("operation-not-supported")
            if request.operation in adapter.denied_operations:
                reasons.append("operation-denied")
            if not set(request.permission_scopes).issubset(set(adapter.permission_scopes)):
                reasons.append("permission-scope-mismatch")
            if request.data_domain and request.data_domain not in adapter.data_domains:
                reasons.append("data-domain-mismatch")
            if request.require_side_effects and adapter.side_effect_level == "read-only":
                reasons.append("side-effects-not-supported")
            matches.append(ToolAdapterMatch(
                record_id=record.record_id, adapter_id=adapter.adapter_id,
                adapter_version=adapter.adapter_version, eligible=not reasons, reasons=reasons,
            ))
        return matches

    def audit(self, workspace_id: str) -> List[dict]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]


tool_adapter_registry_service = ToolAdapterRegistryService()
