from __future__ import annotations

from collections import defaultdict

from .models import (
    AuditEvent,
    SystemicRiskAction,
    SystemicRiskCreate,
    SystemicRiskRecord,
    SystemicRiskState,
    utcnow,
)


class GovernanceError(ValueError):
    pass


class SystemicRiskGovernanceService:
    def __init__(self) -> None:
        self.records: dict[str, SystemicRiskRecord] = {}
        self.audit: list[AuditEvent] = []
        self.source_keys: set[tuple[str, str]] = set()
        self.approval_tokens: set[str] = set()
        self.operation_receipts: set[str] = set()

    def create(self, payload: SystemicRiskCreate) -> SystemicRiskRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self.source_keys:
            raise GovernanceError("duplicate source_key in workspace")
        node_ids = {node.portfolio_id for node in payload.nodes}
        if any(link.source_portfolio_id not in node_ids or link.target_portfolio_id not in node_ids for link in payload.links):
            raise GovernanceError("contagion link references unknown portfolio")
        record = SystemicRiskRecord(
            **payload.model_dump(),
            state=SystemicRiskState.BLOCKED if payload.risk_brain_blocked else SystemicRiskState.DRAFT,
        )
        self._evaluate(record)
        self.records[record.record_id] = record
        self.source_keys.add(key)
        self._audit(record, "create", "system", record.state, record.state)
        return record

    def list(self, workspace_id: str) -> list[SystemicRiskRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> SystemicRiskRecord:
        record = self.records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise KeyError(record_id)
        return record

    def act(self, record_id: str, workspace_id: str, command: SystemicRiskAction) -> SystemicRiskRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        if record.risk_brain_blocked and command.action not in {"revoke", "archive"}:
            raise GovernanceError("Risk Brain hard block is authoritative")

        transitions = {
            "prepare-evidence": ({SystemicRiskState.DRAFT}, SystemicRiskState.EVIDENCE_READY),
            "map-network": ({SystemicRiskState.EVIDENCE_READY}, SystemicRiskState.MAPPED),
            "analyze": ({SystemicRiskState.MAPPED}, SystemicRiskState.ANALYZED),
            "prepare-containment": ({SystemicRiskState.ANALYZED}, SystemicRiskState.CONTAINMENT_READY),
            "request-review": ({SystemicRiskState.CONTAINMENT_READY}, SystemicRiskState.REVIEW_REQUIRED),
            "approve": ({SystemicRiskState.REVIEW_REQUIRED}, SystemicRiskState.APPROVED),
            "start-containment": ({SystemicRiskState.APPROVED}, SystemicRiskState.CONTAINING),
            "escalate": ({
                SystemicRiskState.CONTAINING,
                SystemicRiskState.MONITORING,
                SystemicRiskState.STABLE,
                SystemicRiskState.CONTAGION_WARNING,
                SystemicRiskState.SYSTEMIC_ALERT,
            }, SystemicRiskState.ESCALATED),
            "suspend": ({
                SystemicRiskState.CONTAINING,
                SystemicRiskState.MONITORING,
                SystemicRiskState.STABLE,
                SystemicRiskState.CONTAGION_WARNING,
                SystemicRiskState.SYSTEMIC_ALERT,
                SystemicRiskState.ESCALATED,
            }, SystemicRiskState.SUSPENDED),
            "resume": ({SystemicRiskState.SUSPENDED}, SystemicRiskState.MONITORING),
            "revoke": (set(SystemicRiskState) - {SystemicRiskState.ARCHIVED}, SystemicRiskState.REVOKED),
            "archive": ({SystemicRiskState.STABLE, SystemicRiskState.REVOKED}, SystemicRiskState.ARCHIVED),
        }

        if command.action == "approve":
            self._consume(command.approval_token, self.approval_tokens, "approval_token")
        if command.action == "start-containment":
            self._consume(command.operation_receipt, self.operation_receipts, "operation_receipt")

        if command.action == "observe":
            allowed = {
                SystemicRiskState.CONTAINING,
                SystemicRiskState.MONITORING,
                SystemicRiskState.STABLE,
                SystemicRiskState.CONTAGION_WARNING,
            }
            if record.state not in allowed:
                raise GovernanceError("observe not allowed in current state")
            if command.nodes is not None:
                record.nodes = command.nodes
            if command.links is not None:
                record.links = command.links
            self._evaluate(record)
            if record.systemic_risk_score > record.policy.maximum_systemic_risk_score or record.projected_loss_pct > record.policy.maximum_projected_loss_pct:
                record.stable_cycles = 0
                record.state = SystemicRiskState.SYSTEMIC_ALERT
            elif record.violations:
                record.stable_cycles = 0
                record.state = SystemicRiskState.CONTAGION_WARNING
            else:
                record.stable_cycles += 1
                record.state = (
                    SystemicRiskState.STABLE
                    if record.stable_cycles >= record.policy.stable_cycles_required
                    else SystemicRiskState.MONITORING
                )
        else:
            allowed, target = transitions[command.action]
            if record.state not in allowed:
                raise GovernanceError(f"{command.action} not allowed from {record.state.value}")
            record.state = target
            if command.action == "start-containment":
                record.state = SystemicRiskState.MONITORING

        record.updated_at = utcnow()
        self._audit(record, command.action, command.actor, before, record.state, command.note)
        return record

    def _evaluate(self, record: SystemicRiskRecord) -> None:
        node_map = {node.portfolio_id: node for node in record.nodes}
        total_capital = max(sum(node.capital_share_pct for node in record.nodes), 0.01)
        weighted_stress = sum(node.stress_score * node.capital_share_pct for node in record.nodes) / total_capital
        weighted_drawdown = sum(node.drawdown_pct * node.capital_share_pct for node in record.nodes) / total_capital
        weighted_liquidity = sum(node.liquidity_score * node.capital_share_pct for node in record.nodes) / total_capital
        weighted_leverage = sum(node.leverage * node.capital_share_pct for node in record.nodes) / total_capital

        link_risks: list[float] = []
        projected_losses: list[float] = []
        bucket: dict[str, int] = defaultdict(int)
        for link in record.links:
            source = node_map[link.source_portfolio_id]
            target = node_map[link.target_portfolio_id]
            correlation = max(0.0, link.correlation)
            transmission = link.transmission_probability * 100
            shared = (link.shared_factor_exposure_pct + link.shared_liquidity_dependency_pct) / 2
            risk = correlation * 25 + transmission * 0.35 + shared * 0.25 + min(link.loss_amplification * 10, 15)
            link_risks.append(min(100.0, risk))
            projected_losses.append(
                (source.drawdown_pct + target.drawdown_pct) / 2
                * link.transmission_probability
                * max(1.0, link.loss_amplification)
            )
            if correlation >= record.policy.maximum_correlation_concentration:
                bucket[source.portfolio_id] += 1
                bucket[target.portfolio_id] += 1

        network_risk = sum(link_risks) / max(len(link_risks), 1)
        record.projected_loss_pct = round(sum(projected_losses), 2)
        record.concentration_score = round(min(100.0, max(bucket.values(), default=0) * 20.0), 2)
        record.contagion_paths = sum(1 for score in link_risks if score >= record.policy.warning_systemic_risk_score)
        record.systemic_risk_score = round(min(100.0,
            weighted_stress * 0.25
            + weighted_drawdown * 2.0
            + (100 - weighted_liquidity) * 0.15
            + min(weighted_leverage * 10, 100) * 0.1
            + network_risk * 0.25
            + record.concentration_score * 0.05
        ), 2)

        violations: list[str] = []
        if any(node.stress_score > record.policy.maximum_portfolio_stress_score for node in record.nodes):
            violations.append("portfolio_stress_exceeded")
        if any(node.liquidity_score < record.policy.minimum_liquidity_score for node in record.nodes):
            violations.append("liquidity_below_minimum")
        if any(link.transmission_probability > record.policy.maximum_link_transmission_probability for link in record.links):
            violations.append("transmission_probability_exceeded")
        if any(link.correlation > record.policy.maximum_correlation_concentration for link in record.links):
            violations.append("correlation_concentration_exceeded")
        if record.projected_loss_pct > record.policy.maximum_projected_loss_pct:
            violations.append("projected_loss_exceeded")
        if record.systemic_risk_score > record.policy.warning_systemic_risk_score:
            violations.append("systemic_risk_warning")
        record.violations = violations

    @staticmethod
    def _consume(value: str | None, used: set[str], name: str) -> None:
        if not value:
            raise GovernanceError(f"{name} required")
        if value in used:
            raise GovernanceError(f"{name} replay detected")
        used.add(value)

    def _audit(
        self,
        record: SystemicRiskRecord,
        action: str,
        actor: str,
        before: SystemicRiskState,
        after: SystemicRiskState,
        note: str | None = None,
    ) -> None:
        self.audit.append(AuditEvent(
            record_id=record.record_id,
            workspace_id=record.workspace_id,
            action=action,
            actor=actor,
            from_state=before,
            to_state=after,
            note=note,
        ))


service = SystemicRiskGovernanceService()
