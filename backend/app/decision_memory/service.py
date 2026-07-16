from collections import defaultdict
from uuid import UUID

from .models import (
    CalibrationReport,
    DecisionDomain,
    DecisionMemoryStatus,
    DecisionOutcome,
    DecisionPattern,
    DecisionRecord,
    DecisionRecordCreate,
    PatternType,
)


class DecisionMemoryService:
    def __init__(self) -> None:
        self._records: list[DecisionRecord] = []

    def reset(self) -> None:
        self._records.clear()

    def add(self, payload: DecisionRecordCreate) -> DecisionRecord:
        record = DecisionRecord(**payload.model_dump())
        self._records.append(record)
        return record

    def list_all(self, domain: DecisionDomain | None = None) -> list[DecisionRecord]:
        records = self._records
        if domain is not None:
            records = [record for record in records if record.domain == domain]
        return list(reversed(records))

    def get(self, record_id: UUID) -> DecisionRecord | None:
        return next((record for record in self._records if record.id == record_id), None)

    def calibration(self, domain: DecisionDomain | None = None) -> CalibrationReport:
        records = [
            record
            for record in self._records
            if record.learning_consent
            and record.outcome != DecisionOutcome.pending
            and record.outcome_score is not None
            and (domain is None or record.domain == domain)
        ]
        if not records:
            return CalibrationReport(
                domain=domain,
                sample_size=0,
                average_predicted_confidence=0.0,
                average_outcome_score=0.0,
                calibration_gap=0.0,
                status="insufficient_data",
            )
        predicted = sum(record.predicted_confidence for record in records) / len(records)
        actual = sum(record.outcome_score or 0.0 for record in records) / len(records)
        gap = round(predicted - actual, 4)
        if abs(gap) <= 0.1:
            status = "well_calibrated"
        elif gap > 0:
            status = "overconfident"
        else:
            status = "underconfident"
        return CalibrationReport(
            domain=domain,
            sample_size=len(records),
            average_predicted_confidence=round(predicted, 4),
            average_outcome_score=round(actual, 4),
            calibration_gap=gap,
            status=status,
        )

    def patterns(self, domain: DecisionDomain | None = None) -> list[DecisionPattern]:
        learning_records = [
            record
            for record in self._records
            if record.learning_consent
            and record.outcome != DecisionOutcome.pending
            and record.outcome_score is not None
            and (domain is None or record.domain == domain)
        ]
        grouped: dict[DecisionDomain, list[DecisionRecord]] = defaultdict(list)
        for record in learning_records:
            grouped[record.domain].append(record)

        patterns: list[DecisionPattern] = []
        for current_domain, records in grouped.items():
            average = sum(record.outcome_score or 0.0 for record in records) / len(records)
            if average >= 0.7:
                patterns.append(
                    DecisionPattern(
                        domain=current_domain,
                        pattern_type=PatternType.strength,
                        title="Reliable decision pattern",
                        description="Approved decisions in this domain show consistently strong outcomes.",
                        confidence=min(1.0, 0.5 + len(records) * 0.08),
                        sample_size=len(records),
                        evidence=[record.title for record in records[-5:]],
                    )
                )
            elif average <= 0.4:
                patterns.append(
                    DecisionPattern(
                        domain=current_domain,
                        pattern_type=PatternType.risk,
                        title="Repeated weak outcome pattern",
                        description="Recent approved decisions in this domain require stronger evidence or lower risk.",
                        confidence=min(1.0, 0.5 + len(records) * 0.08),
                        sample_size=len(records),
                        evidence=[record.title for record in records[-5:]],
                    )
                )
            report = self.calibration(current_domain)
            if report.sample_size >= 2 and report.status in {"overconfident", "underconfident"}:
                patterns.append(
                    DecisionPattern(
                        domain=current_domain,
                        pattern_type=PatternType.calibration,
                        title=f"Confidence is {report.status}",
                        description=f"Confidence differs from recorded outcomes by {abs(report.calibration_gap):.2f}.",
                        confidence=min(1.0, 0.6 + report.sample_size * 0.05),
                        sample_size=report.sample_size,
                    )
                )
        return patterns

    def status(self) -> DecisionMemoryStatus:
        patterns = self.patterns()
        return DecisionMemoryStatus(
            records=len(self._records),
            learning_records=sum(1 for record in self._records if record.learning_consent),
            patterns=len(patterns),
        )


decision_memory_service = DecisionMemoryService()
