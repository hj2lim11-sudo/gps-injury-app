"""달력 기반 GPS 데이터 업로드 — 날짜 선택 → 파일 업로드 → 날씨 자동 결합 → 저장."""
import streamlit as st
st.set_page_config(page_title="데이터 업로드", page_icon="📅", layout="wide")

import pandas as pd
import calendar
from datetime import date, datetime

from utils.auth import require_login
require_login()

from utils.storage import (
    load, save, append_rows, next_session_seq,
    make_session_id, season_year_from_date, weekday_kr,
    time_band_from_hour, GPS_META_COLS, GPS_METRIC_COLS,
    TIME_BANDS, EVENT_CODES, KR_COLS,
)

def to_kr(df):
    return df.rename(columns={k: v for k, v in KR_COLS.items() if k in df.columns})
from utils.parser import parse_gps_bytes
from utils.weather import fetch_session_weather

st.title("📅 GPS 데이터 업로드")

# ── 세션 상태 초기화 ───────────────────────────────────────────────────────────
if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
if "num_sessions" not in st.session_state:
    st.session_state.num_sessions = 1
if "_prev_date" not in st.session_state:
    st.session_state._prev_date = None

# 날짜 바뀌면 세션 슬롯 초기화
if st.session_state.selected_date != st.session_state._prev_date:
    st.session_state.num_sessions = 1
    st.session_state._prev_date = st.session_state.selected_date

# ── GPS 업로드 현황 로드 ──────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def _uploaded_dates():
    gps = load("gps")
    if gps.empty or "session_date" not in gps.columns:
        return set()
    return set(gps["session_date"].dropna().astype(str))

uploaded = _uploaded_dates()

# ── 연월 선택 ─────────────────────────────────────────────────────────────────
today    = date.today()
MIN_DATE = date(2025, 12, 26)
hdr1, hdr2, hdr3 = st.columns([1, 1, 5])
year  = hdr1.number_input("년", 2025, 2028, today.year, label_visibility="collapsed")
month = hdr2.number_input("월", 1, 12, today.month, label_visibility="collapsed")
hdr1.caption(f"{int(year)}년")
hdr2.caption(f"{int(month)}월")

st.divider()

# ── 달력 렌더링 ───────────────────────────────────────────────────────────────
DAYS_HDR = ["월", "화", "수", "목", "금", "토", "일"]
cal      = calendar.monthcalendar(int(year), int(month))

# 요일 헤더
hcols = st.columns(7)
for i, d in enumerate(DAYS_HDR):
    color = "red" if i == 5 else ("blue" if i == 6 else "#333")
    hcols[i].markdown(
        f"<div style='text-align:center;font-weight:bold;color:{color}'>{d}</div>",
        unsafe_allow_html=True,
    )

for week in cal:
    wcols = st.columns(7)
    for i, day in enumerate(week):
        with wcols[i]:
            if day == 0:
                st.markdown("<div style='height:64px'></div>", unsafe_allow_html=True)
                continue
            d_str    = f"{int(year):04d}-{int(month):02d}-{day:02d}"
            d_date   = date(int(year), int(month), day)
            if d_date < MIN_DATE:
                st.markdown("<div style='height:64px'></div>", unsafe_allow_html=True)
                continue
            has_data = d_str in uploaded
            is_sel   = (d_str == st.session_state.selected_date)
            is_today = (d_str == today.strftime("%Y-%m-%d"))

            icon      = "✅" if has_data else "⬜"
            border    = "3px solid #1f77b4" if is_sel else "1px solid #ddd"
            bg        = "#e8f0fe" if is_sel else ("#f0fff0" if has_data else "#fafafa")
            day_color = "red" if i == 5 else ("blue" if i == 6 else "#333")
            today_mark = "🔘" if is_today else ""

            st.markdown(
                f"<div style='border:{border};border-radius:8px;padding:4px;min-height:62px;"
                f"background:{bg};text-align:center'>"
                f"<span style='font-size:12px;color:{day_color};font-weight:bold'>{today_mark}{day}</span><br>"
                f"<span style='font-size:18px'>{icon}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("선택", key=f"sel_{d_str}", use_container_width=True,
                         help=d_str, type="secondary"):
                st.session_state.selected_date = d_str
                st.rerun()

