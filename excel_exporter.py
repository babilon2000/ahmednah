"""
excel_exporter.py
-----------------
حفظ الجدران (والخطوط الخام للمراجعة) في ملف Excel.
الورقة الأولى "Walls" هي التي سيقرأها Dynamo في المرحلة الثانية،
لذلك أسماء الأعمدة فيها بالإنجليزية وثابتة.
"""

from __future__ import annotations

import io

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from pdf_extractor import Line
from wall_detector import Wall

WALL_COLUMNS = {
    "wall_id": "Wall_ID",
    "x1": "X1",
    "y1": "Y1",
    "x2": "X2",
    "y2": "Y2",
    "length": "Length_m",
    "thickness": "Thickness_m",
}


def walls_dataframe(walls: list[Wall]) -> pd.DataFrame:
    df = pd.DataFrame([w.to_dict() for w in walls], columns=list(WALL_COLUMNS) + ["line_a", "line_b"])
    return df[list(WALL_COLUMNS)].rename(columns=WALL_COLUMNS)


OPENING_COLUMNS = {
    "opening_id": "Opening_ID",
    "kind": "Type",
    "host_wall_id": "Host_Wall_ID",
    "x": "X",
    "y": "Y",
    "width": "Width_m",
    "wall_thickness": "Wall_Thickness_m",
    "swing_side": "Swing_Side",
    "hinge_at": "Hinge_At",
    "leaves": "Leaves",
}


def openings_dataframe(openings) -> pd.DataFrame:
    df = pd.DataFrame([o.to_dict() for o in openings], columns=list(OPENING_COLUMNS))
    return df.rename(columns=OPENING_COLUMNS)


def lines_dataframe(lines: list[Line]) -> pd.DataFrame:
    df = pd.DataFrame([l.to_dict() for l in lines])
    if df.empty:
        return df
    return df[["id", "x1", "y1", "x2", "y2", "length", "stroke_width"]].rename(
        columns={"id": "Line_ID", "x1": "X1", "y1": "Y1", "x2": "X2", "y2": "Y2",
                 "length": "Length_m", "stroke_width": "Stroke_Width_m"}
    )


def export_to_excel(walls: list[Wall], lines: list[Line], path: str | None = None,
                    meta: dict | None = None, openings=None) -> bytes:
    """
    يكتب الملف إلى path إن أُعطي، ويرجع محتواه bytes دائماً (لزر التحميل في الواجهة).
    meta: معلومات إضافية (المقياس، إزاحة الأصل...) تُحفظ في ورقة Info.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        walls_dataframe(walls).to_excel(xw, sheet_name="Walls", index=False)
        openings_dataframe(openings or []).to_excel(xw, sheet_name="Openings", index=False)
        lines_dataframe(lines).to_excel(xw, sheet_name="Lines", index=False)
        info = {"units": "meters", **(meta or {})}
        pd.DataFrame({"Key": list(info), "Value": [str(v) for v in info.values()]}).to_excel(
            xw, sheet_name="Info", index=False)

        header_fill = PatternFill("solid", fgColor="1F3A5F")
        for ws in xw.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 14
            ws.freeze_panes = "A2"

    data = buf.getvalue()
    if path:
        with open(path, "wb") as f:
            f.write(data)
    return data
