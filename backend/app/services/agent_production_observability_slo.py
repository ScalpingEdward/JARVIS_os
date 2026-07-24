from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_production_observability_slo import (
    AgentProductionObservabilityCreate,
    AgentProductionObservabilityDisposition,
    AgentProductionObservabilityRecord,
    AgentProductionObservabilityScores,
    AgentProductionObservabilityState,
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


class AgentProductionObservabilitySLOService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentProductionObservabilityRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-production-observability-slo-governance",
            "version": "21.97",
            "governance_only": True,
            "automatic_remediation_enabled": False,
            "automatic_scaling_enabled": False,
            "traffic_shift_enabled": False,
            "automatic_rollback_enabled": False,
            "agent_execution_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentProductionObservabilityCreate) -> AgentProductionObservabilityRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = (
            AgentProductionObservabilityState.BLOCKED
            if "risk-brain-hard-block" in flags
            else AgentProductionObservabilityState.EVIDENCE_READY
        )
        record = AgentProductionObservabilityRecord(
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

    def list(self, workspace_id: str) -> List[AgentProductionObservabilityRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentProductionObservabilityRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> AgentProductionObservabilityRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentProductionObservabilityState.ASSESSED,
            "submit-review": AgentProductionObservabilityState.REVIEW_REQUIRED,
            "approve": AgentProductionObservabilityState.APPROVED,
            "activate": AgentProductionObservabilityState.ACTIVE,
            "monitor": AgentProductionObservabilityState.MONITORING,
            "mark-healthy": AgentProductionObservabilityState.HEALTHY,
            "suspend": AgentProductionObservabilityState.SUSPENDED,
            "revoke": AgentProductionObservabilityState.REVOKED,
            "archive": AgentProductionObservabilityState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved production-observability findings block approval")
        if action in {"activate", "monitor", "mark-healthy"} and record.state not in {
            AgentProductionObservabilityState.APPROVED,
            AgentProductionObservabilityState.ACTIVE,
            AgentProductionObservabilityState.MONITORING,
        }:
            raise ValueError("human approval required before production monitoring state")

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

    def _assess(self, payload: AgentProductionObservabilityCreate):
        observations = payload.observations
        slo_assurance = mean(
            mean([o.availability_slo_attainment, o.latency_slo_attainment, o.error_rate_slo_attainment])
            for o in observations
        )
        telemetry_assurance = mean(
            mean([o.telemetry_coverage, o.trace_coverage, o.log_quality, o.metric_quality])
            for o in observations
        )
        alerting_assurance = mean(o.alert_precision for o in observations)
        incident_readiness = mean(mean([o.incident_detection_readiness, o.human_oncall_readiness]) for o in observations)
        error_budget_assurance = mean(o.error_budget_remaining for o in observations)
        drift_assurance = mean(1 - max(o.behavioral_drift_score, o.decision_drift_score) for o in observations)
        operational_assurance = mean(o.runbook_coverage for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(mean([
            slo_assurance,
            telemetry_assurance,
            alerting_assurance,
            incident_readiness,
            error_budget_assurance,
            drift_assurance,
            operational_assurance,
        ]) * confidence)

        aggregate_residual_risk = self._clamp(mean(
            (1 - min(o.availability_slo_attainment, o.latency_slo_attainment, o.error_rate_slo_attainment)) * 0.20
            + (1 - o.telemetry_coverage) * 0.10
            + (1 - o.trace_coverage) * 0.06
            + (1 - o.alert_precision) * 0.08
            + (1 - o.incident_detection_readiness) * 0.10
            + (1 - o.human_oncall_readiness) * 0.08
            + (1 - o.error_budget_remaining) * 0.12
            + max(o.behavioral_drift_score, o.decision_drift_score) * 0.10
            + min(o.critical_incidents / 2, 1) * 0.08
            + min(o.unresolved_incidents / 3, 1) * 0.05
            + min(o.false_negative_alerts / 3, 1) * 0.03
            for o in observations
        ))

        scores = AgentProductionObservabilityScores(
            slo_assurance=self._clamp(slo_assurance),
            telemetry_assurance=self._clamp(telemetry_assurance),
            alerting_assurance=self._clamp(alerting_assurance),
            incident_readiness=self._clamp(incident_readiness),
            error_budget_assurance=self._clamp(error_budget_assurance),
            drift_assurance=self._clamp(drift_assurance),
            operational_assurance=self._clamp(operational_assurance),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentProductionObservabilityDisposition] = []
        flags: List[str] = []

        for o in observations:
            required_actions: List[str] = []
            lifecycle = "healthy"
            slo_floor = min(o.availability_slo_attainment, o.latency_slo_attainment, o.error_rate_slo_attainment)
            drift_peak = max(o.behavioral_drift_score, o.decision_drift_score)
            residual = self._clamp(
                (1 - slo_floor) * 0.24
                + (1 - o.telemetry_coverage) * 0.10
                + (1 - o.trace_coverage) * 0.06
                + (1 - o.alert_precision) * 0.08
                + (1 - o.incident_detection_readiness) * 0.10
                + (1 - o.human_oncall_readiness) * 0.08
                + (1 - o.error_budget_remaining) * 0.12
                + drift_peak * 0.10
                + min(o.critical_incidents / 2, 1) * 0.06
                + min(o.unresolved_incidents / 3, 1) * 0.04
                + min(o.false_negative_alerts / 3, 1) * 0.02
            )

            if slo_floor < payload.min_slo_attainment or o.slo_breaches > 0:
                lifecycle = "slo-alert"
                required_actions.append("production-slo-review")
                flags.append(f"slo-alert:{o.agent_id}:{o.production_environment}")

            if o.error_budget_remaining < payload.min_error_budget_remaining:
                lifecycle = "error-budget-alert"
                required_actions.append("error-budget-burn-review")
                flags.append(f"error-budget-alert:{o.agent_id}:{o.production_environment}")

            if o.telemetry_coverage < payload.min_telemetry_coverage or o.telemetry_gaps > 0:
                lifecycle = "telemetry-alert"
                required_actions.append("telemetry-and-trace-coverage-review")
                flags.append(f"telemetry-alert:{o.agent_id}:{o.production_environment}")

            if o.critical_incidents > 0 or o.unresolved_incidents > 0 or o.false_negative_alerts > 0:
                lifecycle = "incident-alert"
                required_actions.append("incident-detection-and-oncall-review")
                flags.append(f"incident-alert:{o.agent_id}:{o.production_environment}")

            if drift_peak > payload.max_drift_score:
                lifecycle = "drift-alert"
                required_actions.append("production-behavior-and-decision-drift-review")
                flags.append(f"drift-alert:{o.agent_id}:{o.production_environment}")

            if residual > payload.max_residual_risk:
                required_actions.append("agent-production-observability-risk-committee")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.production_environment}")

            if o.business_criticality >= 0.90 and (
                o.critical_incidents > 0
                or o.error_budget_remaining <= 0.05
                or slo_floor < 0.75
                or drift_peak >= 0.65
                or residual >= 0.60
            ):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "incident-alert"

            dispositions.append(AgentProductionObservabilityDisposition(
                agent_id=o.agent_id,
                agent_version=o.agent_version,
                production_environment=o.production_environment,
                production_health_score=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: AgentProductionObservabilityRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


agent_production_observability_slo_service = AgentProductionObservabilitySLOService()