# ── 업로드 폼 ─────────────────────────────────────────────────────────────────
sel = st.session_state.selected_date
if not sel:
    st.info("달력에서 날짜를 선택하면 GPS 파일 업로드 폼이 나타납니다.")
    st.stop()

st.divider()
wd = weekday_kr(sel)
st.subheader(f"📂 {sel} ({wd}) — GPS 업로드")

if sel in uploaded:
    st.info("이 날짜는 이미 데이터가 있습니다. 추가 세션을 업로드하거나 저장하면 기존 데이터에 추가됩니다.")

# 선수 명단 (파싱 시 player_id 매칭용)
players_df = load("players")
VENUE_OPTIONS = [
    "명지대학교 자연캠퍼스", "서울", "수원", "인천", "춘천",
    "강릉", "충주", "청주", "천안", "대전", "전주", "군산",
    "광주", "목포", "대구", "안동", "포항", "울산", "부산",
    "창원", "제주", "직접 입력",
]

sessions_data = []  # 저장할 세션 목록

for idx in range(int(st.session_state.num_sessions)):
    st.markdown(f"#### 세션 {idx + 1}")
    s_cols = st.columns([3, 1])

    with s_cols[0]:
        gps_file = st.file_uploader(
            f"GPS 파일 (Excel/CSV)",
            type=["xlsx", "xls", "csv"],
            key=f"gps_file_{sel}_{idx}",
            help="선수별 GPS 지표가 담긴 파일",
        )

    with s_cols[1]:
        st.write("")

    if gps_file:
        m1, m2, m3, m4 = st.columns(4)
        start_str = m1.text_input("시작시간 (HH:MM)", "10:00",  key=f"start_{sel}_{idx}")
        end_str   = m2.text_input("종료시간 (HH:MM)", "12:00",  key=f"end_{sel}_{idx}")
        venue_sel = m3.selectbox("장소",   VENUE_OPTIONS,   key=f"venue_{sel}_{idx}")
        venue_txt = m3.text_input("장소 직접 입력", key=f"venue_txt_{sel}_{idx}") if venue_sel == "직접 입력" else ""
        venue     = venue_txt if venue_sel == "직접 입력" else venue_sel

        m5, m6, m7 = st.columns(3)
        try:
            start_h = int(start_str.split(":")[0])
        except Exception:
            start_h = 10
        auto_band = time_band_from_hour(start_h)
        band      = m5.selectbox("시간대", TIME_BANDS,
                                  index=TIME_BANDS.index(auto_band), key=f"band_{sel}_{idx}")
        event     = m6.selectbox("이벤트", EVENT_CODES, key=f"event_{sel}_{idx}")
        opponent  = m7.text_input("상대팀 (경기시)", key=f"opp_{sel}_{idx}")
        event_det = st.text_input("경기명/훈련명 (선택)", key=f"edet_{sel}_{idx}")

        sessions_data.append({
            "idx": idx, "file": gps_file,
            "start": start_str, "end": end_str,
            "venue": venue, "band": band,
            "event": event, "opponent": opponent,
            "event_detail": event_det,
        })
    else:
        st.caption("파일을 업로드하면 입력 폼이 나타납니다.")

    st.markdown("---")

col_add, col_save = st.columns([1, 3])
with col_add:
    if st.session_state.num_sessions < 3:
        if st.button("➕ 세션 추가", use_container_width=True):
            st.session_state.num_sessions += 1
            st.rerun()

