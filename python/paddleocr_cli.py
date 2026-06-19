"""PaddleOCR PP-StructureV3 cloud-API CLI wrapper.

Submits a local file or URL to the PaddleOCR job API, polls until the
job finishes, then downloads the result JSONL and saves it as a single
consolidated JSON file with the **same shape as the existing
``窑湾.json``** (i.e. ``{"layoutParsingResults": [...], "ocrResults": ...,
...}``).  This makes the output a drop-in input for ``json_to_word.py``.

Usage::

    python paddleocr_cli.py -i <local-file-or-url> -o <output.json>
    python paddleocr_cli.py -i sample.pdf -o sample.json --token XXX
    python paddleocr_cli.py -i sample.pdf -o sample.json --poll-interval 3

Dependencies::

    pip install requests
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import requests

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
DEFAULT_TOKEN = "d6dc1ddaf988a97fb57ed8ab104ea6c0e292e62e"
DEFAULT_MODEL = "PP-StructureV3"
DEFAULT_POLL_INTERVAL = 5  # seconds


# ---------------------------------------------------------------------------
# Job submission
# ---------------------------------------------------------------------------
def submit_job(
    file_path: str,
    token: str,
    model: str,
    optional_payload: Dict[str, Any],
) -> str:
    """Submit a PaddleOCR job for *file_path* and return the ``jobId``."""
    headers = {"Authorization": f"bearer {token}"}

    if file_path.startswith("http://") or file_path.startswith("https://"):
        # Remote-URL mode.
        headers["Content-Type"] = "application/json"
        payload = {
            "fileUrl": file_path,
            "model": model,
            "optionalPayload": optional_payload,
        }
        resp = requests.post(JOB_URL, json=payload, headers=headers)
    else:
        # Local-file mode: multipart upload.
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")
        data = {"model": model, "optionalPayload": json.dumps(optional_payload)}
        with open(file_path, "rb") as f:
            files = {"file": f}
            resp = requests.post(JOB_URL, headers=headers, data=data, files=files)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Job submission failed (HTTP {resp.status_code}): {resp.text}"
        )

    body = resp.json()
    job_id = body.get("data", {}).get("jobId")
    if not job_id:
        raise RuntimeError(f"Unexpected submit response: {body}")
    return job_id


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
def poll_job(
    job_id: str,
    token: str,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
) -> str:
    """Poll *job_id* until it finishes and return the result JSONL URL."""
    headers = {"Authorization": f"bearer {token}"}
    job_url = f"{JOB_URL}/{job_id}"

    while True:
        resp = requests.get(job_url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Poll failed (HTTP {resp.status_code}): {resp.text}"
            )
        data = resp.json().get("data", {})
        state = data.get("state")

        if state == "pending":
            print("  [pending] waiting in queue ...")
        elif state == "running":
            prog = data.get("extractProgress") or {}
            total = prog.get("totalPages")
            done = prog.get("extractedPages")
            if total is not None and done is not None:
                print(f"  [running] {done}/{total} pages extracted ...")
            else:
                print("  [running] processing ...")
        elif state == "done":
            prog = data.get("extractProgress") or {}
            print(
                f"  [done] pages={prog.get('extractedPages')}, "
                f"start={prog.get('startTime')}, end={prog.get('endTime')}"
            )
            jsonl_url = (data.get("resultUrl") or {}).get("jsonUrl")
            if not jsonl_url:
                raise RuntimeError(f"Job done but no JSONL URL: {data}")
            return jsonl_url
        elif state == "failed":
            raise RuntimeError(
                f"Job failed: {data.get('errorMsg', '<no errorMsg>')}"
            )
        else:
            print(f"  [unknown state: {state}]")

        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# Result fetch / merge
# ---------------------------------------------------------------------------
def fetch_and_merge_result(jsonl_url: str) -> Dict[str, Any]:
    """Download the JSONL result and merge every line's ``result`` block
    into a single dict.

    Each JSONL line has the shape ``{"result": {"layoutParsingResults":
    [...], "ocrResults": [...], ...}}``.  When the API returns multiple
    lines (e.g. for multi-file jobs), we concatenate every list-typed
    field across lines and keep the first non-null scalar for the rest.
    """
    resp = requests.get(jsonl_url)
    resp.raise_for_status()

    lines = [ln for ln in resp.text.strip().split("\n") if ln.strip()]
    if not lines:
        raise RuntimeError("Result JSONL is empty")

    merged: Dict[str, Any] = {}
    for line in lines:
        result = json.loads(line).get("result", {})
        for key, value in result.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key].extend(value)
            # Non-list duplicates: keep the first occurrence.

    return merged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run PaddleOCR PP-StructureV3 on a local file or URL and "
            "save the raw JSON result (drop-in input for json_to_word.py)."
        )
    )
    p.add_argument(
        "-i", "--input", required=True,
        help="Local file path or http(s) URL to OCR.",
    )
    p.add_argument(
        "-o", "--output", required=True,
        help="Output JSON file path.",
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

    print(f"Input : {args.input}")
    print(f"Output: {args.output}")
    print(f"Model : {args.model}")

    print("\n[1/3] Submitting job ...")
    job_id = submit_job(args.input, args.token, args.model, optional_payload)
    print(f"  jobId = {job_id}")

    print("\n[2/3] Polling for completion ...")
    jsonl_url = poll_job(job_id, args.token, args.poll_interval)

    print("\n[3/3] Downloading and merging result ...")
    merged = fetch_and_merge_result(jsonl_url)

    # Make sure the destination directory exists.
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=args.indent)

    pages = len(merged.get("layoutParsingResults") or [])
    size_kb = os.path.getsize(args.output) / 1024.0
    print(f"\nDone. {pages} page(s), {size_kb:.1f} KB written to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001  -- top-level CLI catch-all
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
