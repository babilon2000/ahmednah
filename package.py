"""
package.py  (المرحلة 4)
----------------------
يجمّع كل ما يحتاجه المستخدم لـ Revit في ملف zip واحد:
    - ملف Excel (الجدران + الفتحات)
    - ملف Dynamo (ahmednah.dyn)
    - تعليمات قصيرة
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

DYN_PATH = Path(__file__).resolve().parent / "ahmednah_walls.dyn"

INSTRUCTIONS = """ahmednah - طريقة الاستخدام في Revit
====================================

1. فك ضغط هذا الملف في أي مجلد على جهازك.
2. افتح Revit ثم مشروعاً جديداً (قالب Architectural) أو مشروعك.
3. Manage  ←  Dynamo  ←  Open  ←  ahmednah.dyn
4. في العقدة "1. Excel File" اضغط Browse واختر: {excel_name}
5. اضغط Run.

النتيجة: الجدران بارتفاع 3.5 م (يمكن تغييره من العقدة 2)، ثم الأبواب والشبابيك.

ملاحظات:
- يجب أن يحتوي المشروع على عائلة باب وعائلة شباك واحدة على الأقل.
- إذا فتحت كل الأبواب للجهة الخطأ: افتح كود عقدة "ahmednah - Doors & Windows"
  وغيّر SWING_TOWARD_FACING. وإذا كانت المفصلات في الطرف الخطأ: غيّر HINGE_TOWARD_HAND.
- إذا ظهرت رسالة عن محرك Python: زر يمين على عقدة البايثون واختر المحرك المتوفر
  (CPython3 أو PythonNet3).

الإحداثيات بالمتر، وأصلها (0,0) هو أسفل يسار المبنى.
"""


def build_revit_package(excel_bytes: bytes, base_name: str) -> bytes:
    excel_name = f"{base_name}_walls.xlsx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(excel_name, excel_bytes)
        z.write(DYN_PATH, "ahmednah.dyn")
        z.writestr("اقرأني - README.txt", INSTRUCTIONS.format(excel_name=excel_name).encode("utf-8"))
    return buf.getvalue()