with col_save:
    if sessions_data and st.button("💾 저장 (날씨 자동 수집)", type="primary", use_container_width=True):
        all_rows = []
        errors   = []
        progress = st.progress(0)
        status   = st.empty()

        for k, s in enumerate(sessions_data):
            progress.progress((k + 1) / len(sessions_data))
            status.info(f"세션 {k+1} 처리 중...")

            # 1) GPS 파싱
            try:
                file_bytes = s["file"].read()
                gps_df = parse_gps_bytes(file_bytes, s["file"].name, players_df)
            except Exception as e:
                errors.append(f"세션 {k+1} 파싱 오류: {e}")
                continue

            if gps_df.empty:
                errors.append(f"세션 {k+1}: GPS 데이터 없음")
                continue

            # 2) 날씨 수집
            status.info(f"세션 {k+1} 날씨 수집 중... ({s['venue']})")
            try:
                start_h = int(s["start"].split(":")[0])
                end_h   = int(s["end"].split(":")[0])
                dur_min = max((end_h - start_h) * 60, 10)
                wx = fetch_session_weather(s["venue"], sel, s["start"], dur_min)
            except Exception as e:
                wx = {}
                errors.append(f"세션 {k+1} 날씨 오류: {e}")

            # 3) 세션 메타 조립
            seq        = next_session_seq(sel, s["band"], s["event"])
            session_id = make_session_id(sel, s["band"], s["event"], seq)
            try:
                t_start = datetime.strptime(s["start"], "%H:%M")
                t_end   = datetime.strptime(s["end"],   "%H:%M")
                dur_min = int((t_end - t_start).total_seconds() / 60)
            except Exception:
                dur_min = ""

            meta = {
                "session_id":           session_id,
                "season_year":          season_year_from_date(sel),
                "session_date":         sel,
                "weekday":              weekday_kr(sel),
                "training_time_band":   s["band"],
                "event_code":           s["event"],
                "event_detail":         s["event_detail"],
                "venue":                s["venue"],
                "opponent":             s["opponent"],
                "start_time":           s["start"],
                "end_time":             s["end"],
                "session_duration_min": dur_min,
                "temperature_c":        wx.get("temperature_c", ""),
                "humidity_pct":         wx.get("humidity_pct", ""),
                "precipitation_mm":     wx.get("precipitation_mm", ""),
            }

            # 4) GPS 행마다 메타 결합
            for col, val in meta.items():
                gps_df[col] = val

            # 컬럼 순서 정렬
            ordered = GPS_META_COLS + GPS_METRIC_COLS
            gps_df  = gps_df.reindex(columns=[c for c in ordered if c in gps_df.columns])
            all_rows.append(gps_df)

        progress.progress(1.0)

        if all_rows:
            combined = pd.concat(all_rows, ignore_index=True)
            with st.spinner("Google Sheets에 저장 중..."):
                append_rows("gps", combined)
            _uploaded_dates.clear()
            st.success(f"✅ {len(sessions_data)}개 세션, {len(combined)}행 저장 완료!")
            st.balloons()
            st.session_state.num_sessions = 1
            st.rerun()

        for e in errors:
            st.error(e)

# ── 이 날짜 기존 데이터 미리보기 + 세션 삭제 ─────────────────────────────────
existing = load("gps")
if not existing.empty and "session_date" in existing.columns:
    day_data = existing[existing["session_date"] == sel]
    if not day_data.empty:
        st.divider()
        st.subheader(f"📋 {sel} 저장된 데이터 ({len(day_data)}행)")

        show_cols = ["session_id", "training_time_band", "event_code", "venue",
                     "player_name", "temperature_c", "humidity_pct", "precipitation_mm",
                     "total_distance_km", "max_speed"]
        st.dataframe(to_kr(day_data[[c for c in show_cols if c in day_data.columns]]),
                     use_container_width=True, hide_index=True)

        # 세션 삭제
        sessions_on_day = day_data["session_id"].unique().tolist()
        st.markdown("**🗑️ 세션 삭제**")
        del_col1, del_col2 = st.columns([2, 1])
        del_session = del_col1.selectbox(
            "삭제할 세션 선택", sessions_on_day, key=f"del_sess_{sel}"
        )
        if del_col2.button("삭제", type="secondary", key=f"del_btn_{sel}"):
            updated = existing[existing["session_id"] != del_session]
            with st.spinner("삭제 중..."):
                save("gps", updated)
            _uploaded_dates.clear()
            st.success(f"✅ {del_session} 삭제 완료")
            st.rerun()
