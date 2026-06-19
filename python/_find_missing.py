# -*- coding: utf-8 -*-
"""Search for 廷贵 / 廷璋 / 廷献 across the OCR JSON, recording their page index
and approximate vertical (Y) coordinate so we can tell which generation row
they belong to."""
import json
import re

JSON_PATH = r"C:\Users\alexdu\Downloads\vFlat\家谱\窑湾.json"

with open(JSON_PATH, "r", encoding="utf-8") as fh:
    data = json.load(fh)

print("Top-level keys:", list(data.keys()) if isinstance(data, dict) else type(data).__name__)


def walk(obj, path=""):
    """Yield (path, text) tuples for every string we can find."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


targets = ["廷贵", "廷璋", "廷献"]
hits = {t: [] for t in targets}

for path, text in walk(data):
    for t in targets:
        if t in text:
            hits[t].append((path, text))

for t in targets:
    print(f"\n=== {t}  ({len(hits[t])} hits) ===")
    for path, text in hits[t][:10]:
        snippet = text if len(text) <= 80 else text[:80] + "..."
        print(f"  {path}")
        print(f"      -> {snippet}")
