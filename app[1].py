"""
ahmednah — نقطة البداية (Streamlit Cloud يشغّل هذا الملف)
يعرض صفحتين في القائمة الجانبية:
    📐 تحويل PDF إلى Revit   → pdf_page.py
    🧊 النمذجة ثلاثية الأبعاد → model3d_page.py

التشغيل محلياً:
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="ahmednah", page_icon="🏗️", layout="wide")

# اتجاه عربي (من اليمين لليسار) للنصوص، مع إبقاء الجداول والصور والعارض كما هي
st.markdown("""
<style>
  .stMainBlockContainer, section[data-testid="stSidebar"] { direction: rtl; text-align: right; }
  [data-testid="stDataFrame"], [data-testid="stImage"], iframe { direction: ltr; }
  .ahm-sub { color: #6b7280; margin-top: -0.8rem; }
</style>
""", unsafe_allow_html=True)

pages = [
    st.Page("pdf_page.py", title="تحويل PDF إلى Revit", icon="📐", default=True),
    st.Page("model3d_page.py", title="النمذجة ثلاثية الأبعاد", icon="🧊"),
]
st.navigation(pages).run()
