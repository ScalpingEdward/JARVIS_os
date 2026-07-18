from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    ApprovalRecord,
    ApprovalRequest,
    AlternativeEvaluation,
    AuditRecord,
    ConstraintResult,
    ConstraintType,
    DecisionEvaluation,
    DecisionStatus,
    DecisionStatusResponse,
    DecisionTraceNode,
    ExecutiveDecision,
    ExecutiveDecisionCreate,
)


class ExecutiveDecisionService:
    def __init__(self) -> None:
        self._decisions: dict[UUID, ExecutiveDecision] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, decision_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, decision_id=decision_id, details=details or {}, created_at=self._now()))

    def create(self, payload: ExecutiveDecisionCreate) -> ExecutiveDecision:
        now = self._now()
        record = ExecutiveDecision(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._decisions.values()):
                raise ValueError("An executive decision with this title already exists in the workspace")
            self._decisions[record.id] = record
            self._write_audit(payload.workspace_id, "executive-decision-created", payload.owner_id, record.id, {"alternatives": len(payload.alternatives), "criteria": len(payload.criteria)})
        return record

    def list_decisions(self, workspace_id: str) -> list[ExecutiveDecision]:
        with self._lock:
            return [item for item in self._decisions.values() if item.workspace_id == workspace_id]

    def get(self, decision_id: UUID, workspace_id: str) -> ExecutiveDecision | None:
        with self._lock:
            record = self._decisions.get(decision_id)
            return record if record is not None and record.workspace_id == workspace_id else None

    @staticmethod
    def _constraint_result(constraint, alternative) -> ConstraintResult:
        actual = alternative.attributes.get(constraint.field_name)
        passed = False
        if constraint.constraint_type == ConstraintType.required:
            passed = actual == constraint.value
        elif isinstance(actual, (int, float)) and isinstance(constraint.value, (int, float)):
            if constraint.constraint_type == ConstraintType.maximum:
                passed = actual <= constraint.value
            elif constraint.constraint_type == ConstraintType.minimum:
                passed = actual >= constraint.value
        return ConstraintResult(
            constraint_name=constraint.name,
            alternative_key=alternative.alternative_key,
            passed=passed,
            blocking=constraint.blocking,
            explanation=f"{constraint.field_name}={actual!r}; expected {constraint.constraint_type.value} {constraint.value!r}",
        )

    def evaluate(self, decision_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveDecision:
        with self._lock:
            record = self._decisions.get(decision_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Executive decision not found")
            if record.status in {DecisionStatus.approved, DecisionStatus.rejected}:
                raise ValueError("Finalized decisions cannot be re-evaluated")

            constraint_results: list[ConstraintResult] = []
            raw: list[dict] = []
            trace: list[DecisionTraceNode] = [DecisionTraceNode(node_type="objective", key="objective", label=record.objective)]

            for alternative in record.alternatives:
                contributions: dict[str, float] = {}
                weighted = 0.0
                for criterion in record.criteria:
                    score = alternative.criterion_scores[criterion.name]
                    contribution = score * criterion.weight / 100.0
                    contributions[criterion.name] = round(contribution, 2)
                    weighted += contribution
                    trace.append(DecisionTraceNode(node_type="criterion", key=f"{alternative.alternative_key}:{criterion.name}", label=criterion.name, value=round(contribution, 2)))

                results = [self._constraint_result(item, alternative) for item in record.constraints]
                constraint_results.extend(results)
                feasible = not any(not item.passed and item.blocking for item in results)
                risk_penalty = alternative.risk_score * 0.15
                confidence_factor = 0.75 + alternative.confidence / 400.0
                adjusted = max(0.0, min(100.0, (weighted - risk_penalty) * confidence_factor)) if feasible else 0.0
                trade_offs = []
                if alternative.risk_score >= 60:
                    trade_offs.append("High execution risk reduces the adjusted score")
                if alternative.implementation_cost > 0:
                    trade_offs.append(f"Implementation cost: {alternative.implementation_cost:.2f}")
                if not feasible:
                    trade_offs.append("Alternative violates one or more blocking constraints")
                raw.append({"alternative": alternative, "weighted": weighted, "adjusted": adjusted, "feasible": feasible, "trade_offs": trade_offs, "contributions": contributions})

            ranked = sorted(raw, key=lambda item: (item["feasible"], item["adjusted"], item["alternative"].expected_value), reverse=True)
            evaluations: list[AlternativeEvaluation] = []
            for rank, item in enumerate(ranked, start=1):
                alternative = item["alternative"]
                evaluations.append(AlternativeEvaluation(
                    alternative_key=alternative.alternative_key,
                    title=alternative.title,
                    weighted_score=round(item["weighted"], 2),
                    adjusted_score=round(item["adjusted"], 2),
                    confidence=alternative.confidence,
                    risk_score=alternative.risk_score,
                    expected_value=alternative.expected_value,
                    implementation_cost=alternative.implementation_cost,
                    rank=rank,
                    feasible=item["feasible"],
                    trade_offs=item["trade_offs"],
                    score_explanation=item["contributions"],
                ))
                trace.append(DecisionTraceNode(node_type="alternative", key=alternative.alternative_key, label=alternative.title, value=round(item["adjusted"], 2)))

            feasible = [item for item in evaluations if item.feasible]
            recommended = feasible[0].alternative_key if feasible else None
            blocking = sorted({f"{item.alternative_key}: {item.constraint_name}" for item in constraint_results if not item.passed and item.blocking})
            if feasible:
                top = feasible[0]
                second_score = feasible[1].adjusted_score if len(feasible) > 1 else 0.0
                separation = max(0.0, top.adjusted_score - second_score)
                confidence = min(100.0, top.confidence * 0.6 + separation * 2.0 + 20.0)
                summary = f"{top.title} is the recommended alternative with an adjusted score of {top.adjusted_score:.2f}. Human approval remains mandatory."
            else:
                confidence = 0.0
                summary = "No feasible alternative satisfies all blocking constraints. The decision must be revised before approval."

            evaluation = DecisionEvaluation(
                evaluated_at=self._now(),
                recommended_alternative_key=recommended,
                executive_confidence=round(confidence, 2),
                evaluations=evaluations,
                constraint_results=constraint_results,
                trace=trace,
                blocking_reasons=blocking,
                executive_summary=summary,
            )
            updated = record.model_copy(update={"evaluation": evaluation, "status": DecisionStatus.evaluated, "version": record.version + 1, "updated_at": self._now()})
            self._decisions[decision_id] = updated
            self._write_audit(workspace_id, "executive-decision-evaluated", actor_id, decision_id, {"recommended": recommended, "confidence": evaluation.executive_confidence, "blocking_reasons": len(blocking)})
            return updated

    def approve(self, decision_id: UUID, workspace_id: str, request: ApprovalRequest) -> ExecutiveDecision:
        with self._lock:
            record = self._decisions.get(decision_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Executive decision not found")
            if record.status != DecisionStatus.evaluated or record.evaluation is None:
                raise ValueError("Decision must be evaluated before approval")
            if request.actor_id == record.owner_id:
                raise ValueError("Decision owners cannot approve their own decisions")
            if request.approved and (record.evaluation.recommended_alternative_key is None or record.evaluation.blocking_reasons):
                raise ValueError("Blocked decisions cannot be approved")
            approval = ApprovalRecord(actor_id=request.actor_id, approved=request.approved, comment=request.comment, created_at=self._now())
            status = DecisionStatus.approved if request.approved else DecisionStatus.rejected
            updated = record.model_copy(update={"approval": approval, "status": status, "version": record.version + 1, "updated_at": self._now()})
            self._decisions[decision_id] = updated
            self._write_audit(workspace_id, "executive-decision-approved" if request.approved else "executive-decision-rejected", request.actor_id, decision_id, {"comment": request.comment})
            return updated

    def status(self, workspace_id: str) -> DecisionStatusResponse:
        records = self.list_decisions(workspace_id)
        return DecisionStatusResponse(
            decisions=len(records),
            evaluated_decisions=sum(item.status == DecisionStatus.evaluated for item in records),
            approved_decisions=sum(item.status == DecisionStatus.approved for item in records),
            blocked_decisions=sum(item.evaluation is not None and bool(item.evaluation.blocking_reasons) for item in records),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_decision_service = ExecutiveDecisionService()
