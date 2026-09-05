"""데이터 결합 — GPS + 날씨(기온·습도) → 최종 ML 학습 데이터셋."""
import streamlit as st
import pandas as pd
from io import BytesIO
from utils.auth import require_login
require_login()

from utils.storage import load, save, GPS_METRIC_COLS

st.set_page_config(page_title="데이터 결합", page_icon="🔗", layout="wide")
st.title("🔗 데이터 결합")
st.caption("날짜 + 선수 기준으로 GPS · 날씨(기온·습도)를 한 행으로 결합합니다.")

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
gps = load("gps")

if gps.empty:
    st.warning("GPS 데이터가 없습니다. 홈에서 세션을 먼저 업로드하세요.")
    st.stop()

# 수치 변환
for c in GPS_METRIC_COLS + ["temperature", "humidity", "session_order", "duration_min"]:
    if c in gps.columns:
        gps[c] = pd.to_numeric(gps[c], errors="coerce")
gps["date"] = pd.to_datetime(gps["date"], errors="coerce")

# ── 현황 ─────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("GPS 행 수", len(gps), help="선수×세션")
c2.metric("날짜 수", gps["date"].dt.date.nunique())
c3.metric("날씨 포함 행", int(gps["temperature"].notna().sum()))

st.divider()

# ── 결합 실행 ─────────────────────────────────────────────────────────────────
st.subheader("결합 설정")
st.info("GPS 데이터에 이미 포함된 기온·습도(세션 시간대 평균)를 그대로 사용합니다.")

if st.button("🔗 데이터 결합 실행", type="primary", use_container_width=True):
    with st.spinner("결합 중..."):
        merged = gps.copy()
        merged = merged.sort_values(
            ["date", "session_order", "player_id"]
        ).reset_index(drop=True)
        merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")

        # 최종 컬럼 순서 정리
        front_cols = [
            "date", "session_id", "session_type", "session_order",
            "start_time", "duration_min", "location", "opponent",
            "player_id", "jersey_no", "player_name", "position",
            "temperature", "humidity",
        ]
        metric_cols = [c for c in GPS_METRIC_COLS if c in merged.columns]
        ordered = front_cols + metric_cols
        merged = merged[[c for c in ordered if c in merged.columns]]

        save("merged", merged)

    st.success(f"✅ 결합 완료!  총 {len(merged)}행 · {len(merged.columns)}컬럼")

    # 미리보기
    st.dataframe(merged, use_container_width=True, hide_index=True)

    # 다운로드
    col1, col2 = st.columns(2)
    buf_xl = BytesIO()
    merged.to_excel(buf_xl, index=False)
    col1.download_button("⬇️ Excel 다운로드", buf_xl.getvalue(),
                         file_name="merged_dataset.xlsx",
                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buf_csv = merged.to_csv(index=False).encode("utf-8-sig")
    col2.download_button("⬇️ CSV 다운로드", buf_csv,
                         file_name="merged_dataset.csv", mime="text/csv")

# ── 기존 저장 데이터 ──────────────────────────────────────────────────────────
st.divider()
existing = load("merged")
if not existing.empty:
    st.subheader(f"현재 저장된 결합 데이터  ({len(existing)}행 · {len(existing.columns)}컬럼)")
    st.dataframe(existing, use_container_width=True, hide_index=True)
