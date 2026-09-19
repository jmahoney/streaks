#!/usr/bin/env python3
"""Compare two PNG images for golden-image snapshot testing.

    python3 scripts/compare_png.py GOLDEN ACTUAL [--diff OUT.png] [--tolerance 8] \
        [--max-differing 0.005]

Sizes must match (else FAIL). A pixel differs when any channel differs by more than `tolerance`.
FAILs when the fraction of differing pixels exceeds `max-differing`. Writes a diff image (differing
pixels in red over a faded copy of ACTUAL) when `--diff` is given.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops


def compare(
    golden_path: str,
    actual_path: str,
    tolerance: int = 8,
    max_differing: float = 0.005,
    diff_path: str | None = None,
) -> tuple[bool, float, str]:
    """Compare `golden_path` against `actual_path`.

    Returns `(passed, fraction_differing, message)`.
    """
    name = Path(actual_path).stem

    golden = Image.open(golden_path).convert("RGBA")
    actual = Image.open(actual_path).convert("RGBA")

    if golden.size != actual.size:
        message = (
            f"FAIL {name}: size mismatch — golden {golden.size[0]}x{golden.size[1]} "
            f"vs actual {actual.size[0]}x{actual.size[1]}"
        )
        return False, 1.0, message

    width, height = golden.size
    total = width * height

    diff = ImageChops.difference(golden, actual)
    bands = diff.split()  # R, G, B, A
    max_band = bands[0]
    for band in bands[1:]:
        max_band = ImageChops.lighter(max_band, band)

    # A pixel "differs" when any channel differs by more than `tolerance`.
    mask = max_band.point(lambda p: 255 if p > tolerance else 0)
    histogram = mask.histogram()
    differing = sum(histogram[1:])  # mask is binary (0 or 255), so only bucket 0 is "same"

    fraction = differing / total if total else 0.0
    passed = fraction <= max_differing

    if diff_path:
        actual_rgb = actual.convert("RGB")
        faded = Image.blend(actual_rgb, Image.new("RGB", actual_rgb.size, (255, 255, 255)), 0.6)
        red = Image.new("RGB", actual_rgb.size, (255, 0, 0))
        diff_image = Image.composite(red, faded, mask)
        Path(diff_path).parent.mkdir(parents=True, exist_ok=True)
        diff_image.save(diff_path)

    percent = fraction * 100
    if passed:
        message = f"PASS {name} ({percent:.2f}% differing)"
    else:
        limit_percent = max_differing * 100
        message = f"FAIL {name}: {percent:.1f}% of pixels differ (limit {limit_percent:.1f}%)"
        if diff_path:
            message += f" — diff written to {diff_path}"

    return passed, fraction, message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("golden")
    parser.add_argument("actual")
    parser.add_argument("--diff", default=None, help="path to write a diff PNG")
    parser.add_argument("--tolerance", type=int, default=8)
    parser.add_argument("--max-differing", type=float, default=0.005)
    args = parser.parse_args(argv)

    passed, _fraction, message = compare(
        args.golden, args.actual, args.tolerance, args.max_differing, args.diff
    )
    print(message)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
