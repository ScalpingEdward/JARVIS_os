from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from .models import (
    AuditRecord,
    DeploymentScores,
    DeploymentState,
    DeploymentStatusResponse,
    FundingLine,
    LiveCapitalDeploymentAssessment,
    LiveCapitalDeploymentCreate,
)


class ExecutiveLiveCapitalBrokerDeploymentService:
    def __init__(self) -> None:
        self._records: dict[UUID, LiveCapitalDeploymentAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: LiveCapitalDeploymentCreate) -> LiveCapitalDeploymentAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate Live deployment source key")

        total = round(payload.treasury_approved_live_capital, 2)
        reasons: list[str] = []
        eligible = []
        for candidate in payload.candidates:
            checks = [
                not payload.policy.require_regulation or candidate.regulated,
                not payload.policy.require_verified_withdrawal or candidate.withdrawals_verified,
                candidate.operational_health >= payload.policy.minimum_operational_health,
            ]
            if all(checks):
                eligible.append(candidate)

        hard_block = not payload.risk_brain_clear or total <= 0 or not eligible
        if not payload.risk_brain_clear:
            reasons.append("Risk Brain is not clear for Live funding")
        if total <= 0:
            reasons.append("No treasury-approved Live capital is available")
        if not eligible:
            reasons.append("No broker account satisfies deployment policy")

        lines: list[FundingLine] = []
        remaining = 0.0 if hard_block else total
        broker_allocated: dict[str, float] = defaultdict(float)
        selected_new_accounts = 0

        ranked = sorted(eligible, key=lambda item: (item.operational_health, item.withdrawals_verified), reverse=True)
        for candidate in payload.candidates:
            candidate_reasons: list[str] = []
            approved = 0.0
            action = "hold"

            if candidate not in eligible:
                if payload.policy.require_regulation and not candidate.regulated:
                    candidate_reasons.append("Broker regulation requirement not met")
                if payload.policy.require_verified_withdrawal and not candidate.withdrawals_verified:
                    candidate_reasons.append("Withdrawal verification requirement not met")
                if candidate.operational_health < payload.policy.minimum_operational_health:
                    candidate_reasons.append("Operational health below policy threshold")
            elif not hard_block and remaining > 0:
                if candidate.current_owned_balance == 0 and selected_new_accounts >= payload.policy.max_new_accounts_per_cycle:
                    candidate_reasons.append("New-account deployment limit reached")
                else:
                    broker_cap = total * payload.policy.max_broker_share - broker_allocated[candidate.broker_id]
                    account_cap = total * payload.policy.max_account_share
                    requested = candidate.requested_funding or remaining
                    approved = round(max(0.0, min(requested, remaining, broker_cap, account_cap)), 2)
                    if approved > 0:
                        action = "fund"
                        broker_allocated[candidate.broker_id] += approved
                        remaining = round(remaining - approved, 2)
                        if candidate.current_owned_balance == 0:
                            selected_new_accounts += 1
                    else:
                        candidate_reasons.append("Broker or account concentration cap exhausted")

            deployable = approved > 0 and payload.human_approved and not hard_block
            if approved > 0 and not payload.human_approved:
                candidate_reasons.append("Human approval is required before funding")
                action = "plan"

            lines.append(
                FundingLine(
                    broker_id=candidate.broker_id,
                    account_id=candidate.account_id,
                    base_currency=candidate.base_currency.upper(),
                    requested_funding=round(candidate.requested_funding, 2),
                    approved_funding=approved if payload.human_approved else 0.0,
                    allocation_share=round(approved / total, 4) if total else 0.0,
                    deployable=deployable,
                    action=action,
                    reasons=candidate_reasons,
                )
            )

        planned = round(total - remaining, 2) if not hard_block else 0.0
        deployed = planned if payload.human_approved else 0.0
        unallocated = round(total - deployed, 2)

        if hard_block:
            state = DeploymentState.blocked
        elif not payload.human_approved:
            state = DeploymentState.hold
            reasons.append("Deployment plan requires human approval")
        elif deployed == 0:
            state = DeploymentState.hold
        elif unallocated > 0:
            state = DeploymentState.diversify if len({line.broker_id for line in lines if line.deployable}) < 2 else DeploymentState.fund_reduced
            reasons.append("Some approved Live capital remains unallocated")
        else:
            state = DeploymentState.fund_full

        active_brokers = len({line.broker_id for line in lines if line.approved_funding > 0})
        diversification = min(100, active_brokers * 50)
        max_share = max((line.allocation_share for line in lines), default=0.0)
        concentration = max(0, round(100 * (1 - max_share)))
        operational = round(sum(item.operational_health for item in eligible) / len(eligible)) if eligible else 0
        efficiency = round(100 * deployed / total) if total else 0
        confidence = round((diversification + concentration + operational + efficiency) / 4)

        record = LiveCapitalDeploymentAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            state=state,
            approved_treasury_capital=total,
            approved_deployment_capital=deployed,
            unallocated_capital=unallocated,
            funding_lines=lines,
            scores=DeploymentScores(
                broker_diversification=diversification,
                concentration_safety=concentration,
                operational_readiness=operational,
                funding_efficiency=efficiency,
                deployment_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, assessment_id=record.id, actor_id=record.actor_id, action="live-capital-deployment-assessed"))
        return record

    def list_assessments(self, workspace_id: str) -> list[LiveCapitalDeploymentAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> LiveCapitalDeploymentAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> DeploymentStatusResponse:
        items = self.list_assessments(workspace_id)
        return DeploymentStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_live_capital_broker_deployment_service = ExecutiveLiveCapitalBrokerDeploymentService()
