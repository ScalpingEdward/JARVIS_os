from collections import defaultdict
from copy import deepcopy
from typing import Dict, List
from uuid import uuid4

from app.schemas.autonomous_risk_committee import (
    RiskCommitteeAction,
    RiskCommitteeCreate,
    RiskCommitteeDecision,
    RiskCommitteeRecord,
    RiskCommitteeState,
)


class AutonomousRiskCommitteeService:
    """In-memory governed risk committee. Advisory only; no execution authority."""

    def __init__(self) -> None:
        self._records: Dict[str, RiskCommitteeRecord] = {}
        self._source_keys: Dict[str, set[str]] = defaultdict(set)
        self._operations: Dict[str, set[str]] = defaultdict(set)
        self._audit: List[dict] = []

    @staticmethod
    def status() -> dict:
        return {
            "module": "PHOENIX v21.78 Autonomous Risk Committee Governance",
            "advisory_only": True,
            "portfolio_mutation_enabled": False,
            "allocation_mutation_enabled": False,
            "limit_mutation_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: RiskCommitteeCreate) -> RiskCommitteeRecord:
        if payload.source_key in self._source_keys[payload.workspace_id]:
            raise ValueError("duplicate source_key in workspace")

        record = RiskCommitteeRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=RiskCommitteeState.EVIDENCE_READY,
            decision=self._deliberate(payload),
            assessments=payload.assessments,
        )
        self._records[record.record_id] = record
        self._source_keys[payload.workspace_id].add(payload.source_key)
        self._write_audit(record, "create", payload.requested_by)
        return deepcopy(record)

    def list(self, workspace_id: str) -> List[RiskCommitteeRecord]:
        return [deepcopy(r) for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> RiskCommitteeRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return deepcopy(record)

    def act(self, workspace_id: str, record_id: str, action: RiskCommitteeAction) -> RiskCommitteeRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        if action.operation_id in self._operations[workspace_id]:
            raise ValueError("operation replay detected")
        self._operations[workspace_id].add(action.operation_id)

        transitions = {
            "deliberate": RiskCommitteeState.DELIBERATING,
            "submit-review": RiskCommitteeState.REVIEW_REQUIRED,
            "approve": RiskCommitteeState.APPROVED,
            "activate": RiskCommitteeState.ACTIVE,
            "monitor": RiskCommitteeState.MONITORING,
            "suspend": RiskCommitteeState.SUSPENDED,
            "revoke": RiskCommitteeState.REVOKED,
            "archive": RiskCommitteeState.ARCHIVED,
        }
        if action.action == "approve":
            if not record.decision.quorum_met or record.decision.veto_triggered:
                raise ValueError("committee decision cannot be approved")
            record.approved_by = action.actor
        if action.action == "activate" and not record.approved_by:
            raise ValueError("human approval required before activation")

        record.state = transitions[action.action]
        record.version += 1
        self._write_audit(record, action.action, action.actor, action.reason)
        return deepcopy(record)

    def audit(self, workspace_id: str) -> List[dict]:
        return [deepcopy(e) for e in self._audit if e["workspace_id"] == workspace_id]

    @staticmethod
    def _deliberate(payload: RiskCommitteeCreate) -> RiskCommitteeDecision:
        total_weight = sum(max(a.confidence, 0.01) for a in payload.assessments)
        support = sum(a.confidence for a in payload.assessments if a.stance == "support") / total_weight
        oppose = sum(a.confidence for a in payload.assessments if a.stance == "oppose") / total_weight
        severity = sum(a.severity * a.confidence for a in payload.assessments) / total_weight
        participating = sum(1 for a in payload.assessments if a.stance != "abstain")
        quorum = participating / len(payload.assessments) >= payload.quorum_threshold
        veto = any(
            a.domain in payload.veto_domains and a.stance == "oppose" and a.confidence >= 0.70
            for a in payload.assessments
        )

        actions: List[str] = []
        if severity >= 0.75:
            decision = "capital-preservation-review"
            actions.append("review aggregate risk and reduce-risk options")
        elif veto:
            decision = "hold"
            actions.append("resolve veto-domain objection")
        elif quorum and support >= payload.approval_threshold:
            decision = "approve-advisory-context"
            actions.append("continue human review before activation")
        else:
            decision = "escalate"
            actions.append("request additional evidence and committee review")
        if any(a.domain == "infrastructure" and a.severity >= 0.70 for a in payload.assessments):
            actions.append("perform infrastructure health review")

        return RiskCommitteeDecision(
            decision=decision,
            approval_ratio=round(support, 4),
            opposition_ratio=round(oppose, 4),
            weighted_risk_severity=round(severity, 4),
            quorum_met=quorum,
            veto_triggered=veto,
            required_actions=actions,
        )

    def _write_audit(self, record: RiskCommitteeRecord, event: str, actor: str, reason: str | None = None) -> None:
        self._audit.append({
            "record_id": record.record_id,
            "workspace_id": record.workspace_id,
            "event": event,
            "actor": actor,
            "reason": reason,
            "state": record.state.value,
            "version": record.version,
        })


service = AutonomousRiskCommitteeService()
