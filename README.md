# ahmednah

تطبيق ويب يحوّل مخططاً أرضياً PDF (مصدَّراً من AutoCAD) إلى جدران وأبواب وشبابيك جاهزة لـ Revit.

- الواجهة: `app.py` (Streamlit)
- المنطق: `pdf_extractor.py` ← `wall_detector.py` ← `wall_joiner.py` ← `openings.py` ← `excel_exporter.py`
- ملف Dynamo: `ahmednah_walls.dyn`
- مخطط تجريبي: `sample_plan.pdf`

التشغيل محلياً:
```bash
pip install -r requirements.txt
streamlit run app.py
```
