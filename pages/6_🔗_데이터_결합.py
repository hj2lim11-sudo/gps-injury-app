"""데이터 결합 — GPS + 날씨 + 부상 → 최종 ML 학습 데이터셋 생성."""
import streamlit as st
import pandas as pd
from io import BytesIO
from utils.auth import require_login
require_login()

from utils.storage import load, save, GPS_METRIC_COLS

st.set_page_config(page_title="데이터 결합", page_icon="🔗", layout="wide")
st.title("🔗 데이터 결합")
st.caption("GPS + 날씨 + 부상 데이터를 결합하여 ML 학습용 최종 데이터셋을 생성합니다.")

# ── 데이터 현황 ───────────────────────────────────────────────────────────────
gps = load("gps")
weather = load("weather")
injuries = load("injuries")

c1, c2, c3 = st.columns(3)
c1.metric("GPS 행 수", len(gps), help="선수×세션 행")
c2.metric("날씨 행 수", len(weather), help="시간별 기온·습도")
c3.metric("부상 기록 수", len(injuries))

if gps.empty:
    st.warning("GPS 데이터가 없습니다. 홈에서 세션을 먼저 업로드하세요.")
    st.stop()

st.divider()

# ── 결합 옵션 ─────────────────────────────────────────────────────────────────
st.subheader("결합 설정")

col_a, col_b = st.columns(2)
with col_a:
    merge_weather = st.checkbox("날씨 데이터 결합", value=not weather.empty,
                                 disabled=weather.empty,
                                 help="GPS의 date + start_time 시각으로 날씨 매칭")
    weather_strategy = st.radio(
        "날씨 매칭 방식",
        ["GPS에 이미 있는 temperature/humidity 사용", "weather_data.xlsx에서 재매핑"],
        disabled=not merge_weather,
    )

with col_b:
    merge_injury = st.checkbox("부상 플래그 추가", value=not injuries.empty,
                                disabled=injuries.empty,
                                help="각 선수·날짜에 부상 발생 여부 플래그(0/1) 및 세부 정보 추가")
    injury_window = st.number_input(
        "부상 선행일 (일)", min_value=1, max_value=28, value=7,
        help="부상 발생 N일 전까지를 '위험 기간'으로 표시 (injury_within_Nd 컬럼)",
        disabled=not merge_injury,
    )

st.divider()

# ── 결합 실행 ─────────────────────────────────────────────────────────────────
if st.button("🔗 데이터 결합 실행", type="primary", use_container_width=True):
    with st.spinner("결합 중..."):
        merged = gps.copy()
        merged["date"] = pd.to_datetime(merged["date"], errors="coerce")

        # ── 날씨 재매핑 ──
        if merge_weather and weather_strategy == "weather_data.xlsx에서 재매핑" and not weather.empty:
            weather_num = weather.copy()
            weather_num["date"] = pd.to_datetime(weather_num["date"], errors="coerce")
            weather_num["hour"] = pd.to_numeric(weather_num["hour"], errors="coerce").astype("Int64")
            weather_num["temperature"] = pd.to_numeric(weather_num["temperature"], errors="coerce")
            weather_num["humidity"] = pd.to_numeric(weather_num["humidity"], errors="coerce")

            # start_time → 시각 추출
            merged["_hour"] = pd.to_datetime(merged["start_time"], format="%H:%M", errors="coerce").dt.hour.astype("Int64")

            # 날짜+시각으로 merge
            merged = merged.merge(
                weather_num[["date", "hour", "temperature", "humidity"]].rename(
                    columns={"temperature": "temperature_w", "humidity": "humidity_w"}
                ),
                left_on=["date", "_hour"],
                right_on=["date", "hour"],
                how="left",
            )
            # 날씨 덮어쓰기 (매칭된 경우만)
            merged["temperature"] = merged["temperature_w"].combine_first(
                pd.to_numeric(merged["temperature"], errors="coerce")
            )
            merged["humidity"] = merged["humidity_w"].combine_first(
                pd.to_numeric(merged["humidity"], errors="coerce")
            )
            merged.drop(columns=["temperature_w", "humidity_w", "_hour", "hour"], errors="ignore", inplace=True)

        # ── 부상 플래그 ──
        if merge_injury and not injuries.empty:
            inj = injuries.copy()
            inj["date"] = pd.to_datetime(inj["date"], errors="coerce")
            inj["absence_days"] = pd.to_numeric(inj["absence_days"], errors="coerce")

            # 부상 발생일 집합 (player_id, date)
            inj_set = set(zip(inj["player_id"].astype(str), inj["date"].dt.strftime("%Y-%m-%d")))

            def injury_flag(row):
                return int((str(row["player_id"]), row["date"].strftime("%Y-%m-%d")) in inj_set)

            merged["injury_occurred"] = merged.apply(injury_flag, axis=1)

            # N일 이내 부상 발생 여부 (선행 지표)
            def injury_within(row):
                pid = str(row["player_id"])
                d = row["date"]
                for _, ir in inj.iterrows():
                    if str(ir["player_id"]) == pid:
                        diff = (ir["date"] - d).days
                        if 0 < diff <= injury_window:
                            return 1
                return 0

            merged[f"injury_within_{injury_window}d"] = merged.apply(injury_within, axis=1)

            # 부상 상세 컬럼 (부위, 유형)
            inj_detail = inj.groupby("player_id").apply(
                lambda g: g.sort_values("date").iloc[-1]
            )[["player_id", "body_part", "injury_type", "severity", "absence_days"]].reset_index(drop=True)
            inj_detail.columns = ["player_id", "last_body_part", "last_injury_type",
                                   "last_severity", "last_absence_days"]
            merged = merged.merge(inj_detail, on="player_id", how="left")

        # ── 날짜 정렬 (딥러닝 시계열용) ──
        merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
        merged = merged.sort_values(["date", "session_order", "player_id"]).reset_index(drop=True)
        merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")

        # 저장
        save("merged", merged)

    st.success(f"✅ 결합 완료! 총 {len(merged)}행, {len(merged.columns)}컬럼")

    # 미리보기
    st.dataframe(merged.head(20), use_container_width=True, hide_index=True)

    # 다운로드
    buf = BytesIO()
    merged.to_excel(buf, index=False)
    st.download_button(
        "⬇️ 최종 데이터셋 다운로드 (Excel)",
        buf.getvalue(),
        file_name="merged_dataset.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    buf_csv = merged.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 최종 데이터셋 다운로드 (CSV)",
        buf_csv,
        file_name="merged_dataset.csv",
        mime="text/csv",
    )

# ── 기존 결합 데이터 미리보기 ─────────────────────────────────────────────────
st.divider()
merged_existing = load("merged")
if not merged_existing.empty:
    st.subheader("현재 저장된 결합 데이터")
    m1, m2, m3 = st.columns(3)
    m1.metric("행 수", len(merged_existing))
    m2.metric("컬럼 수", len(merged_existing.columns))
    inj_cols = [c for c in merged_existing.columns if "injury" in c]
    m3.metric("부상 관련 컬럼", len(inj_cols))
    st.dataframe(merged_existing.tail(10), use_container_width=True, hide_index=True)
