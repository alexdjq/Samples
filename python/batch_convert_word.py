# -*- coding: utf-8 -*-
"""
batch_convert_word.py
=====================

Batch-convert every PP-StructureV3 ``*.json`` file in a directory into a
matching Word ``*.docx`` file, automatically choosing the correct
converter for each page:

* **Text-heavy pages** (prefaces, narratives -- markdown without any
  table markup) are rendered by ``text_json_to_word.convert_json_to_docx``
  in-process.
* **Genealogy table pages** (markdown that contains ``<table>`` or a
  pipe-table separator row) are delegated to ``json_to_word.py`` via a
  subprocess so its existing single-file CLI is reused unchanged.

Usage
-----
    python batch_convert_word.py <directory> [--overwrite]

Example::

    python batch_convert_word.py "C:\\Users\\alexdu\\Downloads\\vFlat\\\
iPhone 17 Pro Max - Default folder_cleaned"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Dict, Any, List, Optional, Tuple

# Re-use the text-page renderer and the page-type heuristic that
# text_json_to_word.py already exposes.  Importing keeps the
# classification rules centralised in a single place.
import text_json_to_word as tj

# Locate json_to_word.py next to this script so the subprocess invocation
# does not depend on the current working directory.
_SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
_JSON_TO_WORD   = os.path.join(_SCRIPT_DIR, "json_to_word.py")


def _classify(json_path: str) -> Tuple[str, Optional[str]]:
    """Return ``(kind, error)`` for ``json_path``.

    ``kind`` is one of ``"image"``, ``"text"``, ``"table"`` or
    ``"unknown"``.  ``error`` is ``None`` on success and a
    human-readable message on failure (malformed JSON, missing
    markdown, ...).

    The image-page whitelist defined in ``text_json_to_word`` always
    wins over the markdown-based heuristic below, so genealogy pages
    that happen to OCR as tables but are really pictorial are still
    rendered by ``text_json_to_word``'s image-insertion path.
    """
    # Highest priority: the explicit image-page whitelist.  These pages
    # bypass markdown parsing entirely and are rendered by
    # text_json_to_word, which knows how to drop the original scan into
    # the body cell.
    page_no = tj._extract_page_number(json_path)
    if page_no is not None and page_no in tj.IMAGE_PAGE_WHITELIST:
        return "image", None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            payload: Dict[str, Any] = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return "unknown", f"cannot parse JSON ({exc})"

    try:
        md_text = tj._extract_markdown_text(payload)
    except ValueError as exc:
        return "unknown", str(exc)

    lowered = md_text.lower()
    if "<table" in lowered or "</table>" in lowered:
        return "table", None
    if "|---" in lowered or "| ---" in lowered:
        return "table", None
    return "text", None


def _convert_text(json_path: str, docx_path: str) -> None:
    tj.convert_json_to_docx(json_path, docx_path)


def _convert_table(json_path: str, docx_path: str) -> None:
    """Run ``json_to_word.py <in.json> <out.docx>`` as a subprocess."""
    if not os.path.isfile(_JSON_TO_WORD):
        raise FileNotFoundError(
            f"json_to_word.py not found next to batch_convert_word.py "
            f"(expected at {_JSON_TO_WORD!r})."
        )
    cmd = [sys.executable, _JSON_TO_WORD, json_path, docx_path]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        # Surface the child's stderr so the caller's per-file failure
        # message is actually useful.
        msg = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"json_to_word.py exited with code {proc.returncode}: {msg}"
        )


def batch_convert(target_dir: str, overwrite: bool = False) -> int:
    if not os.path.isdir(target_dir):
        print(f"[ERROR] Not a directory: {target_dir}")
        return 2

    json_files = sorted(
        os.path.join(target_dir, f)
        for f in os.listdir(target_dir)
        if f.lower().endswith(".json")
    )
    if not json_files:
        print(f"[WARN] No .json files found in {target_dir!r}.")
        return 0

    counts = {"text": 0, "table": 0, "image": 0, "skipped": 0, "failed": 0}

    for jp in json_files:
        out_docx = os.path.splitext(jp)[0] + ".docx"
        base = os.path.basename(jp)

        if os.path.exists(out_docx) and not overwrite:
            print(f"[SKIP] {base}: {os.path.basename(out_docx)} already exists.")
            counts["skipped"] += 1
            continue

        kind, err = _classify(jp)
        if err is not None or kind == "unknown":
            print(f"[FAIL] {base}: {err or 'unknown content shape'}")
            counts["failed"] += 1
            continue

        try:
            if kind == "text":
                _convert_text(jp, out_docx)
                tag = "TEXT "
            elif kind == "image":
                # Image-page whitelist: text_json_to_word handles the
                # picture insertion in-process.
                _convert_text(jp, out_docx)
                tag = "IMAGE"
            else:  # "table"
                _convert_table(jp, out_docx)
                tag = "TABLE"
            counts[kind] += 1
            print(f"[ {tag}] {base} -> {os.path.basename(out_docx)}")
        except Exception as exc:                       # noqa: BLE001
            counts["failed"] += 1
            print(f"[FAIL] {base}: {exc}")

    print()
    print("Summary")
    print("-------")
    print(f"  Text pages converted : {counts['text']}")
    print(f"  Image pages converted: {counts['image']}")
    print(f"  Table pages converted: {counts['table']}")
    print(f"  Skipped (existing)   : {counts['skipped']}")
    print(f"  Failed               : {counts['failed']}")
    return 0 if counts["failed"] == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-convert every *.json in DIRECTORY to *.docx, dispatching "
            "text-heavy pages to text_json_to_word and table pages to "
            "json_to_word."
        ),
    )
    parser.add_argument("directory",
                        help="Directory containing the *.json files.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing *.docx files.")
    args = parser.parse_args(argv)
    return batch_convert(args.directory, overwrite=args.overwrite)


if __name__ == "__main__":
    sys.exit(main())
