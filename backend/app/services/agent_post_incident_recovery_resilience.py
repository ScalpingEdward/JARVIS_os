from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_post_incident_recovery_resilience import (
    AgentPostIncidentRecoveryCreate,
    AgentPostIncidentRecoveryDisposition,
    AgentPostIncidentRecoveryRecord,
    AgentPostIncidentRecoveryScores,
    AgentPostIncidentRecoveryState,
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


class AgentPostIncidentRecoveryResilienceService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentPostIncidentRecoveryRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-post-incident-recovery-resilience-governance",
            "version": "21.99",
            "governance_only": True,
            "automatic_remediation_enabled": False,
            "automatic_control_mutation_enabled": False,
            "automatic_redeployment_enabled": False,
            "agent_restart_enabled": False,
            "traffic_shift_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentPostIncidentRecoveryCreate) -> AgentPostIncidentRecoveryRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = AgentPostIncidentRecoveryState.BLOCKED if "risk-brain-hard-block" in flags else AgentPostIncidentRecoveryState.EVIDENCE_READY
        record = AgentPostIncidentRecoveryRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AgentPostIncidentRecoveryRecord]:
        return [r for (workspace, _), r in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentPostIncidentRecoveryRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentPostIncidentRecoveryRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentPostIncidentRecoveryState.ASSESSED,
            "submit-review": AgentPostIncidentRecoveryState.REVIEW_REQUIRED,
            "approve": AgentPostIncidentRecoveryState.APPROVED,
            "activate": AgentPostIncidentRecoveryState.ACTIVE,
            "monitor": AgentPostIncidentRecoveryState.MONITORING,
            "certify-resilient": AgentPostIncidentRecoveryState.RESILIENT,
            "suspend": AgentPostIncidentRecoveryState.SUSPENDED,
            "revoke": AgentPostIncidentRecoveryState.REVOKED,
            "archive": AgentPostIncidentRecoveryState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved post-incident findings block approval")
        if action in {"activate", "monitor", "certify-resilient"} and record.state not in {
            AgentPostIncidentRecoveryState.APPROVED, AgentPostIncidentRecoveryState.ACTIVE,
            AgentPostIncidentRecoveryState.MONITORING, AgentPostIncidentRecoveryState.RESILIENT,
        }:
            raise ValueError("human approval required before resilient state")
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

    def _assess(self, payload: AgentPostIncidentRecoveryCreate):
        obs = payload.observations
        restoration = mean(o.service_restoration_score for o in obs)
        validation = mean((o.stability_validation_score + o.regression_validation_score) / 2 for o in obs)
        root_cause = mean(o.root_cause_confidence for o in obs)
        corrective = mean((o.corrective_action_coverage + o.preventive_control_coverage) / 2 for o in obs)
        resilience = mean(o.resilience_test_coverage for o in obs)
        observability = mean((o.observability_improvement_score + o.runbook_improvement_score) / 2 for o in obs)
        closure = mean((o.lessons_learned_closure + o.owner_accountability_coverage) / 2 for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([restoration, validation, root_cause, corrective, resilience, observability, closure]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.service_restoration_score)*0.15 + (1-o.stability_validation_score)*0.10 +
            (1-o.regression_validation_score)*0.08 + (1-o.root_cause_confidence)*0.12 +
            (1-o.corrective_action_coverage)*0.10 + (1-o.preventive_control_coverage)*0.10 +
            (1-o.resilience_test_coverage)*0.12 + min(o.open_corrective_actions/5,1)*0.08 +
            min(o.repeated_failure_signals/3,1)*0.08 + min(o.failed_resilience_tests/3,1)*0.07
            for o in obs
        ))
        scores = AgentPostIncidentRecoveryScores(
            restoration_assurance=self._clamp(restoration), validation_assurance=self._clamp(validation),
            root_cause_assurance=self._clamp(root_cause), corrective_control_assurance=self._clamp(corrective),
            resilience_assurance=self._clamp(resilience), observability_runbook_assurance=self._clamp(observability),
            closure_accountability_assurance=self._clamp(closure), aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk, confidence=self._clamp(confidence),
        )
        dispositions: List[AgentPostIncidentRecoveryDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            lifecycle = "resilient"
            residual = self._clamp(
                (1-o.service_restoration_score)*0.16 + (1-o.stability_validation_score)*0.10 +
                (1-o.regression_validation_score)*0.08 + (1-o.root_cause_confidence)*0.12 +
                (1-o.corrective_action_coverage)*0.10 + (1-o.preventive_control_coverage)*0.10 +
                (1-o.resilience_test_coverage)*0.12 + (1-o.lessons_learned_closure)*0.06 +
                min(o.open_corrective_actions/5,1)*0.06 + min(o.repeated_failure_signals/3,1)*0.05 +
                min(o.failed_resilience_tests/3,1)*0.05
            )
            if o.service_restoration_score < payload.min_restoration_score:
                lifecycle = "recovery-gap"; actions.append("service-restoration-review"); flags.append(f"recovery-gap:{o.agent_id}:{o.incident_id}")
            if min(o.corrective_action_coverage, o.preventive_control_coverage) < payload.min_control_coverage or o.open_corrective_actions > 0:
                lifecycle = "control-gap"; actions.append("corrective-and-preventive-control-review"); flags.append(f"control-gap:{o.agent_id}:{o.incident_id}")
            if o.repeated_failure_signals > 0:
                lifecycle = "recurrence-alert"; actions.append("repeat-failure-root-cause-review"); flags.append(f"recurrence-alert:{o.agent_id}:{o.incident_id}")
            if min(o.stability_validation_score, o.regression_validation_score) < payload.min_stability_score or o.resilience_test_coverage < payload.min_resilience_test_coverage or o.failed_resilience_tests > 0:
                lifecycle = "validation-alert"; actions.append("stability-regression-resilience-validation-review"); flags.append(f"validation-alert:{o.agent_id}:{o.incident_id}")
            if o.lessons_learned_closure < 0.85 or o.owner_accountability_coverage < 0.90 or o.unresolved_root_cause_questions > 0:
                lifecycle = "lessons-alert"; actions.append("root-cause-lessons-accountability-review"); flags.append(f"lessons-alert:{o.agent_id}:{o.incident_id}")
            if residual > payload.max_residual_risk:
                actions.append("post-incident-resilience-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.incident_id}")
            if o.business_criticality >= 0.90 and (o.repeated_failure_signals > 1 or o.failed_resilience_tests > 0 or residual >= 0.55):
                actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block"); lifecycle = "recurrence-alert"
            dispositions.append(AgentPostIncidentRecoveryDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, incident_id=o.incident_id,
                resilience_score=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=lifecycle, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentPostIncidentRecoveryRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_post_incident_recovery_resilience_service = AgentPostIncidentRecoveryResilienceService()
