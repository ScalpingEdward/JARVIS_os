from __future__ import annotations

from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.change_proposal_safe_execution import (
    ChangeProposalAssessment,
    ChangeProposalCreate,
    ChangeProposalRecord,
    ChangeProposalState,
)


class ChangeProposalSafeExecutionService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ChangeProposalRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "change-proposal-safe-execution-contract",
            "version": "21.112",
            "governance_only": True,
            "proposal_generation_enabled": True,
            "execution_enabled": False,
            "configuration_mutation_enabled": False,
            "deployment_enabled": False,
            "traffic_shift_enabled": False,
            "runtime_restart_enabled": False,
            "credential_mutation_enabled": False,
            "permission_mutation_enabled": False,
            "portfolio_mutation_enabled": False,
            "routing_mutation_enabled": False,
            "fund_movement_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "separate_execution_authorization_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: ChangeProposalCreate) -> ChangeProposalRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")

        assessment = self._assess(payload)
        state = ChangeProposalState.BLOCKED if "risk-brain-hard-block" in assessment.risk_flags else ChangeProposalState.DRAFT
        record = ChangeProposalRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            candidate_id=payload.candidate_id,
            target_system=payload.target_system,
            state=state,
            assessment=assessment,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[ChangeProposalRecord]:
        return [record for (ws, _), record in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> ChangeProposalRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> ChangeProposalRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")

        record = self.get(workspace_id, record_id)
        transitions = {
            "validate": ChangeProposalState.VALIDATED,
            "submit-review": ChangeProposalState.REVIEW_REQUIRED,
            "approve": ChangeProposalState.APPROVED,
            "authorize-execution-contract": ChangeProposalState.EXECUTION_READY,
            "revoke": ChangeProposalState.REVOKED,
            "archive": ChangeProposalState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "validate" and not record.assessment.execution_contract_complete:
            raise ValueError("incomplete execution contract cannot be validated")
        if action == "approve" and record.assessment.risk_flags:
            raise ValueError("unresolved change-proposal findings block approval")
        if action == "authorize-execution-contract":
            if record.state != ChangeProposalState.APPROVED:
                raise ValueError("human approval required before execution contract authorization")
            if not record.assessment.execution_contract_complete:
                raise ValueError("incomplete execution contract cannot become execution-ready")

        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "execution_authorized_by": actor if action == "authorize-execution-contract" else record.execution_authorized_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operations.add(receipt)
        self._audit_event(updated, action, actor, operation_id, reason)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [entry for entry in self._audit if entry["workspace_id"] == workspace_id]

    def _assess(self, payload: ChangeProposalCreate) -> ChangeProposalAssessment:
        reversible_coverage = mean(1.0 if step.reversible else 0.0 for step in payload.steps)
        evidence = mean([
            payload.validation_confidence,
            payload.rollback_readiness,
            payload.observability_readiness,
            payload.dependency_readiness,
            reversible_coverage,
        ])
        completeness = bool(
            payload.preconditions and payload.postconditions and payload.rollback_criteria and payload.steps
            and payload.validation_confidence >= 0.80
            and payload.rollback_readiness >= 0.85
            and payload.observability_readiness >= 0.85
            and payload.dependency_readiness >= 0.80
            and payload.execution_window_ready
        )
        residual_risk = self._clamp(
            payload.blast_radius * 0.30
            + (1 - payload.validation_confidence) * 0.16
            + (1 - payload.rollback_readiness) * 0.16
            + (1 - payload.observability_readiness) * 0.12
            + (1 - payload.dependency_readiness) * 0.10
            + (1 - reversible_coverage) * 0.10
            + (0.06 if not payload.execution_window_ready else 0.0)
        )
        flags: List[str] = []
        actions: List[str] = []
        if payload.validation_confidence < 0.80:
            flags.append("validation-evidence-gap")
            actions.append("validation-evidence-review")
        if payload.rollback_readiness < 0.85 or not payload.rollback_criteria:
            flags.append("rollback-readiness-gap")
            actions.append("rollback-contract-review")
        if payload.observability_readiness < 0.85:
            flags.append("observability-readiness-gap")
            actions.append("observability-contract-review")
        if payload.dependency_readiness < 0.80:
            flags.append("dependency-readiness-gap")
            actions.append("dependency-precondition-review")
        if not payload.execution_window_ready:
            flags.append("execution-window-not-ready")
            actions.append("change-window-review")
        if not all(step.reversible for step in payload.steps):
            flags.append("non-reversible-step-present")
            actions.append("non-reversible-step-review")
        if residual_risk > payload.max_residual_risk:
            flags.append("residual-risk-breach")
            actions.append("change-risk-committee")
        if payload.blast_radius >= 0.85 and (payload.rollback_readiness < 0.90 or residual_risk >= 0.55):
            flags.append("risk-brain-hard-block")
            actions.append("risk-brain-hard-block")

        return ChangeProposalAssessment(
            contract_assurance=self._clamp(evidence),
            residual_risk=residual_risk,
            execution_contract_complete=completeness,
            risk_flags=sorted(set(flags)),
            required_actions=sorted(set(actions)),
        )

    def _audit_event(self, record: ChangeProposalRecord, action: str, actor: str, operation_id: str, reason: str | None = None) -> None:
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "reason": reason,
            "version": record.version,
        })


change_proposal_safe_execution_service = ChangeProposalSafeExecutionService()
