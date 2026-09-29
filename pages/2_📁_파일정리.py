"""세션별 원본 파일명 확인 — 업로드한 파일과 세션ID 매핑."""
import streamlit as st
st.set_page_config(page_title="파일 정리", page_icon="📁", layout="wide")

import pandas as pd
from io import BytesIO

from utils.auth import require_login
require_login()

from utils.storage import load, GPS_META_COLS, GPS_METRIC_COLS, KR_COLS

def to_kr(df):
    return df.rename(columns={k: v for k, v in KR_COLS.items() if k in df.columns})

st.title("📁 파일 정리")
st.caption("업로드한 원본 파일명과 저장된 세션ID를 확인하고, 세션별 데이터를 다운로드합니다.")

gps = load("gps")

if gps.empty or "session_date" not in gps.columns:
    st.info("저장된 데이터가 없습니다.")
    st.stop()

if "session_date" not in gps.columns and "date" in gps.columns:
    gps = gps.rename(columns={"date": "session_date"})

gps["session_date"] = pd.to_datetime(gps["session_date"], errors="coerce")

if "source_filename" not in gps.columns:
    gps["source_filename"] = ""

# ── 세션별 1행 집약 ────────────────────────────────────────────────────────────
sessions = (
    gps.groupby("session_id")
    .agg(
        session_date    = ("session_date",    "first"),
        event_code      = ("event_code",      "first"),
        venue           = ("venue",           "first"),
        opponent        = ("opponent",        "first"),
        source_filename = ("source_filename", "first"),
    )
    .reset_index()
)
n_players_map = gps.groupby("session_id")["player_name"].nunique()
sessions["n_players"] = sessions["session_id"].map(n_players_map)
sessions = sessions.sort_values("session_date", ascending=False).reset_index(drop=True)
sessions["year"]  = sessions["session_date"].dt.year.astype(str)
sessions["month"] = sessions["session_date"].dt.month
sessions["session_date"] = sessions["session_date"].dt.strftime("%Y-%m-%d")

# ── 년 / 월 필터 ──────────────────────────────────────────────────────────────
years  = sorted(sessions["year"].unique(), reverse=True)
f1, f2, _ = st.columns([1, 1, 4])
sel_year  = f1.selectbox("년", years)
month_opts = ["전체"] + list(range(1, 13))
sel_month  = f2.selectbox("월", month_opts, format_func=lambda x: x if x == "전체" else f"{x}월")

view = sessions[sessions["year"] == sel_year].copy()
if sel_month != "전체":
    view = view[view["month"] == int(sel_month)]

# ── 이벤트 필터 (사이드바) ────────────────────────────────────────────────────
with st.sidebar:
    st.header("필터")
    events = sorted(sessions["event_code"].dropna().unique().tolist())
    sel_events = st.multiselect("이벤트", events, default=events)

if sel_events:
    view = view[view["event_code"].isin(sel_events)]

view = view.drop(columns=["year", "month"])

# ── 요약 표 ───────────────────────────────────────────────────────────────────
st.metric("총 세션 수", len(view))

display_cols = {
    "session_date":    "날짜",
    "session_id":      "세션ID",
    "event_code":      "이벤트",
    "venue":           "장소",
    "opponent":        "상대팀",
    "n_players":       "선수 수",
    "source_filename": "원본 파일명",
}
show = view[[c for c in display_cols if c in view.columns]].copy()
show.columns = [display_cols[c] for c in show.columns]
st.dataframe(show, use_container_width=True, hide_index=True)

# 전체 목록 CSV 다운로드
buf_all = show.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 목록 CSV 다운로드", buf_all,
                   file_name="session_file_list.csv", mime="text/csv")

# ── 세션별 GPS 데이터 다운로드 ────────────────────────────────────────────────
st.divider()
st.subheader("📥 세션 데이터 다운로드")

session_ids = view["session_id"].tolist()
if not session_ids:
    st.info("표시된 세션이 없습니다.")
    st.stop()

sel_sess = st.selectbox(
    "세션 선택",
    session_ids,
    format_func=lambda sid: f"{sid}  ({view.loc[view['session_id']==sid, 'session_date'].values[0]}  {view.loc[view['session_id']==sid, 'event_code'].values[0]}  {view.loc[view['session_id']==sid, 'venue'].values[0]})"
)

if sel_sess:
    sess_data = gps[gps["session_id"] == sel_sess].copy()
    sess_data["session_date"] = sess_data["session_date"].dt.strftime("%Y-%m-%d")

    all_cols = [c for c in GPS_META_COLS + GPS_METRIC_COLS if c in sess_data.columns]
    sess_data = sess_data[all_cols]

    st.dataframe(to_kr(sess_data), use_container_width=True, hide_index=True)
    st.caption(f"{len(sess_data)}명")

    dc1, dc2 = st.columns(2)
    csv_buf = to_kr(sess_data).to_csv(index=False).encode("utf-8-sig")
    dc1.download_button("⬇️ CSV", csv_buf,
                        file_name=f"{sel_sess}.csv", mime="text/csv")

    xls_buf = BytesIO()
    to_kr(sess_data).to_excel(xls_buf, index=False)
    dc2.download_button("⬇️ Excel", xls_buf.getvalue(),
                        file_name=f"{sel_sess}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
