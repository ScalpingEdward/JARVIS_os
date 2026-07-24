from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_continuous_resilience_baseline import (
    AgentContinuousResilienceCreate,
    AgentContinuousResilienceDisposition,
    AgentContinuousResilienceRecord,
    AgentContinuousResilienceScores,
    AgentContinuousResilienceState,
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


class AgentContinuousResilienceBaselineService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentContinuousResilienceRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-continuous-resilience-baseline-regression-governance",
            "version": "21.101",
            "governance_only": True,
            "automatic_remediation_enabled": False,
            "automatic_baseline_mutation_enabled": False,
            "automatic_failover_enabled": False,
            "automatic_recovery_enabled": False,
            "agent_execution_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentContinuousResilienceCreate) -> AgentContinuousResilienceRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = (
            AgentContinuousResilienceState.BLOCKED
            if "risk-brain-hard-block" in flags
            else AgentContinuousResilienceState.EVIDENCE_READY
        )
        record = AgentContinuousResilienceRecord(
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

    def list(self, workspace_id: str) -> List[AgentContinuousResilienceRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentContinuousResilienceRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(
        self,
        workspace_id: str,
        record_id: str,
        action: str,
        actor: str,
        operation_id: str,
        reason: str | None = None,
    ) -> AgentContinuousResilienceRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentContinuousResilienceState.ASSESSED,
            "submit-review": AgentContinuousResilienceState.REVIEW_REQUIRED,
            "approve": AgentContinuousResilienceState.APPROVED,
            "activate": AgentContinuousResilienceState.ACTIVE,
            "monitor": AgentContinuousResilienceState.MONITORING,
            "stabilize": AgentContinuousResilienceState.STABLE,
            "suspend": AgentContinuousResilienceState.SUSPENDED,
            "revoke": AgentContinuousResilienceState.REVOKED,
            "archive": AgentContinuousResilienceState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved continuous-resilience findings block approval")
        if action in {"activate", "monitor", "stabilize"} and record.state not in {
            AgentContinuousResilienceState.APPROVED,
            AgentContinuousResilienceState.ACTIVE,
            AgentContinuousResilienceState.MONITORING,
            AgentContinuousResilienceState.STABLE,
        }:
            raise ValueError("human approval required before governed resilience state")

        updated = record.model_copy(
            update={
                "state": transitions[action],
                "approved_by": actor if action == "approve" else record.approved_by,
                "version": record.version + 1,
            }
        )
        self._records[(workspace_id, record_id)] = updated
        self._operation_ids.add(receipt)
        self._append_audit(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _assess(self, payload: AgentContinuousResilienceCreate):
        observations = payload.observations
        service_stability = mean(
            (o.availability_score + o.latency_stability_score + o.error_rate_stability_score) / 3
            for o in observations
        )
        recovery = mean((o.recovery_time_score + o.failover_stability_score) / 2 for o in observations)
        dependency = mean(o.dependency_stability_score for o in observations)
        observability = mean(o.observability_stability_score for o in observations)
        control = mean(o.control_effectiveness_score for o in observations)
        recurrence = mean(o.recurrence_prevention_score for o in observations)
        regression = mean(o.regression_coverage_score for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate = self._clamp(
            mean([service_stability, recovery, dependency, observability, control, recurrence, regression])
            * confidence
        )
        aggregate_risk = self._clamp(
            mean(
                (1 - o.availability_score) * 0.10
                + (1 - o.latency_stability_score) * 0.08
                + (1 - o.error_rate_stability_score) * 0.08
                + (1 - o.recovery_time_score) * 0.10
                + (1 - o.failover_stability_score) * 0.10
                + (1 - o.dependency_stability_score) * 0.08
                + (1 - o.observability_stability_score) * 0.06
                + (1 - o.control_effectiveness_score) * 0.10
                + (1 - o.recurrence_prevention_score) * 0.10
                + (1 - o.regression_coverage_score) * 0.08
                + min(o.baseline_breaches / 3, 1) * 0.04
                + min(o.failed_regression_checks / 3, 1) * 0.04
                + min(o.resilience_drift_events / 3, 1) * 0.02
                + min(o.repeated_incident_count / 3, 1) * 0.02
                for o in observations
            )
        )

        scores = AgentContinuousResilienceScores(
            service_stability=self._clamp(service_stability),
            recovery_assurance=self._clamp(recovery),
            dependency_assurance=self._clamp(dependency),
            observability_assurance=self._clamp(observability),
            control_assurance=self._clamp(control),
            recurrence_assurance=self._clamp(recurrence),
            regression_assurance=self._clamp(regression),
            aggregate_assurance=aggregate,
            aggregate_residual_risk=aggregate_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentContinuousResilienceDisposition] = []
        flags: List[str] = []

        for o in observations:
            baseline = mean([
                o.availability_score,
                o.latency_stability_score,
                o.error_rate_stability_score,
                o.recovery_time_score,
                o.failover_stability_score,
                o.dependency_stability_score,
                o.observability_stability_score,
                o.control_effectiveness_score,
            ])
            residual = self._clamp(
                (1 - baseline) * 0.45
                + (1 - o.recurrence_prevention_score) * 0.20
                + (1 - o.regression_coverage_score) * 0.15
                + min(o.baseline_breaches / 3, 1) * 0.07
                + min(o.failed_regression_checks / 3, 1) * 0.06
                + min(o.resilience_drift_events / 3, 1) * 0.04
                + min(o.repeated_incident_count / 3, 1) * 0.03
            )
            lifecycle = "stable"
            actions: List[str] = []

            if baseline < payload.min_baseline_stability or o.baseline_breaches > 0:
                lifecycle = "baseline-alert"
                actions.append("resilience-baseline-review")
                flags.append(f"baseline-alert:{o.agent_id}:{o.baseline_id}")

            if o.regression_coverage_score < payload.min_regression_coverage or o.failed_regression_checks > 0:
                lifecycle = "regression-alert"
                actions.append("continuous-regression-review")
                flags.append(f"regression-alert:{o.agent_id}:{o.baseline_id}")

            if o.resilience_drift_events > 0:
                lifecycle = "drift-alert"
                actions.append("resilience-drift-investigation")
                flags.append(f"drift-alert:{o.agent_id}:{o.baseline_id}")

            if o.recurrence_prevention_score < payload.min_recurrence_prevention or o.repeated_incident_count > 0:
                lifecycle = "recurrence-alert"
                actions.append("recurrence-prevention-review")
                flags.append(f"recurrence-alert:{o.agent_id}:{o.baseline_id}")

            if residual > payload.max_residual_risk:
                actions.append("continuous-resilience-risk-committee")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.baseline_id}")

            if o.business_criticality >= 0.90 and (
                o.failed_regression_checks > 0
                or o.repeated_incident_count > 0
                or o.baseline_breaches > 1
                or residual >= 0.60
            ):
                actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "regression-alert"

            dispositions.append(
                AgentContinuousResilienceDisposition(
                    agent_id=o.agent_id,
                    agent_version=o.agent_version,
                    baseline_id=o.baseline_id,
                    resilience_score=self._clamp(1 - residual),
                    residual_risk=residual,
                    lifecycle_signal=lifecycle,
                    required_actions=sorted(set(actions)),
                )
            )

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: AgentContinuousResilienceRecord,
        action: str,
        actor: str,
        operation_id: str,
        metadata: dict | None = None,
    ) -> None:
        self._audit.append(
            AuditEntry(
                audit_id=str(uuid4()),
                workspace_id=record.workspace_id,
                record_id=record.record_id,
                action=action,
                actor=actor,
                operation_id=operation_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata=metadata or {},
            )
        )


agent_continuous_resilience_baseline_service = AgentContinuousResilienceBaselineService()
