"""
ahmednah — من مخطط PDF إلى نموذج Revit
واجهة Streamlit: رفع مخطط PDF ← الجدران والأبواب والشبابيك ← حزمة Revit (Excel + Dynamo)

التشغيل محلياً:
    streamlit run app.py
"""

import io
from pathlib import Path

import pymupdf
import streamlit as st
from PIL import Image, ImageDraw

from excel_exporter import export_to_excel, lines_dataframe, openings_dataframe, walls_dataframe
from package import build_revit_package
from pdf_extractor import render_page_png
from pipeline import run

SAMPLE = Path(__file__).parent / "sample_plan.pdf"
NUM_COLS = {c: st.column_config.NumberColumn(c, format="%.2f")
            for c in ["X1", "Y1", "X2", "Y2", "X", "Y", "الطول (م)", "السماكة (م)", "العرض (م)",
                      "سماكة الجدار"]}
MAX_RENDER_PX = 3000  # حد لحجم صورة المعاينة حتى لا تمتلئ ذاكرة السيرفر مع لوحات A0

st.set_page_config(page_title="ahmednah · PDF ← Revit", page_icon="🏗️", layout="wide")

# اتجاه عربي (من اليمين لليسار) للنصوص، مع إبقاء الجداول والأرقام كما هي
st.markdown("""
<style>
  .stMainBlockContainer, section[data-testid="stSidebar"] { direction: rtl; text-align: right; }
  [data-testid="stDataFrame"], [data-testid="stImage"] { direction: ltr; }
  .ahm-sub { color: #6b7280; margin-top: -0.8rem; }
</style>
""", unsafe_allow_html=True)


# ---------------- المعالجة (مع تخزين مؤقت: لا نعيد الحساب عند كل نقرة) ----------------
@st.cache_data(show_spinner=False, max_entries=8)
def process(pdf_bytes, page_no, scale, min_thk, max_thk, angle_tol, min_overlap, min_line,
            do_join, do_norm, do_open):
    return run(pdf_bytes, page_number=page_no, scale=scale, min_thk=min_thk, max_thk=max_thk,
               angle_tol=angle_tol, min_overlap=min_overlap, min_line_length=min_line,
               join=do_join, normalize=do_norm, openings=do_open)


@st.cache_data(show_spinner=False, max_entries=8)
def page_image(pdf_bytes, page_no, zoom):
    return render_page_png(pdf_bytes, page_no, zoom)


@st.cache_data(show_spinner=False, max_entries=8)
def page_count(pdf_bytes):
    return pymupdf.open(stream=pdf_bytes, filetype="pdf").page_count


# ---------------- الرأس ----------------
st.title("🏗️ ahmednah")
st.markdown('<p class="ahm-sub">ارفع مخططاً أرضياً PDF مصدَّراً من AutoCAD، '
            'واحصل على الجدران والأبواب والشبابيك جاهزة لـ Revit</p>', unsafe_allow_html=True)

# ---------------- الإعدادات ----------------
with st.sidebar:
    st.header("⚙️ الإعدادات")
    scale = st.number_input("مقياس الرسم 1:", min_value=1, value=100, step=10,
                            help="المقياس الذي صُدِّر به المخطط من AutoCAD (مثلاً 1:100 أو 1:50)")
    c1, c2 = st.columns(2)
    min_thk = c1.number_input("أقل سماكة (سم)", value=10.0, step=1.0) / 100
    max_thk = c2.number_input("أكبر سماكة (سم)", value=30.0, step=1.0) / 100
    with st.expander("إعدادات متقدمة"):
        angle_tol = st.slider("سماحية التوازي (درجة)", 0.5, 5.0, 2.0, 0.5)
        min_overlap = st.number_input("أقل طول جدار (م)", value=0.20, step=0.05)
        min_line = st.number_input("تجاهل الخطوط الأقصر من (م)", value=0.20, step=0.05)
        do_join = st.checkbox("وصل زوايا الجدران", value=True)
        do_norm = st.checkbox("نقل الأصل (0,0) إلى زاوية المبنى", value=True)
        do_open = st.checkbox("اكتشاف الأبواب والشبابيك", value=True)
    st.divider()
    with st.expander("ℹ️ كيف أستخدم النتيجة في Revit؟"):
        st.markdown("""
1. حمّل **حزمة Revit** وفك ضغطها.
2. في Revit: **Manage ← Dynamo ← Open ← ahmednah.dyn**
3. في عقدة **1. Excel File** اختر ملف Excel من الحزمة.
4. اضغط **Run**.
""")
    st.caption("🔒 الملفات تُعالج في الذاكرة فقط ولا تُحفظ على السيرفر.")

