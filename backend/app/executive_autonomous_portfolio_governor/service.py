from datetime import datetime, timezone
from uuid import UUID

from .models import (
    GovernorAction,
    GovernorExecuteRequest,
    GovernorState,
    PortfolioGovernorAudit,
    PortfolioGovernorCreate,
    PortfolioGovernorRecord,
    PortfolioGovernorStatus,
)


class AutonomousPortfolioGovernorService:
    def __init__(self) -> None:
        self._records: dict[UUID, PortfolioGovernorRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[PortfolioGovernorAudit] = []

    def create(self, payload: PortfolioGovernorCreate) -> PortfolioGovernorRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, breaches, actions = self._evaluate(payload)
        record = PortfolioGovernorRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            breaches=breaches,
            actions=actions,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: PortfolioGovernorCreate):
        if payload.upstream_risk_brain_blocked:
            return GovernorState.BLOCKED, "upstream Risk Brain hard block", ["risk-brain"], [GovernorAction(action="block-new-trades", reason="Risk Brain block", automatic=True)]
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return GovernorState.BLOCKED, "account-risk and prop-rule approval required", ["governance-approval"], []
        s, l = payload.snapshot, payload.limits
        if not (s.market_allowed_by_v19_08 and s.shadow_validated_by_v19_09 and s.journal_validated_by_v19_10 and s.optimizer_approved_by_v19_11):
            return GovernorState.EVIDENCE_REQUIRED, "v19.08-v19.11 evidence required", ["upstream-evidence"], []

        breaches: list[str] = []
        if s.daily_drawdown_pct >= l.max_daily_drawdown_pct:
            breaches.append("daily-drawdown")
        if s.total_drawdown_pct >= l.max_total_drawdown_pct:
            breaches.append("total-drawdown")
        if s.portfolio_heat_pct >= l.max_portfolio_heat_pct:
            breaches.append("portfolio-heat")
        if s.margin_level_pct <= l.min_margin_level_pct:
            breaches.append("margin-level")
        if s.correlated_exposure_pct >= l.max_correlated_exposure_pct:
            breaches.append("correlated-exposure")
        if s.spread_multiplier >= l.max_spread_multiplier:
            breaches.append("spread-expansion")
        if s.broker_latency_ms >= l.max_broker_latency_ms:
            breaches.append("broker-latency")
        if not s.data_feed_healthy:
            breaches.append("data-feed")
        if not s.vps_healthy:
            breaches.append("vps")

        hard = {"daily-drawdown", "total-drawdown", "margin-level", "data-feed", "vps"}
        if hard.intersection(breaches):
            actions = [
                GovernorAction(action="block-new-trades", reason=", ".join(breaches), automatic=True),
                GovernorAction(action="request-position-protection", reason="hard safety breach", automatic=True),
            ]
            return GovernorState.KILL_SWITCH, "hard safety breach; kill switch required", breaches, actions
        if breaches:
            actions = [GovernorAction(action="pause-or-reduce-affected-strategies", reason=", ".join(breaches), automatic=False)]
            return GovernorState.ACTION_REQUIRED, "portfolio requires governed intervention", breaches, actions
        return GovernorState.ACTIVE, "portfolio inside approved limits", [], []

    def execute(self, record_id: UUID, workspace_id: str, request: GovernorExecuteRequest) -> PortfolioGovernorRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("governor record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if request.action in {"approve-recovery", "resume"} and not approved:
            raise ValueError("human approval required")
        if request.action == "activate-kill-switch":
            record.state, record.detail = GovernorState.KILL_SWITCH, "kill switch activated"
            record.actions.append(GovernorAction(action="block-new-trades", reason="manual governor activation", automatic=False))
        elif request.action == "prepare-recovery":
            if record.state != GovernorState.KILL_SWITCH:
                raise ValueError("recovery can only be prepared after kill switch")
            record.state, record.detail = GovernorState.RECOVERY_PENDING, "market, risk and portfolio reevaluation required"
        elif request.action == "approve-recovery":
            if record.state != GovernorState.RECOVERY_PENDING:
                raise ValueError("recovery is not pending")
            record.state, record.detail = GovernorState.RECOVERY_READY, "recovery approved for controlled resume"
        elif request.action == "resume":
            if record.state != GovernorState.RECOVERY_READY:
                raise ValueError("controlled resume is not ready")
            record.state, record.detail = GovernorState.ACTIVE, "portfolio resumed under existing limits"
        elif request.action == "archive":
            record.state, record.detail = GovernorState.ARCHIVED, "governor record archived"
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PortfolioGovernorRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PortfolioGovernorRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PortfolioGovernorStatus:
        records = self.list_records(workspace_id)
        return PortfolioGovernorStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            active_records=sum(r.state == GovernorState.ACTIVE for r in records),
            kill_switch_records=sum(r.state == GovernorState.KILL_SWITCH for r in records),
            recovery_records=sum(r.state in {GovernorState.RECOVERY_PENDING, GovernorState.RECOVERY_READY} for r in records),
        )

    def audit_records(self, workspace_id: str) -> list[PortfolioGovernorAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: PortfolioGovernorRecord, actor_id: str, action: str) -> None:
        self._audit.append(PortfolioGovernorAudit(record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id, action=action, state=record.state, detail=record.detail))


autonomous_portfolio_governor_service = AutonomousPortfolioGovernorService()
