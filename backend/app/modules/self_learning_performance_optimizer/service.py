from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List

from .models import (
    AuditEvent,
    OptimizationRecommendation,
    OptimizerAction,
    OptimizerCommand,
    OptimizerCreate,
    OptimizerRecord,
    OptimizerState,
    SegmentMetric,
)


class OptimizerError(ValueError):
    pass


class SelfLearningPerformanceOptimizerService:
    def __init__(self) -> None:
        self._records: Dict[str, OptimizerRecord] = {}
        self._audit: List[AuditEvent] = []
        self._source_keys: Dict[str, set[str]] = defaultdict(set)
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._lock = RLock()

    def create(self, payload: OptimizerCreate, actor: str = "system") -> OptimizerRecord:
        with self._lock:
            if payload.source_key in self._source_keys[payload.workspace_id]:
                raise OptimizerError("duplicate source_key in workspace")
            if len(payload.samples) != len(payload.journal_record_ids):
                raise OptimizerError("samples and journal_record_ids must align")

            recommendation = None
            if payload.risk_brain_blocked:
                state = OptimizerState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = OptimizerState.EVIDENCE_REQUIRED
            else:
                recommendation = self._optimize(payload)
                state = (
                    OptimizerState.RECOMMENDATION_READY
                    if recommendation.sample_size >= payload.minimum_sample_size
                    else OptimizerState.HUMAN_REVIEW_REQUIRED
                )

            record = OptimizerRecord(
                workspace_id=payload.workspace_id,
                source_key=payload.source_key,
                journal_record_ids=payload.journal_record_ids,
                state=state,
                recommendation=recommendation,
            )
            self._records[record.id] = record
            self._source_keys[payload.workspace_id].add(payload.source_key)
            self._append_audit(record, "created", actor, None, state)
            return record.copy(deep=True)

    def get(self, workspace_id: str, record_id: str) -> OptimizerRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise OptimizerError("record not found")
            return record.copy(deep=True)

    def list(self, workspace_id: str) -> List[OptimizerRecord]:
        with self._lock:
            return [r.copy(deep=True) for r in self._records.values() if r.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> List[AuditEvent]:
        with self._lock:
            return [e.copy(deep=True) for e in self._audit if e.workspace_id == workspace_id]

    def act(self, workspace_id: str, record_id: str, action: OptimizerAction) -> OptimizerRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise OptimizerError("record not found")
            previous = record.state

            if action.command == OptimizerCommand.APPROVE:
                if previous not in {OptimizerState.RECOMMENDATION_READY, OptimizerState.HUMAN_REVIEW_REQUIRED}:
                    raise OptimizerError("record is not approvable")
                if not action.approval_token:
                    raise OptimizerError("approval token required")
                if action.approval_token in self._approval_tokens:
                    raise OptimizerError("approval token replay detected")
                self._approval_tokens.add(action.approval_token)
                record.approval_token = action.approval_token
                record.state = OptimizerState.APPROVED
            elif action.command == OptimizerCommand.ISSUE:
                if previous != OptimizerState.APPROVED:
                    raise OptimizerError("record must be approved before issue")
                if not action.downstream_receipt:
                    raise OptimizerError("downstream receipt required")
                if action.downstream_receipt in self._receipts:
                    raise OptimizerError("downstream receipt replay detected")
                self._receipts.add(action.downstream_receipt)
                record.downstream_receipt = action.downstream_receipt
                record.state = OptimizerState.ISSUED
            elif action.command == OptimizerCommand.REJECT:
                record.state = OptimizerState.REJECTED
            elif action.command == OptimizerCommand.INVALIDATE:
                record.state = OptimizerState.INVALIDATED
            elif action.command == OptimizerCommand.ARCHIVE:
                if previous not in {OptimizerState.ISSUED, OptimizerState.REJECTED, OptimizerState.INVALIDATED}:
                    raise OptimizerError("only terminal records can be archived")
                record.state = OptimizerState.ARCHIVED
            else:
                raise OptimizerError("unsupported command")

            record.updated_at = datetime.now(timezone.utc)
            self._append_audit(record, action.command.value, action.actor, previous, record.state)
            return record.copy(deep=True)

    @staticmethod
    def _optimize(payload: OptimizerCreate) -> OptimizationRecommendation:
        grouped = defaultdict(list)
        for sample in payload.samples:
            key = f"{sample.symbol}:{sample.session}:{sample.strategy_tag}:{sample.setup_grade}"
            grouped[key].append(sample)

        metrics: List[SegmentMetric] = []
        preferred: List[str] = []
        suppressed: List[str] = []
        for segment, samples in grouped.items():
            n = len(samples)
            wins = sum(1 for s in samples if s.realized_r_multiple > 0.05)
            avg_r = sum(s.realized_r_multiple for s in samples) / n
            metric = SegmentMetric(
                segment=segment,
                trades=n,
                win_rate=round(wins / n * 100, 2),
                average_r=round(avg_r, 4),
                expectancy_r=round(avg_r, 4),
                execution_quality=round(sum(s.execution_quality_score for s in samples) / n, 2),
                discipline=round(sum(s.discipline_score for s in samples) / n, 2),
                risk_efficiency=round(sum(s.risk_efficiency_score for s in samples) / n, 2),
            )
            metrics.append(metric)
            if n >= 3 and avg_r >= 0.5 and metric.discipline >= 75:
                preferred.append(segment)
            elif n >= 3 and (avg_r < 0 or metric.discipline < 60):
                suppressed.append(segment)

        all_avg_r = sum(s.realized_r_multiple for s in payload.samples) / len(payload.samples)
        avg_discipline = sum(s.discipline_score for s in payload.samples) / len(payload.samples)
        confidence = min(100.0, len(payload.samples) / payload.minimum_sample_size * 70 + avg_discipline * 0.3)
        permitted_change = payload.max_risk_change_percent / 100
        raw_multiplier = 1 + max(-permitted_change, min(permitted_change, all_avg_r * 0.1))
        risk_multiplier = round(max(0.5, min(1.5, raw_multiplier)), 3)

        recommendations = []
        if preferred:
            recommendations.append("prioritize statistically positive, disciplined segments")
        if suppressed:
            recommendations.append("suppress negative-expectancy or low-discipline segments")
        recommendations.append("revalidate after each new governed sample window")

        return OptimizationRecommendation(
            confidence_score=round(confidence, 2),
            sample_size=len(payload.samples),
            preferred_segments=sorted(preferred),
            suppressed_segments=sorted(suppressed),
            risk_multiplier=risk_multiplier,
            recommendations=recommendations,
            safeguards=[
                "recommendations require human approval",
                "risk changes are bounded by max_risk_change_percent",
                "no live strategy mutation is performed",
                "risk brain hard blocks remain authoritative",
            ],
            metrics=sorted(metrics, key=lambda item: item.segment),
        )

    def _append_audit(self, record, action, actor, previous, state) -> None:
        self._audit.append(AuditEvent(
            workspace_id=record.workspace_id,
            record_id=record.id,
            action=action,
            actor=actor,
            from_state=previous,
            to_state=state,
        ))
