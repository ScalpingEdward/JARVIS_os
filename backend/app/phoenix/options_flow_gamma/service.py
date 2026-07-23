from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
from threading import RLock
from typing import Any
from uuid import uuid4

from .models import OptionObservation, OptionsFlowRecord, OptionsFlowState


class OptionsFlowGovernanceError(RuntimeError):
    pass


class OptionsFlowGovernanceService:
    """In-memory governance boundary for options-flow and gamma intelligence."""

    def __init__(self) -> None:
        self._records: dict[str, OptionsFlowRecord] = {}
        self._workspace_records: dict[str, set[str]] = defaultdict(set)
        self._receipts: set[str] = set()
        self._audit: list[dict[str, Any]] = []
        self._lock = RLock()

    def create_record(
        self,
        workspace_id: str,
        observations: list[OptionObservation],
        metadata: dict[str, Any] | None = None,
    ) -> OptionsFlowRecord:
        if not workspace_id.strip():
            raise OptionsFlowGovernanceError("workspace_id is required")
        if not observations:
            raise OptionsFlowGovernanceError("at least one observation is required")
        source_keys = [item.source_key for item in observations]
        if len(source_keys) != len(set(source_keys)):
            raise OptionsFlowGovernanceError("duplicate source_key detected")

        record = OptionsFlowRecord(
            record_id=str(uuid4()),
            workspace_id=workspace_id,
            observations=observations,
            metadata=metadata or {},
        )
        self._score(record)
        record.state = OptionsFlowState.SCORED
        with self._lock:
            self._records[record.record_id] = record
            self._workspace_records[workspace_id].add(record.record_id)
            self._append_audit(record, "created")
        return record

    def list_records(self, workspace_id: str) -> list[OptionsFlowRecord]:
        with self._lock:
            return [self._records[item] for item in sorted(self._workspace_records.get(workspace_id, set()))]

    def get_record(self, workspace_id: str, record_id: str) -> OptionsFlowRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise OptionsFlowGovernanceError("record not found")
            return record

    def apply_action(
        self,
        workspace_id: str,
        record_id: str,
        action: str,
        operation_id: str,
        risk_brain_blocked: bool = False,
    ) -> OptionsFlowRecord:
        receipt = sha256(f"{workspace_id}:{record_id}:{operation_id}".encode()).hexdigest()
        with self._lock:
            if receipt in self._receipts:
                raise OptionsFlowGovernanceError("operation replay detected")
            record = self.get_record(workspace_id, record_id)
            self._receipts.add(receipt)
            record.risk_brain_blocked = risk_brain_blocked

            if risk_brain_blocked:
                record.state = OptionsFlowState.BLOCKED
            elif action == "submit":
                record.state = OptionsFlowState.REVIEW_REQUIRED
            elif action == "approve":
                record.human_approved = True
                record.state = OptionsFlowState.APPROVED
            elif action == "activate":
                if not record.human_approved:
                    raise OptionsFlowGovernanceError("human approval is required")
                record.state = self._active_state(record)
            elif action == "suspend":
                record.state = OptionsFlowState.SUSPENDED
            elif action == "revoke":
                record.state = OptionsFlowState.REVOKED
            elif action == "archive":
                record.state = OptionsFlowState.ARCHIVED
            else:
                raise OptionsFlowGovernanceError(f"unsupported action: {action}")

            record.touch()
            self._append_audit(record, action)
            return record

    def audit(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [event for event in self._audit if event["workspace_id"] == workspace_id]

    @staticmethod
    def status() -> dict[str, Any]:
        return {
            "module": "PHOENIX v21.66 Options Flow & Gamma Intelligence Governance",
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def _score(self, record: OptionsFlowRecord) -> None:
        calls = 0.0
        puts = 0.0
        net_premium = 0.0
        gamma_by_strike: dict[float, float] = defaultdict(float)
        vol_pressure = 0.0
        weighted_quality = 0.0
        total_weight = 0.0

        for item in record.observations:
            signed = 1.0 if item.side.lower() in {"buy", "bought", "ask"} else -1.0
            premium = signed * item.premium * max(item.contracts, 0)
            net_premium += premium
            if item.option_type.lower() == "call":
                calls += premium
            else:
                puts += premium
            gamma_value = item.gamma * max(item.open_interest, item.volume, item.contracts, 0)
            gamma_by_strike[item.strike] += gamma_value
            vol_pressure += signed * item.vega * item.implied_volatility * max(item.contracts, 0)
            weight = max(item.contracts, 1)
            weighted_quality += ((item.confidence + item.freshness) / 2.0) * weight
            total_weight += weight

        gross = abs(calls) + abs(puts)
        record.net_premium = round(net_premium, 4)
        record.call_put_pressure = round((calls - puts) / gross, 6) if gross else 0.0
        record.dealer_gamma_exposure = round(sum(gamma_by_strike.values()), 6)
        total_gamma = sum(abs(value) for value in gamma_by_strike.values())
        max_gamma = max((abs(value) for value in gamma_by_strike.values()), default=0.0)
        record.gamma_concentration = round(max_gamma / total_gamma, 6) if total_gamma else 0.0
        record.volatility_pressure = round(vol_pressure, 6)
        record.quality_score = round(weighted_quality / total_weight, 6) if total_weight else 0.0
        record.confidence_score = round(
            sum(item.confidence for item in record.observations) / len(record.observations), 6
        )
        record.risk_score = round(
            min(1.0, 0.45 * record.gamma_concentration + 0.35 * abs(record.call_put_pressure) + 0.20 * (1 - record.quality_score)),
            6,
        )

    @staticmethod
    def _active_state(record: OptionsFlowRecord) -> OptionsFlowState:
        if record.risk_score >= 0.8:
            return OptionsFlowState.ESCALATED
        if record.gamma_concentration >= 0.65:
            return OptionsFlowState.GAMMA_SHIFT
        if abs(record.volatility_pressure) > 1_000:
            return OptionsFlowState.VOLATILITY_SHIFT
        return OptionsFlowState.ACTIVE

    def _append_audit(self, record: OptionsFlowRecord, event: str) -> None:
        self._audit.append(
            {
                "event": event,
                "record_id": record.record_id,
                "workspace_id": record.workspace_id,
                "state": record.state.value,
                "risk_score": record.risk_score,
                "snapshot": asdict(record),
            }
        )
