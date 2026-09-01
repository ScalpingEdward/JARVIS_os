from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.instagram_content import api as instagram_api
from app.instagram_content.media_pool_service import media_pool_service
from app.main import app

api_client = TestClient(app)


def test_maintenance_cycle_ingests_and_curates_in_one_call(monkeypatch):
    media_pool_service.reset()

    class FakeAnalyzer:
        def analyze(self, **kwargs):
            from app.instagram_content.vision_analysis import VisionAnalysisResult

            return VisionAnalysisResult(theme="desert-gold", tags=["gold"], aesthetic_score=0.6, reasoning="ok")

    monkeypatch.setattr(instagram_api, "AnthropicVisionAnalyzer", FakeAnalyzer)

    body = {
        "items": [
            {"media_ref": f"img-{i}", "media_type": "image", "image_base64": "ZmFrZQ==", "image_media_type": "image/jpeg"}
            for i in range(3)
        ]
    }
    response = api_client.post("/v1/instagram/maintenance-cycle", json=body)
    assert response.status_code == 200
    drafts = response.json()["items"]
    assert len(drafts) == 1  # 3 same-theme images -> one carousel draft
    assert len(drafts[0]["media_item_ids"]) == 3


def test_maintenance_cycle_without_new_media_just_curates_existing_pool():
    from app.instagram_content.media_pool_models import MediaPoolIngestRequest, MediaPoolItemCreate

    media_pool_service.reset()
    media_pool_service.ingest(
        MediaPoolIngestRequest(
            items=[MediaPoolItemCreate(media_ref=f"a{i}", media_type="image", theme="t", aesthetic_score=0.7) for i in range(3)]
        )
    )
    response = api_client.post("/v1/instagram/maintenance-cycle")
    assert response.status_code == 200
    assert response.json()["count"] == 1
