import pytest

from app.instagram_content import analyze_and_ingest as module
from app.instagram_content import plates


def test_a_failed_plate_check_holds_the_item_back(tmp_path, monkeypatch):
    f = tmp_path / "x.jpg"
    f.write_bytes(b"jpg")
    monkeypatch.setattr(plates, "photo", lambda p: (_ for _ in ()).throw(plates.PlateError("model missing")))
    assert module._plates_covered(f, "ref", video=False) is False
    assert not f.exists()                       # no processed file -> it cannot be posted


def test_covered_plates_keep_the_file(tmp_path, monkeypatch):
    f = tmp_path / "x.mp4"
    f.write_bytes(b"mp4")
    monkeypatch.setattr(plates, "video", lambda p: 12)
    assert module._plates_covered(f, "ref", video=True) is True and f.exists()


def test_cover_makes_the_box_unreadable():
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    img = np.zeros((100, 200, 3), np.uint8)
    img[40:60, 50:150] = 255
    img[45:55, 60:140:4] = 0                    # "characters"
    before = img[45:55, 60:140].std()
    plates.cover(img, [(60, 45, 140, 55)])
    assert img[45:55, 60:140].std() < before / 3
