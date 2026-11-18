"""
model3d_page.py — صفحة النمذجة ثلاثية الأبعاد
المرحلة 1: أشكال أساسية + ملفات OBJ / GLB / GLTF / STL + عارض تفاعلي
المرحلة 2: الخامات (لون، خشونة، معدنية، شفافية، صورة، Normal Map، مكتبة جاهزة)
           + عناصر الموقع (رجال، نساء، أطفال، سيارات، أشجار، شجيرات، مساحات خضراء، طرق)
"""

import base64
import copy
import uuid

import streamlit as st

from viewer3d import render_viewer

MAX_MODEL_MB = 25   # حد حجم ملف ثلاثي الأبعاد
MAX_IMAGE_MB = 4    # حد حجم صورة الخامة

SHAPES = {"box": "مكعب", "sphere": "كرة", "cylinder": "أسطوانة", "plane": "مستوى"}

SITE = {  # عناصر الموقع: الاسم، اللون الافتراضي، الإزاحة الافتراضية
    "man": ("رجل", "#2E5E8C"),
    "woman": ("امرأة", "#B5485D"),
    "child": ("طفل", "#E8A317"),
    "car": ("سيارة", "#B3261E"),
    "tree": ("شجرة", "#3F7D3A"),
    "bush": ("شجيرة", "#4F8A3A"),
    "grass": ("مساحة خضراء", None),
    "road": ("طريق", None),
}
SITE_ICON = {"man": "🧍‍♂️", "woman": "🧍‍♀️", "child": "🧒", "car": "🚗", "tree": "🌳",
             "bush": "🌿", "grass": "🟩", "road": "🛣️"}

# مكتبة الخامات: (الاسم، اللون، الخشونة، المعدنية، الشفافية %)
PRESETS = {
    "none": ("لون فقط", None, 0.55, 0.05, 0),
    "wood": ("🪵 خشب", "#FFFFFF", 0.70, 0.00, 0),
    "marble": ("🤍 رخام", "#EFECE6", 0.25, 0.00, 0),
    "metal": ("🔩 معدن", "#FFFFFF", 0.35, 1.00, 0),
    "glass": ("🪟 زجاج", "#CFE8F5", 0.05, 0.00, 70),
    "fabric": ("🧵 قماش", "#FFFFFF", 0.95, 0.00, 0),
}
PALETTE = ["#C8553D", "#2E86AB", "#3D9970", "#E8A317", "#8E5572", "#4A5568"]

ss = st.session_state
ss.setdefault("objects", [])
ss.setdefault("selected", None)
ss.setdefault("counter", 0)
ss.setdefault("added_files", set())
ss.setdefault("pending_select", None)


# ---------------- أدوات ----------------
def new_id():
    return uuid.uuid4().hex[:8]


def base_obj(**kw):
    o = {"id": new_id(), "px": 0.0, "py": 0.0, "pz": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "scale": 1.0}
    o.update(kw)
    return o


def default_mat(color):
    return {"preset": "none", "color": color, "roughness": 0.55, "metalness": 0.05,
            "opacity": 1.0, "repeat": 1.0, "tex": None, "normal": None, "normal_strength": 1.0}


def make_shape(kind):
    ss.counter += 1
    color = PALETTE[(ss.counter - 1) % len(PALETTE)]
    o = base_obj(type=kind, name=f"{SHAPES[kind]} {ss.counter}", color=color,
                 px=float((len(ss.objects) % 5) * 1.5 - 3))
    if kind == "box":
        o.update(w=1.0, h=1.0, d=1.0, py=0.5)
    elif kind == "sphere":
        o.update(r=0.6, py=0.6)
    elif kind == "cylinder":
        o.update(rt=0.5, rb=0.5, h=1.5, py=0.75)
    elif kind == "plane":
        o.update(w=6.0, d=6.0, px=0.0, color="#D8D2C8")
    o["mat"] = default_mat(o["color"])
    return o


def make_site(kind):
    ss.counter += 1
    label, color = SITE[kind]
    n = len(ss.objects)
    o = base_obj(type="ent", kind=kind, name=f"{label} {ss.counter}", color=color or "#FFFFFF")
    if kind in ("man", "woman", "child"):
        o.update(px=float(n % 6) * 0.8 - 2, pz=3.0)
    elif kind == "car":
        o.update(px=float(n % 3) * 5 - 5, pz=-10.75)
    elif kind == "tree":
        o.update(h=5.0, px=float(n % 5) * 3 - 6, pz=-3.0)
    elif kind == "bush":
        o.update(px=float(n % 6) * 1.5 - 4, pz=5.0)
    elif kind == "grass":
        o.update(w=10.0, d=8.0, pz=9.0)
    elif kind == "road":
        o.update(l=40.0, w=7.0, sidewalk=True, pz=-9.0)
    return o


