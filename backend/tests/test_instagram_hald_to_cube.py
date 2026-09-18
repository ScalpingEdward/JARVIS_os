"""Reading Brano's Lightroom look back out of a processed HALD image.

Lightroom cannot export a LUT and its settings cannot be faithfully
recreated elsewhere -- "Shadows +38" is a number in Adobe's own tone-mapping
model. So the look is measured instead of translated: a HALD image holds
every colour exactly once, and the pixels that come back from Lightroom are
the transform itself.

The failure that matters most here is the silent one: an export where the
preset was never applied yields a perfectly valid LUT that changes nothing,
and every photo afterwards looks untouched with no error to explain it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.instagram_content.hald_to_cube import (
    HaldConversionError,
    hald_to_cube,
    looks_unprocessed,
)

#: Level 2 -> 8x8 px, a 4x4x4 cube. Small enough to assert on by hand,
#: identical in structure to the level-8 image Brano actually exports.
LEVEL = 2
CUBE_SIZE = LEVEL * LEVEL
SIDE = LEVEL ** 3


def _identity_hald(path: Path) -> Path:
    """The same layout ffmpeg's haldclutsrc produces: red varies fastest,
    then green, then blue."""
    image = Image.new("RGB", (SIDE, SIDE))
    step = 255 / (CUBE_SIZE - 1)
    pixels = []
    for blue in range(CUBE_SIZE):
        for green in range(CUBE_SIZE):
            for red in range(CUBE_SIZE):
                pixels.append((round(red * step), round(green * step), round(blue * step)))
    image.putdata(pixels)
    image.save(path)
    return path


def _inverted_hald(path: Path) -> Path:
    """Stands in for "a preset was applied" -- any transform will do, as
    long as the pixels are no longer the identity."""
    with Image.open(_identity_hald(path.with_name("tmp_identity.png"))) as source:
        inverted = source.convert("RGB").point(lambda v: 255 - v)
    inverted.save(path)
    return path


def test_a_processed_hald_becomes_a_valid_cube(tmp_path):
    cube = hald_to_cube(_inverted_hald(tmp_path / "graded.png"), tmp_path / "look.cube")

    lines = [line for line in cube.read_text().splitlines() if line and not line.startswith(("TITLE", "DOMAIN"))]
    assert lines[0] == f"LUT_3D_SIZE {CUBE_SIZE}"
    assert len(lines) - 1 == CUBE_SIZE ** 3, "one entry per colour in the cube"


def test_the_cube_carries_the_actual_measured_colours(tmp_path):
    """The first entry is what the preset does to pure black. Inverted, that
    is white -- read back from the pixels, not assumed."""
    cube = hald_to_cube(_inverted_hald(tmp_path / "graded.png"), tmp_path / "look.cube")

    entries = [l for l in cube.read_text().splitlines() if l and l[0].isdigit()]
    first = [float(v) for v in entries[0].split()]
    assert first == pytest.approx([1.0, 1.0, 1.0], abs=0.01)


def test_an_untouched_export_is_detected_before_it_is_used(tmp_path):
    """The dangerous case: Lightroom opened, preset never applied, exported
    anyway. The resulting LUT is valid and does nothing."""
    assert looks_unprocessed(_identity_hald(tmp_path / "untouched.png")) is True


def test_a_processed_export_is_not_flagged(tmp_path):
    assert looks_unprocessed(_inverted_hald(tmp_path / "graded.png")) is False


def test_a_resized_export_is_refused_with_a_usable_reason(tmp_path):
    """Lightroom resizing on export destroys the colour layout. The message
    has to say what to change, not just that something is wrong."""
    path = tmp_path / "resized.png"
    Image.new("RGB", (SIDE + 3, SIDE + 3)).save(path)

    with pytest.raises(HaldConversionError, match="without resizing"):
        hald_to_cube(path, tmp_path / "look.cube")


def test_a_cropped_export_is_refused(tmp_path):
    path = tmp_path / "cropped.png"
    Image.new("RGB", (SIDE, SIDE - 2)).save(path)

    with pytest.raises(HaldConversionError, match="must be square"):
        hald_to_cube(path, tmp_path / "look.cube")


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(HaldConversionError, match="no such HALD image"):
        hald_to_cube(tmp_path / "gone.png", tmp_path / "look.cube")
