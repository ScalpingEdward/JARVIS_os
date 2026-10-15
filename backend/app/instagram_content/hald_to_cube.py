"""Turns a Lightroom-processed HALD image into a .cube LUT.

Why this detour exists: Lightroom cannot export a LUT, and its own settings
cannot be recreated faithfully anywhere else. "Shadows +38" is a value in
Adobe's own tone-mapping model, not a curve anyone outside it can reproduce
-- approximating it would land close, and close is visible when twelve
posts sit next to each other in a grid.

So instead of translating the numbers, we measure the result. A HALD image
contains every colour exactly once, in a known order. Put it through the
preset, and the pixels that come back *are* the transform: for every input
colour, the colour Lightroom turns it into. That is precisely what a LUT is,
and ffmpeg applies it to every photo and video afterwards.

What this cannot capture, by definition: sharpening, clarity, texture and
dehaze. Those depend on a pixel's neighbours, not on its colour, so they
survive no colour lookup at all and are applied separately as real filters.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


class HaldConversionError(ValueError):
    pass


def _infer_level(width: int, height: int) -> int:
    """A HALD of level N is (N^3) x (N^3) pixels and encodes an N^2 cube.

    Derived from the image rather than taken as a parameter: the file is the
    only thing that knows, and a mismatch would silently produce a LUT whose
    colours are subtly wrong everywhere -- the hardest kind of error to
    notice and the worst kind to ship.
    """
    if width != height:
        raise HaldConversionError(
            f"a HALD image must be square, got {width}x{height} -- if Lightroom "
            f"cropped or resized on export, the colours can no longer be read back."
        )
    level = round(width ** (1 / 3))
    if level ** 3 != width:
        raise HaldConversionError(
            f"{width}x{height} is not a valid HALD size (needs level^3 per side). "
            f"Export at original size, without resizing."
        )
    return level


def hald_to_cube(hald_image: Path, destination: Path, *, title: str = "AURON") -> Path:
    """Read a processed HALD image and write the .cube LUT it describes.

    The identity image AURON generated has every colour laid out in a fixed
    order; reading it back in that same order yields the mapping directly.
    No interpolation, no fitting -- each entry is a measured value.
    """
    if not hald_image.is_file():
        raise HaldConversionError(f"no such HALD image: {hald_image}")

    with Image.open(hald_image) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        level = _infer_level(width, height)
        pixels = list(rgb.getdata())

    cube_size = level * level
    expected = cube_size ** 3
    if len(pixels) != expected:
        raise HaldConversionError(
            f"expected {expected} pixels for a level-{level} HALD, found {len(pixels)}"
        )

    lines = [
        f'TITLE "{title}"',
        f"LUT_3D_SIZE {cube_size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
        "",
    ]
    # HALD pixel order already matches .cube order (red fastest, then green,
    # then blue), so a straight pass through the pixel list is correct.
    for r, g, b in pixels:
        lines.append(f"{r / 255:.6f} {g / 255:.6f} {b / 255:.6f}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")
    return destination


def looks_unprocessed(hald_image: Path, *, tolerance: int = 2) -> bool:
    """True when the image is still the untouched identity HALD.

    Worth checking before writing a LUT: an export where the preset was
    never actually applied produces a perfectly valid .cube that changes
    nothing, and every photo afterwards would come out looking exactly as it
    went in, with no error anywhere to explain why.
    """
    with Image.open(hald_image) as image:
        rgb = image.convert("RGB")
        level = _infer_level(*rgb.size)
        pixels = list(rgb.getdata())

    cube_size = level * level
    step = 255 / (cube_size - 1)
    for index in (0, len(pixels) // 3, len(pixels) // 2, len(pixels) - 1):
        r, g, b = pixels[index]
        blue, rest = divmod(index, cube_size * cube_size)
        green, red = divmod(rest, cube_size)
        identity = (round(red * step), round(green * step), round(blue * step))
        if max(abs(r - identity[0]), abs(g - identity[1]), abs(b - identity[2])) > tolerance:
            return False
    return True
