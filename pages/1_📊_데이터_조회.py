"""GPS + 날씨 결합 데이터 조회 및 다운로드."""
import streamlit as st
st.set_page_config(page_title="데이터 조회", page_icon="📊", layout="wide")

import pandas as pd
from io import BytesIO

from utils.auth import require_login
require_login()

from utils.storage import load, GPS_METRIC_COLS, KR_COLS

def to_kr(df):
    return df.rename(columns={k: v for k, v in KR_COLS.items() if k in df.columns})
st.title("📊 GPS · 날씨 데이터 조회")

gps = load("gps")

if gps.empty:
    st.info("저장된 데이터가 없습니다. 📅 업로드 페이지에서 GPS 파일을 먼저 업로드하세요.")
    st.stop()

# 구 스키마(date) → 신 스키마(session_date) 호환
if "session_date" not in gps.columns and "date" in gps.columns:
    gps = gps.rename(columns={"date": "session_date"})
if "session_date" not in gps.columns:
    st.warning("데이터 컬럼 구조가 맞지 않습니다. GPS_gps_data 시트를 초기화한 뒤 다시 업로드해주세요.")
    st.stop()

# 수치 변환
for c in GPS_METRIC_COLS + ["temperature_c", "humidity_pct", "precipitation_mm",
                             "session_duration_min"]:
    if c in gps.columns:
        gps[c] = pd.to_numeric(gps[c], errors="coerce")
gps["session_date"] = pd.to_datetime(gps["session_date"], errors="coerce")

# ── 요약 지표 ─────────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("총 세션 수",    gps["session_id"].nunique())
m2.metric("총 선수·세션 행", len(gps))
m3.metric("날짜 수",       gps["session_date"].dt.date.nunique())
m4.metric("등록 선수 수",   gps["player_name"].nunique())

st.divider()

# ── 필터 (사이드바) ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("필터")
    dates = sorted(gps["session_date"].dropna().dt.strftime("%Y-%m-%d").unique(), reverse=True)
    sel_dates = st.multiselect("날짜", dates, default=dates[:10] if len(dates) >= 10 else dates)

    events = gps["event_code"].dropna().unique().tolist()
    sel_events = st.multiselect("이벤트", events, default=events)

    players = sorted(gps["player_name"].dropna().unique())
    sel_players = st.multiselect("선수", players)

filtered = gps.copy()
if sel_dates:
    filtered = filtered[filtered["session_date"].dt.strftime("%Y-%m-%d").isin(sel_dates)]
if sel_events:
    filtered = filtered[filtered["event_code"].isin(sel_events)]
if sel_players:
    filtered = filtered[filtered["player_name"].isin(sel_players)]

filtered["session_date"] = filtered["session_date"].dt.strftime("%Y-%m-%d")

# ── 탭 뷰 ─────────────────────────────────────────────────────────────────────
tab_all, tab_session, tab_player = st.tabs(["전체 데이터", "세션별 요약", "선수별 요약"])

META_SHOW = ["session_date", "session_id", "training_time_band", "event_code",
             "venue", "player_id", "jersey_no", "player_name",
             "temperature_c", "humidity_pct", "precipitation_mm"]

with tab_all:
    show_cols = [c for c in META_SHOW + GPS_METRIC_COLS if c in filtered.columns]
    st.dataframe(to_kr(filtered[show_cols]), use_container_width=True, hide_index=True)
    st.caption(f"{len(filtered)}행")

    out = to_kr(filtered[show_cols])
    buf = BytesIO()
    out.to_excel(buf, index=False)
    st.download_button("⬇️ Excel 다운로드", buf.getvalue(),
                       file_name="gps_data.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    csv_buf = out.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ CSV 다운로드", csv_buf,
                       file_name="gps_data.csv", mime="text/csv")

with tab_session:
    num_cols = [c for c in GPS_METRIC_COLS if c in filtered.columns]
    by_sess = (
        filtered.groupby(["session_date", "session_id", "training_time_band",
                          "event_code", "venue",
                          "temperature_c", "humidity_pct", "precipitation_mm"])[num_cols]
        .mean().round(2).reset_index()
    )
    st.dataframe(to_kr(by_sess), use_container_width=True, hide_index=True)
    st.caption("선수 평균값")

with tab_player:
    num_cols = [c for c in GPS_METRIC_COLS if c in filtered.columns]
    by_player = (
        filtered.groupby(["player_id", "jersey_no", "player_name"])[num_cols]
        .mean().round(2).reset_index()
    )
    st.dataframe(to_kr(by_player), use_container_width=True, hide_index=True)
    st.caption("전체 기간 선수 평균값")
