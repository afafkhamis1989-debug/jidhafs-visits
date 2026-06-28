import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.graph_objects as go
import plotly.express as px
import math
import os
import sys
import subprocess

# ── PDF — استيراد المكتبات والخط العربي تلقائياً ─────────────────────────────
# ملاحظة:
# ضعي المكتبات في requirements.txt ولا تثبتيها من داخل Streamlit.
# reportlab
# arabic-reshaper
# python-bidi

PDF_READY = False
PDF_ERROR = ""
_reg_font = None
_reg_bold = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable,
                                    BaseDocTemplate, Frame, PageTemplate)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import arabic_reshaper
    from bidi.algorithm import get_display
    PDF_READY = True
except Exception as e:
    PDF_READY = False
    PDF_ERROR = f"فشل استيراد مكتبات PDF: {e}"


def _safe_base_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def _download_file(url, target_path, timeout=25):
    """تحميل ملف صغير مثل الخطوط عند الحاجة فقط."""
    import urllib.request
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if len(data) < 10000:
        raise RuntimeError("الملف المحمّل صغير جداً وقد لا يكون خطاً صحيحاً.")
    with open(target_path, "wb") as f:
        f.write(data)
    return target_path


def _ensure_arabic_fonts():
    """
    يحاول إيجاد خط عربي محلياً، وإذا لم يجده يحمله تلقائياً في مجلد .streamlit_fonts.
    لا يحتاج منك إنشاء مجلد fonts يدوياً.
    """
    base_dir = _safe_base_dir()
    cache_dir = os.path.join(base_dir, ".streamlit_fonts")

    amiri_r = os.path.join(cache_dir, "Amiri-Regular.ttf")
    amiri_b = os.path.join(cache_dir, "Amiri-Bold.ttf")

    # تحميل Amiri تلقائياً إذا لم يوجد
    if not (os.path.exists(amiri_r) and os.path.exists(amiri_b)):
        download_sources = [
            (
                "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf",
                "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Bold.ttf",
            ),
            (
                "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf",
                "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Bold.ttf",
            ),
        ]
        for url_r, url_b in download_sources:
            try:
                _download_file(url_r, amiri_r)
                _download_file(url_b, amiri_b)
                break
            except Exception:
                try:
                    if os.path.exists(amiri_r):
                        os.remove(amiri_r)
                    if os.path.exists(amiri_b):
                        os.remove(amiri_b)
                except Exception:
                    pass

    candidates = [
        # الخط المحمّل تلقائياً
        (amiri_r, amiri_b),

        # خطوط مرفوعة مع المشروع
        (os.path.join(base_dir, "fonts", "Amiri-Regular.ttf"), os.path.join(base_dir, "fonts", "Amiri-Bold.ttf")),
        (os.path.join(base_dir, "Amiri-Regular.ttf"), os.path.join(base_dir, "Amiri-Bold.ttf")),

        # خطوط غالباً موجودة في Linux / Streamlit Cloud
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]

    errors = []
    for regular_path, bold_path in candidates:
        if os.path.exists(regular_path) and os.path.exists(bold_path):
            try:
                pdfmetrics.registerFont(TTFont("ArabicPDF", regular_path))
                pdfmetrics.registerFont(TTFont("ArabicPDF-Bold", bold_path))
                return "ArabicPDF", "ArabicPDF-Bold", ""
            except Exception as e:
                errors.append(f"{regular_path}: {e}")

    return None, None, "لم يتم العثور على خط عربي مناسب ولم ينجح تحميل Amiri تلقائياً. " + (" | ".join(errors[-3:]) if errors else "")


if PDF_READY:
    try:
        _reg_font, _reg_bold, _font_error = _ensure_arabic_fonts()
        if not _reg_font or not _reg_bold:
            PDF_READY = False
            PDF_ERROR = _font_error
    except Exception as e:
        PDF_READY = False
        PDF_ERROR = f"فشل تجهيز الخط العربي: {e}"

DEFAULT_EXCEL_URL = "https://moebh-my.sharepoint.com/:x:/g/personal/890302057_moe_bh/IQARg9ekg-gGR6izAPSeAlzTATuVdP8MoMG5g0O9aOIlGzI?e=vQIoab&download=1"
HEADER_PATH = "header.png"

