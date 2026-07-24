from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.third_party_supply_chain_risk import (
    ThirdPartyDisposition,
    ThirdPartyRiskCreate,
    ThirdPartyRiskRecord,
    ThirdPartyRiskScores,
    ThirdPartyRiskState,
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


class ThirdPartySupplyChainRiskService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ThirdPartyRiskRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operation_ids: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "third-party-supply-chain-risk",
            "version": "21.84",
            "governance_only": True,
            "vendor_mutation_enabled": False,
            "contract_mutation_enabled": False,
            "access_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ThirdPartyRiskCreate) -> ThirdPartyRiskRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        scores, dispositions, flags = self._assess(payload)
        state = ThirdPartyRiskState.BLOCKED if "risk-brain-hard-block" in flags else ThirdPartyRiskState.EVIDENCE_READY
        record = ThirdPartyRiskRecord(
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

    def list(self, workspace_id: str) -> List[ThirdPartyRiskRecord]:
        return [record for (workspace, _), record in self._records.items() if workspace == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ThirdPartyRiskRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> ThirdPartyRiskRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operation_ids:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": ThirdPartyRiskState.ASSESSED,
            "submit-review": ThirdPartyRiskState.REVIEW_REQUIRED,
            "approve": ThirdPartyRiskState.APPROVED,
            "activate": ThirdPartyRiskState.ACTIVE,
            "monitor": ThirdPartyRiskState.MONITORING,
            "suspend": ThirdPartyRiskState.SUSPENDED,
            "revoke": ThirdPartyRiskState.REVOKED,
            "archive": ThirdPartyRiskState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved third-party risk flags block approval")
        if action == "activate" and record.state != ThirdPartyRiskState.APPROVED:
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

    def _assess(self, payload: ThirdPartyRiskCreate):
        observations = payload.observations
        due_diligence_strength = mean(o.due_diligence_coverage for o in observations)
        security_privacy_strength = mean((o.security_assurance + o.privacy_assurance) / 2 for o in observations)
        resilience_strength = mean(o.operational_resilience for o in observations)
        commercial_strength = mean((o.financial_health + o.contract_control_coverage) / 2 for o in observations)
        supply_chain_transparency = mean(o.subcontractor_transparency for o in observations)
        exit_readiness = mean(o.exit_plan_readiness for o in observations)
        concentration_resilience = mean(1 - o.concentration_dependency for o in observations)
        confidence = mean(o.confidence * o.freshness for o in observations)

        aggregate_assurance = self._clamp(mean([
            due_diligence_strength,
            security_privacy_strength,
            resilience_strength,
            commercial_strength,
            supply_chain_transparency,
            exit_readiness,
            concentration_resilience,
        ]) * confidence)

        aggregate_residual_risk = self._clamp(mean(
            (1 - o.due_diligence_coverage) * 0.15
            + (1 - o.security_assurance) * 0.15
            + (1 - o.privacy_assurance) * 0.10
            + (1 - o.operational_resilience) * 0.15
            + o.concentration_dependency * 0.15
            + (1 - o.contract_control_coverage) * 0.10
            + (1 - o.exit_plan_readiness) * 0.10
            + o.jurisdiction_risk * 0.05
            + o.incident_history_score * 0.05
            for o in observations
        ))

        scores = ThirdPartyRiskScores(
            due_diligence_strength=self._clamp(due_diligence_strength),
            security_privacy_strength=self._clamp(security_privacy_strength),
            resilience_strength=self._clamp(resilience_strength),
            commercial_strength=self._clamp(commercial_strength),
            supply_chain_transparency=self._clamp(supply_chain_transparency),
            exit_readiness=self._clamp(exit_readiness),
            concentration_resilience=self._clamp(concentration_resilience),
            aggregate_assurance=aggregate_assurance,
            aggregate_residual_risk=aggregate_residual_risk,
            confidence=self._clamp(confidence),
        )

        dispositions: List[ThirdPartyDisposition] = []
        flags: List[str] = []
        for observation in observations:
            required_actions: List[str] = []
            lifecycle = "acceptable"
            residual = self._clamp(
                (1 - observation.due_diligence_coverage) * 0.15
                + (1 - observation.security_assurance) * 0.15
                + (1 - observation.privacy_assurance) * 0.10
                + (1 - observation.operational_resilience) * 0.15
                + observation.concentration_dependency * 0.15
                + (1 - observation.contract_control_coverage) * 0.10
                + (1 - observation.exit_plan_readiness) * 0.10
                + observation.jurisdiction_risk * 0.05
                + observation.incident_history_score * 0.05
            )
            assurance = self._clamp(1 - residual)

            if observation.due_diligence_coverage < payload.min_due_diligence_coverage:
                lifecycle = "due-diligence-gap"
                required_actions.append("independent-third-party-due-diligence")
                flags.append(f"due-diligence-gap:{observation.provider_id}")
            if observation.concentration_dependency > payload.max_concentration_dependency:
                lifecycle = "concentration-alert"
                required_actions.append("concentration-and-substitutability-review")
                flags.append(f"concentration-alert:{observation.provider_id}")
            if min(observation.security_assurance, observation.privacy_assurance) < 0.70 or observation.open_high_findings > 0:
                lifecycle = "security-alert"
                required_actions.append("security-and-privacy-remediation-review")
                flags.append(f"security-alert:{observation.provider_id}")
            if observation.operational_resilience < 0.70:
                lifecycle = "resilience-alert"
                required_actions.append("business-continuity-and-recovery-review")
                flags.append(f"resilience-alert:{observation.provider_id}")
            if observation.contract_control_coverage < 0.70:
                lifecycle = "contract-alert"
                required_actions.append("contractual-controls-and-audit-rights-review")
                flags.append(f"contract-alert:{observation.provider_id}")
            if observation.exit_plan_readiness < 0.60:
                lifecycle = "exit-risk"
                required_actions.append("exit-and-transition-plan-review")
                flags.append(f"exit-risk:{observation.provider_id}")
            if residual > payload.max_acceptable_residual_risk:
                required_actions.append("third-party-risk-committee-escalation")
                flags.append(f"residual-risk-breach:{observation.provider_id}")
            if observation.criticality >= 0.90 and residual >= 0.60:
                required_actions.append("risk-brain-hard-block")
                flags.append("risk-brain-hard-block")

            dispositions.append(ThirdPartyDisposition(
                provider_id=observation.provider_id,
                provider_name=observation.provider_name,
                service_domain=observation.service_domain,
                assurance_score=assurance,
                residual_risk=residual,
                lifecycle_signal=lifecycle,
                required_actions=sorted(set(required_actions)),
            ))

        return scores, dispositions, sorted(set(flags))

    def _append_audit(self, record: ThirdPartyRiskRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
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


third_party_supply_chain_risk_service = ThirdPartySupplyChainRiskService()
