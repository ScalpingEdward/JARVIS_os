"""Cropping to the subject and blurring what is around it, on real pixels."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image, ImageStat

from app.instagram_content.reframe import (
    ReframeError,
    SubjectBox,
    SubjectFinder,
    SubjectFinderConfig,
    blur_background,
    crop_to_subject,
    reframe_file,
)


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    """A sharp subject in the middle, noisy clutter along the edges."""
    image = Image.new("RGB", (1000, 800), (30, 30, 30))
    for x in range(0, 1000, 4):  # high-frequency edge clutter, blurs visibly
        for y in range(0, 800, 4):
            if x < 200 or x > 800 or y < 120 or y > 680:
                image.putpixel((x, y), (250, 250, 250))
    for x in range(300, 700):
        for y in range(250, 550):
            image.putpixel((x, y), (200, 120, 40))
    path = tmp_path / "photo.jpg"
    image.save(path, quality=95)
    return path


def _box() -> SubjectBox:
    return SubjectBox(x0=0.3, y0=0.3, x1=0.7, y1=0.7, note="subject in the middle")


def test_a_box_outside_the_image_or_inverted_is_refused():
    with pytest.raises(ReframeError, match="outside the image or inverted"):
        SubjectBox(x0=0.8, y0=0.1, x1=0.2, y1=0.9)
    with pytest.raises(ReframeError):
        SubjectBox(x0=-0.1, y0=0.0, x1=0.5, y1=0.5)


def test_cropping_keeps_the_subject_and_drops_the_cluttered_edges(photo, tmp_path):
    out = crop_to_subject(photo, _box(), tmp_path / "cropped.jpg")

    def bright_pixels(image: Image.Image) -> int:
        return sum(1 for pixel in image.convert("L").getdata() if pixel > 230)

    with Image.open(out) as cropped, Image.open(photo) as original:
        assert cropped.size < original.size
        assert bright_pixels(original) > 1000, "the fixture really has bright clutter"
        assert bright_pixels(cropped) == 0, "and none of it survives the crop"


def test_blurring_keeps_the_frame_softens_the_edges_and_leaves_the_subject(photo, tmp_path):
    out = blur_background(photo, _box(), tmp_path / "soft.jpg")

    with Image.open(out) as soft, Image.open(photo) as original:
        assert soft.size == original.size, "the frame is kept, only the background changes"
        centre = (500, 400)
        assert abs(soft.getpixel(centre)[0] - original.getpixel(centre)[0]) < 12, "subject stays sharp"
        corner = (40, 40)
        assert ImageStat.Stat(soft.crop((0, 0, 150, 150))).stddev[0] < \
               ImageStat.Stat(original.crop((0, 0, 150, 150))).stddev[0], "the corner is softer"
        assert soft.getpixel(corner) != original.getpixel(corner)


def test_an_unknown_mode_is_refused_before_anything_is_asked(photo, tmp_path):
    with pytest.raises(ReframeError, match="unknown reframe mode"):
        reframe_file(photo, "retouch", tmp_path / "x.jpg", finder=None)


def test_the_subject_box_comes_from_the_model_and_the_image_is_sent_small(photo, tmp_path):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(
            {"x0": 0.3, "y0": 0.3, "x1": 0.7, "y1": 0.7, "note": "box in the box"})}]})

    finder = SubjectFinder(config=SubjectFinderConfig(api_key="k"),
                           client=httpx.Client(transport=httpx.MockTransport(handler)))
    out, box = reframe_file(photo, "crop", tmp_path / "cropped.jpg", finder=finder)

    assert out.is_file()
    assert (box.x0, box.y1) == (0.3, 0.7)
    assert box.note == "box in the box"
    sent = seen["body"]["messages"][0]["content"][0]["source"]["data"]
    assert len(sent) < 400_000, "a full-size upload would only cost time and tokens"


def test_a_response_that_is_not_a_box_fails_loudly(photo, tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": '{"note": "no box here"}'}]})

    finder = SubjectFinder(config=SubjectFinderConfig(api_key="k"),
                           client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ReframeError, match="incomplete"):
        reframe_file(photo, "crop", tmp_path / "x.jpg", finder=finder)


def test_without_an_api_key_nothing_is_guessed():
    finder = SubjectFinder(config=SubjectFinderConfig(api_key=None))
    with pytest.raises(ReframeError, match="ANTHROPIC_API_KEY"):
        finder.find(b"not-an-image")
