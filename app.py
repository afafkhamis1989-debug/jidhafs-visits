import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import date

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbziZ27mG690ZT02YN1LqbvWJLZ-rprnHK9qmXDDXcTvQVmnB-Phpm0J4DKjsg6Ts07xJQ/exec"
HEADER_PATH = "header.png"

st.set_page_config(page_title="نظام الزيارات الصفية", layout="wide")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #f7f9ff, #fff8f1);
    direction: rtl;
}
.big-title {
    text-align: center;
    font-size: 46px;
    font-weight: 900;
    color: #1f2937;
    margin-bottom: 25px;
}
.section-title {
    text-align: right;
    font-size: 28px;
    font-weight: 900;
    margin-top: 30px;
    margin-bottom: 15px;
}
.card {
    background: white;
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.07);
    border-right: 7px solid #6366f1;
    text-align: center;
}
.card-title {
    font-size: 17px;
    color: #6b7280;
    font-weight: 700;
}
.card-value {
    font-size: 36px;
    color: #111827;
    font-weight: 900;
}
</style>
""", unsafe_allow_html=True)

try:
    st.image(HEADER_PATH, use_container_width=True)
except:
    pass

st.markdown('<div class="big-title">📊 نظام الزيارات الصفية</div>', unsafe_allow_html=True)

# =======================
# تحميل البيانات من Google Sheet
# =======================
@st.cache_data(ttl=60)
def load_sheet_data():
    response = requests.get(GOOGLE_SCRIPT_URL, timeout=20)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, list):
        return pd.DataFrame(data)

    if isinstance(data, dict):
        if "data" in data:
            return pd.DataFrame(data["data"])
        if "rows" in data:
            return pd.DataFrame(data["rows"])
        if "teachers" in data:
            return pd.DataFrame(data["teachers"])

    return pd.DataFrame()

def send_to_google_sheet(row):
    payload = {
        "sheet_name": "Responses",
        "row": row
    }

    response = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()

def clean_text(x):
    return str(x).strip()

def normalize_dept(x):
    return str(x).strip().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")

# =======================
# صلاحيات الدخول
# =======================
dept_passwords = {
    "admin1825": "الكل",
    "Arab1111": "قسم اللغة العربية",
    "Math2222": "قسم الرياضيات",
    "Sc3333": "قسم العلوم",
    "Islamic4444": "قسم التربية الاسلامية",
    "Ict5555": "قسم الحاسب الآلي",
    "Eng6666": "قسم اللغة الانجليزية",
    "Social7777": "قسم المواد الاجتماعية",
    "Art8888": "قسم التربية الفنية",
    "Sport9999": "قسم التربية البدنية",
    "Com1010": "قسم المواد التجارية",
    "Family2020": "قسم التربية الاسرية"
}

st.sidebar.markdown("## 🔐 الدخول")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["allowed_dept"] = None

if not st.session_state["logged_in"]:
    site_password = st.sidebar.text_input("أدخلي الرقم السري", type="password")

    if site_password:
        if site_password in dept_passwords:
            st.session_state["logged_in"] = True
            st.session_state["allowed_dept"] = dept_passwords[site_password]
            st.rerun()
        else:
            st.sidebar.error("❌ الرقم السري غير صحيح")

    st.stop()

allowed_dept = st.session_state["allowed_dept"]

if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state["logged_in"] = False
    st.session_state["allowed_dept"] = None
    st.rerun()

page = st.sidebar.radio(
    "القائمة",
    ["لوحة التحليل", "إدخال زيارة صفية"]
)

# =======================
# تحميل الشيت
# =======================
try:
    df = load_sheet_data()
except Exception as e:
    st.error("حدث خطأ في تحميل البيانات من Google Sheet")
    st.write(e)
    st.stop()

df.columns = [str(c).strip() for c in df.columns]

# =======================
# صفحة إدخال زيارة صفية
# =======================
if page == "إدخال زيارة صفية":
    st.markdown("## 📝 استمارة الزيارات الصفية")

    visitor_types = [
        "زيارة القيادة العليا لجميع المعلمات",
        "زيارة القيادة العليا للقيادة الوسطى",
        "زيارة الأيام الحية للقيادة الوسطى",
        "زيارة الأيام الحية لجميع المعلمات",
        "زيارة القيادة الوسطى لجميع المعلمات"
    ]

    judgements = [
        "يتجاوز التوقعات بكثير",
        "يتجاوز التوقعات",
        "يفي بالتوقعات",
        "يفي بالتوقعات جزئياً"
    ]

    departments_static = [
        "قسم اللغة الانجليزية",
        "قسم اللغة العربية",
        "قسم التربية الاسلامية",
        "قسم الرياضيات",
        "قسم العلوم",
        "قسم المواد التجارية",
        "قسم المواد الاجتماعية",
        "قسم الحاسب الآلي",
        "قسم التربية الاسرية",
        "قسم التربية البدنية",
        "قسم التربية الفنية"
    ]

    with st.form("visit_form"):
        visitor_name = st.text_input("اسم الزائر")
        visit_date = st.date_input("تاريخ الزيارة", value=date.today())
        school_year = st.selectbox("السنة الدراسية", ["2025-2026", "2026-2027"])
        semester = st.selectbox("الفصل الدراسي", ["الفصل الدراسي الأول", "الفصل الدراسي الثاني"])
        visit_type = st.selectbox("نوع الزيارة", visitor_types)

        if allowed_dept == "الكل":
            selected_dept = st.selectbox("القسم", departments_static)
        else:
            selected_dept = allowed_dept
            st.info(f"القسم: {selected_dept}")

        if "القسم" in df.columns and "اسم المعلمة" in df.columns:
            teachers = df[
                df["القسم"].apply(normalize_dept) == normalize_dept(selected_dept)
            ]["اسم المعلمة"].dropna().astype(str).str.strip().unique()

            teachers = sorted([t for t in teachers if t and t != "nan"])

            if teachers:
                teacher_name = st.selectbox("اسم المعلمة", teachers)
            else:
                teacher_name = st.text_input("اسم المعلمة")
        else:
            teacher_name = st.text_input("اسم المعلمة")

        st.markdown("### بنود التقييم")

        answers = {}
        for i in range(1, 19):
            answers[f"البند {i}"] = st.selectbox(
                f"البند {i}",
                judgements,
                key=f"item_{i}"
            )

        notes = st.text_area("ملاحظات")
        submitted = st.form_submit_button("💾 حفظ الزيارة")

    if submitted:
        if not visitor_name or not teacher_name:
            st.error("الرجاء إدخال اسم الزائر واسم المعلمة")
        else:
            row = {
                "تاريخ الزيارة": str(visit_date),
                "السنة الدراسية": school_year,
                "الفصل الدراسي": semester,
                "اسم الزائر": visitor_name,
                "نوع الزيارة": visit_type,
                "القسم": selected_dept,
                "اسم المعلمة": teacher_name,
                "ملاحظات": notes
            }

            row.update(answers)

            try:
                result = send_to_google_sheet(row)
                st.cache_data.clear()
                st.success("تم حفظ الزيارة بنجاح ✅")
                st.write(result)
            except Exception as e:
                st.error("حدث خطأ أثناء الإرسال")
                st.write(e)

# =======================
# صفحة التحليل
# =======================
else:
    st.markdown("## 📊 لوحة التحليل")

    if df.empty:
        st.warning("لا توجد بيانات في الشيت حتى الآن")
        st.stop()

    needed_cols = ["القسم", "اسم المعلمة"]
    for col in needed_cols:
        if col not in df.columns:
            st.error(f"العمود غير موجود في الشيت: {col}")
            st.write("الأعمدة الموجودة:", df.columns.tolist())
            st.stop()

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    filtered = df.copy()

    if allowed_dept != "الكل":
        filtered = filtered[
            filtered["القسم"].apply(normalize_dept) == normalize_dept(allowed_dept)
        ]
        st.sidebar.success(f"القسم: {allowed_dept}")

    st.sidebar.markdown("## 🎯 الفلاتر")

    if "السنة الدراسية" in filtered.columns:
        years = sorted(filtered["السنة الدراسية"].dropna().unique())
        selected_year = st.sidebar.selectbox("السنة الدراسية", ["الكل"] + years)
        if selected_year != "الكل":
            filtered = filtered[filtered["السنة الدراسية"] == selected_year]

    if "الفصل الدراسي" in filtered.columns:
        terms = sorted(filtered["الفصل الدراسي"].dropna().unique())
        selected_term = st.sidebar.selectbox("الفصل الدراسي", ["الكل"] + terms)
        if selected_term != "الكل":
            filtered = filtered[filtered["الفصل الدراسي"] == selected_term]

    if allowed_dept == "الكل":
        depts = sorted(filtered["القسم"].dropna().unique())
        selected_dept_filter = st.sidebar.selectbox("القسم", ["الكل"] + depts)
        if selected_dept_filter != "الكل":
            filtered = filtered[filtered["القسم"] == selected_dept_filter]

    teachers = sorted(filtered["اسم المعلمة"].dropna().unique())
    selected_teacher_filter = st.sidebar.selectbox("اسم المعلمة", ["الكل"] + teachers)
    if selected_teacher_filter != "الكل":
        filtered = filtered[filtered["اسم المعلمة"] == selected_teacher_filter]

    if "نوع الزيارة" in filtered.columns:
        visits = sorted(filtered["نوع الزيارة"].dropna().unique())
        selected_visit_filter = st.sidebar.selectbox("نوع الزيارة", ["الكل"] + visits)
        if selected_visit_filter != "الكل":
            filtered = filtered[filtered["نوع الزيارة"] == selected_visit_filter]

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f"""
        <div class="card">
            <div class="card-title">عدد الزيارات</div>
            <div class="card-value">{len(filtered)}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="card">
            <div class="card-title">عدد المعلمات</div>
            <div class="card-value">{filtered["اسم المعلمة"].nunique()}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="card">
            <div class="card-title">عدد الأقسام</div>
            <div class="card-value">{filtered["القسم"].nunique()}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">📋 البيانات</div>', unsafe_allow_html=True)
    st.dataframe(filtered, use_container_width=True)

    item_cols = [f"البند {i}" for i in range(1, 19) if f"البند {i}" in filtered.columns]

    if item_cols:
        st.markdown('<div class="section-title">📊 تحليل البنود</div>', unsafe_allow_html=True)

        rows = []
        for item in item_cols:
            counts = filtered[item].value_counts()
            for judgment, count in counts.items():
                rows.append({
                    "البند": item,
                    "الحكم": judgment,
                    "العدد": count
                })

        item_df = pd.DataFrame(rows)

        fig = px.bar(
            item_df,
            x="العدد",
            y="البند",
            color="الحكم",
            orientation="h",
            barmode="stack",
            title="توزيع الأحكام حسب البنود"
        )

        fig.update_layout(height=700, title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)

    if "القسم" in filtered.columns:
        st.markdown('<div class="section-title">📊 عدد الزيارات حسب القسم</div>', unsafe_allow_html=True)

        dept_count = filtered["القسم"].value_counts().reset_index()
        dept_count.columns = ["القسم", "عدد الزيارات"]

        fig_dept = px.bar(
            dept_count,
            x="القسم",
            y="عدد الزيارات",
            text="عدد الزيارات",
            title="عدد الزيارات حسب القسم"
        )

        fig_dept.update_layout(title_x=0.5)
        st.plotly_chart(fig_dept, use_container_width=True)

# =======================
# الفوتر
# =======================
st.markdown("""
<hr style="margin-top:40px;">

<div style="
display:flex;
justify-content:space-between;
font-size:16px;
font-weight:600;
color:#374151;
padding:10px 20px;
">

<div>مديرة المدرسة: أ. خلود يعقوب</div>
<div>المديرة المساعدة: أ. سامية سلمان</div>
<div>تصميم وبرمجة: أ. عفاف حسين</div>

</div>
""", unsafe_allow_html=True)