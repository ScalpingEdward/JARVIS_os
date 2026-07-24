from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_post_incident_root_cause_corrective_action import (
    AgentPostIncidentRcaCreate,
    AgentPostIncidentRcaDisposition,
    AgentPostIncidentRcaRecord,
    AgentPostIncidentRcaScores,
    AgentPostIncidentRcaState,
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


class AgentPostIncidentRootCauseCorrectiveActionService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentPostIncidentRcaRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-post-incident-root-cause-corrective-action-governance",
            "version": "21.99",
            "governance_only": True,
            "automatic_remediation_enabled": False,
            "automatic_change_enabled": False,
            "automatic_deployment_enabled": False,
            "agent_execution_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentPostIncidentRcaCreate) -> AgentPostIncidentRcaRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = AgentPostIncidentRcaState.BLOCKED if "risk-brain-hard-block" in flags else AgentPostIncidentRcaState.EVIDENCE_READY
        record = AgentPostIncidentRcaRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source_identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[AgentPostIncidentRcaRecord]:
        return [r for (workspace, _), r in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentPostIncidentRcaRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentPostIncidentRcaRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentPostIncidentRcaState.ASSESSED,
            "submit-review": AgentPostIncidentRcaState.REVIEW_REQUIRED,
            "approve": AgentPostIncidentRcaState.APPROVED,
            "activate": AgentPostIncidentRcaState.ACTIVE,
            "monitor": AgentPostIncidentRcaState.MONITORING,
            "verify": AgentPostIncidentRcaState.VERIFIED,
            "suspend": AgentPostIncidentRcaState.SUSPENDED,
            "revoke": AgentPostIncidentRcaState.REVOKED,
            "archive": AgentPostIncidentRcaState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved post-incident findings block approval")
        if action in {"activate", "monitor", "verify"} and record.state not in {
            AgentPostIncidentRcaState.APPROVED, AgentPostIncidentRcaState.ACTIVE,
            AgentPostIncidentRcaState.MONITORING, AgentPostIncidentRcaState.VERIFIED,
        }:
            raise ValueError("human approval required before governed corrective-action state")
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

    def _assess(self, payload: AgentPostIncidentRcaCreate):
        observations = payload.observations
        root_cause = mean((o.root_cause_confidence + o.causal_chain_coverage + o.contributing_factor_coverage) / 3 for o in observations)
        evidence = mean(o.evidence_completeness for o in observations)
        corrective = mean(o.corrective_action_quality for o in observations)
        preventive = mean(o.preventive_action_quality for o in observations)
        accountability = mean((o.owner_accountability + o.due_date_readiness) / 2 for o in observations)
        verification = mean(o.verification_plan_quality for o in observations)
        recurrence = mean((o.recurrence_prevention_score + o.cross_agent_impact_review) / 2 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)
        aggregate = self._clamp(mean([root_cause, evidence, corrective, preventive, accountability, verification, recurrence]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.root_cause_confidence)*0.14 + (1-o.evidence_completeness)*0.08 +
            (1-o.corrective_action_quality)*0.14 + (1-o.preventive_action_quality)*0.10 +
            (1-o.owner_accountability)*0.08 + (1-o.verification_plan_quality)*0.10 +
            (1-o.recurrence_prevention_score)*0.12 + min(o.unresolved_root_causes/2,1)*0.08 +
            min(o.overdue_corrective_actions/3,1)*0.06 + min(o.failed_verification_checks/2,1)*0.05 +
            min(o.repeat_incident_count/3,1)*0.05
            for o in observations
        ))
        scores = AgentPostIncidentRcaScores(
            root_cause_assurance=self._clamp(root_cause), evidence_assurance=self._clamp(evidence),
            corrective_action_assurance=self._clamp(corrective), preventive_action_assurance=self._clamp(preventive),
            accountability_assurance=self._clamp(accountability), verification_assurance=self._clamp(verification),
            recurrence_assurance=self._clamp(recurrence), aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk, confidence=self._clamp(confidence),
        )
        dispositions: List[AgentPostIncidentRcaDisposition] = []
        flags: List[str] = []
        for o in observations:
            actions: List[str] = []
            lifecycle = "verified"
            residual = self._clamp(
                (1-o.root_cause_confidence)*0.16 + (1-o.evidence_completeness)*0.08 +
                (1-o.causal_chain_coverage)*0.07 + (1-o.corrective_action_quality)*0.15 +
                (1-o.preventive_action_quality)*0.10 + (1-o.owner_accountability)*0.09 +
                (1-o.verification_plan_quality)*0.10 + (1-o.recurrence_prevention_score)*0.12 +
                min(o.unresolved_root_causes/2,1)*0.05 + min(o.repeat_incident_count/3,1)*0.08
            )
            if o.root_cause_confidence < payload.min_root_cause_confidence or o.unresolved_root_causes > 0:
                lifecycle = "root-cause-alert"; actions.append("root-cause-and-causal-chain-review"); flags.append(f"root-cause-alert:{o.agent_id}:{o.incident_id}")
            if o.corrective_action_quality < payload.min_corrective_action_quality or o.overdue_corrective_actions > 0 or o.failed_verification_checks > 0:
                lifecycle = "corrective-action-alert"; actions.append("corrective-action-effectiveness-review"); flags.append(f"corrective-action-alert:{o.agent_id}:{o.incident_id}")
            if o.preventive_action_quality < payload.min_preventive_action_quality or o.recurrence_prevention_score < 0.85:
                lifecycle = "preventive-action-alert"; actions.append("preventive-action-and-recurrence-review"); flags.append(f"preventive-action-alert:{o.agent_id}:{o.incident_id}")
            if o.owner_accountability < payload.min_owner_accountability or o.unowned_actions > 0:
                lifecycle = "owner-alert"; actions.append("action-owner-accountability-review"); flags.append(f"owner-alert:{o.agent_id}:{o.incident_id}")
            if o.repeat_incident_count > 0:
                lifecycle = "recurrence-alert"; actions.append("repeat-incident-systemic-review"); flags.append(f"recurrence-alert:{o.agent_id}:{o.incident_id}")
            if residual > payload.max_residual_risk:
                actions.append("agent-post-incident-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.incident_id}")
            if o.business_criticality >= 0.90 and (o.unresolved_root_causes > 0 or o.failed_verification_checks > 0 or o.repeat_incident_count > 1 or residual >= 0.60):
                actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block"); lifecycle = "recurrence-alert"
            dispositions.append(AgentPostIncidentRcaDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, incident_id=o.incident_id,
                assurance_score=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=lifecycle, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentPostIncidentRcaRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_post_incident_root_cause_corrective_action_service = AgentPostIncidentRootCauseCorrectiveActionService()
