from __future__ import annotations

from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_capability_registry import (
    CapabilityMatchRequest,
    CapabilityMatchResult,
    CapabilityRegistryCreate,
    CapabilityRegistryRecord,
    CapabilityRegistryState,
)


class AgentCapabilityRegistryService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], CapabilityRegistryRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "agent-capability-registry",
            "version": "21.113",
            "registry_only": True,
            "task_execution_enabled": False,
            "tool_execution_enabled": False,
            "permission_mutation_enabled": False,
            "credential_mutation_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: CapabilityRegistryCreate) -> CapabilityRegistryRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        flags = self._risk_flags(payload)
        record = CapabilityRegistryRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=CapabilityRegistryState.DRAFT,
            profile=payload.profile,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[CapabilityRegistryRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> CapabilityRegistryRecord:
        key = (workspace_id, record_id)
        if key not in self._records:
            raise KeyError("record not found")
        return self._records[key]

    def act(
        self,
        workspace_id: str,
        record_id: str,
        action: str,
        actor: str,
        operation_id: str,
        reason: str | None = None,
    ) -> CapabilityRegistryRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "submit-review": CapabilityRegistryState.REVIEW_REQUIRED,
            "approve": CapabilityRegistryState.APPROVED,
            "activate": CapabilityRegistryState.ACTIVE,
            "degrade": CapabilityRegistryState.DEGRADED,
            "suspend": CapabilityRegistryState.SUSPENDED,
            "revoke": CapabilityRegistryState.REVOKED,
            "archive": CapabilityRegistryState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved capability registry findings block approval")
        if action == "activate" and record.state != CapabilityRegistryState.APPROVED:
            raise ValueError("human approval required before activation")

        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operations.add(receipt)
        self._audit_event(updated, action, actor, operation_id, reason)
        return updated

    def match(self, request: CapabilityMatchRequest) -> List[CapabilityMatchResult]:
        active = [record for record in self.list(request.workspace_id) if record.state == CapabilityRegistryState.ACTIVE]
        results: List[CapabilityMatchResult] = []
        required_caps = set(request.required_capabilities)
        required_tools = set(request.required_tools)
        required_domains = set(request.data_domains)

        for record in active:
            profile = record.profile
            capabilities = set(profile.capabilities)
            tools = {grant.tool_name for grant in profile.tool_grants}
            domains = set(profile.allowed_data_domains)
            cap_coverage = len(required_caps & capabilities) / len(required_caps) if required_caps else 1.0
            tool_coverage = len(required_tools & tools) / len(required_tools) if required_tools else 1.0
            domain_coverage = len(required_domains & domains) / len(required_domains) if required_domains else 1.0
            reasons: List[str] = []
            if cap_coverage < 1.0:
                reasons.append("missing-required-capability")
            if tool_coverage < 1.0:
                reasons.append("missing-required-tool")
            if domain_coverage < 1.0:
                reasons.append("missing-data-domain")
            if profile.confidence_floor < request.minimum_confidence:
                reasons.append("confidence-floor-below-request")
            eligible = not reasons and record.state == CapabilityRegistryState.ACTIVE
            results.append(CapabilityMatchResult(
                agent_id=profile.agent_id,
                agent_version=profile.agent_version,
                role=profile.role,
                capability_coverage=round(cap_coverage, 4),
                tool_coverage=round(tool_coverage, 4),
                data_domain_coverage=round(domain_coverage, 4),
                eligible=eligible,
                reasons=reasons,
            ))
        return sorted(results, key=lambda item: (item.eligible, item.capability_coverage, item.tool_coverage, item.data_domain_coverage), reverse=True)

    def audit(self, workspace_id: str) -> List[dict]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _risk_flags(self, payload: CapabilityRegistryCreate) -> List[str]:
        profile = payload.profile
        flags: List[str] = []
        if not profile.denied_actions:
            flags.append("missing-denied-actions-boundary")
        for grant in profile.tool_grants:
            if not grant.read_only and not grant.requires_human_approval:
                flags.append(f"mutable-tool-without-human-approval:{grant.tool_name}")
            if grant.max_calls_per_task > 500:
                flags.append(f"excessive-tool-call-limit:{grant.tool_name}")
        if profile.max_parallel_tasks > 20:
            flags.append("excessive-parallel-task-limit")
        if profile.criticality >= 0.90 and profile.confidence_floor < 0.80:
            flags.append("risk-brain-hard-block")
        return sorted(set(flags))

    def _audit_event(self, record: CapabilityRegistryRecord, action: str, actor: str, operation_id: str, reason: str | None = None) -> None:
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "agent_id": record.profile.agent_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "reason": reason,
            "version": record.version,
        })


agent_capability_registry_service = AgentCapabilityRegistryService()
