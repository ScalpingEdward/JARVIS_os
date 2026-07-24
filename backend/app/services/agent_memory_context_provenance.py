from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_memory_context_provenance import (
    AgentMemoryContextCreate,
    AgentMemoryContextRecord,
    AgentMemoryContextScores,
    AgentMemoryState,
    MemoryContextDisposition,
)


@dataclass
class AuditEntry:
    audit_id: str
    workspace_id: str
    record_id: str
    action: str
    actor: str
    operation_id: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


class AgentMemoryContextProvenanceService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentMemoryContextRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-memory-context-provenance-governance",
            "version": "21.89",
            "governance_only": True,
            "memory_mutation_enabled": False,
            "context_injection_enabled": False,
            "automatic_memory_deletion_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentMemoryContextCreate) -> AgentMemoryContextRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = AgentMemoryState.BLOCKED if "risk-brain-hard-block" in flags else AgentMemoryState.EVIDENCE_READY
        record = AgentMemoryContextRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            dispositions=dispositions,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AgentMemoryContextRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentMemoryContextRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentMemoryContextRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentMemoryState.ASSESSED,
            "submit-review": AgentMemoryState.REVIEW_REQUIRED,
            "approve": AgentMemoryState.APPROVED,
            "activate": AgentMemoryState.ACTIVE,
            "monitor": AgentMemoryState.MONITORING,
            "suspend": AgentMemoryState.SUSPENDED,
            "revoke": AgentMemoryState.REVOKED,
            "archive": AgentMemoryState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved memory/context findings block approval")
        if action == "activate" and record.state != AgentMemoryState.APPROVED:
            raise ValueError("human approval required before activation")

        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._append_audit(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _assess(self, payload: AgentMemoryContextCreate):
        observations = payload.observations
        provenance = mean((o.source_authority + o.provenance_coverage) / 2 for o in observations)
        freshness = mean(o.freshness_score for o in observations)
        relevance = mean((o.context_relevance + o.conflict_resolution_score) / 2 for o in observations)
        contamination = mean(o.contamination_resilience for o in observations)
        retention = mean(o.retention_compliance for o in observations)
        sensitive = mean(o.sensitive_data_control for o in observations)
        deletion = mean(o.deletion_traceability for o in observations)
        confidence = mean(o.confidence for o in observations)

        aggregate_assurance = self._clamp(mean([
            provenance, freshness, relevance, contamination, retention, sensitive, deletion
        ]) * confidence)

        aggregate_residual_risk = self._clamp(mean(
            (1 - o.source_authority) * 0.10
            + (1 - o.provenance_coverage) * 0.15
            + (1 - o.freshness_score) * 0.10
            + (1 - o.context_relevance) * 0.10
            + (1 - o.contamination_resilience) * 0.15
            + (1 - o.retention_compliance) * 0.10
            + (1 - o.sensitive_data_control) * 0.15
            + min(o.contamination_events / 5, 1) * 0.05
            + min(o.sensitive_memory_events / 5, 1) * 0.05
            + min(o.conflicting_memory_events / 5, 1) * 0.05
            for o in observations
        ))

        scores = AgentMemoryContextScores(
            provenance_assurance=self._clamp(provenance),
            freshness_assurance=self._clamp(freshness),
            relevance_assurance=self._clamp(relevance),
            contamination_resilience=self._clamp(contamination),
            retention_assurance=self._clamp(retention),
            sensitive_data_assurance=self._clamp(sensitive),
            deletion_traceability=self._clamp(deletion),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[MemoryContextDisposition] = []
        flags: List[str] = []
        for o in observations:
            required_actions: List[str] = []
            lifecycle = "trusted"
            residual = self._clamp(
                (1 - o.source_authority) * 0.12
                + (1 - o.provenance_coverage) * 0.18
                + (1 - o.freshness_score) * 0.12
                + (1 - o.context_relevance) * 0.08
                + (1 - o.conflict_resolution_score) * 0.08
                + (1 - o.contamination_resilience) * 0.16
                + (1 - o.retention_compliance) * 0.10
                + (1 - o.sensitive_data_control) * 0.10
                + min(o.contamination_events / 5, 1) * 0.03
                + min(o.sensitive_memory_events / 5, 1) * 0.03
            )

            if o.source_authority < payload.min_source_authority or o.provenance_coverage < payload.min_provenance_coverage or o.provenance_gaps > 0:
                lifecycle = "provenance-alert"
                required_actions.append("memory-provenance-review")
                flags.append(f"provenance-alert:{o.agent_id}:{o.memory_id}")
            if o.freshness_score < payload.min_freshness_score or o.stale_reads > 0:
                lifecycle = "stale-context-alert"
                required_actions.append("context-freshness-review")
                flags.append(f"stale-context-alert:{o.agent_id}:{o.memory_id}")
            if o.contamination_resilience < payload.min_contamination_resilience or o.contamination_events > 0 or o.conflicting_memory_events > 0:
                lifecycle = "contamination-alert"
                required_actions.append("memory-contamination-investigation")
                flags.append(f"contamination-alert:{o.agent_id}:{o.memory_id}")
            if o.retention_compliance < payload.min_retention_compliance or o.retention_breaches > 0:
                lifecycle = "retention-alert"
                required_actions.append("retention-policy-review")
                flags.append(f"retention-alert:{o.agent_id}:{o.memory_id}")
            if o.sensitive_memory_events > 0 or o.sensitive_data_control < 0.85:
                lifecycle = "sensitive-memory-alert"
                required_actions.append("sensitive-memory-access-review")
                flags.append(f"sensitive-memory-alert:{o.agent_id}:{o.memory_id}")
            if residual > payload.max_residual_risk:
                required_actions.append("agent-memory-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.memory_id}")
            if o.business_criticality >= 0.90 and (o.contamination_events > 0 or o.sensitive_memory_events > 0 or residual >= 0.60):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(MemoryContextDisposition(
                agent_id=o.agent_id,
                memory_id=o.memory_id,
                memory_type=o.memory_type,
                assurance_score=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentMemoryContextRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()),
            workspace_id=record.workspace_id,
            record_id=record.record_id,
            action=action,
            actor=actor,
            operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        ))


agent_memory_context_provenance_service = AgentMemoryContextProvenanceService()
