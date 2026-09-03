from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from .models import (
    AuditEvent,
    DynamicRiskCreate,
    DynamicRiskRecord,
    RiskAction,
    RiskAssessment,
    RiskCommand,
    RiskState,
)


class DynamicRiskError(RuntimeError):
    pass


class DynamicRiskService:
    """Calculates governed risk recommendations without placing or modifying trades."""

    def __init__(self) -> None:
        self._records: dict[str, DynamicRiskRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_approval_tokens: set[str] = set()
        self._used_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {
            "module": "dynamic-risk-engine",
            "version": "21.17",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "risk-recommendation-only-no-execution",
        }

    def create(self, payload: DynamicRiskCreate, actor: str = "system") -> DynamicRiskRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_index:
            raise DynamicRiskError(f"duplicate source_key; existing record={self._source_index[key]}")

        assessment = self._assess(payload)
        if payload.risk_brain_hard_block:
            assessment.blocking_reasons.append("Risk Brain hard block is authoritative.")
            state = RiskState.BLOCKED
        elif not payload.v21_16_approved or not payload.v21_16_evidence:
            assessment.blocking_reasons.append("Approved PHOENIX v21.16 evidence is mandatory.")
            state = RiskState.EVIDENCE_REQUIRED
        elif assessment.blocking_reasons:
            state = RiskState.BLOCKED
        elif payload.active_news_risk or assessment.warnings:
            state = RiskState.HUMAN_REVIEW_REQUIRED
        else:
            state = RiskState.RISK_APPROVED

        record = DynamicRiskRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            position_management_record_id=payload.position_management_record_id,
            symbol=payload.symbol,
            direction=payload.direction,
            state=state,
            assessment=assessment,
        )
        self._records[record.id] = record
        self._source_index[key] = record.id
        self._append_audit(record, actor, "create", None, state.value)
        return record

    def list(self, workspace_id: str) -> list[DynamicRiskRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> DynamicRiskRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise DynamicRiskError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: RiskAction) -> DynamicRiskRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == RiskCommand.APPROVE:
            if record.state not in {RiskState.RISK_APPROVED, RiskState.HUMAN_REVIEW_REQUIRED}:
                raise DynamicRiskError("risk record is not approvable")
            token = action.approval_token or token_urlsafe(24)
            if token in self._used_approval_tokens:
                raise DynamicRiskError("approval token replay detected")
            self._used_approval_tokens.add(token)
            record.approval_token = token
            record.state = RiskState.APPROVED
        elif action.command == RiskCommand.ISSUE:
            if record.state != RiskState.APPROVED:
                raise DynamicRiskError("only approved risk records can be issued")
            if not action.downstream_receipt:
                raise DynamicRiskError("downstream receipt is required")
            if action.downstream_receipt in self._used_receipts:
                raise DynamicRiskError("downstream receipt replay detected")
            self._used_receipts.add(action.downstream_receipt)
            record.downstream_receipt = action.downstream_receipt
            record.state = RiskState.ISSUED_TO_EXPOSURE_MANAGER
        elif action.command == RiskCommand.REJECT:
            if record.state in {RiskState.ISSUED_TO_EXPOSURE_MANAGER, RiskState.ARCHIVED}:
                raise DynamicRiskError("terminal risk record cannot be rejected")
            record.state = RiskState.REJECTED
        elif action.command == RiskCommand.INVALIDATE:
            if record.state == RiskState.ARCHIVED:
                raise DynamicRiskError("archived risk record cannot be invalidated")
            record.state = RiskState.INVALIDATED
        elif action.command == RiskCommand.ARCHIVE:
            record.state = RiskState.ARCHIVED

        if action.reason:
            record.notes.append(action.reason)
        record.updated_at = datetime.now(timezone.utc)
        self._append_audit(record, action.actor, action.command.value, before, record.state.value)
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    @staticmethod
    def _assess(payload: DynamicRiskCreate) -> RiskAssessment:
        account = payload.account
        policy = payload.policy
        daily_loss = max(0.0, (account.daily_start_equity - account.equity) / account.daily_start_equity * 100)
        total_drawdown = max(0.0, (account.initial_account_size - account.equity) / account.initial_account_size * 100)
        open_risk_pct = account.open_risk_amount / account.equity * 100
        multiplier = 1.0
        blocking: list[str] = []
        warnings: list[str] = []
        rationale: list[str] = []

        if payload.setup_grade == "A+":
            multiplier *= 1.15
            rationale.append("A+ setup quality increased the base allocation within policy bounds.")
        elif payload.setup_grade == "A":
            multiplier *= 1.0
        elif payload.setup_grade == "B":
            multiplier *= 0.75
            rationale.append("B-grade setup reduced risk.")
        elif payload.setup_grade == "C":
            multiplier *= 0.5
            warnings.append("C-grade setup requires human review.")
        else:
            blocking.append("Rejected setup grade cannot receive risk allocation.")

        if payload.setup_confidence_score < 60:
            multiplier *= 0.5
            warnings.append("Low setup confidence reduced risk allocation.")
        elif payload.setup_confidence_score >= 85:
            multiplier *= 1.05

        if account.consecutive_losses >= policy.losing_streak_hard_limit:
            blocking.append("Hard losing-streak limit reached.")
        elif account.consecutive_losses >= policy.losing_streak_soft_limit:
            multiplier *= 0.5
            warnings.append("Losing streak triggered defensive risk reduction.")

        if account.volatility_score >= policy.high_volatility_threshold:
            multiplier *= 0.7
            warnings.append("High volatility reduced risk allocation.")
        if account.correlation_exposure_score >= policy.high_correlation_threshold:
            multiplier *= 0.6
            warnings.append("High correlation exposure reduced risk allocation.")
        if payload.active_news_risk:
            multiplier *= 0.5
            warnings.append("Active news risk requires explicit human review.")

        if daily_loss >= policy.maximum_daily_loss_percent:
            blocking.append("Maximum daily loss limit reached.")
        elif daily_loss >= policy.maximum_daily_loss_percent * 0.75:
            multiplier *= 0.5
            warnings.append("Daily loss is near the governed limit.")

        if total_drawdown >= policy.maximum_total_drawdown_percent:
            blocking.append("Maximum total drawdown limit reached.")
        elif total_drawdown >= policy.maximum_total_drawdown_percent * 0.75:
            multiplier *= 0.5
            warnings.append("Total drawdown is near the governed limit.")

        if open_risk_pct >= policy.maximum_aggregate_open_risk_percent:
            blocking.append("Maximum aggregate open risk already reached.")

        recommended_pct = policy.base_risk_percent * multiplier
        recommended_pct = max(policy.minimum_risk_percent, min(policy.maximum_risk_percent, recommended_pct))
        available_open_risk = max(0.0, policy.maximum_aggregate_open_risk_percent - open_risk_pct)
        recommended_pct = min(recommended_pct, available_open_risk)
        if recommended_pct < policy.minimum_risk_percent and not blocking:
            blocking.append("Remaining aggregate risk capacity is below the minimum allocation.")

        risk_amount = account.equity * recommended_pct / 100
        stop_distance = abs(payload.entry_price - payload.stop_price)
        units = risk_amount / (stop_distance * payload.value_per_price_unit) if risk_amount > 0 else 0.0
        if blocking:
            recommended_pct = 0.0
            risk_amount = 0.0
            units = 0.0

        return RiskAssessment(
            recommended_risk_percent=round(recommended_pct, 4),
            recommended_risk_amount=round(risk_amount, 2),
            recommended_position_units=round(units, 6),
            stop_distance=round(stop_distance, 8),
            daily_loss_percent=round(daily_loss, 4),
            total_drawdown_percent=round(total_drawdown, 4),
            aggregate_open_risk_percent=round(open_risk_pct, 4),
            risk_multiplier=round(multiplier, 4),
            blocking_reasons=blocking,
            warnings=warnings,
            rationale=rationale,
        )

    def _append_audit(
        self,
        record: DynamicRiskRecord,
        actor: str,
        action: str,
        from_state: str | None,
        to_state: str,
    ) -> None:
        self._audit.append(AuditEvent(
            workspace_id=record.workspace_id,
            record_id=record.id,
            action=action,
            actor=actor,
            from_state=from_state,
            to_state=to_state,
            details={
                "risk_percent": record.assessment.recommended_risk_percent,
                "risk_amount": record.assessment.recommended_risk_amount,
            },
        ))
