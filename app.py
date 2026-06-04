import streamlit as st
import pandas as pd
import requests
import plotly.express as px

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbziZ27mG690ZT02YN1LqbvWJLZ-rprnHK9qmXDDXcTvQVmnB-Phpm0J4DKjsg6Ts07xJQ/exec"
HEADER_PATH = "header.png"

st.set_page_config(page_title="نظام الزيارات الصفية", layout="wide")

JUDGMENT_WEIGHTS = {
    "يفي بالتوقعات جزئياً": 1,
    "يفي بالتوقعات": 2,
    "يتجاوز التوقعات": 3,
    "يتجاوز التوقعات بكثير": 4
}

JUDGMENT_ORDER = [
    "يفي بالتوقعات جزئياً",
    "يفي بالتوقعات",
    "يتجاوز التوقعات",
    "يتجاوز التوقعات بكثير"
]

MONTHS = [
    "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو"
]

VISITOR_TYPES = [
    "زيارة القيادة العليا لجميع المعلمات",
    "زيارة القيادة العليا للقيادة الوسطى",
    "زيارة الأيام الحية للقيادة الوسطى",
    "زيارة الأيام الحية لجميع المعلمات",
    "زيارة القيادة الوسطى لجميع المعلمات",
    "التقييم الذاتي",
    "التوأمة الموجهة"
]

ITEMS_STRUCTURE = {
    "الإنجاز الأكاديمي": [
        (1, "إظهار الطلبة المعارف والمهارات الأساسية وفقاً لمرحلتهم التعليمية."),
        (2, "تحقيق الطلبة التقدم خلال الدروس، واكتسابهم مهارات التعلم.")
    ],
    "التخطيط وإدارة الموقف التعليمي": [
        (3, "اتساق تخطيط الدروس مع الكفايات التعليمية للمنهج، ومراعاته احتياجات الطلبة."),
        (4, "توفير بيئة تعلم آمنة ومحفزة خالية من المخاطر لضمان إنتاجية التعلم."),
        (5, "تضمين الموقف التعليمي إرشادات وتوجيهات واضحة."),
        (6, "استثمار الوقت بما يحقق أهداف التعلم بصورة منتجة."),
        (7, "تحفيز الطلبة ورفع دافعيتهم بأساليب تمكنهم من المشاركة في التعلم وبناء شخصياتهم.")
    ],
    "التعليم والتعلم والتقويم": [
        (8, "سلامة المادة العلمية ومراعاتها كفايات المنهج والمستويات المتوقعة للمرحلة التعليمية."),
        (9, "توظيف إستراتيجيات تعليم وتعلم فاعلة، تسهم في دمج الطلبة على اختلاف احتياجاتهم."),
        (10, "توظيف التقويم والاستفادة من نتائجه في دعم جميع فئات المتعلمين وفق احتياجاتهم."),
        (11, "تنمية مهارات التفكير العليا للطلبة وتحدي قدراتهم."),
        (12, "توظيف التعليم المتمايز لتلبية احتياجات الطلبة المتنوعة على اختلاف فئاتهم.")
    ],
    "الموارد التعليمية والتكنولوجية": [
        (13, "توظيف المصادر والموارد التعليمية والتكنولوجية في عمليات التعليم والتعلم."),
        (14, "تنمية مهارات الطلبة التكنولوجية ومهارات البحث والتعلم الذاتي، وتشجيعهم على إنتاج المحتوى التعليمي الرقمي.")
    ],
    "التطور الشخصي للطلبة": [
        (15, "التزام الطلبة بالقيم الإسلامية، والوطنية، والرقمية، والاستعمال الآمن للتكنولوجيا."),
        (16, "التزام الطلبة السلوك الإيجابي نحو التعلم، والانضباط الذاتي، وتحمل المسؤوليات المختلفة."),
        (17, "قدرة الطلبة على التواصل والمشاركة الفاعلة خلال تعلمهم."),
        (18, "إظهار الطلبة الثقة بالنفس، والقدرة على القيادة، والمبادرة، والابتكار.")
    ]
}

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

