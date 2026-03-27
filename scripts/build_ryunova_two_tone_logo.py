#!/usr/bin/env python3
"""
Build two-tone RyuNova Platform mark for dark headers (black bar).

Splits the original single-colour mark into:
  - Dragon: warm gold (#F4B448)
  - Globe fill: teal (#4ECDC4)
  - Network lines: white

Requires: pip install Pillow

Usage (from repo root):
  python scripts/build_ryunova_two_tone_logo.py \\
    --input path/to/source-mark.png \\
    --output path/to/output.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def build_two_tone(
    input_path: Path,
    output_path: Path,
    *,
    globe_radius: float = 0.38,
    dragon_rgb: tuple[int, int, int] = (244, 180, 72),
    globe_rgb: tuple[int, int, int] = (78, 205, 196),
) -> None:
    im = Image.open(input_path).convert("RGBA")
    w, h = im.size
    px = im.load()

    DRAGON = (*dragon_rgb, 255)
    GLOBE = (*globe_rgb, 255)
    LINE = (255, 255, 255, 255)
    TRANSPARENT = (0, 0, 0, 0)

    bodies: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r > 248 and g > 248 and b > 248:
                continue
            if r > 210 and g > 210 and b > 210:
                continue
            bodies.append((x, y))

    if not bodies:
        raise SystemExit("No coloured body pixels found (unexpected image).")

    cx = sum(t[0] for t in bodies) / len(bodies)
    cy = sum(t[1] for t in bodies) / len(bodies)
    dmax = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x, y in bodies) + 1e-6

    out = Image.new("RGBA", (w, h), TRANSPARENT)
    op = out.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                op[x, y] = TRANSPARENT
                continue
            if r > 248 and g > 248 and b > 248:
                op[x, y] = TRANSPARENT
                continue
            if r > 210 and g > 210 and b > 210:
                op[x, y] = LINE
                continue
            d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / dmax
            op[x, y] = GLOBE if d < globe_radius else DRAGON

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r > 248 and g > 248 and b > 248:
                continue
            if r > 210 and g > 210 and b > 210:
                op[x, y] = LINE

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path, optimize=True)
    print(f"Wrote {output_path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--globe-radius",
        type=float,
        default=0.38,
        help="Fraction of max distance from rust centroid treated as globe (0–1).",
    )
    args = p.parse_args()
    build_two_tone(args.input, args.output, globe_radius=args.globe_radius)


if __name__ == "__main__":
    main()
