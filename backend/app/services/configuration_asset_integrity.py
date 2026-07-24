from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.configuration_asset_integrity import (
    AssetDisposition,
    ConfigurationAssetCreate,
    ConfigurationAssetRecord,
    ConfigurationAssetScores,
    ConfigurationAssetState,
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


class ConfigurationAssetIntegrityService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ConfigurationAssetRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "configuration-asset-integrity",
            "version": "21.86",
            "governance_only": True,
            "asset_mutation_enabled": False,
            "configuration_mutation_enabled": False,
            "remediation_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ConfigurationAssetCreate) -> ConfigurationAssetRecord:
        identity = (payload.workspace_id, payload.source_key)
        if identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = ConfigurationAssetState.BLOCKED if "risk-brain-hard-block" in flags else ConfigurationAssetState.EVIDENCE_READY
        record = ConfigurationAssetRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            dispositions=dispositions,
            risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(identity)
        self._append_audit(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[ConfigurationAssetRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ConfigurationAssetRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> ConfigurationAssetRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": ConfigurationAssetState.ASSESSED,
            "submit-review": ConfigurationAssetState.REVIEW_REQUIRED,
            "approve": ConfigurationAssetState.APPROVED,
            "activate": ConfigurationAssetState.ACTIVE,
            "monitor": ConfigurationAssetState.MONITORING,
            "suspend": ConfigurationAssetState.SUSPENDED,
            "revoke": ConfigurationAssetState.REVOKED,
            "archive": ConfigurationAssetState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved configuration and asset integrity findings block approval")
        if action == "activate" and record.state != ConfigurationAssetState.APPROVED:
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

    def _assess(self, payload: ConfigurationAssetCreate):
        observations = payload.observations
        inventory_strength = mean(o.inventory_coverage for o in observations)
        ownership_strength = mean(o.ownership_coverage for o in observations)
        baseline_strength = mean((o.baseline_compliance + o.patch_baseline_compliance + o.hardening_coverage) / 3 for o in observations)
        configuration_integrity = mean(o.configuration_integrity for o in observations)
        lifecycle_strength = mean((o.lifecycle_currency + o.backup_configuration_coverage) / 2 for o in observations)
        dependency_visibility = mean(o.dependency_mapping for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_integrity = self._clamp(mean([
            inventory_strength,
            ownership_strength,
            baseline_strength,
            configuration_integrity,
            lifecycle_strength,
            dependency_visibility,
        ]) * confidence)

        aggregate_residual_risk = self._clamp(mean(
            (1 - o.inventory_coverage) * 0.10
            + (1 - o.baseline_compliance) * 0.15
            + (1 - o.configuration_integrity) * 0.20
            + o.drift_score * 0.20
            + o.unauthorized_change_score * 0.20
            + (1 - o.lifecycle_currency) * 0.10
            + min(o.open_configuration_findings / 10, 1) * 0.05
            for o in observations
        ))

        scores = ConfigurationAssetScores(
            inventory_strength=self._clamp(inventory_strength),
            ownership_strength=self._clamp(ownership_strength),
            baseline_strength=self._clamp(baseline_strength),
            configuration_integrity=self._clamp(configuration_integrity),
            lifecycle_strength=self._clamp(lifecycle_strength),
            dependency_visibility=self._clamp(dependency_visibility),
            aggregate_integrity=aggregate_integrity,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[AssetDisposition] = []
        flags: List[str] = []
        for observation in observations:
            actions: List[str] = []
            lifecycle = "integrity-verified"
            residual = self._clamp(
                (1 - observation.inventory_coverage) * 0.10
                + (1 - observation.ownership_coverage) * 0.05
                + (1 - observation.baseline_compliance) * 0.15
                + (1 - observation.configuration_integrity) * 0.20
                + observation.drift_score * 0.20
                + observation.unauthorized_change_score * 0.20
                + (1 - observation.lifecycle_currency) * 0.10
            )

            if observation.inventory_coverage < payload.required_inventory_coverage:
                lifecycle = "inventory-gap"
                actions.append("asset-inventory-reconciliation")
                flags.append(f"inventory-gap:{observation.asset_id}")
            if observation.baseline_compliance < payload.required_baseline_compliance:
                lifecycle = "baseline-gap"
                actions.append("configuration-baseline-review")
                flags.append(f"baseline-gap:{observation.asset_id}")
            if observation.ownership_coverage < 0.90:
                lifecycle = "ownership-gap"
                actions.append("asset-owner-assignment")
                flags.append(f"ownership-gap:{observation.asset_id}")
            if observation.drift_score >= 0.30:
                lifecycle = "drift-alert"
                actions.append("configuration-drift-investigation")
                flags.append(f"drift-alert:{observation.asset_id}")
            if observation.unauthorized_change_score >= 0.25 or observation.open_configuration_findings > 0:
                lifecycle = "configuration-alert"
                actions.append("unauthorized-change-and-findings-review")
                flags.append(f"configuration-alert:{observation.asset_id}")
            if observation.lifecycle_currency < 0.70:
                lifecycle = "lifecycle-alert"
                actions.append("lifecycle-and-obsolescence-review")
                flags.append(f"lifecycle-alert:{observation.asset_id}")
            if residual > payload.max_acceptable_residual_risk:
                actions.append("configuration-asset-risk-committee-review")
                flags.append(f"residual-risk-breach:{observation.asset_id}")
            if observation.criticality >= 0.90 and residual >= 0.60:
                actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(AssetDisposition(
                asset_id=observation.asset_id,
                asset_type=observation.asset_type,
                integrity_score=self._clamp(1 - residual),
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: ConfigurationAssetRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


configuration_asset_integrity_service = ConfigurationAssetIntegrityService()