st.markdown("""
<style>
.stApp {
    direction: rtl;
    background: linear-gradient(135deg, #f7f9ff, #fff8f1);
}
.big-title {
    text-align: center;
    font-size: 42px;
    font-weight: 900;
    color: #b91c1c;
    margin-bottom: 20px;
}
.domain-title {
    background: #d9eaf7;
    color: #003b5c;
    padding: 14px;
    border-radius: 12px;
    font-size: 24px;
    font-weight: 900;
    text-align: center;
    margin-top: 28px;
    margin-bottom: 12px;
}
.item-box {
    background: #f2f2f2;
    border: 1px solid #cfcfcf;
    border-radius: 10px;
    padding: 14px;
    font-size: 19px;
    font-weight: 700;
    text-align: right;
}
.kpi-card {
    background: white;
    border-radius: 18px;
    padding: 22px;
    text-align: center;
    box-shadow: 0 3px 10px rgba(0,0,0,0.08);
    border-top: 6px solid #2563eb;
}
.kpi-title {
    font-size: 17px;
    color: #374151;
    font-weight: 700;
}
.kpi-value {
    font-size: 31px;
    color: #111827;
    font-weight: 900;
}
.footer-box {
    display:flex;
    justify-content:space-between;
    font-size:16px;
    font-weight:600;
    color:#374151;
    padding:10px 20px;
}
@media (max-width: 768px) {
    .big-title {font-size: 30px;}
    .domain-title {font-size: 20px;}
    .item-box {font-size: 16px;}
    .footer-box {display:block; text-align:center; line-height:2;}
}
</style>
""", unsafe_allow_html=True)

try:
    st.image(HEADER_PATH, use_container_width=True)
except:
    pass

st.markdown('<div class="big-title">نظام الزيارات الصفية</div>', unsafe_allow_html=True)


def normalize_text(x):
    return (
        str(x)
        .strip()
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
    )


@st.cache_data(ttl=60)
def get_sheet_data(sheet_name):
    res = requests.get(GOOGLE_SCRIPT_URL, params={"sheet_name": sheet_name}, timeout=25)
    res.raise_for_status()
    data = res.json()
    return pd.DataFrame(data)


def send_to_google_sheet(row):
    payload = {
        "sheet_name": "Classroom_Visits",
        "row": row
    }
    res = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=25)
    res.raise_for_status()
    return res.json()


def calculate_percentage(df):
    item_cols = [f"بند {i}" for i in range(1, 19) if f"بند {i}" in df.columns]
    if df.empty or not item_cols:
        return 0

    values = []
    for col in item_cols:
        values.extend(df[col].map(JUDGMENT_WEIGHTS).dropna().tolist())

    if not values:
        return 0

    return round((sum(values) / (len(values) * 4)) * 100, 1)


def get_general_judgment(percent):
    if percent >= 90:
        return "يتجاوز التوقعات بكثير"
    elif percent >= 75:
        return "يتجاوز التوقعات"
    elif percent >= 60:
        return "يفي بالتوقعات"
    else:
        return "يفي بالتوقعات جزئياً"


