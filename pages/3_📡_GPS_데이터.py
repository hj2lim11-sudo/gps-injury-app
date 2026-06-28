"""GPS 데이터 — 날짜별 조회 및 다운로드."""
import streamlit as st
import pandas as pd
from io import BytesIO
from utils.auth import require_login
require_login()

from utils.storage import load, GPS_METRIC_COLS

st.set_page_config(page_title="GPS 데이터", page_icon="📡", layout="wide")
st.title("📡 GPS 데이터")

gps = load("gps")

if gps.empty:
    st.info("저장된 GPS 데이터가 없습니다. 홈에서 세션을 업로드하세요.")
    st.stop()

gps["date"] = pd.to_datetime(gps["date"], errors="coerce")
gps_sorted = gps.sort_values(["date", "session_order", "player_id"])

# ── 필터 ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("필터")
    dates = sorted(gps_sorted["date"].dropna().dt.strftime("%Y-%m-%d").unique(), reverse=True)
    sel_dates = st.multiselect("날짜", dates, default=dates[:5] if len(dates) >= 5 else dates)

    players_list = sorted(gps_sorted["player_name"].dropna().unique())
    sel_players = st.multiselect("선수", players_list)

    session_types = gps_sorted["session_type"].dropna().unique().tolist()
    sel_types = st.multiselect("세션 유형", session_types, default=session_types)

filtered = gps_sorted.copy()
if sel_dates:
    filtered = filtered[filtered["date"].dt.strftime("%Y-%m-%d").isin(sel_dates)]
if sel_players:
    filtered = filtered[filtered["player_name"].isin(sel_players)]
if sel_types:
    filtered = filtered[filtered["session_type"].isin(sel_types)]

filtered["date"] = filtered["date"].dt.strftime("%Y-%m-%d")

# ── 요약 지표 ─────────────────────────────────────────────────────────────────
st.subheader("요약")
m1, m2, m3, m4 = st.columns(4)
m1.metric("총 세션 수", filtered["session_id"].nunique())
m2.metric("총 선수·세션 행", len(filtered))
m3.metric("기간",
    f"{filtered['date'].min()} ~ {filtered['date'].max()}" if not filtered.empty else "-")
m4.metric("등록 선수 수", filtered["player_name"].nunique())

st.divider()

# ── 탭 뷰 ─────────────────────────────────────────────────────────────────────
tab_all, tab_by_date, tab_by_player = st.tabs(["전체 데이터", "날짜별 요약", "선수별 요약"])

with tab_all:
    display_cols = ["date", "session_id", "session_type", "session_order",
                    "player_id", "jersey_no", "player_name", "position"] + GPS_METRIC_COLS
    show = filtered[[c for c in display_cols if c in filtered.columns]]
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.caption(f"{len(show)}행")

    buf = BytesIO()
    show.to_excel(buf, index=False)
    st.download_button("⬇️ Excel 다운로드", buf.getvalue(), file_name="gps_filtered.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_by_date:
    numeric_cols = [c for c in GPS_METRIC_COLS if c in filtered.columns]
    by_date = (
        filtered.groupby(["date", "session_id", "session_type", "session_order"])[numeric_cols]
        .mean().round(2).reset_index()
    )
    st.dataframe(by_date, use_container_width=True, hide_index=True)
    st.caption("선수 평균값")

with tab_by_player:
    numeric_cols = [c for c in GPS_METRIC_COLS if c in filtered.columns]
    by_player = (
        filtered.groupby(["player_id", "player_name", "position"])[numeric_cols]
        .mean().round(2).reset_index()
    )
    st.dataframe(by_player, use_container_width=True, hide_index=True)
    st.caption("전체 기간 평균값")
