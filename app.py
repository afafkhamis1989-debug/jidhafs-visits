import streamlit as st
import pandas as pd
import requests

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
.item-box {
    background: white;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 8px;
    border-right: 5px solid #93c5fd;
}
.domain-title {
    background: #dbeafe;
    padding: 12px;
    border-radius: 14px;
    font-size: 22px;
    font-weight: 900;
    margin-top: 25px;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)

try:
    st.image(HEADER_PATH, use_container_width=True)
except:
    pass

st.markdown('<div class="big-title">📊 نظام الزيارات الصفية</div>', unsafe_allow_html=True)

@st.cache_data(ttl=60)
def load_teachers():
    res = requests.get(GOOGLE_SCRIPT_URL, timeout=20)
    res.raise_for_status()
    return pd.DataFrame(res.json())

def send_to_google_sheet(row):
    payload = {
        "sheet_name": "Classroom_Visits",
        "row": row
    }
    res = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=20)
    res.raise_for_status()
    return res.json()

def normalize_text(x):
    return (
        str(x)
        .strip()
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
    )

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

try:
    teachers_df = load_teachers()
    teachers_df.columns = [str(c).strip() for c in teachers_df.columns]
except Exception as e:
    st.error("حدث خطأ في تحميل بيانات المعلمات من Google Sheet")
    st.write(e)
    st.stop()

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

    months = [
        "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو"
    ]

    items_structure = {
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

    if allowed_dept == "الكل":
        selected_dept = st.selectbox("القسم الأكاديمي", departments)
    else:
        selected_dept = allowed_dept
        st.info(f"القسم: {selected_dept}")

    filtered_teachers = teachers_df[
        teachers_df["القسم الأكاديمي"].apply(normalize_text)
        == normalize_text(selected_dept)
    ]["اسم المعلمة"].dropna().astype(str).str.strip().unique()

    filtered_teachers = sorted([
        name for name in filtered_teachers
        if name and name.lower() != "nan"
    ])

    if filtered_teachers:
        teacher_name = st.selectbox("اسم المعلمة", filtered_teachers)
    else:
        teacher_name = st.text_input("اسم المعلمة")

    with st.form("visit_form"):
        school_year = st.selectbox(
            "السنة الدراسية",
            ["2024-2025", "2025-2026", "2026-2027"]
        )

        semester = st.selectbox(
            "الفصل الدراسي",
            ["الفصل الدراسي الأول", "الفصل الدراسي الثاني"]
        )

        month = st.selectbox("الشهر", months)

        visit_type = st.selectbox("نوع الزيارة", visitor_types)

        st.markdown("### بنود التقييم")

        answers = {}

        for domain, items in items_structure.items():
            st.markdown(f'<div class="domain-title">{domain}</div>', unsafe_allow_html=True)

            for item_number, item_text in items:
                st.markdown(
                    f'<div class="item-box"><b>{item_number}.</b> {item_text}</div>',
                    unsafe_allow_html=True
                )

                

        strengths = st.text_area("نجاحات المعلم")
        improvements = st.text_area("جوانب بحاجة إلى تطوير")

        submitted = st.form_submit_button("💾 حفظ الزيارة")

    if submitted:
        row = {
            "السنة الدراسية": school_year,
            "الفصل الدراسي": semester,
            "القسم الأكاديمي": selected_dept,
            "اسم المعلمة": teacher_name,
            "الزائر": "",
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
            "نجاحات المعلم": strengths,
            "جوانب بحاجة إلى تطوير": improvements
        }

        try:
            result = send_to_google_sheet(row)
            st.cache_data.clear()
            st.success("تم حفظ الزيارة بنجاح ✅")
            st.write(result)
        except Exception as e:
            st.error("حدث خطأ أثناء الإرسال")
            st.write(e)

else:
    st.markdown("## 📊 لوحة التحليل")
    st.info("لوحة التحليل بنرجع نربطها بعد ما نخلص الاستمارة.")
    st.dataframe(teachers_df, use_container_width=True)

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