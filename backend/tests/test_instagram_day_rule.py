from datetime import datetime, timezone
from uuid import uuid4

from PIL import Image

from app.instagram_content import curation
from app.instagram_content.captured_at_resolution import CapturedAtSource
from app.instagram_content.curation import curate
from app.instagram_content.media_pool_models import MediaPoolItem
from app.instagram_content.models import MediaType


def _item(ref, score=0.5, processed=None, **kw):
    return MediaPoolItem(media_ref=ref, media_type=MediaType.image, theme="beach", tags=["beach"], aesthetic_score=score,
                         captured_at=datetime(2021, 1, 5, 12, tzinfo=timezone.utc), captured_at_source=list(CapturedAtSource)[0], processed_file=processed, **kw)


def test_near_identical_photos_never_share_a_post(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PROCESSED_DIR", str(tmp_path))
    curation._hash_cache.clear()
    base = Image.linear_gradient("L").resize((120, 90)).convert("RGB")
    base.save(tmp_path / "a.jpg"); base.point(lambda v: min(255, v + 3)).save(tmp_path / "b.jpg")   # same shot, a touch brighter
    Image.effect_mandelbrot((120, 90), (-2, -1.5, 1, 1.5), 60).convert("RGB").save(tmp_path / "c.jpg")
    for i, name in enumerate("defg"):
        Image.effect_noise((120, 90), 40 + 20 * i).convert("RGB").save(tmp_path / f"{name}.jpg")
    items = [_item("a", 0.6, "a.jpg"), _item("b", 0.55, "b.jpg"), _item("c", 0.5, "c.jpg")] +         [_item(n, 0.45 - k / 100, f"{n}.jpg") for k, n in enumerate("defg")]
    refs = {i.media_ref for g in curate(items) for i in g.media_items}
    assert refs == {"a", "c", "d", "e", "f", "g"}   # b is a's twin: the weaker one stays in the pool


def test_a_day_that_already_had_a_carousel_gets_no_second_one(monkeypatch):
    curation._hash_cache.clear()
    draft = uuid4()
    used = [_item(f"u{i}", reserved_in_draft_id=draft) for i in range(3)]
    fresh = [_item(f"f{i}") for i in range(4)]
    assert curate(used + fresh) == []
    assert len(curate(fresh)) == 1
