from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    BugSeverity,
    ComponentState,
    DetectedIssue,
    ReadinessAssessment,
    ReadinessInput,
    ReadinessScores,
    ReadinessState,
    ReadinessStatusResponse,
)


class ExecutiveTradingReadinessService:
    def __init__(self) -> None:
        self._items: dict[UUID, ReadinessAssessment] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    @staticmethod
    def _component_score(state: ComponentState) -> float:
        return {ComponentState.healthy: 100.0, ComponentState.degraded: 55.0, ComponentState.unavailable: 0.0}[state]

    @staticmethod
    def _issue(code: str, component: str, severity: BugSeverity, message: str, blocking: bool, remediation: str) -> DetectedIssue:
        return DetectedIssue(code=code, component=component, severity=severity, message=message, blocking=blocking, remediation=remediation)

    def assess(self, payload: ReadinessInput) -> ReadinessAssessment:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.source_key == payload.source_key for item in self._items.values()):
                raise ValueError("A readiness assessment with this source key already exists in the workspace")

            issues: list[DetectedIssue] = []
            reasons: list[str] = []

            if not payload.market_regime_allowed:
                issues.append(self._issue("MARKET_REGIME_BLOCK", "market", BugSeverity.critical, "Market regime does not permit trading", True, "Wait for an allowed market regime"))
            if payload.news_risk >= 80:
                issues.append(self._issue("HIGH_IMPACT_NEWS", "market", BugSeverity.critical, "High-impact news risk is active", True, "Wait until the configured news blackout expires"))
            elif payload.news_risk >= 55:
                issues.append(self._issue("ELEVATED_NEWS", "market", BugSeverity.warning, "News risk is elevated", False, "Reduce exposure or wait for confirmation"))
            if not payload.session_open:
                issues.append(self._issue("SESSION_CLOSED", "session", BugSeverity.critical, "Trading session is closed", True, "Wait for an allowed session"))
            elif not payload.killzone_active:
                issues.append(self._issue("OUTSIDE_KILLZONE", "session", BugSeverity.warning, "Configured killzone is inactive", False, "Wait for the preferred execution window"))
            if payload.spread_score < 40:
                issues.append(self._issue("SPREAD_UNACCEPTABLE", "execution", BugSeverity.critical, "Spread quality is below the safe threshold", True, "Wait for spread normalization"))
            elif payload.spread_score < 65:
                issues.append(self._issue("SPREAD_DEGRADED", "execution", BugSeverity.warning, "Spread quality is degraded", False, "Use reduced exposure or delay entry"))
            if not payload.symbol_available:
                issues.append(self._issue("SYMBOL_UNAVAILABLE", "broker", BugSeverity.critical, "Symbol is unavailable", True, "Verify market hours and broker symbol mapping"))
            for name, state in (("broker", payload.broker_state), ("feed", payload.feed_state), ("vps", payload.vps_state)):
                if state == ComponentState.unavailable:
                    issues.append(self._issue(f"{name.upper()}_DOWN", name, BugSeverity.critical, f"{name.title()} component is unavailable", True, f"Restore {name} connectivity before trading"))
                elif state == ComponentState.degraded:
                    issues.append(self._issue(f"{name.upper()}_DEGRADED", name, BugSeverity.warning, f"{name.title()} component is degraded", False, f"Investigate {name} health and monitor stability"))
            if payload.data_age_seconds > payload.max_data_age_seconds:
                issues.append(self._issue("STALE_MARKET_DATA", "data", BugSeverity.critical, "Market data is stale", True, "Refresh the feed and confirm timestamp progression"))
            if payload.latency_ms > payload.max_latency_ms:
                issues.append(self._issue("LATENCY_EXCEEDED", "infrastructure", BugSeverity.critical, "Execution latency exceeds the configured maximum", True, "Stabilize network/VPS latency"))
            if payload.clock_drift_ms > payload.max_clock_drift_ms:
                issues.append(self._issue("CLOCK_DRIFT", "infrastructure", BugSeverity.critical, "System clock drift exceeds the safe threshold", True, "Synchronize system time using a trusted time source"))
            if payload.portfolio_health == "blocked" or payload.risk_state == "blocked" or payload.trading_decision == "reject":
                issues.append(self._issue("UPSTREAM_DECISION_BLOCK", "governance", BugSeverity.critical, "An upstream portfolio, risk or decision gate is blocked", True, "Resolve the upstream blocking state"))
            elif payload.risk_state == "frozen" or payload.trading_decision == "freeze":
                issues.append(self._issue("UPSTREAM_FREEZE", "governance", BugSeverity.critical, "Upstream risk governance froze trading", True, "Wait for a new approved risk assessment"))
            elif payload.trading_decision in {"delay", "shadow"}:
                issues.append(self._issue("UPSTREAM_NON_LIVE", "governance", BugSeverity.warning, "Upstream decision does not authorize live trading", False, "Keep the setup delayed or shadow-only"))

            for signal in payload.open_bug_signals:
                issues.append(DetectedIssue(**signal.model_dump(), remediation="Investigate the reported component and clear the signal after verification"))

            infrastructure = self._clamp((self._component_score(payload.broker_state) + self._component_score(payload.feed_state) + self._component_score(payload.vps_state)) / 3)
            freshness = max(0.0, 100.0 * (1 - payload.data_age_seconds / max(payload.max_data_age_seconds, 1)))
            latency = max(0.0, 100.0 * (1 - payload.latency_ms / max(payload.max_latency_ms, 1)))
            clock = max(0.0, 100.0 * (1 - payload.clock_drift_ms / max(payload.max_clock_drift_ms, 1)))
            data_quality = self._clamp((freshness * 0.5) + (latency * 0.3) + (clock * 0.2))
            market = self._clamp((100 if payload.market_regime_allowed else 0) * 0.25 + payload.evidence_score * 0.2 + payload.strategy_score * 0.2 + payload.spread_score * 0.15 + payload.volatility_score * 0.1 + (100 - payload.news_risk) * 0.1)
            decision = 100.0 if payload.trading_decision == "approve" else 70.0 if payload.trading_decision == "reduce" else 35.0 if payload.trading_decision in {"delay", "shadow"} else 0.0
            execution = self._clamp(payload.spread_score * 0.35 + infrastructure * 0.35 + data_quality * 0.3)
            bug_penalty = sum(45 if item.severity == BugSeverity.critical else 15 if item.severity == BugSeverity.warning else 3 for item in issues)
            bug_health = self._clamp(100 - bug_penalty)
            overall = self._clamp(market * 0.25 + decision * 0.2 + execution * 0.2 + infrastructure * 0.15 + data_quality * 0.1 + bug_health * 0.1)

            blocking = any(item.blocking or item.severity == BugSeverity.critical for item in issues)
            warnings = any(item.severity == BugSeverity.warning for item in issues)
            if blocking:
                state = ReadinessState.blocked
            elif payload.trading_decision in {"delay", "shadow"} or overall < 55:
                state = ReadinessState.wait
            elif warnings or payload.trading_decision == "reduce" or overall < 80:
                state = ReadinessState.conditional
            else:
                state = ReadinessState.ready

            if not issues:
                reasons.append("All configured market, governance, data and infrastructure gates passed")
            else:
                reasons.extend(item.message for item in issues)

            record = ReadinessAssessment(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                source_key=payload.source_key,
                symbol=payload.symbol,
                account_profile=payload.account_profile,
                state=state,
                scores=ReadinessScores(
                    market_readiness=market,
                    decision_readiness=decision,
                    execution_readiness=execution,
                    infrastructure_health=infrastructure,
                    data_quality=data_quality,
                    bug_health=bug_health,
                    overall_readiness=overall,
                ),
                detected_issues=issues,
                reasons=reasons,
                trade_allowed=state in {ReadinessState.ready, ReadinessState.conditional} and payload.trading_decision in {"approve", "reduce"},
                assessed_at=self._now(),
            )
            self._items[record.id] = record
            self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="trading-readiness-assessed", actor_id=payload.actor_id, assessment_id=record.id, details={"state": state.value, "issues": len(issues), "overall": overall}, created_at=self._now()))
            return record

    def list_assessments(self, workspace_id: str) -> list[ReadinessAssessment]:
        with self._lock:
            return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ReadinessAssessment | None:
        with self._lock:
            item = self._items.get(assessment_id)
            return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> ReadinessStatusResponse:
        records = self.list_assessments(workspace_id)
        return ReadinessStatusResponse(
            assessments=len(records),
            ready=sum(item.state == ReadinessState.ready for item in records),
            conditional=sum(item.state == ReadinessState.conditional for item in records),
            waiting=sum(item.state == ReadinessState.wait for item in records),
            blocked=sum(item.state == ReadinessState.blocked for item in records),
            open_critical_issues=sum(issue.severity == BugSeverity.critical for item in records for issue in item.detected_issues),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_trading_readiness_service = ExecutiveTradingReadinessService()
