from __future__ import annotations

from statistics import mean

from .models import (
    AuditEvent, MacroAction, MacroCreate, MacroIndicator, MacroRecord, MacroState, utcnow,
)


class GovernanceError(ValueError):
    pass


class MacroGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, MacroRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: MacroCreate) -> MacroRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        record = MacroRecord(
            **payload.model_dump(),
            state=MacroState.BLOCKED if payload.risk_brain_blocked else MacroState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[MacroRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> MacroRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: MacroAction) -> MacroRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({MacroState.DRAFT}, MacroState.EVIDENCE_READY),
            "classify": ({MacroState.EVIDENCE_READY}, MacroState.CLASSIFIED),
            "prepare-policy": ({MacroState.CLASSIFIED, MacroState.REGIME_SHIFT}, MacroState.POLICY_READY),
            "request-review": ({MacroState.POLICY_READY}, MacroState.REVIEW_REQUIRED),
            "approve": ({MacroState.REVIEW_REQUIRED}, MacroState.APPROVED),
            "activate": ({MacroState.APPROVED}, MacroState.ACTIVE),
            "confirm-stable": ({MacroState.MONITORING}, MacroState.STABLE),
            "escalate": ({MacroState.CLASSIFIED, MacroState.ACTIVE, MacroState.MONITORING, MacroState.REGIME_SHIFT}, MacroState.ESCALATED),
            "suspend": ({MacroState.ACTIVE, MacroState.MONITORING, MacroState.REGIME_SHIFT, MacroState.ESCALATED}, MacroState.SUSPENDED),
            "resume": ({MacroState.SUSPENDED}, MacroState.MONITORING),
            "revoke": (set(MacroState) - {MacroState.ARCHIVED}, MacroState.REVOKED),
            "archive": ({MacroState.STABLE, MacroState.REVOKED}, MacroState.ARCHIVED),
        }

        if command.action == "approve":
            if record.policy.require_human_approval:
                self._consume(command.approval_token, self.approval_tokens, "approval_token")
        if command.action == "activate":
            self._consume(command.operation_receipt, self.operation_receipts, "operation_receipt")

        if command.action == "observe":
            if record.state not in {MacroState.ACTIVE, MacroState.MONITORING, MacroState.REGIME_SHIFT, MacroState.STABLE}:
                raise GovernanceError("observe not allowed in current state")
            previous_regime = record.regime
            previous_risk = record.macro_risk_score
            if command.indicators is not None:
                record.indicators = command.indicators
            if command.central_banks is not None:
                record.central_banks = command.central_banks
            self._evaluate(record)
            shift = previous_regime != record.regime or abs(previous_risk - record.macro_risk_score) >= record.policy.regime_shift_threshold
            if record.macro_risk_score >= record.policy.escalation_risk_threshold:
                record.state = MacroState.ESCALATED
                record.stable_cycles = 0
            elif shift:
                record.state = MacroState.REGIME_SHIFT
                record.stable_cycles = 0
            elif record.violations:
                record.state = MacroState.MONITORING
                record.stable_cycles = 0
            else:
                record.stable_cycles += 1
                record.state = MacroState.MONITORING
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            if command.action == "confirm-stable" and record.stable_cycles < record.policy.stable_cycles_required:
                raise GovernanceError("stable observation cycles incomplete")
            record.state = target

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: MacroRecord) -> None:
        by_category: dict[str, list[float]] = {}
        for item in record.indicators:
            by_category.setdefault(item.category, []).append(item.normalized_score)

        category = lambda name: round(mean(by_category.get(name, [0])), 2)
        record.growth_score = category("growth")
        record.inflation_score = category("inflation")
        record.liquidity_score = category("liquidity")
        record.currency_score = category("currency")

        rate_inputs = by_category.get("rates", []) + by_category.get("yield-curve", [])
        bank_stance = {
            "very-dovish": -100, "dovish": -50, "neutral": 0,
            "hawkish": 50, "very-hawkish": 100,
        }
        rate_inputs += [bank_stance[item.stance] for item in record.central_banks]
        record.rates_score = round(mean(rate_inputs or [0]), 2)

        freshness = [max(0.0, 100 - item.freshness_minutes / record.policy.maximum_indicator_age_minutes * 100) for item in record.indicators]
        source_quality = [100 if item.source_ref else 0 for item in record.indicators]
        record.data_quality_score = round(mean(freshness + source_quality), 2)

        growth = record.growth_score
        inflation = record.inflation_score
        if growth >= 20 and inflation < 35:
            record.regime = "expansion"
        elif growth >= 0 and inflation >= 35:
            record.regime = "late-expansion"
        elif growth < -20 and inflation >= 35:
            record.regime = "stagflation"
        elif growth < -20 and inflation < 0:
            record.regime = "recession"
        elif growth >= 0 and inflation < -20:
            record.regime = "recovery"
        else:
            record.regime = "transition"

        risk = (
            max(0.0, -growth) * 0.25
            + max(0.0, record.inflation_score) * 0.2
            + max(0.0, record.rates_score) * 0.2
            + max(0.0, -record.liquidity_score) * 0.25
            + max(0.0, abs(record.currency_score) - 50) * 0.1
        )
        record.macro_risk_score = round(min(100.0, risk), 2)
        record.regime_confidence = round(min(100.0, abs(growth) * 0.35 + abs(inflation) * 0.35 + record.data_quality_score * 0.3), 2)
        record.risk_environment = "risk-off" if record.macro_risk_score >= 60 else "risk-on" if record.macro_risk_score <= 30 and growth > 0 and record.liquidity_score >= 0 else "neutral"

        violations: list[str] = []
        if record.data_quality_score < record.policy.minimum_data_quality:
            violations.append("data_quality_below_minimum")
        if any(item.freshness_minutes > record.policy.maximum_indicator_age_minutes for item in record.indicators):
            violations.append("stale_indicator_data")
        if record.macro_risk_score >= record.policy.escalation_risk_threshold:
            violations.append("macro_risk_threshold_exceeded")
        record.violations = violations

        recommendations: list[str] = []
        if record.risk_environment == "risk-off":
            recommendations += ["reduce-gross-exposure", "raise-liquidity-buffer", "tighten-risk-limits"]
        elif record.risk_environment == "risk-on":
            recommendations += ["permit-selective-risk-deployment", "favor-growth-sensitive-assets"]
        if record.rates_score >= 35:
            recommendations.append("reduce-duration-and-rate-sensitive-exposure")
        if record.inflation_score >= 35:
            recommendations.append("favor-inflation-resilient-assets")
        if record.liquidity_score <= -30:
            recommendations.append("block-leverage-expansion")
        record.recommendations = recommendations

    @staticmethod
    def _consume(value: str | None, used: set[str], name: str) -> None:
        if not value:
            raise GovernanceError(f"{name} required")
        if value in used:
            raise GovernanceError(f"{name} replay detected")
        used.add(value)

    def _audit(self, record: MacroRecord, action: str, actor: str, before: MacroState, after: MacroState, note: str | None = None) -> None:
        self.audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, note=note))


service = MacroGovernanceService()
