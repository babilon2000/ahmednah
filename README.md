# ahmednah — من مخطط PDF إلى نموذج Revit

تحويل مخطط أرضي PDF (مصدَّر من AutoCAD) إلى جدول جدران جاهز لـ Revit.

## التشغيل
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
python samples/make_sample.py      # مخطط تجريبي (اختياري)
streamlit run app.py               # الواجهة على http://localhost:8501
```

من سطر الأوامر بدون واجهة:
```bash
python extract_cli.py samples/sample_plan.pdf --scale 100
```

## الهيكل
```
ahmednah/
├── app.py                 واجهة Streamlit
├── extract_cli.py         تشغيل من سطر الأوامر
├── requirements.txt
├── core/
│   ├── pdf_extractor.py   قراءة PDF واستخراج الخطوط (PyMuPDF)
│   ├── wall_detector.py   تمييز الجدران من الخطوط المتوازية
│   ├── wall_joiner.py     وصل الزوايا + نقل الأصل (المرحلة 2)
│   ├── openings.py        الأبواب والشبابيك + دمج الجدران المستضيفة (المرحلة 3)
│   ├── pipeline.py        المسار الكامل في دالة واحدة
│   └── excel_exporter.py  الحفظ في Excel
├── dynamo/                (المرحلة 2)
│   ├── ahmednah_walls.dyn     ملف Dynamo جاهز
│   ├── ahmednah_walls.py      كود بايثون: قراءة الجدران
│   ├── ahmednah_openings.py   كود بايثون: الأبواب والشبابيك (المرحلة 3)
│   └── build_dyn.py           يعيد بناء .dyn بعد تعديل الكود
├── samples/make_sample.py مولّد مخطط تجريبي
└── output/                ملفات Excel الناتجة
```

## ملف Excel
- ورقة `Walls`: Wall_ID, X1, Y1, X2, Y2, Length_m, Thickness_m  (بالمتر، Y للأعلى، الإحداثيات لخط محور الجدار)
- ورقة `Lines`: كل الخطوط الخام للمراجعة
- ورقة `Openings`: Opening_ID, Type (Door/Window/Opening), Host_Wall_ID, X, Y, Width_m, Wall_Thickness_m, Swing_Side, Hinge_At, Leaves
- ورقة `Info`: المقياس وإزاحة الأصل

## المرحلة 2: Revit
1. افتح مشروع Revit (أو قالباً جديداً) ← Manage ← Dynamo.
2. افتح `dynamo/ahmednah_walls.dyn`.
3. في عقدة "1. Excel File" اختر ملف Excel الناتج.
4. اضغط Run. تظهر الجدران بارتفاع 3.5 م، ويظهر تقرير في عقدة Report.

## المرحلة 3: الأبواب والشبابيك
نفس ملف `ahmednah_walls.dyn` — العقدة الثانية تضع الأبواب والشبابيك بعد الجدران تلقائياً.
- المدخلات 4 و5 اختيارية: اسم عائلة/نوع الباب والشباك (فارغ = أول عائلة محمّلة).
- إذا فتحت كل الأبواب للجهة الخطأ: غيّر `SWING_TOWARD_FACING` في أعلى كود العقدة.
- إذا كانت كل المفصلات في الطرف الخطأ: غيّر `HINGE_TOWARD_HAND`.

## المرحلة 4: النشر أونلاين (Streamlit Community Cloud — مجاني)
1. أنشئ مستودعاً جديداً على GitHub باسم `ahmednah` (Public).
2. من داخل مجلد المشروع:
   ```bash
   git remote add origin https://github.com/<اسم-حسابك>/ahmednah.git
   git branch -M main
   git push -u origin main
   ```
3. ادخل https://share.streamlit.io وسجّل الدخول بحساب GitHub.
4. Create app ← اختر المستودع `ahmednah`، الفرع `main`، والملف `app.py`.
5. (اختياري) اختر رابطاً مثل `ahmednah.streamlit.app` ← Deploy.

أي تعديل تدفعه بعدها إلى GitHub (`git push`) يُحدِّث التطبيق تلقائياً.
