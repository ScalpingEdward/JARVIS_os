from uuid import UUID

from .models import (
    DecisionRecord,
    DecisionRequest,
    DecisionState,
    DecisionStatus,
    RankedOption,
)


class DecisionEngineService:
    def __init__(self) -> None:
        self._records: dict[UUID, DecisionRecord] = {}

    def reset(self) -> None:
        self._records.clear()

    def evaluate(self, payload: DecisionRequest) -> DecisionRecord:
        total_weight = sum(item.weight for item in payload.criteria)
        ranked: list[RankedOption] = []

        for option in payload.options:
            weighted = 0.0
            reasons: list[str] = []
            for criterion in payload.criteria:
                value = option.scores.get(criterion.name, 0.0)
                value = max(0.0, min(100.0, value))
                weighted += value * criterion.weight
                if value >= 75:
                    reasons.append(f"Strong on {criterion.name}: {value:.0f}/100")
                elif value <= 35:
                    reasons.append(f"Weak on {criterion.name}: {value:.0f}/100")

            base_score = weighted / total_weight
            risk_penalty = option.risk * 0.25
            score = max(0.0, min(100.0, base_score - risk_penalty))
            confidence = max(0.0, min(100.0, option.evidence_quality - len(option.blockers) * 12))
            uncertainty = 100.0 - confidence
            if option.blockers:
                reasons.append(f"Blocked by {len(option.blockers)} unresolved issue(s)")
            reasons.append(f"Risk penalty: {risk_penalty:.1f} points")
            ranked.append(
                RankedOption(
                    name=option.name,
                    score=round(score, 2),
                    confidence=round(confidence, 2),
                    uncertainty=round(uncertainty, 2),
                    risk=option.risk,
                    blockers=option.blockers,
                    reasons=reasons,
                )
            )

        ranked.sort(key=lambda item: (item.score, item.confidence), reverse=True)
        winner = ranked[0]
        if winner.blockers or winner.risk > payload.maximum_risk:
            state = DecisionState.rejected
            selected = None
        elif winner.confidence < payload.minimum_confidence:
            state = DecisionState.needs_review
            selected = winner.name
        else:
            state = DecisionState.recommended
            selected = winner.name

        rationale = [
            f"Top option: {winner.name} with score {winner.score:.2f}/100",
            f"Confidence {winner.confidence:.2f}% and uncertainty {winner.uncertainty:.2f}%",
            f"Risk {winner.risk:.2f}/100; maximum allowed {payload.maximum_risk:.2f}",
            "Human approval is required before any critical action.",
        ]
        record = DecisionRecord(
            title=payload.title,
            domain=payload.domain,
            state=state,
            selected_option=selected,
            ranked_options=ranked,
            rationale=rationale,
            requires_human_approval=True,
        )
        self._records[record.id] = record
        return record

    def list_all(self) -> list[DecisionRecord]:
        return list(self._records.values())

    def get(self, decision_id: UUID) -> DecisionRecord | None:
        return self._records.get(decision_id)

    def approve(self, decision_id: UUID) -> DecisionRecord | None:
        record = self.get(decision_id)
        if record is None:
            return None
        if record.state == DecisionState.rejected:
            raise ValueError("Rejected decisions cannot be approved")
        record.approved = True
        return record

    def status(self) -> DecisionStatus:
        records = self.list_all()
        return DecisionStatus(
            total=len(records),
            recommended=sum(item.state == DecisionState.recommended for item in records),
            needs_review=sum(item.state == DecisionState.needs_review for item in records),
            rejected=sum(item.state == DecisionState.rejected for item in records),
        )


decision_engine_service = DecisionEngineService()
