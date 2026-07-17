from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalCheck,
    ApprovalDecision,
    KillSwitchState,
    KillSwitchUpdate,
    TradeApprovalCreate,
    TradeApprovalRecord,
    TradeApprovalStatus,
)


class TradeApprovalService:
    def __init__(self) -> None:
        self._records: dict[UUID, TradeApprovalRecord] = {}
        self._kill_switch = KillSwitchState()

    def status(self) -> TradeApprovalStatus:
        return TradeApprovalStatus()

    def kill_switch(self) -> KillSwitchState:
        return self._kill_switch

    def update_kill_switch(self, payload: KillSwitchUpdate) -> KillSwitchState:
        self._kill_switch = KillSwitchState(
            active=payload.active,
            reason=payload.reason.strip() if payload.active else "",
            activated_at=datetime.now(timezone.utc) if payload.active else None,
        )
        return self._kill_switch

    def evaluate(self, payload: TradeApprovalCreate) -> TradeApprovalRecord:
        checks = [
            self._check("global_kill_switch", not (self._kill_switch.active or payload.global_kill_switch), "critical", "Global kill switch is active."),
            self._check("playbook", payload.playbook_approved, "critical", "Setup is not approved by the playbook."),
            self._check("daily_drawdown", payload.daily_drawdown_safe, "critical", "Daily drawdown protection blocks the trade."),
            self._check("total_drawdown", payload.total_drawdown_safe, "critical", "Total drawdown protection blocks the trade."),
            self._check("risk_allocation", payload.allocated_risk_amount >= payload.requested_risk_amount, "critical", "Requested risk exceeds the allocated account budget."),
            self._check("correlation", payload.correlation_safe, "high", "Correlation exposure is above the approved limit."),
            self._check("news_window", payload.news_window_clear, "high", "Trade is inside a blocked news window."),
            self._check("spread", payload.spread_safe, "high", "Spread is outside the approved limit."),
            self._check("reward_to_risk", payload.reward_to_risk >= 1.5, "medium", "Reward-to-risk is below 1.5."),
            self._check("manual_approval", payload.manual_approval, "medium", "MASTER Brano has not approved the trade."),
        ]
        critical_failed = [item for item in checks if not item.passed and item.severity == "critical"]
        other_failed = [item for item in checks if not item.passed and item.severity != "critical"]
        if critical_failed:
            decision = ApprovalDecision.BLOCKED
        elif other_failed:
            decision = ApprovalDecision.HOLD
        else:
            decision = ApprovalDecision.APPROVED
        record = TradeApprovalRecord(
            account_id=payload.account_id,
            symbol=payload.symbol.upper(),
            direction=payload.direction,
            setup_tag=payload.setup_tag.strip().lower(),
            requested_risk_amount=payload.requested_risk_amount,
            allocated_risk_amount=payload.allocated_risk_amount,
            reward_to_risk=payload.reward_to_risk,
            decision=decision,
            checks=checks,
            blockers=[item.message for item in checks if not item.passed],
            execution_permitted=False,
        )
        self._records[record.id] = record
        return record

    def list_all(self) -> list[TradeApprovalRecord]:
        return sorted(self._records.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, record_id: UUID) -> TradeApprovalRecord | None:
        return self._records.get(record_id)

    @staticmethod
    def _check(name: str, passed: bool, severity: str, failure_message: str) -> ApprovalCheck:
        return ApprovalCheck(
            check=name,
            passed=passed,
            severity=severity,
            message="Check passed." if passed else failure_message,
        )


trade_approval_service = TradeApprovalService()