st.set_page_config(
    page_title="نظام الزيارات الصفية",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# ✅ الألوان المصححة حسب الطلب
JUDGMENT_COLORS = {
    "يفي بالتوقعات جزئياً": "#f472b6",   # وردي
    "يفي بالتوقعات":         "#fbbf24",   # أصفر
    "يتجاوز التوقعات":       "#3b82f6",   # أزرق
    "يتجاوز التوقعات بكثير": "#10b981",   # أخضر
}

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

# قاموس أسماء البنود القصيرة للعرض في الرسوم البيانية
ITEM_NAMES = {
    1:  "إظهار المعارف والمهارات الأساسية",
    2:  "تحقيق التقدم واكتساب مهارات التعلم",
    3:  "اتساق التخطيط مع الكفايات واحتياجات الطلبة",
    4:  "توفير بيئة تعلم آمنة ومحفزة",
    5:  "تضمين الموقف إرشادات وتوجيهات واضحة",
    6:  "استثمار الوقت لتحقيق أهداف التعلم",
    7:  "تحفيز الطلبة ورفع دافعيتهم",
    8:  "سلامة المادة العلمية ومراعاة الكفايات",
    9:  "توظيف استراتيجيات تعليم وتعلم فاعلة",
    10: "توظيف التقويم ودعم فئات المتعلمين",
    11: "تنمية مهارات التفكير العليا",
    12: "توظيف التعليم المتمايز",
    13: "توظيف الموارد التعليمية والتكنولوجية",
    14: "تنمية المهارات التكنولوجية والبحثية",
    15: "التزام القيم الإسلامية والوطنية والرقمية",
    16: "الانضباط الذاتي وتحمل المسؤولية",
    17: "التواصل والمشاركة الفاعلة",
    18: "الثقة بالنفس والقيادة والابتكار",
}

DOMAIN_ICONS = {
    "الإنجاز الأكاديمي": "🎓",
    "التخطيط وإدارة الموقف التعليمي": "📋",
    "التعليم والتعلم والتقويم": "📚",
    "الموارد التعليمية والتكنولوجية": "💻",
    "التطور الشخصي للطلبة": "🌱"
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

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap');

* { font-family: 'Tajawal', sans-serif !important; }

.stApp {
    direction: rtl;
    background: #f0f4f8;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f2044 0%, #1a3a6e 100%);
    border-left: none;
}
[data-testid="stSidebar"] * { color: #e8edf5 !important; }
[data-testid="stSidebar"] .stRadio label { font-size: 15px !important; padding: 6px 0; }
[data-testid="stSidebar"] h2 {
    color: #7eb3f7 !important; font-size: 18px !important;
    border-bottom: 1px solid rgba(126,179,247,0.3);
    padding-bottom: 8px; margin-bottom: 12px;
}
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(126,179,247,0.4) !important;
    color: white !important; border-radius: 8px !important;
}

.page-header {
    background: linear-gradient(135deg, #0f2044 0%, #1a3a6e 50%, #1e4d9b 100%);
    border-radius: 16px; padding: 28px 36px; margin-bottom: 24px; color: white;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 8px 32px rgba(15,32,68,0.25);
}
.page-header-title { font-size: 28px; font-weight: 900; margin: 0; letter-spacing: -0.5px; }
.page-header-sub { font-size: 14px; opacity: 0.75; margin-top: 4px; }
.page-header-badge {
    background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
    border-radius: 20px; padding: 6px 18px; font-size: 13px; font-weight: 700;
}

.section-title {
    display: flex; align-items: center; gap: 10px;
    font-size: 18px; font-weight: 800; color: #0f2044;
    margin: 28px 0 14px 0; padding-bottom: 8px; border-bottom: 2px solid #dbeafe;
}
.section-icon {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, #1a3a6e, #2563eb);
    border-radius: 8px; display: flex; align-items: center;
    justify-content: center; color: white; font-size: 16px;
}

.kpi-grid { display: flex; gap: 14px; margin-bottom: 8px; }
.kpi-card {
    flex: 1; background: white; border-radius: 14px; padding: 20px 18px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06); border-top: 4px solid #2563eb;
    text-align: center; transition: transform 0.2s;
}
.kpi-card:hover { transform: translateY(-2px); }
.kpi-card.green  { border-top-color: #10b981; }
.kpi-card.amber  { border-top-color: #fbbf24; }
.kpi-card.pink   { border-top-color: #f472b6; }
.kpi-card.blue   { border-top-color: #2563eb; }
.kpi-label { font-size: 13px; color: #6b7280; font-weight: 600; margin-bottom: 6px; }
.kpi-value { font-size: 30px; font-weight: 900; color: #111827; line-height: 1; }
.kpi-sub   { font-size: 12px; color: #9ca3af; margin-top: 4px; }

.badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 13px; font-weight: 700; }
.badge-green  { background: #d1fae5; color: #065f46; }
.badge-blue   { background: #dbeafe; color: #1e40af; }
.badge-amber  { background: #fef3c7; color: #92400e; }
.badge-pink   { background: #fce7f3; color: #9d174d; }

.domain-card {
    background: white; border-radius: 14px; padding: 18px 20px;
    margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    border-right: 5px solid #2563eb;
}
.domain-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.domain-name { font-size: 16px; font-weight: 800; color: #0f2044; }
.progress-bar-bg { height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden; }
.progress-bar-fill {
    height: 100%; border-radius: 4px;
    background: linear-gradient(90deg, #2563eb, #3b82f6); transition: width 0.6s ease;
}

.filter-panel {
    background: white; border-radius: 14px; padding: 20px 24px;
    margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); border: 1px solid #e5e7eb;
}
.filter-title { font-size: 15px; font-weight: 800; color: #374151; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }

.alert-card {
    background: #fff7ed; border: 1px solid #fed7aa; border-right: 4px solid #f97316;
    border-radius: 10px; padding: 12px 16px; margin-bottom: 8px;
    display: flex; align-items: center; justify-content: space-between;
}
.alert-name { font-size: 14px; font-weight: 700; color: #9a3412; }
.alert-info { font-size: 12px; color: #c2410c; }

.rank-card {
    background: white; border-radius: 12px; padding: 14px 18px;
    margin-bottom: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    display: flex; align-items: center; gap: 14px;
}
.rank-num {
    width: 32px; height: 32px; border-radius: 50%;
    background: linear-gradient(135deg, #1a3a6e, #2563eb);
    color: white; display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: 900; flex-shrink: 0;
}
.rank-info { flex: 1; }
.rank-name { font-size: 15px; font-weight: 700; color: #111827; }
.rank-sub  { font-size: 12px; color: #6b7280; }

.footer {
    background: #0f2044; border-radius: 12px; padding: 16px 28px;
    margin-top: 32px; display: flex; justify-content: space-between; align-items: center;
}
.footer span { color: #94a3b8; font-size: 13px; font-weight: 600; }
.footer .highlight { color: #7eb3f7; }

div[data-testid="stSelectbox"] > div { border-radius: 8px !important; }
.stButton > button {
    background: linear-gradient(135deg, #1a3a6e, #2563eb) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-weight: 700 !important; font-size: 16px !important;
    padding: 12px 28px !important; width: 100% !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #0f2044, #1a3a6e) !important; transform: translateY(-1px);
}
div[data-testid="stMetric"] { display: none; }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def normalize_text(x):
    return (str(x).strip()
            .replace("أ","ا").replace("إ","ا")
            .replace("آ","ا").replace("ة","ه"))


def clean_col_name(x):
    return str(x).replace("\xa0", " ").strip()


def combine_first_non_empty(df, candidates):
    found = [c for c in candidates if c in df.columns]
    if not found:
        return pd.Series([pd.NA] * len(df), index=df.index)
    result = df[found[0]].copy()
    for col in found[1:]:
        result = result.combine_first(df[col])
    return result


def guess_ms_forms_download_urls(url):
    base = str(url).strip()
    if not base:
        return []
    # تأكد من وجود download=1
    if "download=1" not in base:
        joiner = "&" if "?" in base else "?"
        return [base, base + joiner + "download=1"]
    return [base]


@st.cache_data(ttl=120, show_spinner=False)
def load_excel_from_url(url):
    last_error = None
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
    })
    for test_url in guess_ms_forms_download_urls(url):
        try:
            res = session.get(test_url, timeout=40, allow_redirects=True)
            res.raise_for_status()
            content_type = res.headers.get("content-type", "").lower()
            if "text/html" in content_type and b"<html" in res.content[:500].lower():
                last_error = "الرابط رجّع صفحة HTML — يحتاج تسجيل دخول أو رابط تنزيل مباشر."
                continue
            return pd.read_excel(BytesIO(res.content), sheet_name="Main")
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(last_error or "تعذّر تحميل ملف Excel من الرابط.")


@st.cache_data(ttl=120, show_spinner=False)
def load_excel_from_upload(uploaded_file):
    return pd.read_excel(uploaded_file, sheet_name="Main")


def standardize_ms_forms_dataframe(raw_df):
    df = raw_df.copy()
    df.columns = [clean_col_name(c) for c in df.columns]

    out = pd.DataFrame(index=df.index)
    out["ID"] = combine_first_non_empty(df, ["ID"])
    out["وقت البدء"] = combine_first_non_empty(df, ["Start time", "وقت البدء"])
    out["وقت الإكمال"] = combine_first_non_empty(df, ["Completion time", "وقت الإكمال"])
    out["البريد الإلكتروني"] = combine_first_non_empty(df, ["Email", "البريد الإلكتروني"])
    out["اسم المعلمة"] = combine_first_non_empty(df, ["اسم المعلمة"])
    out["القسم الأكاديمي"] = combine_first_non_empty(df, ["القسم الأكاديمي", "الأقسام الأكاديمية"])
    out["السنة الدراسية"] = combine_first_non_empty(df, ["السنة الدراسية", "السنة الدراسية2"])
    out["الفصل الدراسي"] = combine_first_non_empty(df, ["الفصل الدراسي", "الفصل الدراسي2"])
    out["الشهر"] = combine_first_non_empty(df, ["الشهر"])
    out["الزائر"] = combine_first_non_empty(df, ["الزائر"])
    out["نوع السجل"] = combine_first_non_empty(df, ["استمارات للقيادة الوسطى", "نوع السجل"])
    out["عدد الزيارات"] = combine_first_non_empty(df, ["عدد الزيارات2", "عدد الزيارات"])

    item_patterns = {
        1: ["إظهار الطلبة المعارف والمهارات الأساسية", "اظهار الطلبة المعارف والمهارات الأساسية"],
        2: ["تحقيق الطلبة التقدم خلال الدروس"],
        3: ["اتساق تخطيط الدروس"],
        4: ["توفير بيئة تعلم"],
        5: ["تضمين الموقف التعليمي إرشادات"],
        6: ["استثمار الوقت"],
        7: ["تحفيز", "رفع دافعيتهم"],
        8: ["سلامة المادة العلمية"],
        9: ["توظيف إستراتيجيات تعليم وتعلم", "توظيف استراتيجيات تعليم وتعلم"],
        10: ["توظيف التقويم"],
        11: ["تنمية مهارات التفكير العليا"],
        12: ["التعليم التمايز", "التعليم المتمايز"],
        13: ["توظيف المصادر والموارد التعليمية"],
        14: ["تنمية مهارات الطلبة التكنولوجية"],
        15: ["التزام الطلبة بالقيم الإسلامية", "التزام الطلبة بالقيم الاسلامية"],
        16: ["التزام الطلبة السلوك الإيجابي", "التزام الطلبة السلوك الايجابي"],
        17: ["قدرة الطلبة على التواصل"],
        18: ["إظهار الطلبة الثقة بالنفس", "اظهار الطلبة الثقة بالنفس"],
    }

    for item_no, patterns in item_patterns.items():
        matches = []
        for col in df.columns:
            col_clean = clean_col_name(col)
            for pat in patterns:
                if pat in col_clean:
                    matches.append(col)
                    break
        out[f"بند {item_no}"] = combine_first_non_empty(df, matches)

    text_mapping = {
        "نجاحات المعلم": ["نجاحات المعلم"],
        "جوانب بحاجة إلى تطوير": ["جوانب بحاجة إلى تطوير"],
        "أبرز نقاط القوة": ["أبرز نقاط القوة"],
        "أبرز الجوانب التي تحتاج إلى تطوير": ["أبرز الجوانب التي تحتاج إلى تطوير"],
        "الدعم المقدم لها": ["الدعم المقدم لها"],
        "توظيف جوانب التميز لديها": ["توظيف جوانب التميز لديها"],
        "مدى التحسين في الأداء": ["مدى التحسين في الأداء"],
        "نقاط القوة في أدائي العام": ["نقاط القوة في أدائي العام"],
        "نقاط الضعف التي تحتاج إلى تطوير": ["نقاط الضعف التي تحتاج إلى تطوير"],
        "الدعم المطلوب من زيارات القيادة الوسطى": ["ما نوع الدعم الذي أحتاجه من القيادة الوسطى لتطوير أدائي", "الدعم المطلوب من زيارات القيادة الوسطى"],
        "مقترحاتي لتطوير أدائي": ["مقترحاتي لتطوير أدائي في المواقف التعليمية", "مقترحاتي لتطوير أدائي"],
        "المعلم الزائر": ["المعلم الزائر", "المعلم المزور"],
        "القسم الأكاديمي للمعلم الزائر": ["القسم الأكاديمي للمعلم الزائر", "القسم الأكاديمي للمعلم المزور"],
        "اسم المدرسة للمعلم الزائر": ["اسم المدرسة للمعلم الزائر"],
        "اسم المدرسة للمعلم المزور": ["اسم المدرسة للمعلم المزور", "اسم المدرسة (إذا كان/ت من مدرسة أخرى)"],
        "الأهداف التعليمية للحصة": ["الأهداف التعليمية للحصة"],
        "أساليب واستراتيجيات التدريس الملحوظة": ["أساليب واستراتيجيات التدريس الملحوظة"],
        "ما الذي يمكن أن أستفيد منه لتطوير ممارساتي التدريسية": ["ما الذي يمكن أن أستفيد منه لتطوير ممارساتي التدريسية"],
        "أفكار جديدة يمكن أن أستفيد منها لتطوير ممارساتي التدريسية": ["أفكار جديدة يمكن أن أستفيد منه لتطوير ممارساتي التدريسية", "أفكار جديدة يمكن أن أستفيد منها لتطوير ممارساتي التدريسية"],
        "توصيات المعلم المزور": ["توصيات المعلم المزور", "توصيات المعلم المزور (خاص بالمعلم المزور)"],
    }
    for out_col, candidates in text_mapping.items():
        out[out_col] = combine_first_non_empty(df, candidates)

    out["نوع السجل"] = out["نوع السجل"].astype("string").str.strip()
    out["نوع السجل"] = out["نوع السجل"].replace({
        "استمارة الزيارة الصفية": "زيارة صفية",
        "استمارة التقييم الذاتي": "تقييم ذاتي",
        "استمارة التوأمة الموجهة": "توأمة موجهة",
    })
    out["نوع السجل"] = out["نوع السجل"].fillna("زيارة صفية")
    out = out[out["اسم المعلمة"].notna() & (out["اسم المعلمة"].astype(str).str.strip() != "")]
    return out


def get_excel_url():
    try:
        return st.secrets.get("EXCEL_URL", DEFAULT_EXCEL_URL)
    except Exception:
        return DEFAULT_EXCEL_URL


def get_forms_data(uploaded_file=None):
    if uploaded_file is not None:
        raw = load_excel_from_upload(uploaded_file)
    else:
        raw = load_excel_from_url(get_excel_url())
    return standardize_ms_forms_dataframe(raw)


def calculate_percentage(df):
    item_cols = [f"بند {i}" for i in range(1,19) if f"بند {i}" in df.columns]
    if df.empty or not item_cols:
        return 0
    values = []
    for col in item_cols:
        values.extend(df[col].map(JUDGMENT_WEIGHTS).dropna().tolist())
    return round((sum(values)/(len(values)*4))*100, 1) if values else 0


def get_general_judgment(percent):
    if percent >= 90:   return "يتجاوز التوقعات بكثير"
    elif percent >= 75: return "يتجاوز التوقعات"
    elif percent >= 60: return "يفي بالتوقعات"
    else:               return "يفي بالتوقعات جزئياً"


def judgment_badge(judgment):
    mapping = {
        "يتجاوز التوقعات بكثير": "badge-green",
        "يتجاوز التوقعات":       "badge-blue",
        "يفي بالتوقعات":         "badge-amber",
        "يفي بالتوقعات جزئياً":  "badge-pink",
    }
    cls = mapping.get(judgment, "badge-blue")
    return f'<span class="badge {cls}">{judgment}</span>'


def kpi_card_html(label, value, color="blue", sub=""):
    return f"""
    <div class="kpi-card {color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
    </div>"""


def section_title(icon, text):
    st.markdown(f"""
    <div class="section-title">
        <div class="section-icon">{icon}</div>
        {text}
    </div>""", unsafe_allow_html=True)


def percent_color(p):
    if p >= 90: return "green"
    elif p >= 75: return "blue"
    elif p >= 60: return "amber"
    return "pink"


def make_rtl_bar_h(y_vals, x_vals, colors, title_text="", label_fontsize=13, right_margin=320):
    """
    رسم بياني أفقي حقيقي RTL:
    - النصوص (أسماء البنود) على اليمين
    - الأشرطة تمتد من اليمين إلى اليسار
    - الأرقام (%) تظهر على يسار الشريط خارجه
    الحيلة: نعكس محور X (autorange=reversed) ونضع النصوص side=right
    وتوضع النسب كـ x سالبة حتى تخرج جهة اليسار.
    """
    # نحوّل القيم إلى سالبة حتى تمتد من اليمين (0) إلى اليسار
    neg_x = [-v for v in x_vals]

    fig = go.Figure(go.Bar(
        x=neg_x,
        y=y_vals,
        orientation="h",
        marker_color=colors,
        text=[f"  {v}%  " for v in x_vals],
        textposition="outside",
        textfont=dict(size=label_fontsize, color="#111827", family="Tajawal"),
        hovertemplate="%{y}<br>النسبة: %{customdata}%<extra></extra>",
        customdata=x_vals,
    ))
    fig.update_layout(
        xaxis=dict(
            range=[-118, 0],          # السالب يسار، الصفر يمين
            showgrid=True,
            gridcolor="#f0f4f8",
            zeroline=True,
            zerolinecolor="#d1d5db",
            tickvals=[-100, -75, -50, -25, 0],
            ticktext=["100%", "75%", "50%", "25%", "0%"],
            tickfont=dict(size=11, family="Tajawal"),
            side="bottom",
        ),
        yaxis=dict(
            tickfont=dict(size=label_fontsize, family="Tajawal"),
            autorange="reversed",   # أعلى قيمة فوق
            side="right",           # ✅ أسماء البنود على اليمين
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=80, r=right_margin, t=20, b=30),
        font=dict(family="Tajawal"),
    )
    return fig



# ─── PDF Generator ────────────────────────────────────────────────────────────
def generate_pdf(filtered_df, allowed_dept, report_type="summary", dept_name="المدرسة"):
    """
    report_type: 'summary' = ملخص تنفيذي | 'detailed' = تفصيلي
    """
    if not PDF_READY:
        return None

    def ar(text):
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)

    # مسار الشعار — يبحث بجانب الملف أولاً ثم المجلد المعروف
    _base_dir = os.path.dirname(os.path.abspath(__file__))
    _header_candidates = [
        os.path.join(_base_dir, "header.png"),
        os.path.join(_base_dir, "fonts", "header.png"),
        "/home/claude/fonts/header.png",
    ]
    _header_img = next((p for p in _header_candidates if os.path.exists(p)), None)

    buf = BytesIO()

    # ── حجم الصفحة والهوامش ───────────────────────────────────────────────
    PAGE_W, PAGE_H = A4
    HEADER_H = 3.2 * cm   # ارتفاع منطقة الشعار
    TOP_MARGIN = HEADER_H + 0.5 * cm

    from reportlab.lib.utils import ImageReader

    # دالة رسم الشعار في رأس كل صفحة
    def _draw_header(canvas_obj, doc_obj):
        canvas_obj.saveState()
        if _header_img:
            canvas_obj.drawImage(
                _header_img,
                x=0, y=PAGE_H - HEADER_H,
                width=PAGE_W, height=HEADER_H,
                preserveAspectRatio=False,
                mask="auto",
            )
        # خط فاصل
        canvas_obj.setStrokeColor(colors.HexColor("#0f2044"))
        canvas_obj.setLineWidth(1)
        canvas_obj.line(1.5*cm, PAGE_H - HEADER_H - 0.15*cm, PAGE_W - 1.5*cm, PAGE_H - HEADER_H - 0.15*cm)
        # رقم الصفحة
        canvas_obj.setFont(_reg_font, 9)
        page_text = ar(f"صفحة {doc_obj.page}")
        canvas_obj.drawCentredString(PAGE_W / 2, 0.6 * cm, page_text)
        canvas_obj.restoreState()

    frame = Frame(
        x1=2*cm, y1=1.5*cm,
        width=PAGE_W - 4*cm,
        height=PAGE_H - TOP_MARGIN - 2*cm,
    )
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=TOP_MARGIN, bottomMargin=1.5*cm,
        title="تقرير الزيارات الصفية",
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_draw_header)])

    # ── أنماط ─────────────────────────────────────────────────────────────
    S = {
        "title":    ParagraphStyle("title",    fontName=_reg_bold,  fontSize=20, alignment=TA_CENTER, leading=28, spaceAfter=6),
        "subtitle": ParagraphStyle("subtitle", fontName=_reg_font,  fontSize=12, alignment=TA_CENTER, leading=18, textColor=colors.HexColor("#4b5563"), spaceAfter=4),
        "h2":       ParagraphStyle("h2",       fontName=_reg_bold,  fontSize=14, alignment=TA_RIGHT,  leading=22, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#0f2044")),
        "body":     ParagraphStyle("body",     fontName=_reg_font,  fontSize=11, alignment=TA_RIGHT,  leading=18),
        "kpi_val":  ParagraphStyle("kpi_val",  fontName=_reg_bold,  fontSize=22, alignment=TA_CENTER, leading=28),
        "kpi_lbl":  ParagraphStyle("kpi_lbl",  fontName=_reg_font,  fontSize=9,  alignment=TA_CENTER, leading=14, textColor=colors.HexColor("#6b7280")),
        "tbl_hdr":  ParagraphStyle("tbl_hdr",  fontName=_reg_bold,  fontSize=10, alignment=TA_CENTER, leading=14, textColor=colors.white),
        "tbl_cell": ParagraphStyle("tbl_cell", fontName=_reg_font,  fontSize=10, alignment=TA_RIGHT,  leading=14),
        "tbl_num":  ParagraphStyle("tbl_num",  fontName=_reg_bold,  fontSize=10, alignment=TA_CENTER, leading=14),
    }

    # ألوان الأحكام
    JCOLORS = {
        "يتجاوز التوقعات بكثير": colors.HexColor("#10b981"),
        "يتجاوز التوقعات":       colors.HexColor("#3b82f6"),
        "يفي بالتوقعات":         colors.HexColor("#fbbf24"),
        "يفي بالتوقعات جزئياً":  colors.HexColor("#f472b6"),
    }

    story = []

    # ── غلاف ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph(ar("تقرير الزيارات الصفية"), S["title"]))
    story.append(Paragraph(ar("مدرسة جدحفص الثانوية للبنات"), S["subtitle"]))
    story.append(Paragraph(ar(f"القسم: {dept_name}"), S["subtitle"]))

    # تاريخ التقرير
    import datetime
    today = datetime.date.today().strftime("%Y/%m/%d")
    story.append(Paragraph(ar(f"تاريخ التقرير: {today}"), S["subtitle"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0f2044")))
    story.append(Spacer(1, 0.5*cm))

    # ── KPIs ──────────────────────────────────────────────────────────────
    percent  = calculate_percentage(filtered_df)
    judgment = get_general_judgment(percent)
    n_rec    = len(filtered_df)
    n_teach  = filtered_df["اسم المعلمة"].nunique() if "اسم المعلمة" in filtered_df.columns else 0
    j_color  = JCOLORS.get(judgment, colors.HexColor("#2563eb"))

    kpi_data = [
        [Paragraph(ar("إجمالي السجلات"), S["kpi_lbl"]),
         Paragraph(ar("عدد المعلمات"),   S["kpi_lbl"]),
         Paragraph(ar("النسبة العامة"),  S["kpi_lbl"]),
         Paragraph(ar("الحكم العام"),    S["kpi_lbl"])],
        [Paragraph(ar(str(n_rec)),   S["kpi_val"]),
         Paragraph(ar(str(n_teach)), S["kpi_val"]),
         Paragraph(ar(f"{percent}%"), ParagraphStyle("kv2", fontName=_reg_bold, fontSize=22, alignment=TA_CENTER, leading=28, textColor=j_color)),
         Paragraph(ar(judgment),      ParagraphStyle("kv3", fontName=_reg_bold, fontSize=13, alignment=TA_CENTER, leading=20, textColor=j_color))],
    ]
    kpi_tbl = Table(kpi_data, colWidths=[3.8*cm]*4)
    kpi_tbl.setStyle(TableStyle([
        ("BOX",         (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ("INNERGRID",   (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ("BACKGROUND",  (0,0), (-1, 0), colors.HexColor("#f8fafc")),
        ("ROWBACKGROUNDS",(0,1),(-1,1),[colors.white]),
        ("TOPPADDING",  (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("LINEABOVE",   (2,0), (2,-1), 2, j_color),
        ("LINEABOVE",   (3,0), (3,-1), 2, j_color),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 0.6*cm))

    # ── المجالات الخمسة ───────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dbeafe")))
    story.append(Paragraph(ar("تحليل المجالات الخمسة"), S["h2"]))

    domain_rows = [[
        Paragraph(ar("الحكم"),    S["tbl_hdr"]),
        Paragraph(ar("النسبة %"), S["tbl_hdr"]),
        Paragraph(ar("المجال"),   S["tbl_hdr"]),
    ]]
    domain_colors_map = []
    for domain, items in ITEMS_STRUCTURE.items():
        dcols = [f"بند {n}" for n, _ in items if f"بند {n}" in filtered_df.columns]
        vals = []
        for dc in dcols:
            vals.extend(filtered_df[dc].map(JUDGMENT_WEIGHTS).dropna().tolist())
        if vals:
            dp = round((sum(vals)/(len(vals)*4))*100, 1)
            jd = get_general_judgment(dp)
            jc = JCOLORS.get(jd, colors.HexColor("#2563eb"))
            domain_rows.append([
                Paragraph(ar(jd),  S["tbl_cell"]),
                Paragraph(ar(f"{dp}%"), S["tbl_num"]),
                Paragraph(ar(domain),  S["tbl_cell"]),
            ])
            domain_colors_map.append(jc)

    dom_tbl = Table(domain_rows, colWidths=[4*cm, 2.5*cm, 9*cm])
    dom_style = [
        ("BACKGROUND",   (0,0), (-1, 0), colors.HexColor("#0f2044")),
        ("TEXTCOLOR",    (0,0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f8fafc")]),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ("INNERGRID",    (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ("TOPPADDING",   (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0), (-1,-1), 7),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]
    for ri, jc in enumerate(domain_colors_map, start=1):
        dom_style.append(("TEXTCOLOR", (0, ri), (0, ri), jc))
        dom_style.append(("FONTNAME",  (0, ri), (0, ri), _reg_bold))
        dom_style.append(("LINERIGHT", (2, ri), (2, ri), 3, jc))
    dom_tbl.setStyle(TableStyle(dom_style))
    story.append(dom_tbl)

    # ── تفصيل البنود (للتقرير التفصيلي فقط) ──────────────────────────────
    if report_type == "detailed":
        story.append(Spacer(1, 0.6*cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dbeafe")))
        story.append(Paragraph(ar("تفصيل البنود الـ 18"), S["h2"]))

        # جدول تفصيلي للبنود: لكل بند يظهر عدد الزيارات/السجلات في كل حكم
        small_hdr = ParagraphStyle("small_hdr", fontName=_reg_bold, fontSize=7.2, alignment=TA_CENTER, leading=9, textColor=colors.white)
        small_cell = ParagraphStyle("small_cell", fontName=_reg_font, fontSize=7.4, alignment=TA_RIGHT, leading=9.2)
        small_num = ParagraphStyle("small_num", fontName=_reg_bold, fontSize=7.4, alignment=TA_CENTER, leading=9.2)

        item_rows = [[
            Paragraph(ar("الحكم العام"), small_hdr),
            Paragraph(ar("النسبة"), small_hdr),
            Paragraph(ar("المجموع"), small_hdr),
            Paragraph(ar("يفي جزئياً"), small_hdr),
            Paragraph(ar("يفي"), small_hdr),
            Paragraph(ar("يتجاوز"), small_hdr),
            Paragraph(ar("يتجاوز بكثير"), small_hdr),
            Paragraph(ar("البند"), small_hdr),
            Paragraph(ar("#"), small_hdr),
        ]]
        item_colors_map = []
        for i in range(1, 19):
            col_i = f"بند {i}"
            if col_i in filtered_df.columns:
                vals_raw = filtered_df[col_i].dropna().astype(str).str.strip()
                vals_i = vals_raw.map(JUDGMENT_WEIGHTS).dropna().tolist()
                if vals_i:
                    counts_i = vals_raw.value_counts()
                    c_partial = int(counts_i.get("يفي بالتوقعات جزئياً", 0))
                    c_meets = int(counts_i.get("يفي بالتوقعات", 0))
                    c_exceeds = int(counts_i.get("يتجاوز التوقعات", 0))
                    c_exceeds_much = int(counts_i.get("يتجاوز التوقعات بكثير", 0))
                    total_i = c_partial + c_meets + c_exceeds + c_exceeds_much
                    ip = round((sum(vals_i)/(len(vals_i)*4))*100, 1)
                    ji = get_general_judgment(ip)
                    jc = JCOLORS.get(ji, colors.HexColor("#2563eb"))
                    item_rows.append([
                        Paragraph(ar(ji), small_cell),
                        Paragraph(ar(f"{ip}%"), small_num),
                        Paragraph(ar(str(total_i)), small_num),
                        Paragraph(ar(str(c_partial)), small_num),
                        Paragraph(ar(str(c_meets)), small_num),
                        Paragraph(ar(str(c_exceeds)), small_num),
                        Paragraph(ar(str(c_exceeds_much)), small_num),
                        Paragraph(ar(ITEM_NAMES.get(i, f"بند {i}")), small_cell),
                        Paragraph(ar(str(i)), small_num),
                    ])
                    item_colors_map.append(jc)

        itm_tbl = Table(item_rows, colWidths=[2.25*cm, 1.25*cm, 1.15*cm, 1.15*cm, 1.0*cm, 1.15*cm, 1.35*cm, 5.15*cm, 0.65*cm], repeatRows=1)
        itm_style = [
            ("BACKGROUND",   (0,0), (-1, 0), colors.HexColor("#0f2044")),
            ("TEXTCOLOR",    (0,0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f8fafc")]),
            ("BOX",          (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
            ("INNERGRID",    (0,0), (-1,-1), 0.35, colors.HexColor("#e5e7eb")),
            ("TOPPADDING",   (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0), (-1,-1), 3),
            ("LEFTPADDING",  (0,0), (-1,-1), 3),
            ("RIGHTPADDING", (0,0), (-1,-1), 3),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("BACKGROUND",   (3,1), (3,-1), colors.HexColor("#fce7f3")),
            ("BACKGROUND",   (4,1), (4,-1), colors.HexColor("#fef3c7")),
            ("BACKGROUND",   (5,1), (5,-1), colors.HexColor("#dbeafe")),
            ("BACKGROUND",   (6,1), (6,-1), colors.HexColor("#d1fae5")),
        ]
        for ri, jc in enumerate(item_colors_map, start=1):
            itm_style.append(("TEXTCOLOR", (0, ri), (0, ri), jc))
            itm_style.append(("FONTNAME",  (0, ri), (0, ri), _reg_bold))
        itm_tbl.setStyle(TableStyle(itm_style))
        story.append(itm_tbl)

        # ── جدول المعلمات ─────────────────────────────────────────────────
        if "اسم المعلمة" in filtered_df.columns:
            story.append(Spacer(1, 0.6*cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dbeafe")))
            story.append(Paragraph(ar("أداء المعلمات"), S["h2"]))

            t_rows = [[
                Paragraph(ar("الحكم"),      S["tbl_hdr"]),
                Paragraph(ar("النسبة %"),   S["tbl_hdr"]),
                Paragraph(ar("عدد السجلات"),S["tbl_hdr"]),
                Paragraph(ar("اسم المعلمة"),S["tbl_hdr"]),
            ]]
            t_colors = []
            for tname, tgrp in filtered_df.groupby("اسم المعلمة"):
                tp = calculate_percentage(tgrp)
                jt = get_general_judgment(tp)
                jc = JCOLORS.get(jt, colors.HexColor("#2563eb"))
                t_rows.append([
                    Paragraph(ar(jt), S["tbl_cell"]),
                    Paragraph(ar(f"{tp}%"), S["tbl_num"]),
                    Paragraph(ar(str(len(tgrp))), S["tbl_num"]),
                    Paragraph(ar(tname), S["tbl_cell"]),
                ])
                t_colors.append(jc)

            t_tbl = Table(t_rows, colWidths=[3.5*cm, 2.5*cm, 2.5*cm, 7*cm])
            t_style = [
                ("BACKGROUND",    (0,0), (-1, 0), colors.HexColor("#0f2044")),
                ("TEXTCOLOR",     (0,0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f8fafc")]),
                ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
                ("INNERGRID",     (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
                ("TOPPADDING",    (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ]
            for ri, jc in enumerate(t_colors, start=1):
                t_style.append(("TEXTCOLOR", (0, ri), (0, ri), jc))
                t_style.append(("FONTNAME",  (0, ri), (0, ri), _reg_bold))
            t_tbl.setStyle(TableStyle(t_style))
            story.append(t_tbl)

    # ── تذييل ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f2044")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(ar("مديرة المدرسة: أ. خلود يعقوب  |  المديرة المساعدة: أ. سامية سلمان  |  تصميم: أ. عفاف حسين"), S["subtitle"]))

    doc.build(story)
    return buf.getvalue()


# ─── Analysis Page ────────────────────────────────────────────────────────────
def show_analysis(df, allowed_dept):
    if df.empty:
        st.warning("⚠️ لا توجد بيانات للعرض حالياً.")
        return

    if "نوع السجل" not in df.columns:
        df["نوع السجل"] = "زيارة صفية"

    # ── FILTERS ──────────────────────────────────────────────────────────────
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown('<div class="filter-title">🔍 &nbsp; تصفية البيانات</div>', unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    filtered = df.copy()

    with col1:
        years = ["الكل"] + sorted(filtered["السنة الدراسية"].dropna().astype(str).unique().tolist()) if "السنة الدراسية" in filtered.columns else ["الكل"]
        year = st.selectbox("📅 السنة الدراسية", years)
    if year != "الكل":
        filtered = filtered[filtered["السنة الدراسية"].astype(str) == year]

    with col2:
        sems = ["الكل"] + sorted(filtered["الفصل الدراسي"].dropna().astype(str).unique().tolist()) if "الفصل الدراسي" in filtered.columns else ["الكل"]
        sem = st.selectbox("📖 الفصل الدراسي", sems)
    if sem != "الكل":
        filtered = filtered[filtered["الفصل الدراسي"].astype(str) == sem]

    with col3:
        months_avail = ["الكل"] + [m for m in MONTHS if "الشهر" in filtered.columns and m in filtered["الشهر"].astype(str).unique()]
        month = st.selectbox("🗓️ الشهر", months_avail)
    if month != "الكل":
        filtered = filtered[filtered["الشهر"].astype(str) == month]

    with col4:
        if "الزائر" in filtered.columns:
            visitor_types = ["الكل"] + sorted(filtered["الزائر"].dropna().astype(str).unique().tolist())
            visitor = st.selectbox("👁️ نوع الزيارة", visitor_types)
        else:
            visitor = "الكل"
    if visitor != "الكل" and "الزائر" in filtered.columns:
        filtered = filtered[filtered["الزائر"].astype(str) == visitor]

    if allowed_dept == "الكل":
        with col5:
            depts = ["الكل"] + sorted(filtered["القسم الأكاديمي"].dropna().astype(str).unique().tolist()) if "القسم الأكاديمي" in filtered.columns else ["الكل"]
            dept = st.selectbox("🏫 القسم الأكاديمي", depts)
        if dept != "الكل":
            filtered = filtered[filtered["القسم الأكاديمي"].astype(str) == dept]
    else:
        filtered = filtered[filtered["القسم الأكاديمي"].apply(normalize_text) == normalize_text(allowed_dept)]

    teachers = ["الكل"] + sorted(filtered["اسم المعلمة"].dropna().astype(str).unique().tolist()) if "اسم المعلمة" in filtered.columns else ["الكل"]
    teacher = st.selectbox("👩‍🏫 اسم المعلمة", teachers)
    if teacher != "الكل":
        filtered = filtered[filtered["اسم المعلمة"].astype(str) == teacher]

    st.markdown('</div>', unsafe_allow_html=True)

    if filtered.empty:
        st.warning("⚠️ لا توجد بيانات حسب الفلاتر المختارة.")
        return

    # ── 1. KPIs ──────────────────────────────────────────────────────────────
    section_title("📊", "الملخص التنفيذي")

    percent  = calculate_percentage(filtered)
    judgment = get_general_judgment(percent)
    n_records = len(filtered)
    n_teachers = filtered["اسم المعلمة"].nunique() if "اسم المعلمة" in filtered.columns else 0

    # حساب عدد الزيارات الصفية المنجزة (غير التقييم الذاتي)
    n_classroom = len(filtered[filtered["نوع السجل"] == "زيارة صفية"]) if "نوع السجل" in filtered.columns else n_records
    pcolor = percent_color(percent)

    st.markdown(f"""
    <div class="kpi-grid">
        {kpi_card_html("إجمالي السجلات", n_records, "blue", "زيارة / تقييم")}
        {kpi_card_html("الزيارات الصفية", n_classroom, "blue", "زيارة منجزة")}
        {kpi_card_html("عدد المعلمات", n_teachers, "blue", "معلمة مشمولة")}
        {kpi_card_html("النسبة العامة", f"{percent}%", pcolor)}
        <div class="kpi-card {pcolor}">
            <div class="kpi-label">الحكم العام</div>
            <div style="margin-top:8px">{judgment_badge(judgment)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 1b. توزيع أنواع الزيارات ──────────────────────────────────────────────
    if "الزائر" in filtered.columns:
        visitor_counts = filtered["الزائر"].dropna().value_counts()
        if len(visitor_counts) >= 1:
            visitor_icons = {
                "زيارة القيادة العليا لجميع المعلمات":  "👑",
                "زيارة القيادة العليا للقيادة الوسطى":  "🏛️",
                "زيارة الأيام الحية للقيادة الوسطى":    "📅",
                "زيارة الأيام الحية لجميع المعلمات":    "🗓️",
                "زيارة القيادة الوسطى لجميع المعلمات":  "🔍",
                "التقييم الذاتي":                        "📝",
                "التوأمة الموجهة":                       "🤝",
            }
            n_cols = min(len(visitor_counts), 4)
            rows = [list(visitor_counts.items())[i:i+n_cols] for i in range(0, len(visitor_counts), n_cols)]
            for row_items in rows:
                cols_vc = st.columns(len(row_items))
                for i, (vtype, cnt) in enumerate(row_items):
                    icon = visitor_icons.get(vtype, "📌")
                    with cols_vc[i]:
                        st.markdown(f"""
                        <div style="background:white; border-radius:12px; padding:12px 10px; text-align:center;
                                    box-shadow:0 2px 8px rgba(0,0,0,0.06); border-top:3px solid #2563eb; margin-bottom:12px;">
                            <div style="font-size:22px">{icon}</div>
                            <div style="font-size:22px; font-weight:900; color:#111827">{cnt}</div>
                            <div style="font-size:11px; color:#6b7280; font-weight:600; line-height:1.3">{vtype}</div>
                        </div>""", unsafe_allow_html=True)

    # ── 2. DOMAINS ────────────────────────────────────────────────────────────
    section_title("🧩", "تحليل المجالات الخمسة")

    domains_result = []
    for domain, items in ITEMS_STRUCTURE.items():
        dcols = [f"بند {n}" for n, _ in items if f"بند {n}" in filtered.columns]
        vals = []
        for col in dcols:
            vals.extend(filtered[col].map(JUDGMENT_WEIGHTS).dropna().tolist())
        if vals:
            dp = round((sum(vals)/(len(vals)*4))*100, 1)
            domains_result.append({"المجال": domain, "النسبة": dp, "الحكم": get_general_judgment(dp)})

    if domains_result:
        col_a, col_b = st.columns([3, 2])

        with col_a:
            df_dom = pd.DataFrame(domains_result).sort_values("النسبة", ascending=True)
            colors_d = [JUDGMENT_COLORS.get(get_general_judgment(p), "#2563eb") for p in df_dom["النسبة"]]
            fig = make_rtl_bar_h(
                df_dom["المجال"].tolist(),
                df_dom["النسبة"].tolist(),
                colors_d,
                label_fontsize=13,
                right_margin=260,
            )
            fig.update_layout(height=320)
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            for row in domains_result:
                icon = DOMAIN_ICONS.get(row["المجال"], "📌")
                pct = row["النسبة"]
                bar_color = JUDGMENT_COLORS.get(row["الحكم"], "#2563eb")
                st.markdown(f"""
                <div class="domain-card" style="border-right-color:{bar_color}">
                    <div class="domain-header">
                        <span class="domain-name">{icon} {row["المجال"]}</span>
                        {judgment_badge(row["الحكم"])}
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width:{pct}%; background:{bar_color}"></div>
                    </div>
                    <div style="text-align:left; font-size:12px; color:#6b7280; margin-top:4px">{pct}%</div>
                </div>
                """, unsafe_allow_html=True)

    # ── 2b. رادار شارت للمجالات ───────────────────────────────────────────────
    if domains_result and len(domains_result) >= 3:
        section_title("🕸️", "الرادار البياني للمجالات")
        radar_df = pd.DataFrame(domains_result)
        categories = radar_df["المجال"].tolist()
        values     = radar_df["النسبة"].tolist()
        # نغلق الشكل بإعادة أول قيمة
        categories_closed = categories + [categories[0]]
        values_closed     = values     + [values[0]]

        import math
        n = len(categories)
        angles = [math.pi/2 - 2*math.pi*i/n for i in range(n)]
        angles_closed = angles + [angles[0]]

        # تحويل من قطبي إلى ديكارتي
        r_max = 100
        xs = [v/r_max * math.cos(a) for v, a in zip(values_closed, angles_closed)]
        ys = [v/r_max * math.sin(a) for v, a in zip(values_closed, angles_closed)]

        # شبكة الخلفية
        grid_levels = [25, 50, 75, 100]
        fig_r = go.Figure()

        for gl in grid_levels:
            gxs = [gl/r_max * math.cos(a) for a in angles_closed]
            gys = [gl/r_max * math.sin(a) for a in angles_closed]
            fig_r.add_trace(go.Scatter(
                x=gxs, y=gys, mode="lines",
                line=dict(color="#e5e7eb", width=1),
                showlegend=False, hoverinfo="skip"
            ))
            fig_r.add_annotation(
                x=0, y=gl/r_max + 0.03,
                text=f"{gl}%", showarrow=False,
                font=dict(size=10, color="#9ca3af", family="Tajawal")
            )

        # خطوط المحاور
        for i in range(n):
            fig_r.add_trace(go.Scatter(
                x=[0, math.cos(angles[i])],
                y=[0, math.sin(angles[i])],
                mode="lines",
                line=dict(color="#e5e7eb", width=1),
                showlegend=False, hoverinfo="skip"
            ))

        # المنطقة الملونة
        fig_r.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers",
            fill="toself",
            fillcolor="rgba(37,99,235,0.15)",
            line=dict(color="#2563eb", width=2.5),
            marker=dict(size=8, color="#2563eb"),
            showlegend=False,
            hovertemplate=[f"{cat}<br>{val}%<extra></extra>"
                           for cat, val in zip(categories_closed, values_closed)],
        ))

        # تسميات المحاور
        label_r = 1.18
        for i, (cat, val) in enumerate(zip(categories, values)):
            lx = label_r * math.cos(angles[i])
            ly = label_r * math.sin(angles[i])
            color = JUDGMENT_COLORS.get(get_general_judgment(val), "#2563eb")
            fig_r.add_annotation(
                x=lx, y=ly,
                text=f"<b>{DOMAIN_ICONS.get(cat,'')} {cat}</b><br><span style='color:{color}'>{val}%</span>",
                showarrow=False,
                font=dict(size=12, family="Tajawal"),
                align="center",
            )

        fig_r.update_layout(
            xaxis=dict(visible=False, range=[-1.45, 1.45]),
            yaxis=dict(visible=False, range=[-1.45, 1.45], scaleanchor="x"),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=60, r=60, t=40, b=40),
            height=460,
            font=dict(family="Tajawal"),
        )
        st.plotly_chart(fig_r, use_container_width=True)

    # ── 3. ITEMS ─────────────────────────────────────────────────────────────
    section_title("📌", "تفصيل البنود الـ 18")

    items_result = []
    for i in range(1, 19):
        col = f"بند {i}"
        if col in filtered.columns:
            vals = filtered[col].map(JUDGMENT_WEIGHTS).dropna().tolist()
            if vals:
                ip = round((sum(vals)/(len(vals)*4))*100, 1)
                label = f"{i}. {ITEM_NAMES.get(i, f'بند {i}')}"
                items_result.append({"البند": f"بند {i}", "الاسم": label, "النسبة": ip, "الحكم": get_general_judgment(ip)})

    if items_result:
        df_items = pd.DataFrame(items_result).sort_values("النسبة", ascending=True)
        colors_i = [JUDGMENT_COLORS.get(get_general_judgment(p), "#2563eb") for p in df_items["النسبة"]]
        fig2 = make_rtl_bar_h(
            df_items["الاسم"].tolist(),
            df_items["النسبة"].tolist(),
            colors_i,
            label_fontsize=12,
            right_margin=380,
        )
        fig2.update_layout(height=580)
        st.plotly_chart(fig2, use_container_width=True)

        # أفضل 3 بنود وأضعف 3 بنود
        df_items_sorted = df_items.sort_values("النسبة", ascending=False)
        col_best, col_worst = st.columns(2)
        with col_best:
            st.markdown("""<div style="background:#f0fdf4; border-radius:12px; padding:14px 18px; margin-bottom:8px;">
                <div style="font-size:15px; font-weight:800; color:#065f46; margin-bottom:10px;">🏆 أفضل 3 بنود أداءً</div>""",
                unsafe_allow_html=True)
            for _, row in df_items_sorted.head(3).iterrows():
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            background:white; border-radius:8px; padding:8px 12px; margin-bottom:6px; gap:8px;">
                    <span style="font-weight:700; color:#111827; font-size:13px">{row['الاسم']}</span>
                    <span style="font-size:15px; font-weight:900; color:#10b981; flex-shrink:0">{row['النسبة']}%</span>
                </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_worst:
            st.markdown("""<div style="background:#fff7ed; border-radius:12px; padding:14px 18px; margin-bottom:8px;">
                <div style="font-size:15px; font-weight:800; color:#9a3412; margin-bottom:10px;">⚠️ أضعف 3 بنود تحتاج تطوير</div>""",
                unsafe_allow_html=True)
            for _, row in df_items_sorted.tail(3).iterrows():
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            background:white; border-radius:8px; padding:8px 12px; margin-bottom:6px; gap:8px;">
                    <span style="font-weight:700; color:#111827; font-size:13px">{row['الاسم']}</span>
                    <span style="font-size:15px; font-weight:900; color:#f472b6; flex-shrink:0">{row['النسبة']}%</span>
                </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("📋 عرض جدول البنود التفصيلي"):
            st.dataframe(df_items_sorted[["الاسم", "النسبة", "الحكم"]], use_container_width=True, hide_index=True)

    # ── 4. JUDGMENT DISTRIBUTION ──────────────────────────────────────────────
    section_title("🎯", "توزيع الأحكام الكلي")

    item_cols = [f"بند {i}" for i in range(1,19) if f"بند {i}" in filtered.columns]
    all_j = []
    for col in item_cols:
        all_j.extend(filtered[col].dropna().astype(str).tolist())

    if all_j:
        j_df = pd.DataFrame({"الحكم": all_j})
        counts = j_df["الحكم"].value_counts().reindex(JUDGMENT_ORDER).dropna().reset_index()
        counts.columns = ["الحكم", "العدد"]
        counts["النسبة"] = round(counts["العدد"]/counts["العدد"].sum()*100, 1)

        col_p, col_t = st.columns([1, 1])
        with col_p:
            fig_pie = go.Figure(go.Pie(
                labels=counts["الحكم"],
                values=counts["العدد"],
                hole=0.45,
                marker_colors=[JUDGMENT_COLORS.get(j,"#94a3b8") for j in counts["الحكم"]],
                textinfo="percent+label",
                textfont=dict(size=13, family="Tajawal"),
                insidetextorientation="radial",
            ))
            fig_pie.update_layout(
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                height=280,
                paper_bgcolor="white",
                font=dict(family="Tajawal"),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_t:
            st.markdown("<br>", unsafe_allow_html=True)
            for _, row in counts.iterrows():
                badge = judgment_badge(row["الحكم"])
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            padding:10px 14px; background:white; border-radius:10px;
                            margin-bottom:8px; box-shadow:0 1px 6px rgba(0,0,0,0.06);">
                    <span>{badge}</span>
                    <span style="font-size:20px; font-weight:900; color:#111827">{int(row['العدد'])}</span>
                    <span style="font-size:13px; color:#6b7280">{row['النسبة']}%</span>
                </div>""", unsafe_allow_html=True)

    # ── 5. TEACHERS ───────────────────────────────────────────────────────────
    section_title("👩‍🏫", "تحليل أداء المعلمات")

    if "اسم المعلمة" in filtered.columns:
        teacher_rows = []
        for tname, grp in filtered.groupby("اسم المعلمة"):
            tp = calculate_percentage(grp)
            teacher_rows.append({
                "اسم المعلمة": tname,
                "عدد السجلات": len(grp),
                "النسبة %": tp,
                "الحكم": get_general_judgment(tp)
            })
        tdf = pd.DataFrame(teacher_rows).sort_values("النسبة %", ascending=False)

        if len(tdf) > 1:
            colors_t = [JUDGMENT_COLORS.get(get_general_judgment(p), "#2563eb") for p in tdf["النسبة %"]]
            fig_t = go.Figure(go.Bar(
                x=tdf["اسم المعلمة"],
                y=tdf["النسبة %"],
                marker_color=colors_t,
                text=[f"{p}%" for p in tdf["النسبة %"]],
                textposition="outside",
                textfont=dict(size=12, family="Tajawal"),
            ))
            fig_t.update_layout(
                xaxis=dict(tickangle=-30, tickfont=dict(size=11, family="Tajawal")),
                yaxis=dict(range=[0,115], showgrid=True, gridcolor="#f0f4f8"),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=10, r=10, t=10, b=60),
                height=320,
                font=dict(family="Tajawal"),
            )
            st.plotly_chart(fig_t, use_container_width=True)

        with st.expander("📋 جدول تفصيلي للمعلمات"):
            st.dataframe(tdf, use_container_width=True, hide_index=True)

    # ── 5b. ✅ جديد: المعلمات اللواتي لم تُسجَّل لهن زيارات ─────────────────
    if allowed_dept != "الكل":
        # نقارن المعلمات الموجودات في البيانات (كل المعلمات في القسم)
        # مقابل اللواتي زُرن فعلاً (لهن سجلات زيارة صفية)
        all_teachers_in_dept = df[
            df["القسم الأكاديمي"].apply(normalize_text) == normalize_text(allowed_dept)
        ]["اسم المعلمة"].dropna().unique()

        visited_teachers = filtered[
            filtered.get("نوع السجل", pd.Series(["زيارة صفية"]*len(filtered))) == "زيارة صفية"
        ]["اسم المعلمة"].dropna().unique() if "نوع السجل" in filtered.columns else filtered["اسم المعلمة"].dropna().unique()

        not_visited = [t for t in all_teachers_in_dept if t not in visited_teachers]

        if not_visited:
            section_title("⚠️", "معلمات لم تُسجَّل لهن زيارة صفية")
            st.markdown(f"""
            <div style="background:#fff7ed; border:1px solid #fed7aa; border-radius:12px;
                        padding:14px 18px; margin-bottom:16px;">
                <div style="font-size:14px; font-weight:700; color:#9a3412; margin-bottom:8px;">
                    ⚠️ عدد المعلمات دون زيارات: {len(not_visited)}
                </div>""", unsafe_allow_html=True)
            for t in not_visited:
                st.markdown(f"""
                <div class="alert-card">
                    <span class="alert-name">👩‍🏫 {t}</span>
                    <span class="alert-info">لا توجد زيارات مسجلة</span>
                </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # ── 6. DEPARTMENTS — للمدير فقط ──────────────────────────────────────────
    if allowed_dept == "الكل" and "القسم الأكاديمي" in filtered.columns:
        section_title("🏫", "ترتيب الأقسام الأكاديمية")

        # ── نظام النقاط المركّب (مقيّد بين 0 و100) ─────────────────────────
        # المعادلة: النقاط = (نسبة الأداء × 0.55) + (% يتجاوز بكثير × 0.35) + (علاوة الحجم × 0.10)
        # علاوة الحجم: 1–2 → 60 | 3–5 → 75 | 6–10 → 88 | 11+ → 100
        # بهذه الطريقة أقصى نقطة = 100×0.55 + 100×0.35 + 100×0.10 = 100
        def size_bonus(n):
            if n <= 2:   return 60
            elif n <= 5:  return 75
            elif n <= 10: return 88
            else:         return 100

        item_cols_dept = [f"بند {i}" for i in range(1,19) if f"بند {i}" in filtered.columns]

        dept_rows = []
        for dname, grp in filtered.groupby("القسم الأكاديمي"):
            dp = calculate_percentage(grp)

            # عدد المعلمات الحقيقي من كل البيانات (مو بس الفترة المفلترة)
            if "اسم المعلمة" in df.columns and "القسم الأكاديمي" in df.columns:
                n_teachers_dept = df[
                    df["القسم الأكاديمي"].apply(normalize_text) == normalize_text(dname)
                ]["اسم المعلمة"].nunique()
            else:
                n_teachers_dept = grp["اسم المعلمة"].nunique() if "اسم المعلمة" in grp.columns else len(grp)

            # نسبة "يتجاوز التوقعات بكثير" من كل الأحكام في القسم
            all_judgments = []
            for ic in item_cols_dept:
                all_judgments.extend(grp[ic].dropna().astype(str).tolist())
            pct_excellent = (
                round(all_judgments.count("يتجاوز التوقعات بكثير") / len(all_judgments) * 100, 1)
                if all_judgments else 0
            )

            sf = size_bonus(n_teachers_dept)
            composite = round(dp * 0.55 + pct_excellent * 0.35 + sf * 0.10, 1)

            dept_rows.append({
                "القسم": dname,
                "عدد المعلمات": n_teachers_dept,
                "عدد السجلات": len(grp),
                "نسبة الأداء %": dp,
                "% يتجاوز بكثير": pct_excellent,
                "علاوة الحجم": sf,
                "النقاط المركّبة": composite,
                "الحكم": get_general_judgment(dp),
            })

        ddf = (
            pd.DataFrame(dept_rows)
            .sort_values("النقاط المركّبة", ascending=False)
            .reset_index(drop=True)
        )
        ddf.index = ddf.index + 1

        # شرح المنهجية


        st.markdown("<div style='margin-top:4px;'>", unsafe_allow_html=True)
        for i, row in ddf.iterrows():
            medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"#{i}"))
            bar_color = JUDGMENT_COLORS.get(row["الحكم"], "#2563eb")
            pct = row["نسبة الأداء %"]
            st.markdown(f"""
            <div class="rank-card" style="border-right: 4px solid {bar_color}; flex-direction: column; align-items: stretch; gap: 10px;">
                <div style="display:flex; align-items:center; justify-content:space-between;">
                    <div style="display:flex; align-items:center; gap:14px;">
                        <div class="rank-num">{medal}</div>
                        <div class="rank-info">
                            <div class="rank-name">{row['القسم']}</div>
                            <div class="rank-sub">{row['عدد المعلمات']} معلمة</div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <div style="font-size:20px; font-weight:900; color:{bar_color}">{pct}%</div>
                        {judgment_badge(row['الحكم'])}
                    </div>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width:{pct}%; background:{bar_color};"></div>
                </div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # ✅ جديد: المعلمات غير المزارات عبر كل الأقسام (للمدير فقط)
        section_title("⚠️", "المعلمات اللواتي لم تُسجَّل لهن زيارات صفية")
        if "نوع السجل" in df.columns:
            all_t = df["اسم المعلمة"].dropna().unique()
            visited_t = df[df["نوع السجل"] == "زيارة صفية"]["اسم المعلمة"].dropna().unique()
            not_vis = [(t, df[df["اسم المعلمة"]==t]["القسم الأكاديمي"].iloc[0] if "القسم الأكاديمي" in df.columns else "") for t in all_t if t not in visited_t]
            if not_vis:
                col_nv1, col_nv2 = st.columns(2)
                for idx, (tname, tdept) in enumerate(not_vis):
                    with (col_nv1 if idx % 2 == 0 else col_nv2):
                        st.markdown(f"""
                        <div class="alert-card">
                            <div>
                                <div class="alert-name">👩‍🏫 {tname}</div>
                                <div class="alert-info">{tdept}</div>
                            </div>
                            <span style="font-size:11px; background:#fed7aa; padding:3px 10px;
                                         border-radius:10px; color:#9a3412; font-weight:700;">بدون زيارة</span>
                        </div>""", unsafe_allow_html=True)
            else:
                st.success("✅ جميع المعلمات لديهن زيارات مسجلة")

        with st.expander("📋 جدول مقارنة الأقسام التفصيلي"):
            show_cols = ["القسم", "عدد المعلمات", "عدد السجلات", "نسبة الأداء %", "% يتجاوز بكثير", "علاوة الحجم", "النقاط المركّبة", "الحكم"]
            st.dataframe(ddf[show_cols], use_container_width=True)

    # ── 7. ✅ جديد: تحليل الأداء عبر الأشهر ─────────────────────────────────
    if "الشهر" in filtered.columns and filtered["الشهر"].nunique() > 1:
        section_title("📈", "تطور الأداء عبر الأشهر")

        months_order = {m: i for i, m in enumerate(MONTHS)}
        monthly_data = []
        for m, grp in filtered.groupby("الشهر"):
            mp = calculate_percentage(grp)
            monthly_data.append({"الشهر": m, "النسبة": mp, "الترتيب": months_order.get(str(m).strip(), 99)})

        mdf = pd.DataFrame(monthly_data).sort_values("الترتيب")
        # قائمة الأشهر الموجودة فقط بترتيبها الدراسي الصحيح
        ordered_months = [m for m in MONTHS if m in mdf["الشهر"].values]

        if len(mdf) > 1:
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=mdf["الشهر"], y=mdf["النسبة"],
                mode="lines+markers+text",
                line=dict(color="#2563eb", width=3),
                marker=dict(
                    size=12,
                    color=[JUDGMENT_COLORS.get(get_general_judgment(p), "#2563eb") for p in mdf["النسبة"]],
                    line=dict(color="white", width=2)
                ),
                text=[f"{p}%" for p in mdf["النسبة"]],
                textposition="top center",
                textfont=dict(size=13, family="Tajawal", color="#111827"),
            ))
            fig_line.add_hline(y=75, line_dash="dash", line_color="#10b981", line_width=1.5,
                               annotation_text="هدف 75%", annotation_position="left")
            fig_line.update_layout(
                xaxis=dict(
                    tickfont=dict(size=12, family="Tajawal"),
                    categoryorder="array",          # ✅ ترتيب يدوي صريح
                    categoryarray=ordered_months,   # ✅ من سبتمبر → يونيو
                ),
                yaxis=dict(range=[0, 115], showgrid=True, gridcolor="#f0f4f8"),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=10, r=10, t=20, b=10),
                height=300,
                font=dict(family="Tajawal"),
            )
            st.plotly_chart(fig_line, use_container_width=True)

    # ── 8. مقارنة الفصلين ────────────────────────────────────────────────────
    if "الفصل الدراسي" in df.columns and df["الفصل الدراسي"].nunique() >= 2:
        sems_available = df["الفصل الدراسي"].dropna().astype(str).unique().tolist()
        if len(sems_available) >= 2:
            section_title("📊", "مقارنة الفصلين الدراسيين")

            # نأخذ البيانات من df الكامل (بدون فلتر الفصل) لكن مع الفلاتر الأخرى
            df_compare = df.copy()
            # نفس السنة الدراسية المختارة في الفلتر
            if year != "الكل" and "السنة الدراسية" in df_compare.columns:
                df_compare = df_compare[df_compare["السنة الدراسية"].astype(str) == year]
            if allowed_dept != "الكل":
                df_compare = df_compare[df_compare["القسم الأكاديمي"].apply(normalize_text) == normalize_text(allowed_dept)]

            sem_results = []
            domain_by_sem = {}
            for sem, grp in df_compare.groupby("الفصل الدراسي"):
                sp = calculate_percentage(grp)
                sem_results.append({"الفصل": str(sem), "النسبة": sp, "عدد السجلات": len(grp)})
                # نسب المجالات لكل فصل
                for domain, items in ITEMS_STRUCTURE.items():
                    dcols = [f"بند {n}" for n, _ in items if f"بند {n}" in grp.columns]
                    vals = []
                    for dc in dcols:
                        vals.extend(grp[dc].map(JUDGMENT_WEIGHTS).dropna().tolist())
                    dp2 = round((sum(vals)/(len(vals)*4))*100, 1) if vals else 0
                    if sem not in domain_by_sem:
                        domain_by_sem[sem] = {}
                    domain_by_sem[sem][domain] = dp2

            if len(sem_results) >= 2:
                col_s1, col_s2 = st.columns(2)
                for idx, row in enumerate(sem_results):
                    with (col_s1 if idx == 0 else col_s2):
                        pcolor_s = percent_color(row["النسبة"])
                        jud_s = get_general_judgment(row["النسبة"])
                        bar_color_s = JUDGMENT_COLORS.get(jud_s, "#2563eb")
                        st.markdown(f"""
                        <div style="background:white; border-radius:14px; padding:20px 22px;
                                    box-shadow:0 2px 10px rgba(0,0,0,0.06);
                                    border-top:4px solid {bar_color_s}; margin-bottom:12px;">
                            <div style="font-size:15px; font-weight:800; color:#0f2044; margin-bottom:8px;">
                                📖 {row['الفصل']}
                            </div>
                            <div style="font-size:34px; font-weight:900; color:{bar_color_s}">{row['النسبة']}%</div>
                            <div style="margin-top:6px">{judgment_badge(jud_s)}</div>
                            <div style="font-size:12px; color:#6b7280; margin-top:8px">{row['عدد السجلات']} سجل</div>
                        </div>""", unsafe_allow_html=True)

                # رسم مقارنة المجالات بين الفصلين
                sems_list = list(domain_by_sem.keys())
                domains_list = list(ITEMS_STRUCTURE.keys())
                if len(sems_list) >= 2:
                    fig_sem = go.Figure()
                    sem_colors = ["#2563eb", "#10b981"]
                    for i, sem in enumerate(sems_list[:2]):
                        fig_sem.add_trace(go.Bar(
                            name=str(sem),
                            x=domains_list,
                            y=[domain_by_sem[sem].get(d, 0) for d in domains_list],
                            marker_color=sem_colors[i],
                            text=[f"{domain_by_sem[sem].get(d,0)}%" for d in domains_list],
                            textposition="outside",
                            textfont=dict(size=11, family="Tajawal"),
                        ))
                    fig_sem.update_layout(
                        barmode="group",
                        xaxis=dict(tickfont=dict(size=11, family="Tajawal"), tickangle=-20),
                        yaxis=dict(range=[0, 115], showgrid=True, gridcolor="#f0f4f8"),
                        plot_bgcolor="white", paper_bgcolor="white",
                        legend=dict(font=dict(family="Tajawal", size=12), orientation="h", y=1.1),
                        margin=dict(l=10, r=10, t=30, b=60),
                        height=340,
                        font=dict(family="Tajawal"),
                    )
                    st.plotly_chart(fig_sem, use_container_width=True)

                    # تنبيه: هل الأداء تحسّن أو تراجع؟
                    if len(sem_results) >= 2:
                        diff = round(sem_results[1]["النسبة"] - sem_results[0]["النسبة"], 1)
                        if diff > 0:
                            st.success(f"✅ تحسّن الأداء بمقدار {diff}% من الفصل الأول إلى الثاني")
                        elif diff < 0:
                            st.warning(f"⚠️ تراجع الأداء بمقدار {abs(diff)}% من الفصل الأول إلى الثاني — يستوجب المتابعة")
                        else:
                            st.info("ℹ️ الأداء ثابت بين الفصلين")

    # ── 9. تنبيهات ذكية ──────────────────────────────────────────────────────
    section_title("🔔", "التنبيهات الذكية")

    alerts = []

    # تنبيه 1: أقسام/معلمات نسبتها انخفضت عن الشهر السابق
    if "الشهر" in filtered.columns and filtered["الشهر"].nunique() >= 2:
        months_order_a = {m: i for i, m in enumerate(MONTHS)}
        months_sorted = sorted(filtered["الشهر"].dropna().unique(), key=lambda x: months_order_a.get(str(x), 99))
        if len(months_sorted) >= 2:
            last_m  = months_sorted[-1]
            prev_m  = months_sorted[-2]
            p_last  = calculate_percentage(filtered[filtered["الشهر"] == last_m])
            p_prev  = calculate_percentage(filtered[filtered["الشهر"] == prev_m])
            diff_m  = round(p_last - p_prev, 1)
            if diff_m < 0:
                alerts.append(("warning", f"انخفض الأداء {abs(diff_m)}% من {prev_m} إلى {last_m}"))
            elif diff_m > 0:
                alerts.append(("success", f"تحسّن الأداء {diff_m}% من {prev_m} إلى {last_m}"))

    # تنبيه 2: بنود تحت 75%
    weak_items = []
    for i in range(1, 19):
        col_i = f"بند {i}"
        if col_i in filtered.columns:
            vals_i = filtered[col_i].map(JUDGMENT_WEIGHTS).dropna().tolist()
            if vals_i:
                ip = round((sum(vals_i)/(len(vals_i)*4))*100, 1)
                if ip < 75:
                    weak_items.append(f"{i}. {ITEM_NAMES.get(i, f'بند {i}')} ({ip}%)")
    if weak_items:
        alerts.append(("danger", f"بنود أداؤها دون 75%: {' · '.join(weak_items)}"))

    # تنبيه 3: معلمات بدون زيارة
    if "نوع السجل" in df.columns and "اسم المعلمة" in df.columns:
        scope = df if allowed_dept == "الكل" else df[df["القسم الأكاديمي"].apply(normalize_text) == normalize_text(allowed_dept)]
        all_t_a   = scope["اسم المعلمة"].dropna().unique()
        visited_a = scope[scope["نوع السجل"] == "زيارة صفية"]["اسم المعلمة"].dropna().unique()
        n_no_visit = len([t for t in all_t_a if t not in visited_a])
        if n_no_visit > 0:
            alerts.append(("warning", f"{n_no_visit} معلمة لم تُسجَّل لهن زيارة صفية بعد"))

    if alerts:
        for atype, amsg in alerts:
            if atype == "success":
                st.success(f"✅ {amsg}")
            elif atype == "warning":
                st.warning(f"⚠️ {amsg}")
            elif atype == "danger":
                st.error(f"🔴 {amsg}")
    else:
        st.success("✅ لا توجد تنبيهات — الأداء العام ضمن المستوى المطلوب")

    # ── 10. مقارنة المعلمة بمتوسط قسمها ─────────────────────────────────────
    if "اسم المعلمة" in filtered.columns and "القسم الأكاديمي" in filtered.columns:
        section_title("📐", "مقارنة المعلمة بمتوسط قسمها")

        teacher_dept_rows = []
        for tname, tgrp in filtered.groupby("اسم المعلمة"):
            tp = calculate_percentage(tgrp)
            dept_name = tgrp["القسم الأكاديمي"].iloc[0] if len(tgrp) > 0 else ""
            dept_grp  = filtered[filtered["القسم الأكاديمي"] == dept_name]
            dept_avg  = calculate_percentage(dept_grp)
            diff_td   = round(tp - dept_avg, 1)
            teacher_dept_rows.append({
                "المعلمة": tname,
                "القسم": dept_name,
                "أداء المعلمة %": tp,
                "متوسط القسم %": dept_avg,
                "الفرق": diff_td,
            })

        tdf2 = pd.DataFrame(teacher_dept_rows).sort_values("الفرق", ascending=False)

        if len(tdf2) > 1:
            # رسم شريطي للفروقات
            colors_diff = ["#10b981" if d >= 0 else "#f472b6" for d in tdf2["الفرق"]]
            fig_diff = go.Figure(go.Bar(
                x=tdf2["المعلمة"],
                y=tdf2["الفرق"],
                marker_color=colors_diff,
                text=[f"{'+' if d>=0 else ''}{d}%" for d in tdf2["الفرق"]],
                textposition="outside",
                textfont=dict(size=11, family="Tajawal"),
            ))
            fig_diff.add_hline(y=0, line_color="#6b7280", line_width=1.5)
            fig_diff.update_layout(
                xaxis=dict(tickangle=-30, tickfont=dict(size=11, family="Tajawal")),
                yaxis=dict(showgrid=True, gridcolor="#f0f4f8", zeroline=False),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=10, r=10, t=20, b=60),
                height=320,
                font=dict(family="Tajawal"),
            )
            st.plotly_chart(fig_diff, use_container_width=True)

        with st.expander("📋 جدول مقارنة المعلمات بمتوسط أقسامهن"):
            st.dataframe(tdf2, use_container_width=True, hide_index=True)

    # ── PDF تنزيل التقرير ─────────────────────────────────────────────────────
    section_title("📄", "تنزيل التقرير")

    if PDF_READY:
        dept_label_pdf = allowed_dept if allowed_dept != "الكل" else "جميع الأقسام"
        col_pdf1, col_pdf2 = st.columns(2)

        if "pdf_summary_bytes" not in st.session_state:
            st.session_state["pdf_summary_bytes"] = None
        if "pdf_detailed_bytes" not in st.session_state:
            st.session_state["pdf_detailed_bytes"] = None

        with col_pdf1:
            if st.button("📄 تجهيز الملخص التنفيذي", key="pdf_summary"):
                try:
                    with st.spinner("جاري إعداد التقرير..."):
                        st.session_state["pdf_summary_bytes"] = generate_pdf(
                            filtered, allowed_dept, report_type="summary", dept_name=dept_label_pdf
                        )
                except Exception as e:
                    st.session_state["pdf_summary_bytes"] = None
                    st.error("تعذر إنشاء الملخص التنفيذي.")
                    st.exception(e)

            if st.session_state.get("pdf_summary_bytes"):
                st.download_button(
                    label="⬇️ تحميل الملخص التنفيذي (PDF)",
                    data=st.session_state["pdf_summary_bytes"],
                    file_name=f"ملخص_تنفيذي_{dept_label_pdf}.pdf",
                    mime="application/pdf",
                    key="dl_summary"
                )

        with col_pdf2:
            if st.button("📋 تجهيز التقرير التفصيلي", key="pdf_detailed"):
                try:
                    with st.spinner("جاري إعداد التقرير التفصيلي..."):
                        st.session_state["pdf_detailed_bytes"] = generate_pdf(
                            filtered, allowed_dept, report_type="detailed", dept_name=dept_label_pdf
                        )
                except Exception as e:
                    st.session_state["pdf_detailed_bytes"] = None
                    st.error("تعذر إنشاء التقرير التفصيلي.")
                    st.exception(e)

            if st.session_state.get("pdf_detailed_bytes"):
                st.download_button(
                    label="⬇️ تحميل التقرير التفصيلي (PDF)",
                    data=st.session_state["pdf_detailed_bytes"],
                    file_name=f"تقرير_تفصيلي_{dept_label_pdf}.pdf",
                    mime="application/pdf",
                    key="dl_detailed"
                )
    else:
        st.error("⚠️ مكتبات PDF أو الخط العربي غير جاهزة، لذلك لا يمكن تنزيل التقرير حالياً.")
        st.code(PDF_ERROR or "راجعي ملف requirements.txt وتأكدي من إضافة reportlab و arabic-reshaper و python-bidi")

    # ── 11. TEXT NOTES ────────────────────────────────────────────────────────
    text_cols = [
        "نجاحات المعلم", "جوانب بحاجة إلى تطوير",
        "نقاط القوة في أدائي العام", "نقاط الضعف التي تحتاج إلى تطوير",
        "الدعم المطلوب من زيارات القيادة الوسطى", "مقترحاتي لتطوير أدائي",
        "الأهداف التعليمية للحصة", "أساليب واستراتيجيات التدريس الملحوظة",
        "ما الذي يمكن أن أستفيد منه لتطوير ممارساتي التدريسية",
        "أفكار جديدة يمكن أن أستفيد منها لتطوير ممارساتي التدريسية",
        "توصيات المعلم المزور"
    ]
    avail_txt = [c for c in text_cols if c in filtered.columns]
    if avail_txt:
        section_title("📝", "الملاحظات والتوصيات النصية")
        with st.expander("عرض الملاحظات النصية التفصيلية"):
            base_cols = ["اسم المعلمة", "القسم الأكاديمي", "نوع السجل", "الشهر"]
            show_cols = [c for c in base_cols if c in filtered.columns] + avail_txt
            st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)


# ─── Auth ─────────────────────────────────────────────────────────────────────
try:
    st.image(HEADER_PATH, use_container_width=True)
except:
    pass

st.sidebar.markdown("## 🔐 تسجيل الدخول")

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "allowed_dept": None})

if not st.session_state["logged_in"]:
    pwd = st.sidebar.text_input("الرقم السري", type="password", placeholder="أدخلي الرقم السري...")
    if pwd:
        if pwd in dept_passwords:
            st.session_state.update({"logged_in": True, "allowed_dept": dept_passwords[pwd]})
            st.rerun()
        else:
            st.sidebar.error("❌ الرقم السري غير صحيح")
    st.markdown("""
    <div style="text-align:center; padding:80px 20px; color:#6b7280;">
        <div style="font-size:64px; margin-bottom:16px;">🏫</div>
        <div style="font-size:22px; font-weight:800; color:#0f2044; margin-bottom:8px;">نظام الزيارات الصفية</div>
        <div style="font-size:15px;">مدرسة جدحفص الثانوية للبنات</div>
        <div style="margin-top:24px; font-size:14px; color:#94a3b8;">الرجاء تسجيل الدخول من القائمة الجانبية</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

allowed_dept = st.session_state["allowed_dept"]

st.sidebar.markdown("---")
dept_label = "🛡️ مدير النظام" if allowed_dept == "الكل" else f"🏫 {allowed_dept}"
st.sidebar.markdown(
    f"<div style='color:#7eb3f7; font-size:14px; font-weight:700; margin-bottom:8px'>{dept_label}</div>",
    unsafe_allow_html=True
)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 تسجيل الخروج"):
    st.session_state.update({"logged_in": False, "allowed_dept": None})
    st.rerun()

st.markdown(f"""
<div class="page-header">
    <div>
        <div class="page-header-title">📊 لوحة التحليل التفاعلية</div>
        <div class="page-header-sub">عرض وتحليل بيانات الزيارات الصفية القادمة من Microsoft Forms</div>
    </div>
    <div class="page-header-badge">{dept_label}</div>
</div>""", unsafe_allow_html=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 تحديث البيانات"):
    st.cache_data.clear()
    st.rerun()

uploaded_excel = st.sidebar.file_uploader(
    "رفع ملف Excel بديل عند تعذر قراءة SharePoint",
    type=["xlsx"],
    help="استخدميه فقط إذا رابط SharePoint يحتاج صلاحية ولا يفتح من Streamlit Cloud."
)

try:
    with st.spinner("جاري تحميل بيانات Microsoft Forms..."):
        visits_df = get_forms_data(uploaded_excel)
    show_analysis(visits_df, allowed_dept)
except Exception as e:
    st.error("⚠️ تعذّر تحميل بيانات الزيارات.")
    st.warning("💡 الحل: حمّلي ملف Excel من Forms وارفعيه من الزر الجانبي")
    with st.expander("تفاصيل الخطأ"):
        st.code(str(e))

st.markdown("""
<div class="footer">
    <span>مديرة المدرسة: <span class="highlight">أ. خلود يعقوب</span></span>
    <span>المديرة المساعدة: <span class="highlight">أ. سامية سلمان</span></span>
    <span>تصميم وبرمجة: <span class="highlight">أ. عفاف حسين</span></span>
</div>
""", unsafe_allow_html=True)


