"""데이터 결합 — GPS + 날씨 + 부상 → 최종 ML 학습 데이터셋."""
import streamlit as st
import pandas as pd
from io import BytesIO
from utils.auth import require_login
require_login()

from utils.storage import load, save, GPS_METRIC_COLS

st.set_page_config(page_title="데이터 결합", page_icon="🔗", layout="wide")
st.title("🔗 데이터 결합")
st.caption("날짜 + 선수 기준으로 GPS · 날씨 · 부상 데이터를 한 행으로 결합합니다.")

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
gps      = load("gps")
injuries = load("injuries")

if gps.empty:
    st.warning("GPS 데이터가 없습니다. 홈에서 세션을 먼저 업로드하세요.")
    st.stop()

# 수치 변환
for c in GPS_METRIC_COLS + ["temperature", "humidity", "session_order", "duration_min"]:
    if c in gps.columns:
        gps[c] = pd.to_numeric(gps[c], errors="coerce")
gps["date"] = pd.to_datetime(gps["date"], errors="coerce")

if not injuries.empty:
    injuries["date"] = pd.to_datetime(injuries["date"], errors="coerce")
    injuries["pain_level"]   = pd.to_numeric(injuries["pain_level"],   errors="coerce")
    injuries["absence_days"] = pd.to_numeric(injuries["absence_days"], errors="coerce")

# ── 현황 ─────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("GPS 행 수",    len(gps),      help="선수×세션")
c2.metric("부상 기록 수", len(injuries))
c3.metric("결합 가능 날짜", gps["date"].dt.date.nunique())

st.divider()

# ── 결합 옵션 ─────────────────────────────────────────────────────────────────
st.subheader("결합 설정")
col_a, col_b = st.columns(2)
with col_a:
    merge_injury = st.checkbox("부상 데이터 결합", value=not injuries.empty, disabled=injuries.empty)
with col_b:
    injury_window = st.number_input(
        "향후 부상 예측 기간 (일)", min_value=1, max_value=28, value=7,
        help="GPS 기록 후 N일 이내 부상 발생 시 injury_within_Nd = 1",
        disabled=not merge_injury,
    )

st.divider()

# ── 결합 실행 ─────────────────────────────────────────────────────────────────
if st.button("🔗 데이터 결합 실행", type="primary", use_container_width=True):
    with st.spinner("결합 중..."):

        # 기본: GPS (날씨 기온·습도 이미 포함)
        merged = gps.copy()

        # ── 부상 데이터 결합 ─────────────────────────────────────────────────
        if merge_injury and not injuries.empty:
            inj = injuries.copy()

            # 당일 부상 여부 (0/1)
            inj_day = inj[["player_id", "date", "injury_status", "body_part",
                            "pain_level", "absence_days"]].copy()
            inj_day = inj_day.rename(columns={
                "injury_status": "injury_cause",
                "body_part":     "injury_body_part",
                "pain_level":    "injury_pain_level",
                "absence_days":  "injury_absence_days",
            })
            inj_day["injured"] = (inj_day["injury_cause"] != "해당없음").astype(int)

            merged = merged.merge(
                inj_day, on=["player_id", "date"], how="left"
            )
            merged["injured"] = merged["injured"].fillna(0).astype(int)

            # 향후 N일 이내 부상 발생 여부 (예측 타겟)
            inj_dates = inj[inj["injury_cause"].fillna("해당없음") != "해당없음"][
                ["player_id", "date"]
            ].copy()
            inj_dates = inj_dates.rename(columns={"date": "inj_date"})

            def future_injury(row):
                pid = row["player_id"]
                d   = row["date"]
                sub = inj_dates[inj_dates["player_id"] == pid]
                if sub.empty:
                    return 0
                diffs = (sub["inj_date"] - d).dt.days
                return int(((diffs > 0) & (diffs <= injury_window)).any())

            merged[f"injury_within_{injury_window}d"] = merged.apply(future_injury, axis=1)

        # ── 정렬 ─────────────────────────────────────────────────────────────
        merged = merged.sort_values(
            ["date", "session_order", "player_id"]
        ).reset_index(drop=True)
        merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")

        save("merged", merged)

    st.success(f"✅ 결합 완료!  총 {len(merged)}행 · {len(merged.columns)}컬럼")

    # 미리보기
    preview_cols = (
        ["date", "player_name", "session_type", "location", "temperature", "humidity"]
        + [c for c in GPS_METRIC_COLS if c in merged.columns]
        + [c for c in ["injured", "injury_cause", "injury_body_part",
                        "injury_pain_level", f"injury_within_{injury_window}d"]
           if c in merged.columns]
    )
    st.dataframe(
        merged[[c for c in preview_cols if c in merged.columns]],
        use_container_width=True, hide_index=True,
    )

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
    st.dataframe(existing.head(30), use_container_width=True, hide_index=True)
