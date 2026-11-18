"""
openings.py  (المرحلة 3)
-----------------------
من قطع الجدران والشبابيك إلى: جدران مستضيفة (Host Walls) + فتحات (أبواب/شبابيك).

لماذا ندمج؟
  في PDF الجدار الذي فيه باب يظهر كقطعتين بينهما فراغ. لكن في Revit الباب
  والشباك FamilyInstance "مستضاف" داخل جدار، والجدار يجب أن يكون مستمراً
  عبر الفتحة، والعنصر نفسه هو الذي يقصّ الفتحة. لذلك:

  1) نجمع القطع المتسامتة (نفس الاتجاه + نفس خط المحور + نفس السماكة).
  2) نرتبها على المحور، والفراغ بين قطعتين (0.5–2.5 م) = فتحة،
     بشرط ألا يقطع الفراغَ جدارٌ عمودي (وإلا فهو تقاطع وليس فتحة).
  3) التصنيف:
       قطعة نوعها window          ← شباك (Window)
       فراغ بجانبه قوس فتح        ← باب (Door)، ومن القوس نعرف جهة الفتح والمفصلة
       فراغ بدون قوس              ← فتحة فارغة (Opening)
  4) كل سلسلة متصلة تصبح جداراً واحداً من أول قطعة إلى آخر قطعة.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from wall_detector import Wall
from wall_joiner import _intersect


@dataclass
class Opening:
    opening_id: int
    kind: str           # Door / Window / Opening
    host_wall_id: int
    x: float            # مركز الفتحة على محور الجدار
    y: float
    width: float
    wall_thickness: float
    swing_side: int     # للأبواب: +1 يسار اتجاه الجدار (X1→X2)، -1 يمينه، 0 غير معروف
    hinge_at: str       # للأبواب: "start" المفصلة جهة (X1,Y1)، "end" جهة (X2,Y2)، "double" بابان
    leaves: int         # عدد الضلف

    def to_dict(self):
        return asdict(self)


class _Ax:
    """محور قطعة: اتجاه u، عمودي n، بُعد c، وامتداد [t0,t1]."""

    def __init__(self, w: Wall):
        self.w = w
        dx, dy = w.x2 - w.x1, w.y2 - w.y1
        L = math.hypot(dx, dy)
        th = math.atan2(dy, dx) % math.pi
        if th >= math.pi - math.radians(2):
            th -= math.pi
        self.th = th
        self.u = (math.cos(th), math.sin(th))
        self.n = (-self.u[1], self.u[0])
        self.c = self.n[0] * w.x1 + self.n[1] * w.y1
        a = self.u[0] * w.x1 + self.u[1] * w.y1
        b = self.u[0] * w.x2 + self.u[1] * w.y2
        self.t0, self.t1 = min(a, b), max(a, b)

    def point(self, t, c=None):
        c = self.c if c is None else c
        return (self.u[0] * t + self.n[0] * c, self.u[1] * t + self.n[1] * c)


def _gap_blocked(ax: _Ax, c: float, gs: float, ge: float, others: list[_Ax]) -> bool:
    """هل يقطع جدارٌ آخر (غير موازٍ) الفراغ بين gs و ge؟"""
    p1, p2 = ax.point(gs, c), ax.point(ge, c)
    for o in others:
        if abs(math.sin(o.th - ax.th)) < math.sin(math.radians(10)):
            continue
        P = _intersect(p1, p2, (o.w.x1, o.w.y1), (o.w.x2, o.w.y2))
        if P is None:
            continue
        t = ax.u[0] * P[0] + ax.u[1] * P[1]
        to = o.u[0] * P[0] + o.u[1] * P[1]
        if gs + 0.02 < t < ge - 0.02 and o.t0 - 0.02 <= to <= o.t1 + 0.02:
            return True
    return False


def _door_info(ax: _Ax, c: float, gs: float, ge: float, thk: float, arcs):
    """يبحث عن أقواس فتح قرب الفراغ. يرجع (عدد الأقواس, جهة الفتح, المفصلة)."""
    width = ge - gs
    found = []
    for arc in arcs:
        ts = [ax.u[0] * x + ax.u[1] * y for x, y in arc]
        offs = [ax.n[0] * x + ax.n[1] * y - c for x, y in arc]
        tm = sum(ts) / len(ts)
        if not (gs - 0.05 <= tm <= ge + 0.05):
            continue
        if max(abs(o) for o in offs) > width + thk + 0.1:
            continue
        found.append((ts, offs))
    if not found:
        return 0, 0, ""

    side = 1 if sum(sum(o) for _, o in found) > 0 else -1
    if len(found) >= 2:
        return len(found), side, "double"
    ts, offs = found[0]
    # طرف القوس الأبعد عن الجدار = طرف الضلفة المفتوحة، وهو فوق المفصلة
    i_tip = 0 if abs(offs[0]) > abs(offs[-1]) else len(offs) - 1
    t_tip = ts[i_tip]
    hinge_t = gs if abs(t_tip - gs) < abs(t_tip - ge) else ge
    return 1, side, ("start" if hinge_t == gs else "end")  # نسبةً لاتجاه u


def build_hosts_and_openings(segments: list[Wall], arcs, gap_range=(0.5, 2.5),
                             axis_tol=0.03, thk_tol=0.03):
    """
    segments: الجدران (kind=wall) والشبابيك (kind=window) بعد وصل الزوايا
    arcs    : أقواس بيزيه من المخطط
    يرجع (host_walls, openings)
    """
    axes = [_Ax(w) for w in segments]
    walls_only = [a for a in axes if a.w.kind == "wall"]

    # 1) تجميع القطع المتسامتة
    groups: list[list[_Ax]] = []
    for a in sorted(axes, key=lambda a: (round(a.th, 2), a.c)):
        for g in groups:
            r = g[0]
            if (abs(a.th - r.th) <= math.radians(2) and abs(a.c - r.c) <= axis_tol
                    and abs(a.w.thickness - r.w.thickness) <= thk_tol):
                g.append(a)
                break
        else:
            groups.append([a])

    hosts: list[Wall] = []
    openings: list[Opening] = []

    def flush(run, run_openings, ref: _Ax):
        t0 = min(a.t0 for a in run)
        t1 = max(a.t1 for a in run)
        c = sum(a.c * (a.t1 - a.t0) for a in run) / sum(a.t1 - a.t0 for a in run)
        thk = max(a.w.thickness for a in run)
        (x1, y1), (x2, y2) = ref.point(t0, c), ref.point(t1, c)
        hid = len(hosts) + 1
        hosts.append(Wall(hid, round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3),
                          round(t1 - t0, 3), thk, run[0].w.line_a, run[-1].w.line_b))
        # اتجاه الجدار في Excel هو اتجاه u (من t0 إلى t1)، فجهة الفتح والمفصلة كما حسبناهما
        for kind, tc, width, side, hinge, leaves in run_openings:
            px, py = ref.point(tc, c)
            openings.append(Opening(len(openings) + 1, kind, hid, round(px, 3), round(py, 3),
                                    round(width, 3), thk, side, hinge, leaves))

    for g in groups:
        g.sort(key=lambda a: a.t0)
        ref = g[0]
        run, run_ops = [g[0]], []
        if g[0].w.kind == "window":
            run_ops.append(("Window", (g[0].t0 + g[0].t1) / 2, g[0].t1 - g[0].t0, 0, "", 1))
        end = g[0].t1
        for a in g[1:]:
            gap = a.t0 - end
            c = ref.c
            thk = max(x.w.thickness for x in run)
            if gap > gap_range[1] or (gap > 0.05 and _gap_blocked(ref, c, end, a.t0, walls_only)):
                flush(run, run_ops, ref)
                run, run_ops = [a], []
            else:
                if gap >= gap_range[0]:
                    n, side, hinge = _door_info(ref, c, end, a.t0, thk, arcs)
                    kind = "Door" if n else "Opening"
                    run_ops.append((kind, (end + a.t0) / 2, gap, side, hinge, max(n, 1)))
                run.append(a)
            if a.w.kind == "window":
                run_ops.append(("Window", (a.t0 + a.t1) / 2, a.t1 - a.t0, 0, "", 1))
            end = max(end, a.t1)
        flush(run, run_ops, ref)

    return hosts, openings


def shift_openings(openings: list[Opening], offset):
    ox, oy = offset
    for o in openings:
        o.x, o.y = round(o.x - ox, 3), round(o.y - oy, 3)
    return openings
