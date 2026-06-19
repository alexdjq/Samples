"""Merge all per-page docx files into a single Word document.

The script collects every ``Default folder - <N>.docx`` file in the source
directory, sorts them by the trailing page number, and concatenates them
with :class:`docxcompose.composer.Composer`.  ``docxcompose`` keeps each
document's section properties intact (page size, margins, columns, headers,
footers...) and inserts a hard page break between consecutive documents,
so every original page is reproduced exactly as-is in the merged file.

Usage (PowerShell):

    python merge_genealogy.py

The output is written next to the source folder as ``家谱.docx``.

Note: Microsoft Word's legacy ``.doc`` format (Word 97-2003 binary) cannot
be produced by python-docx / docxcompose.  The merged file is therefore a
modern ``.docx``; it opens identically in Word, WPS and LibreOffice.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple

from docx import Document
from docxcompose.composer import Composer


SRC_DIR_DEFAULT = Path(
    r"C:\Users\alexdu\Downloads\vFlat\iPhone 17 Pro Max - Default folder_cleaned"
)
OUT_NAME_DEFAULT = "家谱.docx"

_PAGE_RE = re.compile(r"(\d+)(?=\.docx$)", re.IGNORECASE)


def collect_pages(src_dir: Path) -> List[Tuple[int, Path]]:
    """Return ``[(page_number, path), ...]`` sorted ascending by page number."""

    pages: List[Tuple[int, Path]] = []
    for p in src_dir.iterdir():
        if not p.is_file() or p.suffix.lower() != ".docx":
            continue
        # Skip Word lock files like ``~$Default folder - 1.docx``.
        if p.name.startswith("~$"):
            continue
        m = _PAGE_RE.search(p.name)
        if not m:
            continue
        pages.append((int(m.group(1)), p))

    pages.sort(key=lambda x: x[0])
    return pages


def merge(src_dir: Path, out_path: Path) -> None:
    pages = collect_pages(src_dir)
    if not pages:
        raise SystemExit(f"No .docx files found in: {src_dir}")

    nums = [n for n, _ in pages]
    print(f"[info] discovered {len(pages)} docx files: page {nums[0]} ... {nums[-1]}")
    missing = [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)]
    if missing:
        print(f"[warn] missing page numbers: {missing}")

    # The first document becomes the container; its sectPr is preserved as the
    # very first section of the merged file.  Every appended document keeps
    # its own sectPr too, so per-page page setup (margins, page size,
    # orientation) survives the merge unchanged.
    first_num, first_path = pages[0]
    print(f"[info] base = page {first_num}: {first_path.name}")
    base = Document(str(first_path))
    composer = Composer(base)

    started = time.time()
    for idx, (num, path) in enumerate(pages[1:], start=2):
        if idx % 25 == 0 or idx == len(pages):
            elapsed = time.time() - started
            print(f"[info] appending {idx}/{len(pages)} (page {num}) ... {elapsed:.1f}s elapsed")
        try:
            doc = Document(str(path))
        except Exception as exc:
            print(f"[error] cannot open {path.name}: {exc}", file=sys.stderr)
            continue
        # ``append`` inserts a page break before the appended content and
        # preserves the appended document's section properties.
        composer.append(doc)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[info] saving -> {out_path}")
    composer.save(str(out_path))
    print(f"[done] merged {len(pages)} pages in {time.time() - started:.1f}s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge per-page genealogy docx files in page order.")
    parser.add_argument(
        "--src",
        type=Path,
        default=SRC_DIR_DEFAULT,
        help=f"Source directory containing per-page .docx files (default: {SRC_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output .docx path (default: <src>/../{OUT_NAME_DEFAULT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    src: Path = args.src
    out: Path = args.out or (src.parent / OUT_NAME_DEFAULT)
    if not src.is_dir():
        raise SystemExit(f"Source directory does not exist: {src}")
    merge(src, out)


if __name__ == "__main__":
    main()
