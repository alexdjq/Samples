# -*- coding: utf-8 -*-
"""Dump all rec_texts + boxes for page 2 (layoutParsingResults[1])."""
import json

JSON_PATH = r"C:\Users\alexdu\Downloads\vFlat\家谱\窑湾.json"

with open(JSON_PATH, "r", encoding="utf-8") as fh:
    data = json.load(fh)

page = data["layoutParsingResults"][1]["prunedResult"]
ocr = page["overall_ocr_res"]
texts = ocr["rec_texts"]
boxes = ocr.get("rec_boxes") or ocr.get("dt_polys") or []

print(f"Total rec_texts on page 2: {len(texts)}")
print(f"Total rec_boxes on page 2: {len(boxes)}")
print()
print("idx | x1   y1   x2   y2  | text")
print("----|--------------------|----")
for i, t in enumerate(texts):
    if i < len(boxes):
        b = boxes[i]
        if isinstance(b, list) and len(b) == 4:
            x1, y1, x2, y2 = b
        elif isinstance(b, list) and len(b) >= 4 and isinstance(b[0], list):
            xs = [p[0] for p in b]
            ys = [p[1] for p in b]
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        else:
            x1 = y1 = x2 = y2 = -1
    else:
        x1 = y1 = x2 = y2 = -1
    print(f"{i:3d} | {x1:4.0f} {y1:4.0f} {x2:4.0f} {y2:4.0f} | {t}")
