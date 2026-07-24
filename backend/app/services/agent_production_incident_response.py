from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_production_incident_response import (
    AgentProductionIncidentCreate,
    AgentProductionIncidentDisposition,
    AgentProductionIncidentRecord,
    AgentProductionIncidentScores,
    AgentProductionIncidentState,
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


class AgentProductionIncidentResponseService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentProductionIncidentRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-production-incident-response-governance",
            "version": "21.98",
            "governance_only": True,
            "automatic_containment_enabled": False,
            "automatic_recovery_enabled": False,
            "automatic_rollback_enabled": False,
            "agent_restart_enabled": False,
            "traffic_shift_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentProductionIncidentCreate) -> AgentProductionIncidentRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = AgentProductionIncidentState.BLOCKED if "risk-brain-hard-block" in flags else AgentProductionIncidentState.EVIDENCE_READY
        record = AgentProductionIncidentRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AgentProductionIncidentRecord]:
        return [r for (workspace, _), r in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentProductionIncidentRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentProductionIncidentRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentProductionIncidentState.ASSESSED,
            "submit-review": AgentProductionIncidentState.REVIEW_REQUIRED,
            "approve": AgentProductionIncidentState.APPROVED,
            "activate": AgentProductionIncidentState.ACTIVE,
            "monitor": AgentProductionIncidentState.MONITORING,
            "contain": AgentProductionIncidentState.CONTAINED,
            "suspend": AgentProductionIncidentState.SUSPENDED,
            "revoke": AgentProductionIncidentState.REVOKED,
            "archive": AgentProductionIncidentState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved incident-response findings block approval")
        if action in {"activate", "monitor", "contain"} and record.state not in {
            AgentProductionIncidentState.APPROVED, AgentProductionIncidentState.ACTIVE,
            AgentProductionIncidentState.MONITORING, AgentProductionIncidentState.CONTAINED,
        }:
            raise ValueError("human approval required before governed incident state")
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
        return [e for e in self._audit if e.workspace_id == workspace_id]

    def _assess(self, payload: AgentProductionIncidentCreate):
        observations = payload.observations
        detection = mean((o.detection_quality + o.triage_readiness) / 2 for o in observations)
        containment = mean(o.containment_readiness for o in observations)
        recovery = mean((o.recovery_readiness + o.rollback_readiness) / 2 for o in observations)
        command = mean(o.human_command_coverage for o in observations)
        communication = mean(o.stakeholder_communication_readiness for o in observations)
        evidence = mean(o.evidence_preservation_score for o in observations)
        learning = mean((o.postmortem_readiness + o.lessons_learned_traceability) / 2 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)
        aggregate = self._clamp(mean([detection, containment, recovery, command, communication, evidence, learning]) * confidence)
        aggregate_risk = self._clamp(mean(
            o.severity * 0.18 + (1-o.detection_quality)*0.08 + (1-o.containment_readiness)*0.14 +
            (1-o.recovery_readiness)*0.12 + (1-o.human_command_coverage)*0.10 +
            (1-o.stakeholder_communication_readiness)*0.06 + (1-o.evidence_preservation_score)*0.06 +
            min(o.unresolved_critical_impacts/3,1)*0.10 + min(o.containment_failures/2,1)*0.06 +
            min(o.recovery_failures/2,1)*0.06 + min(o.repeat_incident_count/3,1)*0.04
            for o in observations
        ))
        scores = AgentProductionIncidentScores(
            detection_assurance=self._clamp(detection), containment_assurance=self._clamp(containment),
            recovery_assurance=self._clamp(recovery), command_assurance=self._clamp(command),
            communication_assurance=self._clamp(communication), evidence_assurance=self._clamp(evidence),
            learning_assurance=self._clamp(learning), aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk, confidence=self._clamp(confidence),
        )
        dispositions: List[AgentProductionIncidentDisposition] = []
        flags: List[str] = []
        for o in observations:
            actions: List[str] = []
            lifecycle = "contained"
            residual = self._clamp(
                o.severity*0.20 + (1-o.detection_quality)*0.08 + (1-o.triage_readiness)*0.06 +
                (1-o.containment_readiness)*0.14 + (1-o.recovery_readiness)*0.12 +
                (1-o.rollback_readiness)*0.08 + (1-o.human_command_coverage)*0.10 +
                (1-o.stakeholder_communication_readiness)*0.05 + (1-o.evidence_preservation_score)*0.05 +
                min(o.unresolved_critical_impacts/3,1)*0.06 + min(o.repeat_incident_count/3,1)*0.06
            )
            if o.severity >= 0.80 or o.unresolved_critical_impacts > 0:
                lifecycle = "severity-alert"; actions.append("critical-impact-and-severity-review"); flags.append(f"severity-alert:{o.agent_id}:{o.incident_id}")
            if o.containment_readiness < payload.min_containment_readiness or o.containment_failures > 0:
                lifecycle = "containment-alert"; actions.append("containment-readiness-review"); flags.append(f"containment-alert:{o.agent_id}:{o.incident_id}")
            if o.recovery_readiness < payload.min_recovery_readiness or o.recovery_failures > 0:
                lifecycle = "recovery-alert"; actions.append("recovery-and-rollback-review"); flags.append(f"recovery-alert:{o.agent_id}:{o.incident_id}")
            if o.human_command_coverage < payload.min_human_command_coverage or o.communication_failures > 0:
                lifecycle = "communication-alert"; actions.append("human-command-and-stakeholder-communication-review"); flags.append(f"communication-alert:{o.agent_id}:{o.incident_id}")
            if o.postmortem_readiness < 0.80 or o.lessons_learned_traceability < 0.80 or o.repeat_incident_count > 0:
                lifecycle = "postmortem-alert"; actions.append("postmortem-and-lessons-learned-review"); flags.append(f"postmortem-alert:{o.agent_id}:{o.incident_id}")
            if o.detection_quality < payload.min_detection_quality:
                actions.append("incident-detection-and-triage-review"); flags.append(f"detection-gap:{o.agent_id}:{o.incident_id}")
            if residual > payload.max_residual_risk:
                actions.append("agent-production-incident-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.incident_id}")
            if o.business_criticality >= 0.90 and (o.unresolved_critical_impacts > 0 or o.containment_failures > 0 or o.recovery_failures > 0 or residual >= 0.60):
                actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block"); lifecycle = "severity-alert"
            dispositions.append(AgentProductionIncidentDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, incident_id=o.incident_id,
                incident_assurance=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=lifecycle, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentProductionIncidentRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_production_incident_response_service = AgentProductionIncidentResponseService()
