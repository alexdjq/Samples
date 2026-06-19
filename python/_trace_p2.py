# -*- coding: utf-8 -*-
"""Run the actual filter + grid builder on page[1] cells, then run
build_grid_from_cells and assign_text_to_cells to see what bucket each
OCR fragment ends up in."""
import json
import sys

sys.path.insert(0, r"d:\UGit\Samples\python")

from json_to_word import (
    _filter_main_table_cells,
    build_grid_from_cells,
    assign_text_to_cells,
)

JSON_PATH = r"C:\Users\alexdu\Downloads\vFlat\家谱\窑湾.json"

with open(JSON_PATH, "r", encoding="utf-8") as fh:
    data = json.load(fh)

page = data["layoutParsingResults"][1]["prunedResult"]
ocr = page["overall_ocr_res"]
t_texts = ocr["rec_texts"]
t_boxes_raw = ocr["rec_boxes"]
t_boxes = [tuple(b) for b in t_boxes_raw]

table_res = page["table_res_list"][0]
cell_box_list = [tuple(b) for b in table_res["cell_box_list"]]

print(f"Original cells: {len(cell_box_list)}")
filtered = _filter_main_table_cells(cell_box_list)
print(f"After filter:   {len(filtered)}")

print("\nFiltered cells (sorted by Y):")
for i, b in enumerate(sorted(filtered, key=lambda b: (b[1] + b[3]) / 2)):
    x1, y1, x2, y2 = b
    print(f"  cell[{i:2d}] x=({x1:4.0f},{x2:4.0f}) y=({y1:4.0f},{y2:4.0f}) "
          f"w={x2-x1:4.0f} h={y2-y1:4.0f}")

grid = build_grid_from_cells(filtered)
print(f"\nGrid: {len(grid)} rows")
for ri, row in enumerate(grid):
    print(f"  row[{ri}]: {len(row)} cells:")
    for ci, b in enumerate(row):
        x1, y1, x2, y2 = b
        print(f"    [{ci}] x=({x1:4.0f},{x2:4.0f}) y=({y1:4.0f},{y2:4.0f})")

bucket = assign_text_to_cells(grid, t_boxes, t_texts)
print(f"\nBucket dimensions: {len(bucket)} rows")
for r in range(len(bucket)):
    for c in range(len(bucket[r])):
        idxs = bucket[r][c]
        if idxs:
            preview = " | ".join(t_texts[i][:8] for i in idxs[:6])
            print(f"  [{r}][{c}] -> {len(idxs)} texts: {preview}")
