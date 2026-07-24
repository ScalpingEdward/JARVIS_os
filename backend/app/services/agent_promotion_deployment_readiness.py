from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_promotion_deployment_readiness import (
    AgentPromotionCreate,
    AgentPromotionRecord,
    AgentPromotionScores,
    AgentPromotionState,
    PromotionDisposition,
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


class AgentPromotionDeploymentReadinessService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], AgentPromotionRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-promotion-deployment-readiness-governance",
            "version": "21.95",
            "governance_only": True,
            "deployment_execution_enabled": False,
            "automatic_promotion_enabled": False,
            "traffic_shift_enabled": False,
            "automatic_rollback_enabled": False,
            "agent_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: AgentPromotionCreate) -> AgentPromotionRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = (
            AgentPromotionState.BLOCKED
            if "risk-brain-hard-block" in flags
            else AgentPromotionState.EVIDENCE_READY
        )
        record = AgentPromotionRecord(
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

    def list(self, workspace_id: str) -> List[AgentPromotionRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> AgentPromotionRecord:
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
    ) -> AgentPromotionRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": AgentPromotionState.ASSESSED,
            "submit-review": AgentPromotionState.REVIEW_REQUIRED,
            "approve": AgentPromotionState.APPROVED,
            "activate": AgentPromotionState.ACTIVE,
            "monitor": AgentPromotionState.MONITORING,
            "suspend": AgentPromotionState.SUSPENDED,
            "revoke": AgentPromotionState.REVOKED,
            "archive": AgentPromotionState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved promotion-readiness findings block approval")
        if action == "activate" and record.state != AgentPromotionState.APPROVED:
            raise ValueError("human approval required before activation")

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

    def _assess(self, payload: AgentPromotionCreate):
        observations = payload.observations
        validation = mean((o.validation_coverage + o.regression_coverage) / 2 for o in observations)
        safety = mean(o.safety_validation_score for o in observations)
        compatibility = mean(o.compatibility_score for o in observations)
        dependency = mean(o.dependency_readiness for o in observations)
        observability = mean(o.observability_readiness for o in observations)
        rollback = mean(o.rollback_readiness for o in observations)
        release = mean((o.canary_readiness + o.change_traceability + o.human_review_coverage) / 3 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_readiness = self._clamp(
            mean([validation, safety, compatibility, dependency, observability, rollback, release]) * confidence
        )
        aggregate_residual_risk = self._clamp(
            mean(
                (1 - o.validation_coverage) * 0.12
                + (1 - o.regression_coverage) * 0.10
                + (1 - o.safety_validation_score) * 0.15
                + (1 - o.compatibility_score) * 0.10
                + (1 - o.dependency_readiness) * 0.10
                + (1 - o.observability_readiness) * 0.10
                + (1 - o.rollback_readiness) * 0.13
                + (1 - o.canary_readiness) * 0.05
                + min(o.blocking_findings / 3, 1) * 0.05
                + min(o.failed_regressions / 3, 1) * 0.04
                + min(o.rollback_failures / 2, 1) * 0.03
                + min(o.unresolved_dependencies / 4, 1) * 0.02
                + min(o.observability_gaps / 4, 1) * 0.01
                for o in observations
            )
        )

        scores = AgentPromotionScores(
            validation_assurance=self._clamp(validation),
            safety_assurance=self._clamp(safety),
            compatibility_assurance=self._clamp(compatibility),
            dependency_assurance=self._clamp(dependency),
            observability_assurance=self._clamp(observability),
            rollback_assurance=self._clamp(rollback),
            release_assurance=self._clamp(release),
            aggregate_readiness=aggregate_readiness,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[PromotionDisposition] = []
        flags: List[str] = []

        for o in observations:
            required_actions: List[str] = []
            lifecycle = "promotion-ready"
            residual = self._clamp(
                (1 - o.validation_coverage) * 0.14
                + (1 - o.regression_coverage) * 0.10
                + (1 - o.safety_validation_score) * 0.16
                + (1 - o.compatibility_score) * 0.12
                + (1 - o.dependency_readiness) * 0.10
                + (1 - o.observability_readiness) * 0.10
                + (1 - o.rollback_readiness) * 0.14
                + (1 - o.canary_readiness) * 0.06
                + min(o.blocking_findings / 3, 1) * 0.04
                + min(o.failed_regressions / 3, 1) * 0.02
                + min(o.rollback_failures / 2, 1) * 0.02
            )

            if o.validation_coverage < payload.min_validation_coverage or o.failed_regressions > 0:
                lifecycle = "validation-gap"
                required_actions.append("validation-and-regression-review")
                flags.append(f"validation-gap:{o.agent_id}:{o.candidate_version}")

            if o.safety_validation_score < payload.min_safety_validation or o.blocking_findings > 0:
                lifecycle = "release-risk-alert"
                required_actions.append("safety-and-blocking-findings-review")
                flags.append(f"release-risk-alert:{o.agent_id}:{o.candidate_version}")

            if o.compatibility_score < payload.min_compatibility_score or o.unresolved_dependencies > 0:
                lifecycle = "compatibility-alert"
                required_actions.append("compatibility-and-dependency-review")
                flags.append(f"compatibility-alert:{o.agent_id}:{o.candidate_version}")

            if o.observability_readiness < payload.min_observability_readiness or o.observability_gaps > 0:
                lifecycle = "observability-alert"
                required_actions.append("observability-readiness-review")
                flags.append(f"observability-alert:{o.agent_id}:{o.candidate_version}")

            if o.rollback_readiness < payload.min_rollback_readiness or o.rollback_failures > 0:
                lifecycle = "rollback-alert"
                required_actions.append("rollback-readiness-review")
                flags.append(f"rollback-alert:{o.agent_id}:{o.candidate_version}")

            if residual > payload.max_residual_risk:
                required_actions.append("agent-promotion-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{o.agent_id}:{o.candidate_version}")

            if o.business_criticality >= 0.90 and (
                o.blocking_findings > 0
                or o.rollback_failures > 0
                or o.safety_validation_score < 0.60
                or residual >= 0.60
            ):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")
                lifecycle = "release-risk-alert"

            dispositions.append(
                PromotionDisposition(
                    agent_id=o.agent_id,
                    candidate_version=o.candidate_version,
                    readiness_score=self._clamp(1 - residual),
                    residual_risk=residual,
                    lifecycle_signal=lifecycle,
                    required_actions=sorted(set(required_actions)),
                )
            )

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: AgentPromotionRecord,
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


agent_promotion_deployment_readiness_service = AgentPromotionDeploymentReadinessService()
