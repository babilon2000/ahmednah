"""
تشغيل الاستخراج من سطر الأوامر بدون واجهة (مفيد للتجربة السريعة).

مثال:
    python extract_cli.py samples/sample_plan.pdf --scale 100
النتيجة تُحفظ في: output/<اسم الملف>_walls.xlsx
"""

import argparse
from pathlib import Path

from core.pipeline import run
from core.excel_exporter import export_to_excel


def main():
    p = argparse.ArgumentParser(description="ahmednah - استخراج الجدران من PDF")
    p.add_argument("pdf")
    p.add_argument("--scale", type=float, default=100, help="مقياس الرسم (100 يعني 1:100)")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--min", type=float, default=10, help="أقل سماكة جدار بالسم")
    p.add_argument("--max", type=float, default=30, help="أكبر سماكة جدار بالسم")
    p.add_argument("--no-join", action="store_true", help="بدون وصل الزوايا")
    p.add_argument("--keep-origin", action="store_true", help="إبقاء أصل الورقة")
    a = p.parse_args()

    lines, walls, ops, info, offset, meta = run(
        a.pdf, page_number=a.page - 1, scale=a.scale, min_thk=a.min / 100, max_thk=a.max / 100,
        join=not a.no_join, normalize=not a.keep_origin)

    out = Path("output") / (Path(a.pdf).stem + "_walls.xlsx")
    out.parent.mkdir(exist_ok=True)
    export_to_excel(walls, lines, str(out), meta=meta, openings=ops)

    print(f"الخطوط: {len(lines)} | الجدران: {len(walls)}")
    for w in walls:
        print(f"  #{w.wall_id:>3}  ({w.x1:7.2f},{w.y1:7.2f}) → ({w.x2:7.2f},{w.y2:7.2f})"
              f"  L={w.length:6.2f}م  t={w.thickness*100:5.1f}سم")
    print(f"الفتحات: {len(ops)}")
    for o in ops:
        extra = f"  فتح={o.swing_side:+d} مفصلة={o.hinge_at}" if o.kind == "Door" else ""
        print(f"  #{o.opening_id:>3}  {o.kind:<8} جدار {o.host_wall_id}  ({o.x:6.2f},{o.y:6.2f})"
              f"  عرض={o.width:.2f}م{extra}")
    print(f"تم الحفظ: {out}")


if __name__ == "__main__":
    main()
