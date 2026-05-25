# -*- coding: utf-8 -*-
"""
Convert PaddlePaddle PP-StructureV3 JSON output into a Word (.docx) file.

The script reads the JSON produced by PP-StructureV3 (which contains layout
information, table cell bounding boxes and OCR text boxes) and reconstructs
the table(s) into a Word document by mapping each recognized text box to the
table cell whose bounding box contains it.

Usage:
    python json_to_word.py <input_json> [output_docx]

Dependencies:
    pip install python-docx
"""

from __future__ import annotations

import json
import os
import sys
from typing import List, Tuple, Dict, Any, Optional

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.table import WD_ALIGN_VERTICAL
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("Missing dependency 'python-docx'. Please install it via:")
    print("    pip install python-docx")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

Box = Tuple[float, float, float, float]  # (x1, y1, x2, y2)


def box_center(box: Box) -> Tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def point_in_box(px: float, py: float, box: Box, tol: float = 2.0) -> bool:
    x1, y1, x2, y2 = box
    return (x1 - tol) <= px <= (x2 + tol) and (y1 - tol) <= py <= (y2 + tol)


def box_overlap_area(a: Box, b: Box) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    return inter_w * inter_h


# ---------------------------------------------------------------------------
# Cell grid reconstruction
# ---------------------------------------------------------------------------

def build_grid_from_cells(cell_boxes: List[Box]) -> List[List[Box]]:
    """Group cell boxes into a 2D grid.

    Cluster cells by Y center to obtain rows, sort cells inside each row
    by X center to obtain columns, then return ``grid[row][col] -> box``.
    """
    if not cell_boxes:
        return []

    centers = [box_center(b) for b in cell_boxes]
    heights = [b[3] - b[1] for b in cell_boxes]
    avg_h = sum(heights) / len(heights)
    row_tol = max(avg_h * 0.4, 5.0)

    indexed = sorted(range(len(cell_boxes)), key=lambda i: centers[i][1])
    rows: List[List[int]] = []
    for i in indexed:
        cy = centers[i][1]
        placed = False
        for row in rows:
            row_cy = sum(centers[j][1] for j in row) / len(row)
            if abs(cy - row_cy) <= row_tol:
                row.append(i)
                placed = True
                break
        if not placed:
            rows.append([i])

    rows.sort(key=lambda r: sum(centers[j][1] for j in r) / len(r))
    for row in rows:
        row.sort(key=lambda j: centers[j][0])

    grid: List[List[Box]] = [[cell_boxes[j] for j in row] for row in rows]
    return grid


def assign_text_to_cells(
    grid: List[List[Box]],
    text_boxes: List[Box],
    texts: List[str],
) -> List[List[List[int]]]:
    """Assign indices of text fragments to the matching cell of ``grid``.

    Returns a 2D list ``bucket[row][col] -> [frag_idx, ...]``.
    """
    rows = len(grid)
    cols = max((len(r) for r in grid), default=0)
    bucket: List[List[List[int]]] = [
        [[] for _ in range(cols)] for _ in range(rows)
    ]

    for idx, (tb, txt) in enumerate(zip(text_boxes, texts)):
        if not txt or not txt.strip():
            continue
        cx, cy = box_center(tb)

        best = (-1, -1)
        best_score = -1.0
        for r_idx, row in enumerate(grid):
            for c_idx, cell in enumerate(row):
                if point_in_box(cx, cy, cell):
                    score = box_overlap_area(tb, cell) + 1e6
                else:
                    score = box_overlap_area(tb, cell)
                if score > best_score:
                    best_score = score
                    best = (r_idx, c_idx)

        if best_score <= 0:
            min_dist = float("inf")
            for r_idx, row in enumerate(grid):
                for c_idx, cell in enumerate(row):
                    ccx, ccy = box_center(cell)
                    d = (ccx - cx) ** 2 + (ccy - cy) ** 2
                    if d < min_dist:
                        min_dist = d
                        best = (r_idx, c_idx)

        r_idx, c_idx = best
        if 0 <= r_idx < rows and 0 <= c_idx < cols:
            bucket[r_idx][c_idx].append(idx)

    return bucket


# ---------------------------------------------------------------------------
# Vertical-Chinese cell content splitting
# ---------------------------------------------------------------------------

