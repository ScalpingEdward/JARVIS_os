from collections import Counter
from uuid import UUID

from .models import (
    MarketVisionCreate,
    MarketVisionRecord,
    MarketVisionStatus,
    VisualBias,
)


_DIRECTION_SCORE = {
    VisualBias.bullish: 1,
    VisualBias.bearish: -1,
    VisualBias.neutral: 0,
    VisualBias.mixed: 0,
    VisualBias.insufficient_data: 0,
}


class MarketVisionService:
    def __init__(self) -> None:
        self._records: dict[UUID, MarketVisionRecord] = {}

    def reset(self) -> None:
        self._records.clear()

    def create(self, payload: MarketVisionCreate) -> MarketVisionRecord:
        symbol = payload.symbol.upper()
        observations = payload.observations
        warnings: list[str] = []
        confirmations: list[str] = []
        contradictions: list[str] = []

        usable = [item for item in observations if item.detected_bias != VisualBias.insufficient_data]
        weighted = [
            (_DIRECTION_SCORE[item.detected_bias], item.image_quality)
            for item in usable
        ]
        weight_total = sum(weight for _, weight in weighted)
        direction_score = sum(score * weight for score, weight in weighted) / weight_total if weight_total else 0

        if not usable:
            visual_bias = VisualBias.insufficient_data
            warnings.append("No observation contains a usable directional interpretation")
        elif direction_score >= 0.25:
            visual_bias = VisualBias.bullish
        elif direction_score <= -0.25:
            visual_bias = VisualBias.bearish
        elif any(item.detected_bias in {VisualBias.bullish, VisualBias.bearish} for item in usable):
            visual_bias = VisualBias.mixed
        else:
            visual_bias = VisualBias.neutral

        directional = [item.detected_bias for item in usable if item.detected_bias in {VisualBias.bullish, VisualBias.bearish}]
        if directional:
            majority_count = Counter(directional).most_common(1)[0][1]
            timeframe_alignment = majority_count / len(directional)
        else:
            timeframe_alignment = 0

        structured_scores: list[float] = []
        for label, bias, confidence in (
            ("market intelligence", payload.market_bias, payload.market_confidence),
            ("orderflow", payload.orderflow_bias, payload.orderflow_confidence),
        ):
            if bias is None:
                continue
            confidence_value = confidence if confidence is not None else 0.5
            if bias == visual_bias and bias in {VisualBias.bullish, VisualBias.bearish, VisualBias.neutral}:
                structured_scores.append(confidence_value)
                confirmations.append(f"Visual interpretation agrees with {label}")
            elif visual_bias not in {VisualBias.insufficient_data, VisualBias.mixed} and bias not in {VisualBias.mixed, VisualBias.insufficient_data}:
                structured_scores.append(0)
                contradictions.append(f"Visual interpretation conflicts with {label}")

        structured_alignment = sum(structured_scores) / len(structured_scores) if structured_scores else 0.5
        average_quality = sum(item.image_quality for item in observations) / len(observations)
        region_count = sum(len(item.regions) for item in observations)
        evidence_factor = min(region_count / 8, 1)
        confidence = min(1, average_quality * 0.35 + timeframe_alignment * 0.35 + structured_alignment * 0.2 + evidence_factor * 0.1)

        detected_symbols = {item.detected_symbol.upper() for item in observations if item.detected_symbol}
        if detected_symbols and detected_symbols != {symbol}:
            warnings.append("One or more images appear to reference a different symbol")
            confidence *= 0.7
        if any(item.image_quality < 0.45 for item in observations):
            warnings.append("At least one image has low visual quality")
        if len({item.timeframe.upper() for item in observations}) == 1:
            warnings.append("Analysis contains only one timeframe")
        if payload.current_price is None:
            warnings.append("Current price was not supplied; zone proximity cannot be validated")

        uncertainty = 1 - confidence
        regions = [region for item in observations for region in item.regions]
        summary = (
            f"{symbol}: visual bias {visual_bias.value}; "
            f"multi-timeframe alignment {timeframe_alignment:.0%}; "
            f"structured-data alignment {structured_alignment:.0%}."
        )
        record = MarketVisionRecord(
            symbol=symbol,
            observations=observations,
            visual_bias=visual_bias,
            multi_timeframe_alignment=round(timeframe_alignment, 4),
            structured_data_alignment=round(structured_alignment, 4),
            confidence=round(confidence, 4),
            uncertainty=round(uncertainty, 4),
            detected_regions=regions,
            confirmations=confirmations,
            contradictions=contradictions,
            warnings=warnings,
            summary=summary,
        )
        self._records[record.id] = record
        return record

    def list_all(self, symbol: str | None = None) -> list[MarketVisionRecord]:
        values = list(self._records.values())
        if symbol:
            values = [item for item in values if item.symbol == symbol.upper()]
        return sorted(values, key=lambda item: item.created_at, reverse=True)

    def get(self, record_id: UUID) -> MarketVisionRecord | None:
        return self._records.get(record_id)

    def latest(self, symbol: str) -> MarketVisionRecord | None:
        values = self.list_all(symbol=symbol)
        return values[0] if values else None

    def status(self) -> MarketVisionStatus:
        values = list(self._records.values())
        return MarketVisionStatus(
            analyses=len(values),
            symbols=len({item.symbol for item in values}),
            bullish=sum(item.visual_bias == VisualBias.bullish for item in values),
            bearish=sum(item.visual_bias == VisualBias.bearish for item in values),
            mixed_or_neutral=sum(
                item.visual_bias in {VisualBias.mixed, VisualBias.neutral, VisualBias.insufficient_data}
                for item in values
            ),
        )


market_vision_service = MarketVisionService()
