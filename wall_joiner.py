"""
wall_joiner.py
--------------
تنظيف الجدران قبل إرسالها إلى Revit:

1) وصل الزوايا (L) والتقاطعات (T):
   خط المحور الناتج من wall_detector يقف عند الوجه الداخلي للجدار المجاور،
   فيبقى فراغ عند كل زاوية. هنا نمدّ (أو نقص) طرف كل جدار حتى يلتقي
   بمحور الجدار العمودي عليه. Revit بعدها يصنع الـ Join تلقائياً.

2) نقل الأصل: نجعل أسفل يسار المبنى هو النقطة (0,0) بدل زاوية الورقة.
"""

from __future__ import annotations

import math

from wall_detector import Wall


def _intersect(p1, p2, p3, p4):
    """تقاطع المستقيمين اللانهائيين (p1p2) و (p3p4). يرجع None إذا كانا متوازيين."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (p4[0] - p3[0], p4[1] - p3[1])
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    n1, n2 = math.hypot(*d1), math.hypot(*d2)
    if n1 == 0 or n2 == 0 or abs(cross) / (n1 * n2) < math.sin(math.radians(10)):
        return None
    t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / cross
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def _param_on(seg_a, seg_b, p):
    """موقع النقطة p على امتداد القطعة (a→b) بالمتر: 0 عند a و L عند b."""
    dx, dy = seg_b[0] - seg_a[0], seg_b[1] - seg_a[1]
    L = math.hypot(dx, dy)
    return ((p[0] - seg_a[0]) * dx + (p[1] - seg_a[1]) * dy) / L, L


def join_walls(walls: list[Wall]) -> list[Wall]:
    pts = [[(w.x1, w.y1), (w.x2, w.y2)] for w in walls]
    orig = [list(p) for p in pts]  # المستقيمات اللانهائية لا تتغير بتحريك الأطراف

    for i, wi in enumerate(walls):
        for end in (0, 1):
            e = orig[i][end]
            best, best_d = None, None
            for j, wj in enumerate(walls):
                if i == j:
                    continue
                P = _intersect(orig[i][0], orig[i][1], orig[j][0], orig[j][1])
                if P is None:
                    continue
                tol = max(wi.thickness, wj.thickness) * 0.75 + 0.02
                d = math.hypot(P[0] - e[0], P[1] - e[1])
                if d > tol:
                    continue
                s, Lj = _param_on(orig[j][0], orig[j][1], P)
                if s < -tol or s > Lj + tol:
                    continue
                if best_d is None or d < best_d:
                    best, best_d = P, d
            if best is not None:
                pts[i][end] = best

    out = []
    for w, ((x1, y1), (x2, y2)) in zip(walls, pts):
        out.append(Wall(w.wall_id, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3),
                        round(math.hypot(x2 - x1, y2 - y1), 3), w.thickness, w.line_a, w.line_b))
    return out


def normalize_origin(walls: list[Wall]) -> tuple[list[Wall], tuple[float, float]]:
    """يزيح كل الجدران بحيث يصبح أسفل يسار المبنى (0,0). يرجع الإزاحة لاستخدامها لاحقاً (الأبواب)."""
    if not walls:
        return walls, (0.0, 0.0)
    ox = min(min(w.x1, w.x2) for w in walls)
    oy = min(min(w.y1, w.y2) for w in walls)
    out = [Wall(w.wall_id, round(w.x1 - ox, 3), round(w.y1 - oy, 3), round(w.x2 - ox, 3),
                round(w.y2 - oy, 3), w.length, w.thickness, w.line_a, w.line_b) for w in walls]
    return out, (round(ox, 4), round(oy, 4))