def kpi_card(title, value):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def filter_dataframe(df, allowed_dept):
    st.markdown("### 🔍 الفلاتر")

    c1, c2, c3, c4, c5 = st.columns(5)

    filtered = df.copy()

    if "نوع السجل" not in filtered.columns:
        filtered["نوع السجل"] = "زيارة صفية"

    with c1:
        years = ["الكل"] + sorted(filtered["السنة الدراسية"].dropna().astype(str).unique().tolist()) if "السنة الدراسية" in filtered.columns else ["الكل"]
        year = st.selectbox("السنة الدراسية", years)

    if year != "الكل":
        filtered = filtered[filtered["السنة الدراسية"].astype(str) == year]

    with c2:
        semesters = ["الكل"] + sorted(filtered["الفصل الدراسي"].dropna().astype(str).unique().tolist()) if "الفصل الدراسي" in filtered.columns else ["الكل"]
        semester = st.selectbox("الفصل الدراسي", semesters)

    if semester != "الكل":
        filtered = filtered[filtered["الفصل الدراسي"].astype(str) == semester]

    with c3:
        months = ["الكل"] + [m for m in MONTHS if "الشهر" in filtered.columns and m in filtered["الشهر"].astype(str).unique()]
        month = st.selectbox("الشهر", months)

    if month != "الكل":
        filtered = filtered[filtered["الشهر"].astype(str) == month]

    with c4:
        record_types = ["الكل"] + sorted(filtered["نوع السجل"].dropna().astype(str).unique().tolist())
        record_type = st.selectbox("نوع السجل", record_types)

    if record_type != "الكل":
        filtered = filtered[filtered["نوع السجل"].astype(str) == record_type]

    if allowed_dept == "الكل":
        with c5:
            depts = ["الكل"] + sorted(filtered["القسم الأكاديمي"].dropna().astype(str).unique().tolist()) if "القسم الأكاديمي" in filtered.columns else ["الكل"]
            dept = st.selectbox("القسم الأكاديمي", depts)

        if dept != "الكل":
            filtered = filtered[filtered["القسم الأكاديمي"].astype(str) == dept]
    else:
        filtered = filtered[
            filtered["القسم الأكاديمي"].apply(normalize_text) == normalize_text(allowed_dept)
        ]

    teachers = ["الكل"] + sorted(filtered["اسم المعلمة"].dropna().astype(str).unique().tolist()) if "اسم المعلمة" in filtered.columns else ["الكل"]
    teacher = st.selectbox("اسم المعلمة", teachers)

    if teacher != "الكل":
        filtered = filtered[filtered["اسم المعلمة"].astype(str) == teacher]

    return filtered