# ---------------- الرفع ----------------
up_col, sample_col = st.columns([4, 1], vertical_alignment="bottom")
uploaded = up_col.file_uploader("ارفع ملف PDF للمخطط الأرضي", type=["pdf"])
if sample_col.button("🧪 جرّب مخططاً تجريبياً", width="stretch"):
    st.session_state.use_sample = True

if uploaded:
    st.session_state.use_sample = False
    pdf_bytes, file_name = uploaded.getvalue(), uploaded.name
elif st.session_state.get("use_sample"):
    pdf_bytes, file_name = SAMPLE.read_bytes(), "sample_plan.pdf"
    st.info("تعرض الآن المخطط التجريبي (مقياس 1:100). ارفع ملفك في أي وقت.")
else:
    st.markdown("""
#### كيف يعمل؟
1. **ارفع** مخططاً أرضياً PDF، صدّره من AutoCAD مباشرة (وليس ممسوحاً ضوئياً).
2. **اضبط المقياس** من القائمة الجانبية ليطابق مقياس التصدير.
3. **راجع** الجدران والأبواب والشبابيك المكتشفة فوق المخطط.
4. **حمّل حزمة Revit** وشغّلها في Dynamo.
""")
    st.stop()

base_name = Path(file_name).stem

try:
    n_pages = page_count(pdf_bytes)
except Exception:
    st.error("تعذّرت قراءة الملف. تأكد أنه PDF سليم وغير محمي بكلمة مرور.")
    st.stop()

page_no = st.selectbox("الصفحة", range(1, n_pages + 1)) - 1 if n_pages > 1 else 0

with st.spinner("جارٍ تحليل المخطط..."):
    try:
        lines, walls, ops, info, offset, meta = process(
            pdf_bytes, page_no, scale, min_thk, max_thk, angle_tol, min_overlap, min_line,
            do_join, do_norm, do_open)
    except Exception as e:
        st.error(f"حدث خطأ أثناء التحليل: {e}")
        st.stop()

k = info["factor_m_per_pt"]
page_w_pt, page_h_pt = info["page_width_m"] / k, info["page_height_m"] / k
zoom = min(2.0, MAX_RENDER_PX / max(page_w_pt, page_h_pt))

if not lines:
    st.warning("لم أجد أي خطوط متجهية في هذه الصفحة. "
               "على الأغلب الملف ممسوح ضوئياً (صورة) وليس مصدَّراً من AutoCAD مباشرة.")
    st.image(page_image(pdf_bytes, page_no, zoom))
    st.stop()

