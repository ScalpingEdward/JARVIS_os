from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.data_governance_lineage import (
    DataAssetDisposition,
    DataGovernanceCreate,
    DataGovernanceRecord,
    DataGovernanceScores,
    DataGovernanceState,
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


class DataGovernanceLineageService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], DataGovernanceRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "data-governance-lineage",
            "version": "21.82",
            "governance_only": True,
            "data_mutation_enabled": False,
            "schema_mutation_enabled": False,
            "access_policy_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: DataGovernanceCreate) -> DataGovernanceRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = DataGovernanceState.BLOCKED if "risk-brain-hard-block" in flags else DataGovernanceState.EVIDENCE_READY
        record = DataGovernanceRecord(
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

    def list(self, workspace_id: str) -> List[DataGovernanceRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> DataGovernanceRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> DataGovernanceRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": DataGovernanceState.ASSESSED,
            "submit-review": DataGovernanceState.REVIEW_REQUIRED,
            "approve": DataGovernanceState.APPROVED,
            "activate": DataGovernanceState.ACTIVE,
            "monitor": DataGovernanceState.MONITORING,
            "suspend": DataGovernanceState.SUSPENDED,
            "revoke": DataGovernanceState.REVOKED,
            "archive": DataGovernanceState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved data-governance flags block approval")
        if action == "activate" and record.state != DataGovernanceState.APPROVED:
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

    def _assess(self, payload: DataGovernanceCreate):
        observations = payload.observations
        lineage_strength = mean((o.lineage_coverage + o.source_authority + o.schema_integrity) / 3 for o in observations)
        quality_strength = mean((o.completeness + o.accuracy) / 2 for o in observations)
        freshness_strength = mean((o.freshness + o.timeliness) / 2 for o in observations)
        ownership_strength = mean(1.0 if o.owner and o.steward else 0.5 if o.owner or o.steward else 0.0 for o in observations)
        access_strength = mean((o.access_control_coverage + (1 - o.pii_exposure_risk)) / 2 for o in observations)
        retention_strength = mean(o.retention_compliance for o in observations)
        confidence = mean(o.confidence for o in observations)

        aggregate_trust = self._clamp(mean([
            lineage_strength,
            quality_strength,
            freshness_strength,
            ownership_strength,
            access_strength,
            retention_strength,
        ]) * confidence)

        aggregate_residual_risk = self._clamp(mean(
            (1 - o.lineage_coverage) * 0.20
            + (1 - o.completeness) * 0.10
            + (1 - o.accuracy) * 0.15
            + (1 - o.freshness) * 0.10
            + (1 - o.access_control_coverage) * 0.15
            + o.pii_exposure_risk * 0.15
            + (1 - o.retention_compliance) * 0.10
            + min(o.unresolved_quality_issues / 10, 1) * 0.05
            for o in observations
        ))

        scores = DataGovernanceScores(
            lineage_strength=self._clamp(lineage_strength),
            quality_strength=self._clamp(quality_strength),
            freshness_strength=self._clamp(freshness_strength),
            ownership_strength=self._clamp(ownership_strength),
            access_governance_strength=self._clamp(access_strength),
            retention_strength=self._clamp(retention_strength),
            aggregate_trust=aggregate_trust,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[DataAssetDisposition] = []
        flags: List[str] = []
        for observation in observations:
            actions: List[str] = []
            lifecycle = "trusted"
            quality = self._clamp((observation.completeness + observation.accuracy) / 2)
            residual = self._clamp(
                (1 - observation.lineage_coverage) * 0.25
                + (1 - quality) * 0.20
                + (1 - observation.freshness) * 0.15
                + (1 - observation.access_control_coverage) * 0.15
                + observation.pii_exposure_risk * 0.15
                + (1 - observation.retention_compliance) * 0.10
            )

            if observation.lineage_coverage < payload.required_lineage_coverage:
                lifecycle = "lineage-gap"
                actions.append("lineage-remediation")
                flags.append(f"lineage-gap:{observation.asset_id}")
            if quality < payload.required_quality_score or observation.unresolved_quality_issues > 0:
                lifecycle = "quality-alert"
                actions.append("data-quality-remediation")
                flags.append(f"quality-alert:{observation.asset_id}")
            if observation.freshness < 0.70 or observation.timeliness < 0.70:
                lifecycle = "freshness-alert"
                actions.append("freshness-sla-review")
                flags.append(f"freshness-alert:{observation.asset_id}")
            if not observation.owner or not observation.steward:
                lifecycle = "ownership-gap"
                actions.append("assign-data-owner-and-steward")
                flags.append(f"ownership-gap:{observation.asset_id}")
            if observation.access_control_coverage < 0.80 or observation.pii_exposure_risk > payload.max_pii_exposure_risk:
                lifecycle = "access-alert"
                actions.append("access-and-privacy-review")
                flags.append(f"access-alert:{observation.asset_id}")
            if observation.retention_compliance < 0.80:
                lifecycle = "retention-alert"
                actions.append("retention-policy-review")
                flags.append(f"retention-alert:{observation.asset_id}")
            if observation.criticality >= 0.90 and residual >= 0.60:
                actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(DataAssetDisposition(
                asset_id=observation.asset_id,
                trust_score=self._clamp(1 - residual),
                residual_data_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: DataGovernanceRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


data_governance_lineage_service = DataGovernanceLineageService()
