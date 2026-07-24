from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.change_release_governance import (
    ChangeDisposition,
    ChangeReleaseGovernanceCreate,
    ChangeReleaseGovernanceRecord,
    ChangeReleaseScores,
    ChangeReleaseState,
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


class ChangeReleaseGovernanceService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ChangeReleaseGovernanceRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "change-release-governance",
            "version": "21.85",
            "governance_only": True,
            "deployment_mutation_enabled": False,
            "release_execution_enabled": False,
            "rollback_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ChangeReleaseGovernanceCreate) -> ChangeReleaseGovernanceRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = ChangeReleaseState.BLOCKED if "risk-brain-hard-block" in flags else ChangeReleaseState.EVIDENCE_READY
        record = ChangeReleaseGovernanceRecord(
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

    def list(self, workspace_id: str) -> List[ChangeReleaseGovernanceRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ChangeReleaseGovernanceRecord:
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
    ) -> ChangeReleaseGovernanceRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": ChangeReleaseState.ASSESSED,
            "submit-review": ChangeReleaseState.REVIEW_REQUIRED,
            "approve": ChangeReleaseState.APPROVED,
            "activate": ChangeReleaseState.ACTIVE,
            "monitor": ChangeReleaseState.MONITORING,
            "suspend": ChangeReleaseState.SUSPENDED,
            "revoke": ChangeReleaseState.REVOKED,
            "archive": ChangeReleaseState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved change-governance flags block approval")
        if action == "activate" and record.state != ChangeReleaseState.APPROVED:
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

    def _assess(self, payload: ChangeReleaseGovernanceCreate):
        observations = payload.observations
        test_assurance = mean((o.test_coverage + o.regression_coverage) / 2 for o in observations)
        rollback_resilience = mean(o.rollback_readiness for o in observations)
        review_integrity = mean((o.peer_review_coverage + o.segregation_of_duties) / 2 for o in observations)
        security_assurance = mean(o.security_review_coverage for o in observations)
        dependency_readiness = mean(o.dependency_impact_known for o in observations)
        observability_readiness = mean(o.observability_readiness for o in observations)
        deployment_readiness = mean((o.canary_readiness + o.deployment_rehearsal) / 2 for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_release_assurance = self._clamp(
            mean(
                [
                    test_assurance,
                    rollback_resilience,
                    review_integrity,
                    security_assurance,
                    dependency_readiness,
                    observability_readiness,
                    deployment_readiness,
                ]
            )
            * confidence
        )

        aggregate_residual_risk = self._clamp(
            mean(
                (1 - o.test_coverage) * 0.18
                + (1 - o.rollback_readiness) * 0.18
                + (1 - o.segregation_of_duties) * 0.10
                + (1 - o.security_review_coverage) * 0.14
                + (1 - o.dependency_impact_known) * 0.10
                + (1 - o.observability_readiness) * 0.10
                + min(o.open_blocking_findings / 10, 1) * 0.12
                + min(o.recent_failed_releases / 5, 1) * 0.08
                for o in observations
            )
        )

        scores = ChangeReleaseScores(
            test_assurance=self._clamp(test_assurance),
            rollback_resilience=self._clamp(rollback_resilience),
            review_integrity=self._clamp(review_integrity),
            security_assurance=self._clamp(security_assurance),
            dependency_readiness=self._clamp(dependency_readiness),
            observability_readiness=self._clamp(observability_readiness),
            deployment_readiness=self._clamp(deployment_readiness),
            aggregate_release_assurance=aggregate_release_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[ChangeDisposition] = []
        flags: List[str] = []
        for observation in observations:
            required_actions: List[str] = []
            lifecycle = "release-ready"
            residual = self._clamp(
                (1 - observation.test_coverage) * 0.20
                + (1 - observation.regression_coverage) * 0.10
                + (1 - observation.rollback_readiness) * 0.20
                + (1 - observation.segregation_of_duties) * 0.10
                + (1 - observation.security_review_coverage) * 0.15
                + (1 - observation.dependency_impact_known) * 0.10
                + (1 - observation.observability_readiness) * 0.10
                + min(observation.open_blocking_findings / 10, 1) * 0.05
            )
            readiness = self._clamp(1 - residual)

            if observation.test_coverage < payload.required_test_coverage or observation.regression_coverage < 0.70:
                lifecycle = "test-gap"
                required_actions.append("expand-test-and-regression-coverage")
                flags.append(f"test-gap:{observation.change_id}")
            if observation.rollback_readiness < payload.required_rollback_readiness:
                lifecycle = "rollback-gap"
                required_actions.append("prove-rollback-and-recovery-plan")
                flags.append(f"rollback-gap:{observation.change_id}")
            if observation.segregation_of_duties < 0.75 or observation.peer_review_coverage < 0.75:
                lifecycle = "segregation-alert"
                required_actions.append("independent-change-review")
                flags.append(f"segregation-alert:{observation.change_id}")
            if observation.security_review_coverage < 0.75:
                lifecycle = "security-alert"
                required_actions.append("security-impact-review")
                flags.append(f"security-alert:{observation.change_id}")
            if observation.observability_readiness < 0.70:
                lifecycle = "observability-gap"
                required_actions.append("define-release-observability-and-alerting")
                flags.append(f"observability-gap:{observation.change_id}")
            if residual > payload.max_acceptable_risk or observation.open_blocking_findings > 0:
                lifecycle = "change-risk-alert"
                required_actions.append("change-advisory-board-review")
                flags.append(f"change-risk-alert:{observation.change_id}")
            if observation.criticality >= 0.90 and (
                observation.open_blocking_findings > 0 or residual >= 0.60 or observation.rollback_readiness < 0.40
            ):
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(
                ChangeDisposition(
                    change_id=observation.change_id,
                    component=observation.component,
                    readiness_score=readiness,
                    residual_risk=residual,
                    lifecycle_signal=lifecycle,
                    required_actions=sorted(set(required_actions)),
                )
            )

        return scores, dispositions, sorted(set(flags))

    def _append_audit(
        self,
        record: ChangeReleaseGovernanceRecord,
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


change_release_governance_service = ChangeReleaseGovernanceService()