def split_into_vertical_lines(
    frag_indices: List[int],
    text_boxes: List[Box],
    texts: List[str],
) -> List[str]:
    """Split fragments inside a wide cell into reading lines.

    The PP-Structure OCR returns each piece of vertically-written Chinese
    text as a tall narrow box (height >> width).  Lines (i.e. "columns of
    glyphs" as printed in the original document) are then identified by
    grouping fragments whose horizontal centers are close enough.  Within
    one line, fragments are concatenated top-to-bottom.  Lines themselves
    are emitted right-to-left, which is the natural reading order for
    traditional vertical Chinese text.
    """
    if not frag_indices:
        return []

    items: List[Tuple[float, float, float, float, str]] = []
    widths: List[float] = []
    for idx in frag_indices:
        x1, y1, x2, y2 = text_boxes[idx]
        items.append((x1, y1, x2, y2, texts[idx]))
        widths.append(x2 - x1)

    if not items:
        return []

    widths.sort()
    median_w = widths[len(widths) // 2]
    col_tol = max(median_w * 0.7, 8.0)

    # Sort by x descending (right-to-left).
    items.sort(key=lambda t: -((t[0] + t[2]) / 2.0))

    columns: List[List[Tuple[float, float, float, float, str]]] = []
    for it in items:
        cx = (it[0] + it[2]) / 2.0
        placed = False
        for col in columns:
            col_cx = sum((c[0] + c[2]) / 2.0 for c in col) / len(col)
            if abs(cx - col_cx) <= col_tol:
                col.append(it)
                placed = True
                break
        if not placed:
            columns.append([it])

    # Right-to-left ordering of columns.
    columns.sort(key=lambda col: -sum((c[0] + c[2]) / 2.0 for c in col) / len(col))

    lines: List[str] = []
    for col in columns:
        col.sort(key=lambda c: c[1])  # top-to-bottom
        lines.append("".join(c[4] for c in col))
    return lines


# ---------------------------------------------------------------------------
# Word document helpers
# ---------------------------------------------------------------------------

def _set_run_chinese_font(run, font_name: str = "SimSun") -> None:
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font_name)


def set_cell_text(cell, text: str, bold: bool = False) -> None:
    """Write ``text`` into a docx cell, preserving newlines as paragraphs."""
    cell.text = ""
    paragraphs = text.split("\n") if text else [""]
    first = True
    for line in paragraphs:
        if first:
            p = cell.paragraphs[0]
            first = False
        else:
            p = cell.add_paragraph()
        run = p.add_run(line)
        run.font.size = Pt(10)
        run.font.name = "SimSun"
        run.bold = bold
        _set_run_chinese_font(run, "SimSun")
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