def show_analysis(df, allowed_dept):
    if df.empty:
        st.warning("لا توجد بيانات للعرض حالياً.")
        return

    filtered = filter_dataframe(df, allowed_dept)

    if filtered.empty:
        st.warning("لا توجد بيانات حسب الفلاتر المختارة.")
        return

    percent = calculate_percentage(filtered)
    judgment = get_general_judgment(percent)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("عدد السجلات", len(filtered))
    with c2:
        kpi_card("عدد المعلمات", filtered["اسم المعلمة"].nunique() if "اسم المعلمة" in filtered.columns else 0)
    with c3:
        kpi_card("النسبة العامة", f"{percent}%")
    with c4:
        kpi_card("الحكم العام", judgment)

    st.divider()

    item_cols = [f"بند {i}" for i in range(1, 19) if f"بند {i}" in filtered.columns]

    st.markdown("### 📊 توزيع الأحكام")
    all_judgments = []
    for col in item_cols:
        all_judgments.extend(filtered[col].dropna().astype(str).tolist())

    judgment_df = pd.DataFrame({"الحكم": all_judgments})
    if not judgment_df.empty:
        counts = judgment_df["الحكم"].value_counts().reindex(JUDGMENT_ORDER).dropna().reset_index()
        counts.columns = ["الحكم", "العدد"]
        counts["النسبة"] = round(counts["العدد"] / counts["العدد"].sum() * 100, 1)

        fig = px.pie(counts, names="الحكم", values="العدد", hole=0.35)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(counts, use_container_width=True, hide_index=True)

    st.markdown("### 🧩 تحليل المجالات الخمسة")
    domains_result = []

    for domain, items in ITEMS_STRUCTURE.items():
        domain_cols = [f"بند {num}" for num, _ in items if f"بند {num}" in filtered.columns]
        values = []
        for col in domain_cols:
            values.extend(filtered[col].map(JUDGMENT_WEIGHTS).dropna().tolist())

        if values:
            domain_percent = round((sum(values) / (len(values) * 4)) * 100, 1)
            domains_result.append({
                "المجال": domain,
                "النسبة": domain_percent,
                "الحكم": get_general_judgment(domain_percent)
            })

    domains_df = pd.DataFrame(domains_result)
    if not domains_df.empty:
        fig = px.bar(domains_df, x="النسبة", y="المجال", orientation="h", text="النسبة")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(domains_df, use_container_width=True, hide_index=True)

    st.markdown("### 📌 تحليل البنود الـ 18")
    items_result = []

    for i in range(1, 19):
        col = f"بند {i}"
        if col in filtered.columns:
            values = filtered[col].map(JUDGMENT_WEIGHTS).dropna().tolist()
            if values:
                item_percent = round((sum(values) / (len(values) * 4)) * 100, 1)
                items_result.append({
                    "البند": col,
                    "النسبة": item_percent,
                    "الحكم": get_general_judgment(item_percent)
                })

    items_df = pd.DataFrame(items_result)
    if not items_df.empty:
        fig = px.bar(items_df, x="النسبة", y="البند", orientation="h", text="النسبة")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(items_df, use_container_width=True, hide_index=True)

    st.markdown("### 👩‍🏫 تحليل المعلمات")
    if "اسم المعلمة" in filtered.columns:
        teacher_rows = []
        for teacher_name, group in filtered.groupby("اسم المعلمة"):
            p = calculate_percentage(group)
            teacher_rows.append({
                "اسم المعلمة": teacher_name,
                "عدد السجلات": len(group),
                "النسبة": p,
                "الحكم": get_general_judgment(p)
            })

        teachers_analysis = pd.DataFrame(teacher_rows).sort_values("النسبة", ascending=False)
        st.dataframe(teachers_analysis, use_container_width=True, hide_index=True)

    if allowed_dept == "الكل" and "القسم الأكاديمي" in filtered.columns:
        st.markdown("### 🏫 مقارنة الأقسام")
        dept_rows = []
        for dept, group in filtered.groupby("القسم الأكاديمي"):
            p = calculate_percentage(group)
            dept_rows.append({
                "القسم الأكاديمي": dept,
                "عدد السجلات": len(group),
                "النسبة": p,
                "الحكم": get_general_judgment(p)
            })

        dept_analysis = pd.DataFrame(dept_rows).sort_values("النسبة", ascending=False)
        fig = px.bar(dept_analysis, x="القسم الأكاديمي", y="النسبة", text="النسبة")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dept_analysis, use_container_width=True, hide_index=True)

    st.markdown("### 📝 الملاحظات النصية")
    text_cols = [
        "نجاحات المعلم",
        "جوانب بحاجة إلى تطوير",
        "نقاط القوة في أدائي العام",
        "نقاط الضعف التي تحتاج إلى تطوير",
        "الدعم المطلوب من زيارات القيادة الوسطى",
        "مقترحاتي لتطوير أدائي",
        "الأهداف التعليمية للحصة",
        "أساليب واستراتيجيات التدريس الملحوظة",
        "ما الذي يمكن أن أستفيد منه لتطوير ممارساتي التدريسية",
        "أفكار جديدة يمكن أن أستفيد منها لتطوير ممارساتي التدريسية",
        "توصيات المعلم المزور"
    ]

    available_text_cols = [c for c in text_cols if c in filtered.columns]
    if available_text_cols:
        st.dataframe(
            filtered[["اسم المعلمة", "القسم الأكاديمي", "نوع السجل", "الشهر"] + available_text_cols],
            use_container_width=True,
            hide_index=True
        )


