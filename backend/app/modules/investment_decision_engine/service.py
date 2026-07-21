from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe
from threading import RLock

from .models import (
    InvestmentDecisionAuditEvent,
    InvestmentDecisionCreate,
    InvestmentDecisionExecute,
    InvestmentDecisionRecord,
    InvestmentDecisionState,
    InvestmentScore,
)


class InvestmentDecisionError(ValueError):
    pass


class InvestmentDecisionService:
    def __init__(self) -> None:
        self._records: dict[str, InvestmentDecisionRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._used_receipts: set[tuple[str, str]] = set()
        self._audit: list[InvestmentDecisionAuditEvent] = []
        self._lock = RLock()

    def status(self) -> dict[str, object]:
        return {
            "module": "investment-decision-engine",
            "version": "21.08",
            "records": len(self._records),
            "safety_boundary": "decision governance only; no capital movement or execution",
        }

    def create(self, payload: InvestmentDecisionCreate) -> InvestmentDecisionRecord:
        with self._lock:
            source_identity = (payload.workspace_id, payload.source_key)
            if source_identity in self._source_keys:
                raise InvestmentDecisionError("duplicate source_key in workspace")

            state = InvestmentDecisionState.ANALYSIS_PENDING
            reasons: list[str] = []
            if payload.risk_brain_hard_block:
                state = InvestmentDecisionState.BLOCKED
                reasons.append("Risk Brain hard block is active")
            elif not payload.evidence_refs or any(not option.evidence_refs for option in payload.options):
                state = InvestmentDecisionState.EVIDENCE_REQUIRED
                reasons.append("complete v21.07 evidence is required")

            record = InvestmentDecisionRecord(
                workspace_id=payload.workspace_id,
                source_risk_register_id=payload.source_risk_register_id,
                source_key=payload.source_key,
                state=state,
                available_capital=payload.available_capital,
                minimum_expected_roi=payload.minimum_expected_roi,
                maximum_residual_risk=payload.maximum_residual_risk,
                strategic_constraints=payload.strategic_constraints,
                evidence_refs=payload.evidence_refs,
                options=payload.options,
                escalation_reasons=reasons,
            )
            self._records[record.record_id] = record
            self._source_keys.add(source_identity)
            self._audit_transition(record, "create", "system", InvestmentDecisionState.ANALYSIS_PENDING, state, "; ".join(reasons) or "record created")
            return record.model_copy(deep=True)

    def list(self, workspace_id: str) -> list[InvestmentDecisionRecord]:
        return [item.model_copy(deep=True) for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> InvestmentDecisionRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise InvestmentDecisionError("record not found")
        return record.model_copy(deep=True)

    def execute(self, workspace_id: str, record_id: str, command: InvestmentDecisionExecute) -> InvestmentDecisionRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise InvestmentDecisionError("record not found")

            previous = record.state
            if command.action == "analyze":
                self._analyze(record)
            elif command.action == "approve":
                if record.state != InvestmentDecisionState.DECISION_READY:
                    raise InvestmentDecisionError("only decision-ready records may be approved")
                if not command.approval_token or command.approval_token != record.approval_token:
                    raise InvestmentDecisionError("valid approval_token required")
                record.approval_token = None
                record.state = InvestmentDecisionState.APPROVED
            elif command.action == "reject":
                if record.state in {InvestmentDecisionState.ISSUED_TO_EXECUTION_PLANNING, InvestmentDecisionState.ARCHIVED}:
                    raise InvestmentDecisionError("record can no longer be rejected")
                record.state = InvestmentDecisionState.REJECTED
            elif command.action == "issue":
                if record.state != InvestmentDecisionState.APPROVED:
                    raise InvestmentDecisionError("only approved records may be issued")
                if not command.downstream_receipt:
                    raise InvestmentDecisionError("downstream_receipt required")
                receipt_identity = (workspace_id, command.downstream_receipt)
                if receipt_identity in self._used_receipts:
                    raise InvestmentDecisionError("downstream receipt replay detected")
                self._used_receipts.add(receipt_identity)
                record.downstream_receipt = command.downstream_receipt
                record.state = InvestmentDecisionState.ISSUED_TO_EXECUTION_PLANNING
            elif command.action == "archive":
                if record.state not in {InvestmentDecisionState.REJECTED, InvestmentDecisionState.ISSUED_TO_EXECUTION_PLANNING}:
                    raise InvestmentDecisionError("only terminal records may be archived")
                record.state = InvestmentDecisionState.ARCHIVED

            record.updated_at = datetime.now(timezone.utc)
            self._audit_transition(record, command.action, command.actor_id, previous, record.state, command.note or command.action)
            return record.model_copy(deep=True)

    def audit(self, workspace_id: str) -> list[InvestmentDecisionAuditEvent]:
        return [event.model_copy(deep=True) for event in self._audit if event.workspace_id == workspace_id]

    def _analyze(self, record: InvestmentDecisionRecord) -> None:
        if record.state in {InvestmentDecisionState.BLOCKED, InvestmentDecisionState.EVIDENCE_REQUIRED}:
            raise InvestmentDecisionError("blocked records cannot be analyzed")
        if record.state not in {InvestmentDecisionState.ANALYSIS_PENDING, InvestmentDecisionState.HUMAN_REVIEW_REQUIRED}:
            raise InvestmentDecisionError("record is not awaiting analysis")

        scores: list[InvestmentScore] = []
        for option in record.options:
            emv = option.expected_value * option.probability_of_success
            roi = (emv - option.required_capital) / option.required_capital if option.required_capital else 20.0
            risk_factor = max(0.0, 1 - option.residual_risk_score / 100)
            risk_adjusted = emv * risk_factor
            efficiency = risk_adjusted / max(option.required_capital, 1.0)
            speed = max(0.0, 100 - min(option.time_to_value_months, 60) / 60 * 100)
            composite = round(
                0.30 * min(efficiency * 25, 100)
                + 0.25 * option.strategic_alignment
                + 0.15 * option.reversibility
                + 0.15 * speed
                + 0.15 * (100 - option.residual_risk_score),
                4,
            )
            reasons: list[str] = []
            if not option.dependencies_ready:
                recommendation = "reject"
                reasons.append("dependencies are not ready")
            elif option.residual_risk_score > record.maximum_residual_risk:
                recommendation = "defer"
                reasons.append("residual risk exceeds approved maximum")
            elif option.required_capital > record.available_capital:
                recommendation = "defer"
                reasons.append("required capital exceeds available capital")
            elif roi < record.minimum_expected_roi:
                recommendation = "conditional"
                reasons.append("expected ROI is below the minimum threshold")
            elif composite >= 65:
                recommendation = "invest"
            elif composite >= 45:
                recommendation = "conditional"
            else:
                recommendation = "defer"
            scores.append(
                InvestmentScore(
                    option_id=option.option_id,
                    expected_monetary_value=round(emv, 4),
                    expected_roi=round(roi, 6),
                    risk_adjusted_value=round(risk_adjusted, 4),
                    capital_efficiency=round(efficiency, 6),
                    strategic_score=option.strategic_alignment,
                    composite_score=composite,
                    recommendation=recommendation,
                    reasons=reasons,
                )
            )

        scores.sort(key=lambda item: (-item.composite_score, item.option_id))
        capital_left = record.available_capital
        selected: list[str] = []
        committed = 0.0
        expected_value = 0.0
        score_by_id = {score.option_id: score for score in scores}
        for option in sorted(record.options, key=lambda item: (-score_by_id[item.option_id].composite_score, item.option_id)):
            score = score_by_id[option.option_id]
            if score.recommendation != "invest" or option.required_capital > capital_left:
                continue
            selected.append(option.option_id)
            capital_left -= option.required_capital
            committed += option.required_capital
            expected_value += score.expected_monetary_value

        escalations: list[str] = []
        if not selected:
            escalations.append("no investable option satisfies governance thresholds")
        if any(score.recommendation == "conditional" for score in scores):
            escalations.append("conditional options require explicit executive review")
        if any(option.residual_risk_score >= 80 for option in record.options):
            escalations.append("critical residual risk is present")

        record.scores = scores
        record.selected_option_ids = selected
        record.committed_capital = round(committed, 4)
        record.portfolio_expected_value = round(expected_value, 4)
        record.portfolio_expected_roi = round((expected_value - committed) / committed, 6) if committed else 0
        record.confidence_score = round(sum(option.probability_of_success for option in record.options) / len(record.options) * 100, 4)
        record.escalation_reasons = escalations
        if escalations:
            record.state = InvestmentDecisionState.HUMAN_REVIEW_REQUIRED
            record.approval_token = None
        else:
            record.state = InvestmentDecisionState.DECISION_READY
            record.approval_token = token_urlsafe(24)

    def _audit_transition(
        self,
        record: InvestmentDecisionRecord,
        action: str,
        actor_id: str,
        from_state: InvestmentDecisionState,
        to_state: InvestmentDecisionState,
        detail: str,
    ) -> None:
        self._audit.append(
            InvestmentDecisionAuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor_id=actor_id,
                from_state=from_state,
                to_state=to_state,
                detail=detail,
            )
        )


service = InvestmentDecisionService()
