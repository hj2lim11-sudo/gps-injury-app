"""업로드 현황 — 달력으로 GPS·날씨·부상 입력 여부 확인."""
import streamlit as st
import pandas as pd
import calendar
from datetime import date
from utils.auth import require_login
require_login()

from utils.storage import load

st.set_page_config(page_title="업로드 현황", page_icon="📅", layout="wide")
st.title("📅 업로드 현황")
st.caption("날짜별 GPS · 날씨 · 부상 데이터 입력 여부를 달력으로 확인합니다.")

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
gps      = load("gps")
weather  = load("weather")
injuries = load("injuries")

def date_set(df, col="date"):
    if df.empty or col not in df.columns:
        return set()
    return set(pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d").dropna())

gps_dates = date_set(gps)
weather_dates = date_set(weather)
injury_dates = date_set(injuries)

all_dates = gps_dates | weather_dates | injury_dates

# ── 연월 선택 ─────────────────────────────────────────────────────────────────
today = date.today()
col1, col2 = st.columns([1, 4])
with col1:
    year  = st.number_input("년", min_value=2025, max_value=2028, value=today.year)
    month = st.number_input("월", min_value=1, max_value=12, value=today.month)

st.divider()

# ── 범례 ─────────────────────────────────────────────────────────────────────
lc1, lc2, lc3, lc4, lc5 = st.columns(5)
lc1.markdown("🟢 **GPS + 날씨 + 부상** 모두")
lc2.markdown("🔵 **GPS + 날씨** 입력")
lc3.markdown("🟡 **GPS만** 입력")
lc4.markdown("🔴 **부상만** 입력 (GPS 없음)")
lc5.markdown("⬜ 데이터 없음")

st.divider()

# ── 달력 생성 ─────────────────────────────────────────────────────────────────
cal = calendar.monthcalendar(int(year), int(month))
days_header = ["일", "월", "화", "수", "목", "금", "토"]

def get_status(d_str):
    has_gps     = d_str in gps_dates
    has_weather = d_str in weather_dates
    has_injury  = d_str in injury_dates
    if has_gps and has_weather and has_injury:
        return "🟢", "GPS+날씨+부상"
    elif has_gps and has_weather:
        return "🔵", "GPS+날씨"
    elif has_gps:
        return "🟡", "GPS만"
    elif has_injury:
        return "🔴", "부상만"
    else:
        return "⬜", ""

# 헤더
cols = st.columns(7)
for i, d in enumerate(days_header):
    color = "color:red;" if i == 0 else ("color:blue;" if i == 6 else "")
    cols[i].markdown(f"<div style='text-align:center;font-weight:bold;{color}'>{d}</div>",
                     unsafe_allow_html=True)

# 주별 행
for week in cal:
    cols = st.columns(7)
    for i, day in enumerate(week):
        with cols[i]:
            if day == 0:
                st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
                continue

            d_str = f"{int(year):04d}-{int(month):02d}-{day:02d}"
            icon, label = get_status(d_str)
            is_today = (d_str == today.strftime("%Y-%m-%d"))

            day_style = "font-weight:bold;color:red;" if i == 0 else \
                        "font-weight:bold;color:blue;" if i == 6 else ""
            today_mark = "🔘" if is_today else ""

            st.markdown(
                f"<div style='border:1px solid #ddd;border-radius:8px;padding:6px;"
                f"min-height:75px;background:#f9f9f9'>"
                f"<span style='{day_style}font-size:14px'>{today_mark}{day}</span><br>"
                f"<span style='font-size:20px'>{icon}</span><br>"
                f"<span style='font-size:10px;color:#666'>{label}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

st.divider()

# ── 월 요약 ──────────────────────────────────────────────────────────────────
month_dates = {
    f"{int(year):04d}-{int(month):02d}-{d:02d}"
    for week in cal for d in week if d != 0
}
month_gps     = len(gps_dates & month_dates)
month_weather = len(weather_dates & month_dates)
month_injury  = len(injury_dates & month_dates)
month_full    = len(gps_dates & weather_dates & injury_dates & month_dates)

st.subheader(f"{int(year)}년 {int(month)}월 요약")
s1, s2, s3, s4 = st.columns(4)
s1.metric("GPS 입력일",  month_gps)
s2.metric("날씨 수집일", month_weather)
s3.metric("부상 입력일", month_injury)
s4.metric("3개 모두 완료", month_full)
