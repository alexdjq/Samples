# -*- coding: utf-8 -*-
"""Inspect page[1] (the so-called '第2页') table cell_box_list and
text boxes to see why row 4 (十世) content is dropped."""
import json

JSON_PATH = r"C:\Users\alexdu\Downloads\vFlat\家谱\窑湾.json"

with open(JSON_PATH, "r", encoding="utf-8") as fh:
    data = json.load(fh)

page = data["layoutParsingResults"][1]["prunedResult"]
table_res_list = page.get("table_res_list", [])
print(f"Number of detected tables on page[1]: {len(table_res_list)}")

for ti, tres in enumerate(table_res_list):
    cells = tres.get("cell_box_list", [])
    print(f"\nTable[{ti}] has {len(cells)} cells:")
    # Sort by Y center for readability.
    sorted_cells = sorted(enumerate(cells),
                          key=lambda kv: (kv[1][1] + kv[1][3]) / 2.0)
    for idx, b in sorted_cells:
        x1, y1, x2, y2 = b
        h = y2 - y1
        w = x2 - x1
        print(f"  cell[{idx:2d}] x=({x1:4.0f},{x2:4.0f}) "
              f"y=({y1:4.0f},{y2:4.0f}) w={w:4.0f} h={h:4.0f}")