def _split_cell_into_person_lines(
    frag_indices: List[int],
    t_boxes: List[Box],
    t_texts: List[str],
) -> List[Tuple[float, str]]:
    """Split a wide cell into "person columns".

    Returns a list of ``(x_center, text)`` tuples, one per detected
    vertical text column inside the cell.  The text is the top-to-bottom
    concatenation of all fragments that belong to the same X cluster.
    The list is **not** pre-sorted; the caller decides the final order.
    """
    if not frag_indices:
        return []

    items: List[Tuple[float, float, float, float, str]] = []
    widths: List[float] = []
    for idx in frag_indices:
        x1, y1, x2, y2 = t_boxes[idx]
        items.append((x1, y1, x2, y2, t_texts[idx]))
        widths.append(x2 - x1)

    widths.sort()
    median_w = widths[len(widths) // 2]
    col_tol = max(median_w * 0.7, 8.0)

    # Group fragments by X center.
    items.sort(key=lambda t: (t[0] + t[2]) / 2.0)
    groups: List[List[Tuple[float, float, float, float, str]]] = []
    for it in items:
        cx = (it[0] + it[2]) / 2.0
        placed = False
        for g in groups:
            g_cx = sum((c[0] + c[2]) / 2.0 for c in g) / len(g)
            if abs(cx - g_cx) <= col_tol:
                g.append(it)
                placed = True
                break
        if not placed:
            groups.append([it])

    out: List[Tuple[float, str]] = []
    for g in groups:
        g.sort(key=lambda c: c[1])  # top-to-bottom
        text = "".join(c[4] for c in g)
        x_center = sum((c[0] + c[2]) / 2.0 for c in g) / len(g)
        out.append((x_center, text))
    return out


def _cluster_x_anchors(
    x_values: List[float], tol: float
) -> List[float]:
    """Cluster x values into anchor points (sorted descending)."""
    if not x_values:
        return []
    sorted_x = sorted(x_values)
    clusters: List[List[float]] = [[sorted_x[0]]]
    for x in sorted_x[1:]:
        if abs(x - clusters[-1][-1]) <= tol:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    anchors = [sum(c) / len(c) for c in clusters]
    anchors.sort(reverse=True)  # right -> left
    return anchors


def render_table(
    doc: Document,
    cell_box_list: List[Box],
    t_texts: List[str],
    t_boxes: List[Box],
) -> bool:
    """Render one detected table to ``doc``.

    Two layouts are supported:

    * **Genealogy (rotated) layout** — one narrow header column (e.g.
      "十六世~二十世") plus one wide content column per generation, with
      vertically written, right-to-left Chinese text.  The renderer:
        1. Treats each image-row as one **generation**.
        2. Splits the wide content cell into per-person vertical lines.
        3. Clusters those lines' X centers across **all** generations to
           form a global set of person-column anchors.
        4. Builds a Word table whose **rows are generations** ordered
           top-to-bottom (十六世 at the top), and whose **columns are
           aligned person columns** ordered left-to-right by image X.
           The generation label sits in the **rightmost** column,
           matching the original document layout.
    * **Generic grid** — falls back to a simple row x col rendering.
    """
    grid = build_grid_from_cells(cell_box_list)
    if not grid:
        return False

    bucket = assign_text_to_cells(grid, t_boxes, t_texts)

    rows = len(grid)
    cols = max(len(r) for r in grid)

    # ---- Detect "header column" layout (one column much narrower) -------
    transposed_layout = False
    header_col_idx: Optional[int] = None
    if cols >= 2:
        col_widths: List[float] = []
        for c in range(cols):
            ws = [grid[r][c][2] - grid[r][c][0] for r in range(rows) if c < len(grid[r])]
            col_widths.append(sum(ws) / len(ws) if ws else 0.0)
        max_w = max(col_widths)
        min_w = min(col_widths)
        if max_w > 0 and min_w / max_w < 0.25:
            header_col_idx = col_widths.index(min_w)
            transposed_layout = True

    if transposed_layout and header_col_idx is not None:
        # 1. Per generation: header label + list of (x_center, text).
        gen_count = rows
        header_labels: List[str] = []
        person_lists: List[List[Tuple[float, str]]] = []

        for r in range(gen_count):
            head_indices = bucket[r][header_col_idx] if header_col_idx < len(bucket[r]) else []
            head_lines = split_into_vertical_lines(head_indices, t_boxes, t_texts)
            header_labels.append("\n".join(head_lines).strip())

            persons: List[Tuple[float, str]] = []
            for c in range(cols):
                if c == header_col_idx:
                    continue
                if c < len(bucket[r]):
                    persons.extend(
                        _split_cell_into_person_lines(bucket[r][c], t_boxes, t_texts)
                    )
            person_lists.append(persons)

        # 2. Build global X anchors across all generations.
        all_x = [x for plist in person_lists for x, _ in plist]
        if not all_x:
            return False

        # Estimate tolerance from the *minimum non-zero* gap between
        # neighbouring person-column X centers across all generations.
        # The original document uses a fixed character pitch, so genuinely
        # different person-columns are separated by roughly one character
        # width.  Using half of that as the clustering tolerance makes the
        # algorithm robust to small OCR jitter while still keeping
        # neighbouring person columns distinct.
        widths_all = [t_boxes[i][2] - t_boxes[i][0] for i in range(len(t_boxes))]
        widths_all.sort()
        median_w = widths_all[len(widths_all) // 2] if widths_all else 30.0
        anchor_tol = max(median_w * 0.45, 10.0)
        anchors = _cluster_x_anchors(all_x, anchor_tol)  # right -> left

        # 3. Word table layout (transposed):
        #    - rows         = generations (one row per 世), ordered
        #                     top-to-bottom 十六世 -> 二十世 (i.e. by
        #                     image Y ascending).
        #    - cols 0..N-1  = person columns aligned to global anchors,
        #                     ordered left-to-right (= image X ascending).
        #                     This mirrors the original document where the
        #                     leftmost person column in the image becomes
        #                     the leftmost column in the Word table.
        #    - col   N      = generation label (header column on the
        #                     **right** side, matching the original
        #                     document layout).
        gen_order = sorted(
            range(gen_count),
            key=lambda r: (grid[r][0][1] + grid[r][0][3]) / 2.0,
        )

        # 4. For each generation, assign every (x, text) to the closest
        #    anchor index. ``anchors`` is sorted right-to-left (X
        #    descending), so to lay them out left-to-right in the Word
        #    table we map anchor index ``a_idx`` to Word column
        #    ``(n_anchor_cols - 1) - a_idx``.
        def _anchor_index(x: float) -> int:
            best_idx = 0
            best_d = float("inf")
            for i, a in enumerate(anchors):
                d = abs(x - a)
                if d < best_d:
                    best_d = d
                    best_idx = i
            return best_idx

        n_anchor_cols = len(anchors)
        word_rows = len(gen_order)
        word_cols = n_anchor_cols + 1  # anchor columns + trailing header
        header_col = n_anchor_cols      # rightmost column
        cell_text: List[List[str]] = [
            ["" for _ in range(word_cols)] for _ in range(word_rows)
        ]

        for w_row, g_idx in enumerate(gen_order):
            # Generation label goes into the rightmost column.
            cell_text[w_row][header_col] = header_labels[g_idx]

            # Sort persons by X ascending so that, when multiple persons
            # collapse onto the same anchor column, the leftmost one is
            # appended first (matching left-to-right reading).
            persons_sorted = sorted(person_lists[g_idx], key=lambda t: t[0])
            for x, text in persons_sorted:
                a_idx = _anchor_index(x)
                col = (n_anchor_cols - 1) - a_idx
                if cell_text[w_row][col]:
                    cell_text[w_row][col] += "\n" + text
                else:
                    cell_text[w_row][col] = text

        # 5. Render the Word table.
        word_table = doc.add_table(rows=word_rows, cols=word_cols)
        word_table.style = "Table Grid"
        for r_idx in range(word_rows):
            for c_idx in range(word_cols):
                set_cell_text(
                    word_table.cell(r_idx, c_idx),
                    cell_text[r_idx][c_idx],
                    bold=(c_idx == header_col),
                )
        doc.add_paragraph("")
        return True

    # ---- Fallback: generic grid rendering -------------------------------
    word_table = doc.add_table(rows=rows, cols=cols)
    word_table.style = "Table Grid"
    for r_idx in range(rows):
        for c_idx in range(cols):
            indices = bucket[r_idx][c_idx] if c_idx < len(bucket[r_idx]) else []
            lines = split_into_vertical_lines(indices, t_boxes, t_texts)
            set_cell_text(word_table.cell(r_idx, c_idx), "\n".join(lines))
    doc.add_paragraph("")
    return True


# ---------------------------------------------------------------------------
# Document building
# ---------------------------------------------------------------------------

def build_docx(parsing_results: List[Dict[str, Any]], output_path: str) -> None:
    """Build a Word document from the parsed JSON results."""
    doc = Document()
    doc.add_heading("PP-StructureV3 Recovered Document", level=1)

    table_index = 0
    for page_idx, page in enumerate(parsing_results):
        pruned = page.get("prunedResult", page)
        parsing_list = pruned.get("parsing_res_list", [])
        table_res_list = pruned.get("table_res_list", [])

        # ``overall_ocr_res`` uses the same global image coordinates as
        # ``cell_box_list``; ``table_ocr_pred`` may use a different (often
        # rotated) local coordinate system, so we prefer the overall result.
        overall = pruned.get("overall_ocr_res", {})
        overall_texts: List[str] = list(overall.get("rec_texts", []))
        overall_boxes: List[Box] = [tuple(b) for b in overall.get("rec_boxes", [])]

        for block in parsing_list:
            label = block.get("block_label", "")
            if label == "table":
                if table_index >= len(table_res_list):
                    doc.add_paragraph(block.get("block_content", ""))
                    continue

                tres = table_res_list[table_index]
                table_index += 1

                cell_box_list = [tuple(b) for b in tres.get("cell_box_list", [])]

                # Filter overall OCR boxes to those overlapping this table
                # region (defined by the union of its cell boxes).
                if cell_box_list:
                    tx1 = min(b[0] for b in cell_box_list)
                    ty1 = min(b[1] for b in cell_box_list)
                    tx2 = max(b[2] for b in cell_box_list)
                    ty2 = max(b[3] for b in cell_box_list)
                    table_region: Box = (tx1, ty1, tx2, ty2)
                else:
                    table_region = (0.0, 0.0, 0.0, 0.0)

                t_texts: List[str] = []
                t_boxes: List[Box] = []
                for txt, bx in zip(overall_texts, overall_boxes):
                    if box_overlap_area(bx, table_region) > 0:
                        t_texts.append(txt)
                        t_boxes.append(bx)

                if not render_table(doc, cell_box_list, t_texts, t_boxes):
                    doc.add_paragraph(block.get("block_content", ""))
            elif label in ("text", "title", "paragraph_title", "doc_title"):
                content = block.get("block_content", "").strip()
                if content:
                    if label.endswith("title"):
                        doc.add_heading(content, level=2)
                    else:
                        doc.add_paragraph(content)
            elif label == "image":
                continue
            else:
                content = block.get("block_content", "").strip()
                if content:
                    doc.add_paragraph(content)

        if page_idx < len(parsing_results) - 1:
            doc.add_page_break()

    doc.save(output_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    input_path = argv[1]
    if len(argv) >= 3:
        output_path = argv[2]
    else:
        base, _ = os.path.splitext(input_path)
        output_path = base + ".docx"

    if not os.path.isfile(input_path):
        print(f"Input file not found: {input_path}")
        return 2

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]

    build_docx(data, output_path)
    print(f"Word document generated: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
