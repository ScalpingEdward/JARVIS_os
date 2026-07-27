from __future__ import annotations

from hashlib import sha256
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.decision_synthesis_uncertainty import (
    DecisionSynthesisCreate,
    DecisionSynthesisRecord,
    DecisionSynthesisScores,
    DecisionSynthesisState,
)


class DecisionSynthesisUncertaintyService:
    PROTECTED_OBJECTIVES = {
        "fund-movement", "order-submit", "trade-execute", "credential-mutate",
        "permission-escalate", "safety-control-disable",
    }

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], DecisionSynthesisRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "decision-synthesis-uncertainty-governance",
            "version": "21.125",
            "decision_synthesis_enabled": True,
            "execution_proposal_generation_enabled": False,
            "external_write_enabled": False,
            "fund_movement_enabled": False,
            "order_submission_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: DecisionSynthesisCreate) -> DecisionSynthesisRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")

        preferred = next(a for a in payload.alternatives if a.alternative_id == payload.preferred_alternative_id)
        ranked = sorted(payload.alternatives, key=lambda a: a.expected_utility * a.confidence, reverse=True)
        top_score = ranked[0].expected_utility * ranked[0].confidence
        second_score = ranked[1].expected_utility * ranked[1].confidence
        separation = self._clamp(top_score - second_score)
        evidence_assurance = self._clamp(mean([payload.aggregate_evidence_confidence, payload.aggregate_freshness]))
        uncertainty = self._clamp(
            (1 - preferred.confidence) * 0.35
            + preferred.downside_risk * 0.20
            + (1 - evidence_assurance) * 0.20
            + (1 - separation) * 0.10
            + min(len(payload.unresolved_questions) / 5, 1) * 0.10
            + (0.05 if not payload.context_conflict_resolved else 0.0)
        )
        residual_risk = self._clamp(
            uncertainty * 0.55
            + preferred.downside_risk * 0.25
            + (1 - preferred.reversibility) * 0.10
            + (1 - evidence_assurance) * 0.10
        )

        scores = DecisionSynthesisScores(
            preferred_confidence=self._clamp(preferred.confidence),
            uncertainty=uncertainty,
            evidence_assurance=evidence_assurance,
            alternative_separation=separation,
            reversibility_assurance=self._clamp(preferred.reversibility),
            residual_risk=residual_risk,
        )

        flags: List[str] = []
        if not payload.context_conflict_resolved:
            flags.append("reasoning-conflict-unresolved")
        if preferred.confidence < payload.min_decision_confidence:
            flags.append("decision-confidence-below-threshold")
        if uncertainty > payload.max_uncertainty:
            flags.append("decision-uncertainty-above-threshold")
        if payload.unresolved_questions:
            flags.append("unresolved-questions-present")
        if preferred.downside_risk >= 0.70:
            flags.append("high-downside-risk")
        if preferred.reversibility < 0.30:
            flags.append("low-reversibility")

        objective_key = payload.objective.strip().lower()
        if any(protected in objective_key for protected in self.PROTECTED_OBJECTIVES):
            flags += ["protected-execution-objective", "risk-brain-hard-block"]
        if payload.criticality >= 0.90 and (preferred.confidence < 0.50 or uncertainty >= 0.65 or not payload.context_conflict_resolved):
            flags.append("risk-brain-hard-block")

        if "risk-brain-hard-block" in flags:
            state = DecisionSynthesisState.BLOCKED
        elif not payload.context_conflict_resolved:
            state = DecisionSynthesisState.CONFLICT
        else:
            state = DecisionSynthesisState.REVIEW_REQUIRED

        decision_packet_digest = sha256(
            f"{payload.reasoning_packet_digest}|{payload.objective}|{payload.preferred_alternative_id}|{preferred.confidence}|{uncertainty}|{residual_risk}".encode()
        ).hexdigest()

        record = DecisionSynthesisRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            reasoning_record_id=payload.reasoning_record_id,
            reasoning_packet_digest=payload.reasoning_packet_digest,
            objective=payload.objective,
            preferred_alternative_id=payload.preferred_alternative_id,
            alternatives=payload.alternatives,
            assumptions=payload.assumptions,
            unresolved_questions=payload.unresolved_questions,
            scores=scores,
            risk_flags=sorted(set(flags)),
            decision_packet_digest=decision_packet_digest,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[DecisionSynthesisRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> DecisionSynthesisRecord:
        if (workspace_id, record_id) not in self._records:
            raise KeyError("record not found")
        return self._records[(workspace_id, record_id)]

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> DecisionSynthesisRecord:
        op = (workspace_id, operation_id)
        if op in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "approve": DecisionSynthesisState.APPROVED,
            "mark-ready": DecisionSynthesisState.READY,
            "reject": DecisionSynthesisState.REJECTED,
            "revoke": DecisionSynthesisState.REVOKED,
            "archive": DecisionSynthesisState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved decision findings block approval")
        if action == "mark-ready" and record.state != DecisionSynthesisState.APPROVED:
            raise ValueError("human approval required before ready state")

        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operations.add(op)
        self._audit_event(updated, action, actor, operation_id, reason)
        return updated

    def audit(self, workspace_id: str) -> List[dict]:
        return [e for e in self._audit if e["workspace_id"] == workspace_id]

    def _audit_event(self, record: DecisionSynthesisRecord, action: str, actor: str, operation_id: str, detail: str | None = None) -> None:
        raw = f"{record.workspace_id}|{record.record_id}|{action}|{actor}|{operation_id}|{record.version}|{record.decision_packet_digest}"
        self._audit.append({
            "workspace_id": record.workspace_id,
            "record_id": record.record_id,
            "action": action,
            "actor": actor,
            "operation_id": operation_id,
            "detail": detail,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


decision_synthesis_uncertainty_service = DecisionSynthesisUncertaintyService()
