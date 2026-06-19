"""Batch-OCR every JPEG image in a directory using ``paddleocr_cli``.

For every ``*.jpg`` / ``*.jpeg`` file in the input directory, submit a
PaddleOCR job (PP-StructureV3 by default), wait for it to finish, and
write the consolidated JSON result next to the original image with the
same stem (``foo.jpg`` -> ``foo.json``).

Highlights
----------
* Reuses :func:`paddleocr_cli.submit_job`, :func:`paddleocr_cli.poll_job`
  and :func:`paddleocr_cli.fetch_and_merge_result` directly, so the
  output format is identical to running the single-file CLI.
* Submissions and polling run on a small thread-pool (``--workers``,
  default 4) -- the OCR service handles each job independently, so this
  shortens wall-clock time dramatically.
* Existing JSON files are skipped by default; pass ``--overwrite`` to
  force re-OCR.
* Failures are collected and reported at the end; one bad image will
  not abort the whole batch.

Usage::

    python batch_ocr_dir.py -d "C:\\path\\to\\folder"
    python batch_ocr_dir.py -d ".\\photos" --workers 6 --overwrite
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

# Reuse the single-file CLI implementation.
from paddleocr_cli import (
    DEFAULT_MODEL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TOKEN,
    fetch_and_merge_result,
    poll_job,
    submit_job,
)

JPEG_SUFFIXES = {".jpg", ".jpeg"}


@dataclass
class JobResult:
    """Outcome of OCR-ing a single image."""
    src: Path
    dst: Path
    ok: bool
    pages: int = 0
    size_kb: float = 0.0
    skipped: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Per-image worker
# ---------------------------------------------------------------------------
def _process_image(
    src: Path,
    *,
    token: str,
    model: str,
    optional_payload: Dict[str, Any],
    poll_interval: int,
    overwrite: bool,
    indent: Optional[int],
    log_lock: Lock,
    index: int,
    total: int,
) -> JobResult:
    """OCR one image and write ``<stem>.json`` next to it."""
    dst = src.with_suffix(".json")
    tag = f"[{index}/{total}] {src.name}"

    if dst.exists() and not overwrite:
        with log_lock:
            print(f"{tag}  -> SKIP (json exists)")
        return JobResult(src=src, dst=dst, ok=True, skipped=True)

    try:
        with log_lock:
            print(f"{tag}  submitting ...")
        job_id = submit_job(str(src), token, model, optional_payload)

        with log_lock:
            print(f"{tag}  jobId={job_id}, polling ...")
        jsonl_url = poll_job(job_id, token, poll_interval)

        merged = fetch_and_merge_result(jsonl_url)
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=indent)

        pages = len(merged.get("layoutParsingResults") or [])
        size_kb = dst.stat().st_size / 1024.0
        with log_lock:
            print(f"{tag}  OK  pages={pages}  size={size_kb:.1f}KB  -> {dst.name}")
        return JobResult(src=src, dst=dst, ok=True, pages=pages, size_kb=size_kb)

    except Exception as exc:  # noqa: BLE001  -- we want to keep the batch alive
        with log_lock:
            print(f"{tag}  FAIL  {exc}", file=sys.stderr)
        return JobResult(src=src, dst=dst, ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Directory orchestration
# ---------------------------------------------------------------------------
def collect_images(directory: Path, recursive: bool) -> List[Path]:
    """Return a sorted list of JPEG images under *directory*."""
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    iterator = directory.rglob("*") if recursive else directory.iterdir()
    images = [
        p for p in iterator
        if p.is_file() and p.suffix.lower() in JPEG_SUFFIXES
    ]
    images.sort(key=lambda p: p.name.lower())
    return images


def run_batch(
    directory: Path,
    *,
    token: str,
    model: str,
    optional_payload: Dict[str, Any],
    poll_interval: int,
    overwrite: bool,
    workers: int,
    recursive: bool,
    indent: Optional[int],
) -> List[JobResult]:
    images = collect_images(directory, recursive)
    total = len(images)
    if total == 0:
        print(f"No JPEG images found in: {directory}")
        return []

    print(f"Found {total} image(s) in {directory}")
    print(f"Workers={workers}, model={model}, overwrite={overwrite}\n")

    log_lock = Lock()
    results: List[JobResult] = []
    started = time.time()

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [
            pool.submit(
                _process_image,
                src,
                token=token,
                model=model,
                optional_payload=optional_payload,
                poll_interval=poll_interval,
                overwrite=overwrite,
                indent=indent,
                log_lock=log_lock,
                index=i,
                total=total,
            )
            for i, src in enumerate(images, start=1)
        ]
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.time() - started
    print(f"\nFinished in {elapsed:.1f}s.")
    return results


def summarize(results: List[JobResult]) -> int:
    """Print a summary; return the number of failures."""
    ok = [r for r in results if r.ok and not r.skipped]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in results if not r.ok]

    print(f"  Success : {len(ok)}")
    print(f"  Skipped : {len(skipped)}")
    print(f"  Failed  : {len(failed)}")

    if failed:
        print("\nFailed files:")
        for r in failed:
            print(f"  - {r.src.name}: {r.error}")
    return len(failed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Batch-OCR every JPEG image in a directory using PaddleOCR "
            "PP-StructureV3 (cloud API). Writes <stem>.json next to each "
            "image."
        )
    )
    p.add_argument(
        "-d", "--dir", required=True,
        help="Input directory containing .jpg / .jpeg files.",
    )
    p.add_argument(
        "--recursive", action="store_true",
        help="Recurse into sub-directories.",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Re-OCR images even if a sibling .json already exists.",
    )
    p.add_argument(
        "--workers", type=int, default=4,
        help="Number of concurrent OCR jobs (default: 4).",
    )
    p.add_argument(
        "--token", default=os.environ.get("PADDLEOCR_TOKEN", DEFAULT_TOKEN),
        help="API bearer token (env: PADDLEOCR_TOKEN).",
    )
    p.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"OCR model name (default: {DEFAULT_MODEL}).",
    )
    p.add_argument(
        "--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL}).",
    )
    p.add_argument(
        "--use-doc-orientation-classify", action="store_true",
        help="Enable document orientation classification.",
    )
    p.add_argument(
        "--use-doc-unwarping", action="store_true",
        help="Enable document unwarping.",
    )
    p.add_argument(
        "--use-chart-recognition", action="store_true",
        help="Enable chart recognition.",
    )
    p.add_argument(
        "--indent", type=int, default=None,
        help="Pretty-print JSON output with the given indent "
             "(default: compact one-line output).",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    optional_payload = {
        "useDocOrientationClassify": args.use_doc_orientation_classify,
        "useDocUnwarping": args.use_doc_unwarping,
        "useChartRecognition": args.use_chart_recognition,
    }

    directory = Path(args.dir).expanduser().resolve()

    results = run_batch(
        directory,
        token=args.token,
        model=args.model,
        optional_payload=optional_payload,
        poll_interval=args.poll_interval,
        overwrite=args.overwrite,
        workers=args.workers,
        recursive=args.recursive,
        indent=args.indent,
    )

    print("\nSummary")
    print("-------")
    failures = summarize(results)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001  -- top-level CLI catch-all
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
