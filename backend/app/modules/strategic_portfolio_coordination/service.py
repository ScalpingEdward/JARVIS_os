from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, PortfolioActionRequest, PortfolioState, RiskDecision, StrategicPortfolio, StrategicPortfolioCreate


class StrategicPortfolioError(RuntimeError):
    pass


class StrategicPortfolioService:
    def __init__(self) -> None:
        self._records: dict[str, StrategicPortfolio] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: StrategicPortfolioCreate) -> StrategicPortfolio:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise StrategicPortfolioError("duplicate source key")
        record = StrategicPortfolio(**payload.model_dump())
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> StrategicPortfolio:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise StrategicPortfolioError("strategic portfolio not found")
        return record

    def list(self, workspace_id: str) -> list[StrategicPortfolio]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: PortfolioActionRequest) -> StrategicPortfolio:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, PortfolioState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = PortfolioState.BLOCKED
            elif not record.portfolio_evidence_refs:
                raise StrategicPortfolioError("portfolio evidence is required")
            else:
                record.state = PortfolioState.EVIDENCE_READY
        elif action == "evaluate":
            self._require(record, PortfolioState.EVIDENCE_READY)
            if any(item.current_drawdown > item.risk_budget for item in record.sleeves):
                record.state = PortfolioState.ESCALATED
            elif any(item.current_allocation / record.total_capital > record.maximum_single_sleeve_weight for item in record.sleeves):
                record.state = PortfolioState.ESCALATED
            else:
                record.state = PortfolioState.EVALUATED
        elif action == "propose-rebalance":
            self._require(record, PortfolioState.EVALUATED)
            known = {item.instruction_id: item for item in record.instructions}
            if not request.instruction_ids or not set(request.instruction_ids).issubset(known):
                raise StrategicPortfolioError("known instruction_ids are required")
            if any(known[item].confidence < record.minimum_confidence for item in request.instruction_ids):
                raise StrategicPortfolioError("allocation confidence below threshold")
            selected = [known[item] for item in dict.fromkeys(request.instruction_ids)]
            targets = {item.sleeve_id: item.target_allocation for item in selected}
            projected = sum(targets.get(sleeve.sleeve_id, sleeve.current_allocation) for sleeve in record.sleeves)
            if projected > record.total_capital:
                raise StrategicPortfolioError("proposed allocations exceed total capital")
            if any(targets.get(sleeve.sleeve_id, sleeve.current_allocation) > sleeve.maximum_allocation for sleeve in record.sleeves):
                raise StrategicPortfolioError("proposed allocation exceeds sleeve maximum")
            if any(targets.get(sleeve.sleeve_id, sleeve.current_allocation) / record.total_capital > record.maximum_single_sleeve_weight for sleeve in record.sleeves):
                raise StrategicPortfolioError("proposed allocation exceeds sleeve weight ceiling")
            record.selected_instruction_ids = list(dict.fromkeys(request.instruction_ids))
            record.state = PortfolioState.REBALANCE_PROPOSED
        elif action == "request-review":
            self._require(record, PortfolioState.REBALANCE_PROPOSED)
            record.state = PortfolioState.EXECUTIVE_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, PortfolioState.EXECUTIVE_REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = PortfolioState.APPROVED
        elif action == "allocate":
            self._require(record, PortfolioState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            selected = {item.instruction_id: item for item in record.instructions}
            targets = {selected[item].sleeve_id: selected[item].target_allocation for item in record.selected_instruction_ids}
            for sleeve in record.sleeves:
                if sleeve.sleeve_id in targets:
                    sleeve.current_allocation = targets[sleeve.sleeve_id]
            record.allocation_evidence_refs.extend(request.evidence_refs)
            record.consecutive_healthy_cycles = 0
            record.state = PortfolioState.ALLOCATED
        elif action == "record-cycle":
            if record.state not in {PortfolioState.ALLOCATED, PortfolioState.MONITORING}:
                raise StrategicPortfolioError("portfolio monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            if request.portfolio_drawdown is not None:
                record.portfolio_drawdown = request.portfolio_drawdown
            record.allocation_evidence_refs.extend(request.evidence_refs)
            if record.portfolio_drawdown > record.maximum_portfolio_drawdown:
                record.consecutive_healthy_cycles = 0
                record.state = PortfolioState.ESCALATED
            elif request.cycle_healthy:
                record.consecutive_healthy_cycles += 1
                record.state = PortfolioState.MONITORING
            else:
                record.consecutive_healthy_cycles = 0
                record.state = PortfolioState.MONITORING
        elif action == "confirm-balanced":
            self._require(record, PortfolioState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise StrategicPortfolioError("healthy monitoring cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = PortfolioState.BALANCED
        elif action == "escalate":
            if record.state in {PortfolioState.ARCHIVED, PortfolioState.REVOKED, PortfolioState.BLOCKED}:
                raise StrategicPortfolioError("escalation not allowed")
            record.state = PortfolioState.ESCALATED
        elif action == "suspend":
            if record.state not in {PortfolioState.ALLOCATED, PortfolioState.MONITORING, PortfolioState.BALANCED, PortfolioState.ESCALATED}:
                raise StrategicPortfolioError("suspension not allowed")
            record.state = PortfolioState.SUSPENDED
        elif action == "resume":
            self._require(record, PortfolioState.SUSPENDED)
            record.state = PortfolioState.MONITORING
        elif action == "revoke":
            if record.state in {PortfolioState.ARCHIVED, PortfolioState.REVOKED, PortfolioState.BLOCKED}:
                raise StrategicPortfolioError("revocation not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = PortfolioState.REVOKED
        elif action == "archive":
            if record.state not in {PortfolioState.BALANCED, PortfolioState.REVOKED, PortfolioState.ESCALATED, PortfolioState.BLOCKED}:
                raise StrategicPortfolioError("archive not allowed")
            record.state = PortfolioState.ARCHIVED
        else:
            raise StrategicPortfolioError("unsupported action")

        self._touch(record)
        self._emit(record, action, request.actor, before, record.state, {"instruction_ids": request.instruction_ids})
        return record

    @staticmethod
    def _require(record: StrategicPortfolio, expected: PortfolioState) -> None:
        if record.state != expected:
            raise StrategicPortfolioError(f"action requires state {expected.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise StrategicPortfolioError(f"{label} is required")
        if value in store:
            raise StrategicPortfolioError(f"{label} replay detected")
        store.add(value)

    @staticmethod
    def _touch(record: StrategicPortfolio) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record: StrategicPortfolio, action: str, actor: str, before: PortfolioState | None, after: PortfolioState, details: dict | None = None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details or {}))


service = StrategicPortfolioService()
