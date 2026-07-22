from __future__ import annotations

from datetime import datetime
from secrets import token_urlsafe

from .models import (
    AuditEvent,
    OutcomeMetricResult,
    OutcomeVerificationCreate,
    VerificationAction,
    VerificationCommand,
    VerificationRecord,
    VerificationState,
)


class OutcomeVerificationError(RuntimeError):
    pass


class OutcomeVerificationService:
    """Deterministic, in-memory outcome verification with explicit governance gates."""

    def __init__(self) -> None:
        self._records: dict[str, VerificationRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_acceptance_tokens: set[str] = set()
        self._used_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {
            "module": "outcome-verification-engine",
            "version": "21.12",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "verification-and-recommendation-only",
        }

    def create(self, payload: OutcomeVerificationCreate, actor: str = "system") -> VerificationRecord:
        duplicate = self._source_index.get((payload.workspace_id, payload.source_key))
        if duplicate:
            raise OutcomeVerificationError(f"duplicate source_key; existing record={duplicate}")

        if payload.risk_brain_hard_block:
            state = VerificationState.BLOCKED
            findings = ["Risk Brain hard block is authoritative."]
        elif not payload.v21_11_evidence:
            state = VerificationState.EVIDENCE_REQUIRED
            findings = ["PHOENIX v21.11 execution-supervisor evidence is mandatory."]
        elif not payload.workflow_completed:
            state = VerificationState.BLOCKED
            findings = ["Outcome verification requires a completed workflow."]
        else:
            state = VerificationState.INTAKE
            findings = []

        record = VerificationRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            workflow_id=payload.workflow_id,
            execution_supervisor_record_id=payload.execution_supervisor_record_id,
            state=state,
            findings=findings,
        )
        self._records[record.id] = record
        self._source_index[(record.workspace_id, record.source_key)] = record.id
        self._append_audit(record, actor, "create", None, record.state.value)
        if state == VerificationState.INTAKE:
            self._verify(record, payload, actor)
        return record

    def list(self, workspace_id: str) -> list[VerificationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> VerificationRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise OutcomeVerificationError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: VerificationAction) -> VerificationRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == VerificationCommand.ACCEPT:
            if record.state not in {
                VerificationState.VERIFIED,
                VerificationState.PARTIALLY_VERIFIED,
                VerificationState.HUMAN_REVIEW_REQUIRED,
            }:
                raise OutcomeVerificationError("record is not acceptable")
            token = action.acceptance_token or token_urlsafe(24)
            if token in self._used_acceptance_tokens:
                raise OutcomeVerificationError("acceptance token replay detected")
            self._used_acceptance_tokens.add(token)
            record.acceptance_token = token
            record.state = VerificationState.ACCEPTED
        elif action.command == VerificationCommand.REJECT:
            if record.state in {VerificationState.ACCEPTED, VerificationState.ARCHIVED}:
                raise OutcomeVerificationError("terminal record cannot be rejected")
            record.state = VerificationState.REJECTED
        elif action.command == VerificationCommand.REQUEST_REVIEW:
            if record.state in {VerificationState.BLOCKED, VerificationState.EVIDENCE_REQUIRED, VerificationState.ARCHIVED}:
                raise OutcomeVerificationError("record cannot enter human review")
            record.state = VerificationState.HUMAN_REVIEW_REQUIRED
        elif action.command == VerificationCommand.ISSUE:
            if record.state != VerificationState.ACCEPTED:
                raise OutcomeVerificationError("only accepted verification can be issued")
            if not action.downstream_receipt:
                raise OutcomeVerificationError("downstream receipt is required")
            if action.downstream_receipt in self._used_receipts:
                raise OutcomeVerificationError("downstream receipt replay detected")
            self._used_receipts.add(action.downstream_receipt)
            record.downstream_receipt = action.downstream_receipt
        elif action.command == VerificationCommand.ARCHIVE:
            record.state = VerificationState.ARCHIVED

        if action.reason:
            record.findings.append(action.reason)
        record.updated_at = datetime.utcnow()
        self._append_audit(record, action.actor, action.command.value, before, record.state.value)
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def _verify(self, record: VerificationRecord, payload: OutcomeVerificationCreate, actor: str) -> None:
        before = record.state.value
        record.state = VerificationState.VERIFYING
        results: list[OutcomeMetricResult] = []
        mandatory_failures: list[str] = []
        weighted_score = 0.0
        total_weight = 0.0
        evidenced_weight = 0.0

        for metric in payload.metrics:
            target = metric.target_value
            actual = metric.actual_value
            if target == 0:
                variance = 0.0 if actual == 0 else 100.0
                attainment = 100.0 if actual == 0 else 0.0
            else:
                variance = ((actual - target) / abs(target)) * 100
                raw_attainment = actual / target * 100 if metric.higher_is_better else target / max(actual, 1e-9) * 100
                attainment = max(0.0, min(150.0, raw_attainment))

            tolerance = metric.tolerance_percent
            passed = actual >= target * (1 - tolerance / 100) if metric.higher_is_better else actual <= target * (1 + tolerance / 100)
            notes: list[str] = []
            if not metric.evidence_refs:
                passed = False
                notes.append("No evidence reference supplied.")
            if metric.mandatory and not passed:
                mandatory_failures.append(metric.key)
            results.append(
                OutcomeMetricResult(
                    key=metric.key,
                    description=metric.description,
                    target_value=target,
                    actual_value=actual,
                    variance_percent=round(variance, 2),
                    attainment_percent=round(attainment, 2),
                    weight=metric.weight,
                    passed=passed,
                    mandatory=metric.mandatory,
                    evidence_refs=metric.evidence_refs,
                    notes=notes,
                )
            )
            total_weight += metric.weight
            weighted_score += min(100.0, attainment) * metric.weight
            if metric.evidence_refs:
                evidenced_weight += metric.weight

        outcome_score = weighted_score / max(total_weight, 1)
        evidence_coverage = evidenced_weight / max(total_weight, 1) * 100
        benefit_realization = (
            payload.realized_benefit / payload.expected_benefit * 100 if payload.expected_benefit > 0 else 100.0
        )
        cost_variance = (
            (payload.total_cost - payload.planned_cost) / payload.planned_cost * 100 if payload.planned_cost > 0 else 0.0
        )
        value_for_money = min(100.0, max(0.0, benefit_realization - max(0.0, cost_variance)))

        record.metric_results = results
        record.outcome_score = round(outcome_score, 2)
        record.evidence_coverage_score = round(evidence_coverage, 2)
        record.benefit_realization_percent = round(benefit_realization, 2)
        record.cost_variance_percent = round(cost_variance, 2)
        record.value_for_money_score = round(value_for_money, 2)
        record.mandatory_failures = mandatory_failures

        if evidence_coverage < 100:
            record.findings.append("Evidence coverage is incomplete.")
        if mandatory_failures:
            record.findings.append("Mandatory metrics failed: " + ", ".join(mandatory_failures))
        if benefit_realization < 70:
            record.findings.append("Expected benefit realization is materially at risk.")
        if cost_variance > 20:
            record.findings.append("Cost variance exceeds the governed tolerance.")

        if benefit_realization < 50 or value_for_money < 40:
            record.state = VerificationState.BENEFIT_AT_RISK
        elif mandatory_failures or evidence_coverage < 100:
            record.state = VerificationState.HUMAN_REVIEW_REQUIRED
        elif outcome_score >= payload.acceptance_threshold and benefit_realization >= 80:
            record.state = VerificationState.VERIFIED
        elif outcome_score >= 60:
            record.state = VerificationState.PARTIALLY_VERIFIED
        else:
            record.state = VerificationState.NOT_VERIFIED

        record.updated_at = datetime.utcnow()
        self._append_audit(
            record,
            actor,
            "verify",
            before,
            record.state.value,
            {
                "outcome_score": record.outcome_score,
                "benefit_realization_percent": record.benefit_realization_percent,
                "mandatory_failures": mandatory_failures,
            },
        )

    def _append_audit(
        self,
        record: VerificationRecord,
        actor: str,
        action: str,
        from_state: str | None,
        to_state: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
                details=details or {},
            )
        )
