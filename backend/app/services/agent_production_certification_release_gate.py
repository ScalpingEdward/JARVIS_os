from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_production_certification_release_gate import (
    AgentProductionCertificationCreate,
    AgentProductionCertificationDisposition,
    AgentProductionCertificationRecord,
    AgentProductionCertificationScores,
    AgentProductionCertificationState,
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


class AgentProductionCertificationReleaseGateService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentProductionCertificationRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-production-certification-release-gate-governance",
            "version": "21.96",
            "governance_only": True,
            "deployment_execution_enabled": False,
            "release_gate_mutation_enabled": False,
            "traffic_shift_enabled": False,
            "automatic_rollback_enabled": False,
            "agent_execution_enabled": False,
            "portfolio_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentProductionCertificationCreate) -> AgentProductionCertificationRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = (
            AgentProductionCertificationState.BLOCKED
            if "risk-brain-hard-block" in flags
            else AgentProductionCertificationState.EVIDENCE_READY
        )
        record = AgentProductionCertificationRecord(
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

    def list(self, workspace_id: str) -> List[AgentProductionCertificationRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentProductionCertificationRecord:
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
    ) -> AgentProductionCertificationRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentProductionCertificationState.ASSESSED,
            "submit-review": AgentProductionCertificationState.REVIEW_REQUIRED,
            "approve": AgentProductionCertificationState.APPROVED,
            "activate": AgentProductionCertificationState.ACTIVE,
            "monitor": AgentProductionCertificationState.MONITORING,
            "certify": AgentProductionCertificationState.CERTIFIED,
            "suspend": AgentProductionCertificationState.SUSPENDED,
            "revoke": AgentProductionCertificationState.REVOKED,
            "archive": AgentProductionCertificationState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved production-certification findings block approval")
        if action in {"activate", "certify"} and record.state not in {
            AgentProductionCertificationState.APPROVED,
            AgentProductionCertificationState.ACTIVE,
            AgentProductionCertificationState.MONITORING,
        }:
            raise ValueError("human approval required before production certification")

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

    def _assess(self, payload: AgentProductionCertificationCreate):
        observations = payload.observations
        environment_assurance = mean(o.environment_parity_score for o in observations)
        artifact_configuration = mean(
            (o.artifact_integrity_score + o.configuration_integrity_score + o.dependency_lock_score) / 3
            for o in observations
        )
        signoff_assurance = mean(
            (o.security_signoff_coverage + o.risk_signoff_coverage + o.operations_signoff_coverage) / 3
            for o in observations
        )
        release_gate_assurance = mean(o.release_gate_coverage for o in observations)
        observability_assurance = mean(o.observability_baseline_score for o in observations)
        recovery_assurance = mean(
            (o.rollback_recovery_readiness + o.break_glass_readiness) / 2 for o in observations
        )
        operational_readiness = mean(
            (o.change_window_readiness + o.runbook_readiness) / 2 for o in observations
        )
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(
            mean(
                [
                    environment_assurance,
                    artifact_configuration,
                    signoff_assurance,
                    release_gate_assurance,
                    observability_assurance,
                    recovery_assurance,
                    operational_readiness,
                ]
            )
            * confidence
        )

        aggregate_residual_risk = self._clamp(
            mean(
                (1 - o.environment_parity_score) * 0.12
                + (1 - o.artifact_integrity_score) * 0.08
                + (1 - o.configuration_integrity_score) * 0.08
                + (1 - o.dependency_lock_score) * 0.06
                + (1 - min(o.security_signoff_coverage, o.risk_signoff_coverage, o.operations_signoff_coverage)) * 0.14
                + (1 - o.release_gate_coverage) * 0.12
                + (1 - o.observability_baseline_score) * 0.08
                + (1 - o.rollback_recovery_readiness) * 0.12
                + min(o.unresolved_blocking_findings / 3, 1) * 0.08
                + min(o.failed_release_gate_checks / 3, 1) * 0.06
                + min(o.rollback_recovery_failures / 2, 1) * 0.06
                for o in observations
            )
        )

        scores = AgentProductionCertificationScores(
            environment_assurance=self._clamp(environment_assurance),
            artifact_configuration_assurance=self._clamp(artifact_configuration),
            signoff_assurance=self._clamp(signoff_assurance),
            release_gate_assurance=self._clamp(release_gate_assurance),
            observability_assurance=self._clamp(observability_assurance),
            recovery_assurance=self._clamp(recovery_assurance),
            operational_readiness=self._clamp(operational_readiness),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AgentProductionCertificationDisposition] = []
        flags: List[str] = []

        for o in observations:
            required_actions: List[str] = []
            lifecycle = "certified"
            signoff_floor = min(o.security_signoff_coverage, o.risk_signoff_coverage, o.operations_signoff_coverage)
            residual = self._clamp(
                (1 - o.environment_parity_score) * 0.14
                + (1 - o.artifact_integrity_score) * 0.08
                + (1 - o.configuration_integrity_score) * 0.08
                + (1 - o.dependency_lock_score) * 0.06
                + (1 - signoff_floor) * 0.14
                + (1 - o.release_gate_coverage) * 0.12
                + (1 - o.observability_baseline_score) * 0.08
                + (1 - o.rollback_recovery_readiness) * 0.12
                + (1 - o.change_window_readiness) * 0.06
                + (1 - o.runbook_readiness) * 0.04
                + min(o.unresolved_blocking_findings / 3, 1) * 0.04
                + min(o.rollback_recovery_failures / 2, 1) * 0.04
            )

            if o.environment_parity_score < payload.min_environment_parity or o.environment_drift_events > 0:
                lifecycle = "environment-alert"
                required_actions.append("production-environment-parity-review")
                flags.append(f"environment-alert:{o.agent_id}:{o.target_environment}")

            if signoff_floor < payload.min_signoff_coverage or o.missing_required_signoffs > 0:
                lifecycle = "signoff-alert"
                required_actions.append("required-production-signoff-review")
                flags.append(f"signoff-alert:{o.agent_id}:{o.target_environment}")

            if o.release_gate_coverage < payload.min_release_gate_coverage or o.failed_release_gate_checks > 0:
                lifecycle = "release-gate-alert"
                required_actions.append("release-gate-control-review")
                flags.append(f"release-gate-alert:{o.agent_id}:{o.target_environment}")

            if o.change_window_readiness < 0.80 or o.runbook_readiness < 0.80:
                lifecycle = "change-window-alert"
                required_actions.append("change-window-and-runbook-review")
                flags.append(f"change-window-alert:{o.agent_id}:{o.target_environment}")

            if o.rollback_recovery_readiness < payload.min_recovery_readiness or o.rollback_recovery_failures > 0:
                lifecycle = "recovery-alert"
                required_actions.append("rollback-and-recovery-certification-review")
                flags.append(f"recovery-alert:{o.agent_id}:{o.target_environment}")

            if o.unresolved_blocking_findings > 0:
                required_actions.append("blocking-findings-resolution-review")
                flags.append(f"blocking-findings:{o.agent_id}:{o.target_environment}")

            if residual > payload.max_residual_risk:
                required_actions.append("agent-production-certification-risk-committee")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.target_environment}")

            if o.business_criticality >= 0.90 and (
                o.unresolved_blocking_findings > 0
                or o.rollback_recovery_failures > 0
                or o.failed_release_gate_checks > 1
                or residual >= 0.60
            ):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "release-gate-alert"

            dispositions.append(
                AgentProductionCertificationDisposition(
                    agent_id=o.agent_id,
                    agent_version=o.agent_version,
                    target_environment=o.target_environment,
                    certification_score=self._clamp(1 - residual),
                    residual_risk=residual,
                    lifecycle_signal=lifecycle,
                    required_actions=sorted(set(required_actions)),
                )
            )

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: AgentProductionCertificationRecord,
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


agent_production_certification_release_gate_service = AgentProductionCertificationReleaseGateService()
