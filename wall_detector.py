"""
wall_detector.py
----------------
تمييز الجدران من الخطوط المستخرجة.

القاعدة: أي خطين
  1) متوازيين (فرق الزاوية أقل من angle_tol درجة)
  2) المسافة العمودية بينهما بين min_thk و max_thk (افتراضياً 10–30 سم)
  3) متداخلين في الطول (إسقاط أحدهما على الآخر يعطي جزءاً مشتركاً كافياً)
يُعتبران وجهَي جدار واحد.

الجدار الناتج:
  - خط المحور (Centerline) في منتصف المسافة بين الخطين، على طول الجزء المشترك فقط
  - السماكة = المسافة العمودية بين الخطين
خط المحور هو بالضبط ما سنحتاجه في Revit (Wall.ByCurveAndHeight) في المرحلة الثانية.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from dataclasses import dataclass, asdict

from pdf_extractor import Line


@dataclass
class Wall:
    wall_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    thickness: float
    line_a: int  # رقم الخط الأول المكوِّن للجدار
    line_b: int  # رقم الخط الثاني
    kind: str = "wall"  # "wall" أو "window" (المرحلة 3)

    def to_dict(self) -> dict:
        return asdict(self)


class _Seg:
    """خط مع خصائصه الهندسية الجاهزة للحساب."""

    def __init__(self, ln: Line, angle_tol: float):
        self.ln = ln
        dx, dy = ln.x2 - ln.x1, ln.y2 - ln.y1
        L = math.hypot(dx, dy)
        theta = math.degrees(math.atan2(dy, dx)) % 180.0
        # الخطوط الأفقية قد تأتي بزاوية 0.01 أو 179.99 → نوحّدها حول الصفر
        if theta >= 180.0 - angle_tol:
            theta -= 180.0
        self.theta = theta
        t = math.radians(theta)
        self.u = (math.cos(t), math.sin(t))   # اتجاه الخط
        self.n = (-math.sin(t), math.cos(t))  # العمودي عليه
        self.offset = self.n[0] * ln.x1 + self.n[1] * ln.y1  # بُعد الخط عن الأصل
        a = self.u[0] * ln.x1 + self.u[1] * ln.y1
        b = self.u[0] * ln.x2 + self.u[1] * ln.y2
        self.t0, self.t1 = min(a, b), max(a, b)  # امتداد الخط على محوره
        self.length = L
        self.used: list[tuple[float, float]] = []  # أجزاء استُخدمت في جدران سابقة

    def used_fraction(self, s: float, e: float) -> float:
        """نسبة الفترة [s,e] المستخدمة مسبقاً في جدار آخر."""
        if e <= s:
            return 1.0
        covered = 0.0
        for a, b in self.used:
            covered += max(0.0, min(b, e) - max(a, s))
        return min(1.0, covered / (e - s))


def detect_walls(
    lines: list[Line],
    min_thk: float = 0.10,
    max_thk: float = 0.30,
    angle_tol: float = 2.0,
    min_overlap: float = 0.20,
    min_line_length: float = 0.20,
    detect_windows: bool = True,
    window_len: tuple[float, float] = (0.40, 3.00),
) -> list[Wall]:
    """
    يرجع الجدران، ومعها الشبابيك بـ kind="window".

    الشباك في مخططات AutoCAD = خطان على وجهي الجدار + خط زجاج أو أكثر بينهما
    بنفس الطول تقريباً. لو لم نكتشفه أولاً، سيقترن خط الزجاج مع وجه الجدار
    ويظهر كجدار رفيع وهمي. لذلك نكتشف الشبابيك في جولة أولى ونحجز خطوطها.

    المعاملات (كلها بالمتر ما عدا الزاوية):
        min_thk, max_thk : حدود سماكة الجدار
        angle_tol        : السماحية في التوازي (درجات)
        min_overlap      : أقل طول مشترك بين الخطين ليُعتبرا جداراً
        min_line_length  : تجاهل الخطوط القصيرة جداً (رموز، تهشير، نصوص)
    """
    segs = [_Seg(l, angle_tol) for l in lines if l.length >= min_line_length]

    # 1) تجميع الخطوط حسب الزاوية (كل درجة سلة) لتسريع البحث
    buckets: dict[int, list[_Seg]] = defaultdict(list)
    for s in segs:
        buckets[int(math.floor(s.theta))].append(s)
    for b in buckets.values():
        b.sort(key=lambda s: s.offset)

    # 2) إيجاد كل الأزواج المرشحة
    candidates = []
    span = int(math.ceil(angle_tol))
    for A in segs:
        base = int(math.floor(A.theta))
        for k in range(base - span, base + span + 1):
            group = buckets.get(k)
            if not group:
                continue
            offsets = [g.offset for g in group]
            # نبحث فقط عن الخطوط التي offset تبعها أكبر (لتجنب تكرار الزوج)
            lo = bisect.bisect_left(offsets, A.offset + min_thk * 0.5)
            hi = bisect.bisect_right(offsets, A.offset + max_thk * 1.5)
            for B in group[lo:hi]:
                if B is A or abs(B.theta - A.theta) > angle_tol:
                    continue
                # المسافة العمودية الحقيقية: من منتصف B إلى امتداد A
                mx = (B.ln.x1 + B.ln.x2) / 2
                my = (B.ln.y1 + B.ln.y2) / 2
                d = abs(A.n[0] * mx + A.n[1] * my - A.offset)
                if not (min_thk - 1e-6 <= d <= max_thk + 1e-6):
                    continue
                # التداخل: نسقط B على محور A
                b0 = A.u[0] * B.ln.x1 + A.u[1] * B.ln.y1
                b1 = A.u[0] * B.ln.x2 + A.u[1] * B.ln.y2
                s, e = max(A.t0, min(b0, b1)), min(A.t1, max(b0, b1))
                if e - s < min_overlap:
                    continue
                candidates.append((d, -(e - s), A, B, s, e))

    walls: list[Wall] = []

    def project_on_b(A, B, s, e):
        pA_s = (A.u[0] * s + A.n[0] * A.offset, A.u[1] * s + A.n[1] * A.offset)
        pA_e = (A.u[0] * e + A.n[0] * A.offset, A.u[1] * e + A.n[1] * A.offset)
        tb_s = B.u[0] * pA_s[0] + B.u[1] * pA_s[1]
        tb_e = B.u[0] * pA_e[0] + B.u[1] * pA_e[1]
        return pA_s, pA_e, min(tb_s, tb_e), max(tb_s, tb_e)

    def make(A, B, d, s, e, pA_s, pA_e, kind):
        mx = (B.ln.x1 + B.ln.x2) / 2
        my = (B.ln.y1 + B.ln.y2) / 2
        side = 1.0 if (A.n[0] * mx + A.n[1] * my - A.offset) > 0 else -1.0
        h = side * d / 2
        return Wall(
            wall_id=len(walls) + 1,
            x1=round(pA_s[0] + A.n[0] * h, 3), y1=round(pA_s[1] + A.n[1] * h, 3),
            x2=round(pA_e[0] + A.n[0] * h, 3), y2=round(pA_e[1] + A.n[1] * h, 3),
            length=round(e - s, 3), thickness=round(d, 3),
            line_a=A.ln.id, line_b=B.ln.id, kind=kind,
        )

    # 3) الشبابيك أولاً: زوج متوازي وبينه خط (أو أكثر) يغطي معظم طوله
    if detect_windows:
        for d, _, A, B, s, e in sorted(candidates, key=lambda c: -c[0]):
            if not (window_len[0] <= e - s <= window_len[1]):
                continue
            if A.used_fraction(s, e) > 0.1:
                continue
            inner = []
            for k in range(int(math.floor(A.theta)) - span, int(math.floor(A.theta)) + span + 1):
                for C in buckets.get(k, []):
                    if C is A or C is B or abs(C.theta - A.theta) > angle_tol:
                        continue
                    mx, my = (C.ln.x1 + C.ln.x2) / 2, (C.ln.y1 + C.ln.y2) / 2
                    off = A.n[0] * mx + A.n[1] * my - A.offset
                    if not (0.01 < abs(off) < d - 0.01):
                        continue
                    c0 = A.u[0] * C.ln.x1 + A.u[1] * C.ln.y1
                    c1 = A.u[0] * C.ln.x2 + A.u[1] * C.ln.y2
                    ov = min(e, max(c0, c1)) - max(s, min(c0, c1))
                    if ov >= 0.7 * (e - s):
                        inner.append(C)
            if not inner:
                continue
            pA_s, pA_e, bs, be = project_on_b(A, B, s, e)
            if B.used_fraction(bs, be) > 0.1:
                continue
            A.used.append((s, e))
            B.used.append((bs, be))
            for C in inner:  # خطوط الزجاج محجوزة بالكامل
                C.used.append((C.t0 - 1, C.t1 + 1))
            walls.append(make(A, B, d, s, e, pA_s, pA_e, "window"))

    # 4) الجدران: الأقرب أولاً، ثم الأطول تداخلاً.
    #    كل جزء من الخط يُستخدم مرة واحدة فقط (الخط الطويل الخارجي يمكن أن
    #    يشكّل عدة جدران مع عدة خطوط داخلية قصيرة بسبب فتحات الأبواب).
    candidates.sort(key=lambda c: (round(c[0], 3), c[1]))
    for d, _, A, B, s, e in candidates:
        pA_s, pA_e, bs, be = project_on_b(A, B, s, e)
        if A.used_fraction(s, e) > 0.5 or B.used_fraction(bs, be) > 0.5:
            continue
        A.used.append((s, e))
        B.used.append((bs, be))
        walls.append(make(A, B, d, s, e, pA_s, pA_e, "wall"))
    return walls
