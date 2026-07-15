from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    DetectedZone,
    LiveFeedCreate,
    LiveFeedRecord,
    LiveFrameIngest,
    MarketBias,
    VisionAnalysis,
    VisionFinding,
    VisionFrameCreate,
    VisionSource,
    VisionStatus,
)


class VisionError(ValueError):
    pass


class VisionService:
    """Advisory-only vision gateway for screenshots and controlled live frame feeds."""

    def __init__(self) -> None:
        self._feeds: dict[UUID, LiveFeedRecord] = {}
        self._analyses: dict[UUID, VisionAnalysis] = {}

    def reset(self) -> None:
        self._feeds.clear()
        self._analyses.clear()

    def create_feed(self, payload: LiveFeedCreate) -> LiveFeedRecord:
        if payload.source not in {VisionSource.tradingview, VisionSource.mt5, VisionSource.desktop}:
            raise VisionError("Live feeds are only supported for TradingView, MT5 or desktop capture")
        feed = LiveFeedRecord(**payload.model_dump())
        self._feeds[feed.id] = feed
        return deepcopy(feed)

    def list_feeds(self) -> list[LiveFeedRecord]:
        return [deepcopy(feed) for feed in self._feeds.values()]

    def ingest_live_frame(self, feed_id: UUID, payload: LiveFrameIngest) -> VisionAnalysis:
        feed = self._feeds.get(feed_id)
        if feed is None:
            raise VisionError("Live feed not found")
        if not feed.enabled:
            raise VisionError("Live feed is disabled")
        frame = VisionFrameCreate(
            source=feed.source,
            image_ref=payload.image_ref,
            symbol=feed.symbol,
            timeframe=feed.timeframe,
            captured_at=payload.captured_at,
            metadata=payload.metadata,
        )
        feed.last_frame_at = datetime.now(timezone.utc)
        feed.frame_count += 1
        return self.analyze(frame)

    def analyze(self, frame: VisionFrameCreate) -> VisionAnalysis:
        # Provider-neutral contract. A real multimodal provider is attached at deployment.
        findings = [
            VisionFinding(
                label="frame_received",
                detail=f"{frame.source.value} frame accepted for multimodal analysis",
                confidence=1.0,
            )
        ]
        zones: list[DetectedZone] = []
        summary = "Frame queued for multimodal chart or application analysis. No trade is executed."
        analysis = VisionAnalysis(
            frame=frame,
            provider="configured_multimodal_provider",
            summary=summary,
            bias=MarketBias.unknown,
            findings=findings,
            zones=zones,
            advisory_only=True,
            order_execution_allowed=False,
        )
        self._analyses[analysis.id] = analysis
        return deepcopy(analysis)

    def get(self, analysis_id: UUID) -> VisionAnalysis:
        analysis = self._analyses.get(analysis_id)
        if analysis is None:
            raise VisionError("Vision analysis not found")
        return deepcopy(analysis)

    def status(self) -> VisionStatus:
        return VisionStatus(
            supported_sources=list(VisionSource),
            live_feeds=len(self._feeds),
            analyses=len(self._analyses),
        )


vision_service = VisionService()
