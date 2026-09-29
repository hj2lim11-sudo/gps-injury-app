"""세션별 원본 파일명 확인 — 업로드한 파일과 세션ID 매핑."""
import streamlit as st
st.set_page_config(page_title="파일 정리", page_icon="📁", layout="wide")

import pandas as pd

from utils.auth import require_login
require_login()

from utils.storage import load

st.title("📁 파일 정리")
st.caption("업로드한 원본 파일명과 저장된 세션ID를 확인합니다.")

gps = load("gps")

if gps.empty or "session_date" not in gps.columns:
    st.info("저장된 데이터가 없습니다.")
    st.stop()

# 구 스키마 호환
if "session_date" not in gps.columns and "date" in gps.columns:
    gps = gps.rename(columns={"date": "session_date"})

gps["session_date"] = pd.to_datetime(gps["session_date"], errors="coerce")

# 세션별 1행으로 집약
agg_dict = {
    "session_date": ("session_date", "first"),
    "event_code":   ("event_code",   "first"),
    "venue":        ("venue",        "first"),
    "opponent":     ("opponent",     "first"),
}
if "source_filename" in gps.columns:
    agg_dict["source_filename"] = ("source_filename", "first")
else:
    gps["source_filename"] = ""
    agg_dict["source_filename"] = ("source_filename", "first")

sessions = (
    gps.groupby("session_id")
    .agg(**agg_dict)
    .reset_index()
)
n_players_map = gps.groupby("session_id")["player_name"].nunique()
sessions["n_players"] = sessions["session_id"].map(n_players_map)
sessions = sessions.sort_values("session_date", ascending=False).reset_index(drop=True)
sessions["session_date"] = sessions["session_date"].dt.strftime("%Y-%m-%d")

# ── 필터 ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("필터")
    events = sorted(sessions["event_code"].dropna().unique().tolist())
    sel_events = st.multiselect("이벤트", events, default=events)

if sel_events:
    sessions = sessions[sessions["event_code"].isin(sel_events)]

# ── 표시 ─────────────────────────────────────────────────────────────────────
st.metric("총 세션 수", len(sessions))

display_cols = {
    "session_date":   "날짜",
    "session_id":     "세션ID",
    "event_code":     "이벤트",
    "venue":          "장소",
    "opponent":       "상대팀",
    "n_players":      "선수 수",
    "source_filename": "원본 파일명",
}
show = sessions[[c for c in display_cols if c in sessions.columns]].copy()
show.columns = [display_cols[c] for c in show.columns]

st.dataframe(show, use_container_width=True, hide_index=True)

# 다운로드
buf = show.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ CSV 다운로드", buf, file_name="session_file_list.csv", mime="text/csv")