if not walls:
    st.warning("وجدت خطوطاً لكن بدون جدران. على الأغلب **المقياس غير صحيح** — "
               "جرّب 1:50 أو 1:100 أو 1:200 من القائمة الجانبية.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("الخطوط", len(lines))
m2.metric("الجدران", len(walls))
m3.metric("الأبواب", sum(o.kind == "Door" for o in ops))
m4.metric("الشبابيك", sum(o.kind == "Window" for o in ops))

# ---------------- العرض ----------------
left, right = st.columns([5, 4])

with left:
    show_overlay = st.toggle("إظهار العناصر المكتشفة فوق المخطط", value=True)
    img = Image.open(io.BytesIO(page_image(pdf_bytes, page_no, zoom))).convert("RGB")
    if show_overlay and walls:
        draw = ImageDraw.Draw(img)
        ox, oy = offset  # الجدران مزاحة؛ نعيدها لمكانها على الورقة للرسم

        def to_px(x, y):
            return ((x + ox) / k * zoom, (page_h_pt - (y + oy) / k) * zoom)

        for w in walls:
            draw.line([to_px(w.x1, w.y1), to_px(w.x2, w.y2)], fill=(230, 60, 40),
                      width=max(2, int(w.thickness / k * zoom * 0.6)))
            cx, cy = to_px((w.x1 + w.x2) / 2, (w.y1 + w.y2) / 2)
            draw.text((cx + 3, cy + 3), str(w.wall_id), fill=(20, 60, 200))

        colors = {"Door": (30, 90, 220), "Window": (20, 170, 90), "Opening": (240, 160, 0)}
        by_id = {w.wall_id: w for w in walls}
        for o in ops:
            h = by_id[o.host_wall_id]
            L = max(h.length, 1e-6)
            ux, uy = (h.x2 - h.x1) / L, (h.y2 - h.y1) / L
            a = to_px(o.x - ux * o.width / 2, o.y - uy * o.width / 2)
            b = to_px(o.x + ux * o.width / 2, o.y + uy * o.width / 2)
            draw.line([a, b], fill=colors[o.kind], width=max(4, int(o.wall_thickness / k * zoom * 1.3)))
            cx, cy = to_px(o.x, o.y)
            draw.text((cx + 6, cy - 14), f"{o.kind[0]}{o.opening_id}", fill=colors[o.kind])
    # قصّ الصورة على حدود الرسم (المخطط غالباً لا يملأ الورقة)
    xs = [v / k * zoom for l in lines for v in (l.x1, l.x2)]
    ys = [(page_h_pt - v / k) * zoom for l in lines for v in (l.y1, l.y2)]
    pad = 0.04 * max(max(xs) - min(xs), max(ys) - min(ys)) + 10
    img = img.crop((max(0, int(min(xs) - pad)), max(0, int(min(ys) - pad)),
                    min(img.width, int(max(xs) + pad)), min(img.height, int(max(ys) + pad))))
    st.image(img, width="stretch")
    st.caption("🔴 جدار   🔵 باب   🟢 شباك   🟠 فتحة بدون باب")

with right:
    excel_bytes = export_to_excel(walls, lines, meta=meta, openings=ops)
    st.download_button("📦 تحميل حزمة Revit (Excel + Dynamo)", type="primary",
                       data=build_revit_package(excel_bytes, base_name),
                       file_name=f"{base_name}_ahmednah.zip", mime="application/zip",
                       width="stretch", disabled=not walls)
    st.download_button("⬇️ ملف Excel فقط", data=excel_bytes,
                       file_name=f"{base_name}_walls.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")

    tab_w, tab_o = st.tabs([f"الجدران ({len(walls)})", f"الفتحات ({len(ops)})"])
    with tab_w:
        st.dataframe(walls_dataframe(walls).rename(columns={
            "Wall_ID": "رقم", "Length_m": "الطول (م)", "Thickness_m": "السماكة (م)"}),
            width="stretch", hide_index=True, height=360, column_config=NUM_COLS)
    with tab_o:
        st.dataframe(openings_dataframe(ops).rename(columns={
            "Opening_ID": "رقم", "Type": "النوع", "Host_Wall_ID": "الجدار",
            "Width_m": "العرض (م)", "Swing_Side": "جهة الفتح", "Hinge_At": "المفصلة",
            "Wall_Thickness_m": "سماكة الجدار"}),
            width="stretch", hide_index=True, height=360, column_config=NUM_COLS)

with st.expander(f"الخطوط الخام ({len(lines)})"):
    st.dataframe(lines_dataframe(lines), width="stretch", hide_index=True)
