# -*- coding: utf-8 -*-
"""Show which page each of the 廷瑾/廷玉/廷印/廷杰/廷祥/廷奇/廷秀/廷林/廷言/廷珍
appears on, to confirm they are NOT from page 2."""
import json

JSON_PATH = r"C:\Users\alexdu\Downloads\vFlat\家谱\窑湾.json"

with open(JSON_PATH, "r", encoding="utf-8") as fh:
    data = json.load(fh)

names = ["廷瑾", "廷玉", "廷印", "廷杰", "廷祥", "廷奇", "廷秀", "廷林", "廷言", "廷珍"]

results = data["layoutParsingResults"]
print(f"Total pages: {len(results)}")

for n in names:
    print(f"\n{n}:")
    for i, page in enumerate(results):
        try:
            texts = page["prunedResult"]["overall_ocr_res"]["rec_texts"]
        except KeyError:
            continue
        for t in texts:
            if n in t:
                print(f"  page[{i}] -> {t}")
                break