def show_form(teachers_df, allowed_dept):
    st.markdown("## 📝 استمارة الزيارات الصفية")

    if "القسم الأكاديمي" not in teachers_df.columns or "اسم المعلمة" not in teachers_df.columns:
        st.error("لازم يكون في شيت Teachers عمودين باسم: القسم الأكاديمي، اسم المعلمة")
        st.stop()

    departments = sorted(
        teachers_df["القسم الأكاديمي"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        if allowed_dept == "الكل":
            selected_dept = st.selectbox("القسم الأكاديمي", departments)
        else:
            selected_dept = allowed_dept
            st.info(f"القسم: {selected_dept}")

    filtered_teachers = teachers_df[
        teachers_df["القسم الأكاديمي"].apply(normalize_text) == normalize_text(selected_dept)
    ]["اسم المعلمة"].dropna().astype(str).str.strip().unique()

    filtered_teachers = sorted([name for name in filtered_teachers if name and name.lower() != "nan"])

    with c2:
        teacher_name = st.selectbox("اسم المعلمة", filtered_teachers) if filtered_teachers else st.text_input("اسم المعلمة")

    with c3:
        visit_type = st.selectbox("الزائر", VISITOR_TYPES)

    c4, c5, c6 = st.columns(3)

    with c4:
        school_year = st.selectbox("السنة الدراسية", ["2024-2025", "2025-2026", "2026-2027"])

    with c5:
        semester = st.selectbox("الفصل الدراسي", ["الفصل الدراسي الأول", "الفصل الدراسي الثاني"])

    with c6:
        month = st.selectbox("الشهر", MONTHS)

    is_self_assessment = visit_type == "التقييم الذاتي"
    is_peer_coaching = visit_type == "التوأمة الموجهة"

    st.markdown(
        '<div style="text-align:center; font-size:30px; font-weight:900; margin-top:25px;">بنود الملاحظة</div>',
        unsafe_allow_html=True
    )

    answers = {}

    for domain, items in ITEMS_STRUCTURE.items():
        st.markdown(f'<div class="domain-title">{domain}</div>', unsafe_allow_html=True)

        for item_number, item_text in items:
            col_text, col_choice = st.columns([3, 2])

            with col_text:
                st.markdown(
                    f'<div class="item-box"><b>{item_number}.</b> {item_text}</div>',
                    unsafe_allow_html=True
                )

            with col_choice:
                answers[f"بند {item_number}"] = st.radio(
                    "اختيار الحكم",
                    JUDGMENT_ORDER,
                    horizontal=True,
                    key=f"item_{item_number}",
                    label_visibility="collapsed"
                )

    st.divider()
    st.markdown("### 📝 البيانات الختامية")

    strengths = ""
    improvements = ""
    weaknesses = ""
    support_needed = ""
    suggestions = ""

    visiting_teacher = ""
    visiting_teacher_dept = ""
    visiting_teacher_school = ""
    visited_teacher_school = ""
    lesson_goals = ""
    observed_strategies = ""
    useful_practices = ""
    new_ideas = ""
    visited_teacher_recommendations = ""

    if is_self_assessment:
        strengths = st.text_area("نقاط القوة في أدائي العام")
        weaknesses = st.text_area("نقاط الضعف التي تحتاج إلى تطوير")
        support_needed = st.text_area("ما نوع الدعم الذي أحتاجه من زيارات القيادة الوسطى لجميع المعلمات لتطوير أدائي؟")
        suggestions = st.text_area("مقترحاتي لتطوير أدائي في المواقف التعليمية")

    elif is_peer_coaching:
        c1, c2 = st.columns(2)
        with c1:
            visiting_teacher = st.text_input("المعلم الزائر")
            visiting_teacher_dept = st.text_input("القسم الأكاديمي للمعلم الزائر")
            visiting_teacher_school = st.text_input("اسم المدرسة للمعلم الزائر")
        with c2:
            visited_teacher_school = st.text_input("اسم المدرسة للمعلم المزور")

        lesson_goals = st.text_area("الأهداف التعليمية للحصة")
        observed_strategies = st.text_area("أساليب واستراتيجيات التدريس الملحوظة")
        useful_practices = st.text_area("ما الذي يمكن أن أستفيد منه لتطوير ممارساتي التدريسية")
        new_ideas = st.text_area("أفكار جديدة يمكن أن أستفيد منها لتطوير ممارساتي التدريسية")
        visited_teacher_recommendations = st.text_area("توصيات المعلم المزور - خاص بالمعلم المزور")

    else:
        strengths = st.text_area("نجاحات المعلم")
        improvements = st.text_area("جوانب بحاجة إلى تطوير")

    if st.button("💾 حفظ السجل", use_container_width=True):
        record_type = (
            "تقييم ذاتي" if is_self_assessment
            else "توأمة موجهة" if is_peer_coaching
            else "زيارة صفية"
        )

        row = {
            "نوع السجل": record_type,
            "السنة الدراسية": school_year,
            "الفصل الدراسي": semester,
            "القسم الأكاديمي": selected_dept,
            "اسم المعلمة": teacher_name,
            "الزائر": visit_type,
            "الشهر": month,
            "نوع الزيارة": visit_type,

            "بند 1": answers["بند 1"],
            "بند 2": answers["بند 2"],
            "بند 3": answers["بند 3"],
            "بند 4": answers["بند 4"],
            "بند 5": answers["بند 5"],
            "بند 6": answers["بند 6"],
            "بند 7": answers["بند 7"],
            "بند 8": answers["بند 8"],
            "بند 9": answers["بند 9"],
            "بند 10": answers["بند 10"],
            "بند 11": answers["بند 11"],
            "بند 12": answers["بند 12"],
            "بند 13": answers["بند 13"],
            "بند 14": answers["بند 14"],
            "بند 15": answers["بند 15"],
            "بند 16": answers["بند 16"],
            "بند 17": answers["بند 17"],
            "بند 18": answers["بند 18"],

            "نجاحات المعلم": strengths if not is_self_assessment else "",
            "جوانب بحاجة إلى تطوير": improvements,

            "نقاط القوة في أدائي العام": strengths if is_self_assessment else "",
            "نقاط الضعف التي تحتاج إلى تطوير": weaknesses,
            "الدعم المطلوب من زيارات القيادة الوسطى": support_needed,
            "مقترحاتي لتطوير أدائي": suggestions,

            "المعلم الزائر": visiting_teacher,
            "القسم الأكاديمي للمعلم الزائر": visiting_teacher_dept,
            "اسم المدرسة للمعلم الزائر": visiting_teacher_school,
            "اسم المدرسة للمعلم المزور": visited_teacher_school,
            "الأهداف التعليمية للحصة": lesson_goals,
            "أساليب واستراتيجيات التدريس الملحوظة": observed_strategies,
            "ما الذي يمكن أن أستفيد منه لتطوير ممارساتي التدريسية": useful_practices,
            "أفكار جديدة يمكن أن أستفيد منها لتطوير ممارساتي التدريسية": new_ideas,
            "توصيات المعلم المزور": visited_teacher_recommendations
        }

        try:
            send_to_google_sheet(row)
            st.cache_data.clear()
            st.success("تم حفظ السجل بنجاح ✅")
        except Exception as e:
            st.error("حدث خطأ أثناء الحفظ")
            st.write(e)


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

try:
    teachers_df = get_sheet_data("Teachers")
except Exception as e:
    st.error("حدث خطأ في تحميل بيانات المعلمات من Google Sheet")
    st.write(e)
    st.stop()

if page == "إدخال زيارة صفية":
    show_form(teachers_df, allowed_dept)

else:
    st.markdown("## 📊 لوحة التحليل")

    try:
        visits_df = get_sheet_data("Classroom_Visits")
        visits_df.columns = [str(c).strip() for c in visits_df.columns]
        show_analysis(visits_df, allowed_dept)
    except Exception as e:
        st.error("حدث خطأ في تحميل بيانات الزيارات من Google Sheet")
        st.write(e)

st.markdown("""
<hr style="margin-top:40px;">
<div class="footer-box">
<div>مديرة المدرسة: أ. خلود يعقوب</div>
<div>المديرة المساعدة: أ. سامية سلمان</div>
<div>تصميم وبرمجة: أ. عفاف حسين</div>
</div>
""", unsafe_allow_html=True)
