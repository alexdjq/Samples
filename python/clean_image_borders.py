"""
Clean image borders by filling the outer 5mm of each image with pure white.

Use Case:
    Scanned images (e.g. from vFlat) sometimes contain stray black dots or
    artifacts near the edges. This script overwrites a configurable margin
    (default 5 mm) around each image with pure white (255,255,255), which
    effectively wipes out edge noise.

Usage:
    python clean_image_borders.py
    python clean_image_borders.py --src "C:\\path\\to\\images" --margin-mm 5
    python clean_image_borders.py --in-place             # overwrite originals
    python clean_image_borders.py --dpi 300              # force a DPI value

Notes:
    - By default the script writes cleaned images into a sibling folder named
      "<src>_cleaned" so originals are preserved.
    - If the JPEG metadata reports a low DPI (e.g. 72) it is treated as
      unreliable and DEFAULT_DPI is used instead. Pass --dpi to override.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image, ImageDraw, ImageFile

# Allow loading slightly truncated JPEGs without raising.
ImageFile.LOAD_TRUNCATED_IMAGES = True

DEFAULT_SRC_DIR = r"C:\Users\alexdu\Downloads\vFlat\iPhone 17 Pro Max - Default folder"
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

# When the JPEG-reported DPI is below this threshold we consider it unreliable
# (vFlat and many camera apps tag images as 72 DPI regardless of real density).
MIN_TRUSTED_DPI = 150
DEFAULT_DPI = 300  # Fallback DPI used to convert millimetres to pixels.


def mm_to_pixels(mm: float, dpi: float) -> int:
    """Convert a millimetre measurement to whole pixels for a given DPI."""
    inches = mm / 25.4
    return max(1, int(round(inches * dpi)))


def resolve_dpi(image: Image.Image, override_dpi: float | None) -> float:
    """Pick the DPI to use for mm->px conversion."""
    if override_dpi and override_dpi > 0:
        return float(override_dpi)

    dpi_info = image.info.get("dpi")
    if dpi_info:
        # PIL returns a tuple (x_dpi, y_dpi); use the smaller axis to be safe.
        try:
            dpi_value = float(min(dpi_info))
        except (TypeError, ValueError):
            dpi_value = 0.0
        if dpi_value >= MIN_TRUSTED_DPI:
            return dpi_value

    return float(DEFAULT_DPI)


def whiten_borders(image: Image.Image, margin_px: int) -> Image.Image:
    """Return a copy of *image* with a margin_px-wide white border."""
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")

    width, height = image.size
    if margin_px * 2 >= min(width, height):
        # Edge case: image too small. Just return a fully white image.
        return Image.new(image.mode, image.size, _white_for_mode(image.mode))

    cleaned = image.copy()
    draw = ImageDraw.Draw(cleaned)
    white = _white_for_mode(cleaned.mode)

    # Top
    draw.rectangle([(0, 0), (width, margin_px)], fill=white)
    # Bottom
    draw.rectangle([(0, height - margin_px), (width, height)], fill=white)
    # Left
    draw.rectangle([(0, 0), (margin_px, height)], fill=white)
    # Right
    draw.rectangle([(width - margin_px, 0), (width, height)], fill=white)

    return cleaned


def _white_for_mode(mode: str):
    if mode == "L":
        return 255
    if mode == "RGBA":
        return (255, 255, 255, 255)
    return (255, 255, 255)


def iter_image_files(src_dir: Path) -> Iterable[Path]:
    for path in sorted(src_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
            yield path


def process_one(
    src_path: Path,
    dst_path: Path,
    margin_mm: float,
    override_dpi: float | None,
) -> Tuple[Path, str]:
    """Process a single image. Returns (path, status_message)."""
    try:
        with Image.open(src_path) as img:
            img.load()
            dpi = resolve_dpi(img, override_dpi)
            margin_px = mm_to_pixels(margin_mm, dpi)
            cleaned = whiten_borders(img, margin_px)

            save_kwargs = {}
            ext = dst_path.suffix.lower()
            if ext in (".jpg", ".jpeg"):
                save_kwargs.update(quality=95, subsampling=0, optimize=True)
                # Preserve DPI metadata when writing JPEGs.
                save_kwargs["dpi"] = (int(dpi), int(dpi))

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            cleaned.save(dst_path, **save_kwargs)
        return src_path, f"OK (margin={margin_px}px @ {dpi:.0f} dpi)"
    except Exception as exc:  # noqa: BLE001
        return src_path, f"FAILED: {exc}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        default=DEFAULT_SRC_DIR,
        help="Source directory containing images (default: vFlat folder).",
    )
    parser.add_argument(
        "--dst",
        default=None,
        help="Destination directory (default: <src>_cleaned).",
    )
    parser.add_argument(
        "--margin-mm",
        type=float,
        default=5.0,
        help="Width of the white border in millimetres (default: 5).",
    )
    parser.add_argument(
        "--dpi",
        type=float,
        default=None,
        help="Force a DPI value for mm->px conversion. "
             "If omitted, the script auto-detects (with 300 DPI fallback).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the original files instead of writing to a new folder.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel worker threads (default: 8).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    src_dir = Path(args.src)
    if not src_dir.is_dir():
        print(f"[ERROR] Source directory does not exist: {src_dir}", file=sys.stderr)
        return 1

    if args.in_place:
        dst_dir = src_dir
    else:
        dst_dir = Path(args.dst) if args.dst else src_dir.with_name(src_dir.name + "_cleaned")
    dst_dir.mkdir(parents=True, exist_ok=True)

    files = list(iter_image_files(src_dir))
    if not files:
        print(f"[WARN] No supported image files found in {src_dir}")
        return 0

    print(f"Source     : {src_dir}")
    print(f"Destination: {dst_dir}")
    print(f"Margin     : {args.margin_mm} mm")
    print(f"Files      : {len(files)}")
    print(f"Workers    : {args.workers}")
    print("-" * 60)

    total = len(files)
    failures = 0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = []
        for src_path in files:
            dst_path = dst_dir / src_path.name
            futures.append(
                pool.submit(process_one, src_path, dst_path, args.margin_mm, args.dpi)
            )

        for index, future in enumerate(as_completed(futures), start=1):
            src_path, status = future.result()
            if status.startswith("FAILED"):
                failures += 1
            print(f"[{index:>4}/{total}] {src_path.name}: {status}")

    print("-" * 60)
    print(f"Done. Success: {total - failures}, Failed: {failures}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