def add(obj):
    ss.objects.append(obj)
    ss.selected = obj["id"]
    ss.pending_select = obj["id"]


def find(oid):
    return next((o for o in ss.objects if o["id"] == oid), None)


def kw(key, value):
    """نمرر القيمة الافتراضية فقط عند أول إنشاء للحقل (حتى لا يحذّر Streamlit)."""
    return {} if key in ss else {"value": value}


def num(label, obj, field, step=0.1, min_value=None, fmt="%.2f", target=None):
    target = obj if target is None else target
    key = f"{obj['id']}_{field}"
    target[field] = st.number_input(label, step=step, min_value=min_value, format=fmt, key=key,
                                    **kw(key, float(target[field])))


def to_data_url(upload):
    mime = upload.type or "image/png"
    return f"data:{mime};base64," + base64.b64encode(upload.getvalue()).decode("ascii")


def apply_preset(oid):
    """عند اختيار خامة جاهزة: نضبط اللون والخشونة والمعدنية والشفافية على قيمها المناسبة."""
    o = find(oid)
    key = ss[f"{oid}_preset"]
    _, color, rough, metal, transp = PRESETS[key]
    ss[f"{oid}_mcolor"] = color or o["mat"]["color"]
    ss[f"{oid}_rough"] = rough
    ss[f"{oid}_metal"] = metal
    ss[f"{oid}_transp"] = transp


def white_for_texture(oid):
    """عند رفع صورة خامة: نجعل اللون أبيض حتى تظهر الصورة بألوانها الحقيقية."""
    if ss.get(f"{oid}_texup") is not None:
        ss[f"{oid}_mcolor"] = "#FFFFFF"


def material_panel(o):
    m = o.setdefault("mat", default_mat(o.get("color", "#C8553D")))
    oid = o["id"]
    pk = f"{oid}_preset"
    m["preset"] = st.selectbox("مكتبة الخامات", list(PRESETS), format_func=lambda k: PRESETS[k][0],
                               key=pk, on_change=apply_preset, args=(oid,),
                               **({} if pk in ss else {"index": list(PRESETS).index(m["preset"])}))
    m["color"] = st.color_picker("اللون", key=f"{oid}_mcolor", **kw(f"{oid}_mcolor", m["color"]))
    a, b = st.columns(2)
    with a:
        m["roughness"] = st.slider("الخشونة", 0.0, 1.0, step=0.05, key=f"{oid}_rough",
                                   **kw(f"{oid}_rough", m["roughness"]),
                                   help="0 = لامع كالمرآة · 1 = مطفي تماماً")
    with b:
        m["metalness"] = st.slider("المعدنية", 0.0, 1.0, step=0.05, key=f"{oid}_metal",
                                   **kw(f"{oid}_metal", m["metalness"]))
    transp = st.slider("الشفافية %", 0, 95, step=5, key=f"{oid}_transp",
                       **kw(f"{oid}_transp", int(round((1 - m["opacity"]) * 100))))
    m["opacity"] = 1 - transp / 100

    st.markdown("**صورة الخامة (اختياري)**")
    tex = st.file_uploader("صورة الخامة", type=["png", "jpg", "jpeg", "webp"], key=f"{oid}_texup",
                           label_visibility="collapsed", on_change=white_for_texture, args=(oid,),
                           help="صورة تُلف على المجسم. تحل محل خامة المكتبة.")
    m["tex"] = None
    if tex is not None:
        if tex.size > MAX_IMAGE_MB * 1024 * 1024:
            st.error(f"الصورة أكبر من {MAX_IMAGE_MB} ميغابايت")
        else:
            m["tex"] = to_data_url(tex)
    nrm = st.file_uploader("Normal Map", type=["png", "jpg", "jpeg", "webp"], key=f"{oid}_nrmup",
                           help="صورة بنفسجية تعطي إحساس البروز والتجاويف بدون تعديل الشكل")
    m["normal"] = None
    if nrm is not None:
        if nrm.size > MAX_IMAGE_MB * 1024 * 1024:
            st.error(f"الصورة أكبر من {MAX_IMAGE_MB} ميغابايت")
        else:
            m["normal"] = to_data_url(nrm)
            m["normal_strength"] = st.slider("قوة البروز", 0.0, 3.0, step=0.1, key=f"{oid}_nstr",
                                             **kw(f"{oid}_nstr", m["normal_strength"]))
    if m["tex"] or m["normal"] or m["preset"] in ("wood", "marble", "metal", "fabric"):
        num("تكرار الخامة", o, "repeat", step=0.5, min_value=0.1, fmt="%.1f", target=m)


