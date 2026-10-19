import base64
from io import BytesIO

from PIL import Image

from app.instagram_content import analyze_and_ingest as module
from app.instagram_content.heic import is_heic, live_photo_companion, to_jpeg_base64
from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
from app.instagram_content.media_pool_service import MediaPoolService
from app.instagram_content.models import MediaType
from app.instagram_content.vision_analysis import VisionAnalysisResult


def _heic_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (64, 48), (200, 120, 40)).save(buf, format="HEIF")
    return base64.b64encode(buf.getvalue()).decode()


def test_heic_is_recognised_and_turned_into_jpeg():
    b64 = _heic_b64()
    raw = base64.b64decode(b64)
    assert is_heic(raw) and is_heic(b"x" * 12, "image/heic") and is_heic(b"x" * 12, None, "IMG_1.HEIC")
    assert not is_heic(b"\xff\xd8\xff\xe0" + b"0" * 8, "image/jpeg", "a.jpg")
    jpg = base64.b64decode(to_jpeg_base64(b64))
    assert jpg[:3] == b"\xff\xd8\xff" and Image.open(BytesIO(jpg)).size == (64, 48)


def test_a_live_photo_mov_is_recognised_but_a_short_clip_of_its_own_is_not():
    assert live_photo_companion("IMG_4021.MOV", 2.4, set())
    assert live_photo_companion("sunset.mov", 1.9, {"sunset"})
    assert not live_photo_companion("IMG_4021.MOV", 6.0, set())          # long enough to be meant
    assert not live_photo_companion("jump.mov", 2.0, set())              # short, but nobody's still
    assert not live_photo_companion("IMG_4021.mp4", 2.0, set())


def test_ingest_hands_the_analysis_and_the_pool_a_jpeg(monkeypatch):
    seen = {}

    class _Vision:
        def analyze(self, **kwargs):
            seen.update(kwargs)
            return VisionAnalysisResult(theme="t", tags=["x"], aesthetic_score=0.5, reasoning="stub")

    monkeypatch.setattr(module, "grade_photo_bytes", lambda data, ref: seen.setdefault("graded", data[:3]) and None)
    service = MediaPoolService()
    service.reset()
    r = module.analyze_and_ingest(
        items=[MediaAnalyzeAndIngestItem(media_ref="heic-1", media_type=MediaType.image,
                                         image_base64=_heic_b64(), image_media_type="image/heif")],
        analyzer=_Vision(), pool_service=service)
    assert r.failed == 0
    assert seen["image_media_type"] == "image/jpeg" and seen["graded"] == b"\xff\xd8\xff"
