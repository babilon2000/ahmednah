"""
pdf_extractor.py
----------------
قراءة ملف PDF (مخطط أرضي مصدَّر من AutoCAD) واستخراج كل الخطوط منه.

الفكرة:
- AutoCAD عند التصدير إلى PDF يحوّل الخطوط والـ Polylines إلى "مسارات متجهية" (vector paths).
- PyMuPDF يعطينا هذه المسارات عبر page.get_drawings().
- كل مسار يحتوي عناصر: "l" خط مستقيم، "re" مستطيل، "qu" رباعي، "c" منحنى بيزيه.
- نأخذ الخطوط المستقيمة، ونفكك المستطيلات والرباعيات إلى 4 خطوط.
- المنحنيات (أقواس الأبواب مثلاً) نتجاهلها في هذه المرحلة.

نظام الإحداثيات:
- PDF في PyMuPDF: الأصل أعلى يسار الصفحة، ومحور Y للأسفل، والوحدة "point" (1/72 إنش).
- نحن نحوّل إلى: الأصل أسفل يسار، ومحور Y للأعلى (مثل AutoCAD و Revit)، والوحدة متر حقيقي.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import pymupdf  # PyMuPDF

POINT_TO_MM = 25.4 / 72.0  # 1 point = 0.3528 mm على الورق


@dataclass
class Line:
    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    stroke_width: float  # سماكة الخط المرسوم (بالمتر الحقيقي بعد تطبيق المقياس)
    color: tuple | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def paper_to_real_factor(scale: float) -> float:
    """
    معامل التحويل من point (على الورق) إلى متر (في الواقع).
    مثال: مقياس 1:100 → 1 point = 0.3528 mm ورق = 35.28 mm واقع = 0.03528 m
    """
    return POINT_TO_MM * scale / 1000.0


def _segments_from_drawing(d: dict):
    """يحوّل عناصر مسار واحد إلى قائمة مقاطع ((x1,y1),(x2,y2))."""
    segs = []
    for item in d["items"]:
        kind = item[0]
        if kind == "l":  # خط مستقيم
            p1, p2 = item[1], item[2]
            segs.append(((p1.x, p1.y), (p2.x, p2.y)))
        elif kind == "re":  # مستطيل → 4 أضلاع
            r = item[1]
            c = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
            segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
        elif kind == "qu":  # رباعي (مستطيل مدوّر مثلاً) → 4 أضلاع
            q = item[1]
            c = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
            segs += [(c[i], c[(i + 1) % 4]) for i in range(4)]
        # "c" منحنيات: تُجمع منفصلة في extract_lines (أقواس الأبواب)
    return segs


def extract_lines(
    pdf_path_or_bytes,
    page_number: int = 0,
    scale: float = 100.0,
    min_length_m: float = 0.05,
) -> tuple[list[Line], dict]:
    """
    يستخرج كل الخطوط من صفحة واحدة.

    المعاملات:
        pdf_path_or_bytes : مسار الملف أو محتواه bytes (من Streamlit)
        page_number       : رقم الصفحة (يبدأ من 0)
        scale             : مقياس الرسم، 100 يعني 1:100
        min_length_m      : تجاهل الخطوط الأقصر من هذا الطول (بالمتر) — ضجيج/نصوص/تهشير

    يرجع:
        (قائمة الخطوط, معلومات الصفحة)
    """
    if isinstance(pdf_path_or_bytes, (bytes, bytearray)):
        doc = pymupdf.open(stream=pdf_path_or_bytes, filetype="pdf")
    else:
        doc = pymupdf.open(pdf_path_or_bytes)

    page = doc[page_number]
    page_h = page.rect.height
    k = paper_to_real_factor(scale)

    lines: list[Line] = []
    arcs: list[list[tuple[float, float]]] = []  # منحنيات بيزيه (أقواس الأبواب) — 4 نقاط لكل منحنى
    seen: set = set()

    for d in page.get_drawings():
        width_pt = d.get("width") or 0.0
        color = d.get("color")
        for item in d["items"]:
            if item[0] == "c":
                arcs.append([(round(p.x * k, 4), round((page_h - p.y) * k, 4)) for p in item[1:5]])
        for (ax, ay), (bx, by) in _segments_from_drawing(d):
            # قلب محور Y وتحويل الوحدة إلى متر
            x1, y1 = ax * k, (page_h - ay) * k
            x2, y2 = bx * k, (page_h - by) * k
            length = math.hypot(x2 - x1, y2 - y1)
            if length < min_length_m:
                continue

            # إزالة التكرار (AutoCAD أحياناً يرسم الخط مرتين)
            key = tuple(sorted([(round(x1, 3), round(y1, 3)), (round(x2, 3), round(y2, 3))]))
            if key in seen:
                continue
            seen.add(key)

            lines.append(
                Line(
                    id=len(lines) + 1,
                    x1=round(x1, 4), y1=round(y1, 4),
                    x2=round(x2, 4), y2=round(y2, 4),
                    length=round(length, 4),
                    stroke_width=round(width_pt * k, 5),
                    color=tuple(round(c, 3) for c in color) if color else None,
                )
            )

    info = {
        "pages": len(doc),
        "page_width_m": round(page.rect.width * k, 3),
        "page_height_m": round(page_h * k, 3),
        "factor_m_per_pt": k,
        "arcs": arcs,
    }
    doc.close()
    return lines, info


def render_page_png(pdf_bytes: bytes, page_number: int = 0, zoom: float = 2.0) -> bytes:
    """يحوّل صفحة PDF إلى صورة PNG لعرضها في الواجهة."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[page_number].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    png = pix.tobytes("png")
    doc.close()
    return png
