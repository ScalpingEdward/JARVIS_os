from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List, Tuple
from uuid import uuid4

from .schemas import (
    ExposureDecision,
    ExposureExecutionRequest,
    ExposureState,
    PortfolioExposureRequest,
)


class PortfolioExposureError(ValueError):
    pass


class PortfolioExposureService:
    def __init__(self) -> None:
        self._records: Dict[str, ExposureDecision] = {}
        self._payloads: Dict[str, PortfolioExposureRequest] = {}
        self._source_index: Dict[Tuple[str, str], str] = {}
        self._approval_tokens: set[str] = set()
        self._downstream_receipts: set[str] = set()
        self._audit: List[dict] = []
        self._lock = RLock()

    @staticmethod
    def _correlation(payload: PortfolioExposureRequest, left: str, right: str) -> float:
        if left == right:
            return 1.0
        return abs(
            payload.correlation_matrix.get(left, {}).get(
                right, payload.correlation_matrix.get(right, {}).get(left, 0.0)
            )
        )

    @staticmethod
    def _currency_exposure(payload: PortfolioExposureRequest) -> float:
        currencies = {
            currency
            for currency in (payload.proposed_base_currency, payload.proposed_quote_currency)
            if currency
        }
        if not currencies:
            return payload.proposed_risk_percent
        total = payload.proposed_risk_percent
        for position in payload.open_positions:
            if currencies.intersection({position.base_currency, position.quote_currency}):
                total += position.risk_percent
        return total

    def assess(self, payload: PortfolioExposureRequest) -> ExposureDecision:
        with self._lock:
            key = (payload.workspace_id, payload.source_key)
            if key in self._source_index:
                raise PortfolioExposureError("duplicate source key in workspace")

            reasons: List[str] = []
            total_risk = payload.proposed_risk_percent + sum(p.risk_percent for p in payload.open_positions)
            correlated_risk = payload.proposed_risk_percent + sum(
                p.risk_percent
                for p in payload.open_positions
                if self._correlation(payload, payload.proposed_symbol, p.symbol)
                >= payload.correlation_threshold
            )
            asset_risk = payload.proposed_risk_percent + sum(
                p.risk_percent
                for p in payload.open_positions
                if p.asset_class == payload.proposed_asset_class
            )
            currency_risk = self._currency_exposure(payload)
            long_positions = sum(p.side == "long" for p in payload.open_positions) + int(payload.proposed_side == "long")
            short_positions = sum(p.side == "short" for p in payload.open_positions) + int(payload.proposed_side == "short")
            same_direction = long_positions if payload.proposed_side == "long" else short_positions
            news_count = sum(p.news_risk_active for p in payload.open_positions) + int(payload.proposed_news_risk_active)

            hard_block = payload.risk_brain_hard_block
            if not payload.upstream_evidence_approved:
                state = ExposureState.EVIDENCE_REQUIRED
                reasons.append("approved PHOENIX v21.17 risk evidence is required")
            elif hard_block:
                state = ExposureState.BLOCKED
                reasons.append("Risk Brain hard block is authoritative")
            else:
                if total_risk > payload.max_total_risk_percent:
                    reasons.append("maximum total portfolio risk exceeded")
                if correlated_risk > payload.max_correlated_risk_percent:
                    reasons.append("maximum correlated exposure exceeded")
                if asset_risk > payload.max_asset_class_risk_percent:
                    reasons.append("maximum asset-class exposure exceeded")
                if currency_risk > payload.max_currency_risk_percent:
                    reasons.append("maximum currency exposure exceeded")
                if same_direction > payload.max_same_direction_positions:
                    reasons.append("maximum same-direction positions exceeded")
                if news_count > payload.max_news_exposed_positions:
                    reasons.append("maximum simultaneous news exposure exceeded")

                state = ExposureState.BLOCKED if reasons else ExposureState.HUMAN_REVIEW_REQUIRED
                if not reasons and payload.confidence_score < 70:
                    reasons.append("low confidence requires explicit human review")

            heat = min(
                100.0,
                round(
                    100
                    * max(
                        total_risk / payload.max_total_risk_percent,
                        correlated_risk / payload.max_correlated_risk_percent,
                        asset_risk / payload.max_asset_class_risk_percent,
                        currency_risk / payload.max_currency_risk_percent,
                    ),
                    2,
                ),
            )
            approved_risk = payload.proposed_risk_percent if state == ExposureState.HUMAN_REVIEW_REQUIRED else 0.0
            decision = ExposureDecision(
                workspace_id=payload.workspace_id,
                source_record_id=payload.source_record_id,
                source_key=payload.source_key,
                state=state,
                approved_risk_percent=approved_risk,
                portfolio_risk_percent=round(total_risk, 4),
                correlated_risk_percent=round(correlated_risk, 4),
                asset_class_risk_percent=round(asset_risk, 4),
                currency_risk_percent=round(currency_risk, 4),
                portfolio_heat_score=heat,
                long_positions=long_positions,
                short_positions=short_positions,
                reasons=reasons,
            )
            self._records[decision.record_id] = decision
            self._payloads[decision.record_id] = payload
            self._source_index[key] = decision.record_id
            self._audit_event(decision, "assessed", "system")
            return decision

    def execute(self, workspace_id: str, record_id: str, command: ExposureExecutionRequest) -> ExposureDecision:
        with self._lock:
            record = self.get(workspace_id, record_id)
            if command.action == "approve":
                if record.state != ExposureState.HUMAN_REVIEW_REQUIRED:
                    raise PortfolioExposureError("record is not awaiting human approval")
                token = command.approval_token or str(uuid4())
                if token in self._approval_tokens:
                    raise PortfolioExposureError("approval token replay detected")
                self._approval_tokens.add(token)
                record.approval_token = token
                record.state = ExposureState.APPROVED
            elif command.action == "reject":
                record.state = ExposureState.REJECTED
            elif command.action == "issue":
                if record.state != ExposureState.APPROVED:
                    raise PortfolioExposureError("human approval is required before issuance")
                receipt = command.downstream_receipt or str(uuid4())
                if receipt in self._downstream_receipts:
                    raise PortfolioExposureError("downstream receipt replay detected")
                self._downstream_receipts.add(receipt)
                record.downstream_receipt = receipt
                record.state = ExposureState.ISSUED_TO_EXECUTION_BOUNDARY
            elif command.action == "invalidate":
                record.state = ExposureState.INVALIDATED
            elif command.action == "archive":
                record.state = ExposureState.ARCHIVED
            record.updated_at = datetime.now(timezone.utc)
            self._audit_event(record, command.action, command.actor)
            return record

    def get(self, workspace_id: str, record_id: str) -> ExposureDecision:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise PortfolioExposureError("record not found")
        return record

    def list(self, workspace_id: str) -> List[ExposureDecision]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> List[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]

    def _audit_event(self, record: ExposureDecision, action: str, actor: str) -> None:
        self._audit.append(
            {
                "record_id": record.record_id,
                "workspace_id": record.workspace_id,
                "state": record.state.value,
                "action": action,
                "actor": actor,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )


service = PortfolioExposureService()
