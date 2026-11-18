"""
pipeline.py
-----------
المسار الكامل في دالة واحدة، تستخدمها الواجهة وسطر الأوامر معاً:
PDF → خطوط + أقواس → جدران + شبابيك → وصل الزوايا → دمج الجدران المستضيفة + الفتحات → نقل الأصل
"""

from __future__ import annotations

from pdf_extractor import extract_lines
from wall_detector import detect_walls
from wall_joiner import join_walls, normalize_origin
from openings import build_hosts_and_openings, shift_openings


def run(pdf, page_number=0, scale=100.0, min_thk=0.10, max_thk=0.30, angle_tol=2.0,
        min_overlap=0.20, min_line_length=0.20, join=True, normalize=True, openings=True):
    lines, info = extract_lines(pdf, page_number=page_number, scale=scale, min_length_m=0.01)
    segs = detect_walls(lines, min_thk=min_thk, max_thk=max_thk, angle_tol=angle_tol,
                        min_overlap=min_overlap, min_line_length=min_line_length,
                        detect_windows=openings)
    walls = [w for w in segs if w.kind == "wall"]
    windows = [w for w in segs if w.kind == "window"]

    if join:
        walls = join_walls(walls)

    ops = []
    if openings:
        walls, ops = build_hosts_and_openings(walls + windows, info["arcs"])

    offset = (0.0, 0.0)
    if normalize:
        walls, offset = normalize_origin(walls)
        shift_openings(ops, offset)

    meta = {"scale": f"1:{scale:g}", "page": page_number + 1,
            "origin_offset_x": offset[0], "origin_offset_y": offset[1],
            "corners_joined": join}
    return lines, walls, ops, info, offset, meta