# ---------------- الشريط الجانبي: الإضافة ----------------
with st.sidebar:
    st.header("🧊 النمذجة")

    st.subheader("إضافة شكل")
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    kind = c1.selectbox("النوع", list(SHAPES), format_func=SHAPES.get, label_visibility="collapsed",
                        key="new_shape")
    if c2.button("➕ إضافة", width="stretch", key="add_shape"):
        add(make_shape(kind))

    st.subheader("عناصر الموقع")
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    skind = c1.selectbox("العنصر", list(SITE), format_func=lambda k: f"{SITE_ICON[k]} {SITE[k][0]}",
                         label_visibility="collapsed", key="new_site")
    if c2.button("➕ إضافة", width="stretch", key="add_site"):
        add(make_site(skind))

    st.subheader("رفع ملف ثلاثي الأبعاد")
    up = st.file_uploader("OBJ · GLB · GLTF · STL", type=["obj", "glb", "gltf", "stl"],
                          help="ملف GLTF يجب أن يكون مدمجاً (Embedded). الأفضل استخدام GLB.")
    if up is not None:
        size_mb = up.size / 1024 / 1024
        if size_mb > MAX_MODEL_MB:
            st.error(f"حجم الملف {size_mb:.1f} ميغابايت — الحد الأقصى {MAX_MODEL_MB}.")
        elif up.file_id in ss.added_files:
            st.caption("✅ تمت إضافة هذا الملف للمشهد.")
        else:
            fmt = up.name.rsplit(".", 1)[-1].lower()
            unit = st.selectbox("وحدة الملف", ["متر", "سنتيمتر", "مليمتر"],
                                help="ملفات STL من برامج CAD غالباً بالمليمتر")
            if st.button("إضافة الملف للمشهد", type="primary", width="stretch"):
                scale = {"متر": 1.0, "سنتيمتر": 0.01, "مليمتر": 0.001}[unit]
                add(base_obj(type="model", name=up.name, fmt=fmt,
                             data=base64.b64encode(up.getvalue()).decode("ascii"),
                             px=float((len(ss.objects) % 5) * 2 - 4), pz=2.5, scale=scale,
                             override=False, mat=default_mat("#B8B2A7")))
                ss.added_files.add(up.file_id)
                st.rerun()

    st.divider()

    # ---------------- الشريط الجانبي: التعديل ----------------
    if ss.objects:
        st.subheader("تعديل مجسم")
        ids = [o["id"] for o in ss.objects]
        if ss.pending_select in ids:
            ss.sel_obj = ss.pending_select
        ss.pending_select = None
        if ss.get("sel_obj") not in ids:
            ss.sel_obj = ids[-1]
        ss.selected = st.selectbox("المجسم المحدد", ids, key="sel_obj",
                                   format_func=lambda i: find(i)["name"])
        o = find(ss.selected)
        oid = o["id"]

        # --- الخامة
        if o["type"] in SHAPES:
            with st.expander("🎨 الخامة", expanded=True):
                material_panel(o)
        elif o["type"] == "model":
            with st.expander("🎨 الخامة", expanded=False):
                o["override"] = st.checkbox("استبدال خامات الملف", key=f"{oid}_ovr",
                                            **kw(f"{oid}_ovr", o.get("override", False)),
                                            help="بدون تفعيل: تبقى الألوان والخامات الأصلية للملف")
                if o["override"]:
                    material_panel(o)
        elif o["type"] == "ent" and o["kind"] not in ("grass", "road"):
            label = {"car": "لون السيارة", "tree": "لون الأوراق", "bush": "لون الأوراق"}.get(o["kind"], "لون الملابس")
            o["color"] = st.color_picker(label, key=f"{oid}_color", **kw(f"{oid}_color", o["color"]))

        # --- الأبعاد
        with st.expander("📏 الأبعاد (متر)", expanded=o["type"] in SHAPES):
            t, k = o["type"], o.get("kind")
            if t == "box":
                a, b, c = st.columns(3)
                with a: num("العرض", o, "w", min_value=0.01)
                with b: num("الارتفاع", o, "h", min_value=0.01)
                with c: num("العمق", o, "d", min_value=0.01)
            elif t == "sphere":
                num("نصف القطر", o, "r", min_value=0.01)
            elif t == "cylinder":
                a, b, c = st.columns(3)
                with a: num("نصف قطر أعلى", o, "rt", min_value=0.0)
                with b: num("نصف قطر أسفل", o, "rb", min_value=0.0)
                with c: num("الارتفاع", o, "h", min_value=0.01)
            elif t == "plane" or k == "grass":
                a, b = st.columns(2)
                with a: num("العرض", o, "w", min_value=0.1)
                with b: num("العمق", o, "d", min_value=0.1)
            elif k == "tree":
                num("ارتفاع الشجرة", o, "h", step=0.5, min_value=1.0)
            elif k == "road":
                a, b = st.columns(2)
                with a: num("طول الطريق", o, "l", step=5.0, min_value=2.0)
                with b: num("عرض الطريق", o, "w", step=0.5, min_value=2.0)
                o["sidewalk"] = st.checkbox("أرصفة على الجانبين", key=f"{oid}_sw",
                                            **kw(f"{oid}_sw", o["sidewalk"]))
            elif k in ("man", "woman", "child", "car", "bush"):
                st.caption("مقاسات حقيقية: رجل 1.78 م · امرأة 1.65 م · طفل 1.15 م · سيارة 4.4 × 1.8 م")
            num("التكبير (Scale)", o, "scale", step=0.1, min_value=0.0001, fmt="%.4g")

        # --- الموقع والدوران
        with st.expander("📍 الموقع (متر)", expanded=True):
            a, b, c = st.columns(3)
            with a: num("X", o, "px")
            with b: num("Y ↑", o, "py")
            with c: num("Z", o, "pz")

        with st.expander("🔄 الدوران (درجة)", expanded=o["type"] == "ent"):
            for axis, label in (("rx", "حول X"), ("ry", "حول Y ↑"), ("rz", "حول Z")):
                key = f"{oid}_{axis}"
                o[axis] = float(st.slider(label, -180, 180, step=5, key=key, **kw(key, int(o[axis]))))

        a, b = st.columns(2)
        if a.button("📄 نسخ", width="stretch"):
            dup = copy.deepcopy(o)
            dup["id"], dup["name"] = new_id(), o["name"] + " (نسخة)"
            dup["px"] = o["px"] + (5.0 if o.get("kind") == "car" else 1.5)
            add(dup)
            st.rerun()
        if b.button("🗑️ حذف", width="stretch"):
            ss.objects = [x for x in ss.objects if x["id"] != oid]
            ss.selected = ss.objects[-1]["id"] if ss.objects else None
            ss.pending_select = ss.selected
            st.rerun()

        st.divider()
        if st.button("مسح المشهد بالكامل", width="stretch"):
            ss.objects, ss.selected = [], None
            ss.added_files = set()
            st.rerun()
    else:
        st.info("المشهد فارغ. أضف شكلاً أو عنصراً من الموقع أو ارفع ملفاً.")


# ---------------- الصفحة الرئيسية ----------------
st.title("🧊 النمذجة ثلاثية الأبعاد")
st.caption("الأشكال والخامات وعناصر الموقع · الإطار البرتقالي = المجسم المحدد")

render_viewer(ss.objects, ss.selected, height=640)

if ss.objects:
    def kind_label(o):
        if o["type"] == "ent":
            return f"{SITE_ICON[o['kind']]} {SITE[o['kind']][0]}"
        if o["type"] == "model":
            return "📦 ملف"
        return SHAPES[o["type"]]

    with st.expander(f"قائمة المجسمات ({len(ss.objects)})"):
        st.dataframe(
            [{"الاسم": o["name"], "النوع": kind_label(o),
              "الخامة": PRESETS[o["mat"]["preset"]][0] if o.get("mat") and o["type"] != "ent" else "—",
              "X": o["px"], "Y": o["py"], "Z": o["pz"]} for o in ss.objects],
            hide_index=True, width="stretch")
