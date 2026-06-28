"""대시보드 — 부하량·부상 현황 시각화."""
import streamlit as st
import pandas as pd

from utils.storage import load, GPS_METRIC_COLS

st.set_page_config(page_title="대시보드", page_icon="📊", layout="wide")
st.title("📊 대시보드")

gps = load("gps")
injuries = load("injuries")
players = load("players")

if gps.empty:
    st.info("GPS 데이터가 없습니다.")
    st.stop()

gps["date"] = pd.to_datetime(gps["date"], errors="coerce")
for col in GPS_METRIC_COLS:
    if col in gps.columns:
        gps[col] = pd.to_numeric(gps[col], errors="coerce")
gps["session_order"] = pd.to_numeric(gps.get("session_order"), errors="coerce")

# ── 필터 ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("필터")
    all_players = sorted(gps["player_name"].dropna().unique())
    sel_player = st.selectbox("선수", ["전체"] + all_players)
    date_range = st.date_input("기간",
        value=[gps["date"].min().date(), gps["date"].max().date()],
        min_value=gps["date"].min().date(),
        max_value=gps["date"].max().date(),
    )

filtered = gps.copy()
if sel_player != "전체":
    filtered = filtered[filtered["player_name"] == sel_player]
if len(date_range) == 2:
    filtered = filtered[
        (filtered["date"] >= pd.Timestamp(date_range[0])) &
        (filtered["date"] <= pd.Timestamp(date_range[1]))
    ]

# ── 요약 카드 ─────────────────────────────────────────────────────────────────
st.subheader("기간 요약")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("세션 수", filtered["session_id"].nunique())
c2.metric("평균 이동거리 (km)",
    round(pd.to_numeric(filtered.get("total_distance_km", pd.Series()), errors="coerce").mean(), 2))
c3.metric("평균 최고속도 (km/h)",
    round(pd.to_numeric(filtered.get("max_speed", pd.Series()), errors="coerce").mean(), 2))
c4.metric("평균 HSR 거리 (m)",
    round(pd.to_numeric(filtered.get("hsr_distance", pd.Series()), errors="coerce").mean(), 1))
inj_count = 0
if not injuries.empty and sel_player != "전체":
    inj_count = len(injuries[injuries["player_name"] == sel_player])
elif not injuries.empty:
    inj_count = len(injuries)
c5.metric("부상 건수", inj_count)

st.divider()

# ── 날짜별 이동거리 트렌드 ────────────────────────────────────────────────────
st.subheader("날짜별 총 이동거리 트렌드")
if "total_distance_km" in filtered.columns:
    trend = (
        filtered.groupby("date")["total_distance_km"]
        .mean().reset_index()
        .sort_values("date")
    )
    trend["date_str"] = trend["date"].dt.strftime("%Y-%m-%d")
    st.line_chart(trend.set_index("date_str")["total_distance_km"])
else:
    st.info("total_distance_km 데이터 없음")

# ── 선수별 평균 부하 비교 ─────────────────────────────────────────────────────
st.subheader("선수별 평균 부하량 비교")
compare_col = st.selectbox("지표 선택",
    [c for c in GPS_METRIC_COLS if c in filtered.columns and filtered[c].notna().any()])

if compare_col:
    by_player = (
        filtered.groupby("player_name")[compare_col]
        .mean().sort_values(ascending=False).reset_index()
    )
    by_player.columns = ["선수", compare_col]
    st.bar_chart(by_player.set_index("선수"))

# ── 세션 유형별 평균 ─────────────────────────────────────────────────────────
st.subheader("세션 유형별 평균 GPS 지표")
if "session_type" in filtered.columns:
    type_cols = [c for c in ["total_distance_km", "max_speed", "hsr_distance", "sprint_distance"]
                 if c in filtered.columns]
    by_type = filtered.groupby("session_type")[type_cols].mean().round(2)
    st.dataframe(by_type, use_container_width=True)

# ── 부상 현황 ─────────────────────────────────────────────────────────────────
if not injuries.empty:
    st.divider()
    st.subheader("부상 현황")
    inj = injuries.copy()
    inj["date"] = pd.to_datetime(inj["date"], errors="coerce")
    if sel_player != "전체":
        inj = inj[inj["player_name"] == sel_player]

    if not inj.empty:
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("총 부상 건수", len(inj))
        ic2.metric("평균 결장일",
            round(pd.to_numeric(inj["absence_days"], errors="coerce").mean(), 1))
        ic3.metric("최근 부상",
            inj.sort_values("date")["date"].iloc[-1].strftime("%Y-%m-%d") if not inj.empty else "-")

        inj_show = inj.sort_values("date", ascending=False).copy()
        inj_show["date"] = inj_show["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            inj_show[["date", "player_name", "body_part", "injury_type", "severity", "absence_days"]],
            use_container_width=True, hide_index=True,
        )
