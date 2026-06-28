"""날씨 데이터 — 누적 조회 + 수동 추가/일괄 수집."""
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import date
from utils.auth import require_login
require_login()

from utils.storage import load, save
from utils.weather import fetch_range

st.set_page_config(page_title="날씨 데이터", page_icon="🌤", layout="wide")
st.title("🌤 날씨 데이터")
st.caption("날씨 데이터는 홈에서 세션 저장 시 자동으로 누적됩니다. 이 페이지는 조회 및 수동 보완용입니다.")

weather = load("weather")

# ── 요약 ─────────────────────────────────────────────────────────────────────
if not weather.empty:
    w = weather.copy()
    w["date"] = pd.to_datetime(w["date"], errors="coerce")
    w["temperature"] = pd.to_numeric(w["temperature"], errors="coerce")
    w["humidity"]    = pd.to_numeric(w["humidity"], errors="coerce")
    w = w.sort_values("date")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("수집된 날씨 레코드", len(w))
    c2.metric("수집 시작일", w["date"].min().strftime("%Y-%m-%d") if not w.empty else "-")
    c3.metric("수집 최종일", w["date"].max().strftime("%Y-%m-%d") if not w.empty else "-")
    c4.metric("커버된 날짜 수", w["date"].dt.date.nunique())
else:
    st.info("아직 수집된 날씨 데이터가 없습니다. 홈에서 세션을 저장하거나 아래에서 일괄 수집하세요.")

st.divider()

tab_view, tab_bulk, tab_manual = st.tabs(["📋 데이터 조회", "🌐 일괄 수집 (Open-Meteo)", "✏️ 수동 추가"])

# ── 조회 ─────────────────────────────────────────────────────────────────────
with tab_view:
    if weather.empty:
        st.info("데이터 없음")
    else:
        w_show = weather.copy()
        w_show["date"] = pd.to_datetime(w_show["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        w_show["hour"] = pd.to_numeric(w_show["hour"], errors="coerce").astype("Int64")
        w_show["temperature"] = pd.to_numeric(w_show["temperature"], errors="coerce")
        w_show["humidity"]    = pd.to_numeric(w_show["humidity"], errors="coerce")
        w_show = w_show.sort_values(["date", "hour"])

        # 날짜 필터
        all_dates = w_show["date"].unique().tolist()
        sel_dates = st.multiselect("날짜 필터", all_dates,
                                    default=all_dates[-7:] if len(all_dates) >= 7 else all_dates)
        if sel_dates:
            w_show = w_show[w_show["date"].isin(sel_dates)]

        st.dataframe(w_show, use_container_width=True, hide_index=True)
        st.caption(f"{len(w_show)}건")

        buf = BytesIO()
        w_show.to_excel(buf, index=False)
        st.download_button("⬇️ Excel 다운로드", buf.getvalue(), file_name="weather_data.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # 기온 추이 차트
        st.subheader("기온 추이")
        daily_avg = (w_show.groupby("date")["temperature"]
                    .mean().round(1).reset_index())
        st.line_chart(daily_avg.set_index("date"))

# ── 일괄 수집 ─────────────────────────────────────────────────────────────────
with tab_bulk:
    st.markdown("**과거 날짜 범위**를 지정해 Open-Meteo에서 시간별 데이터를 일괄 수집합니다.")
    c1, c2 = st.columns(2)
    start_d = c1.date_input("시작 날짜", value=date(2025, 12, 26), key="bulk_start")
    end_d   = c2.date_input("종료 날짜", value=date.today(),       key="bulk_end")

    if st.button("🌐 일괄 수집 시작", type="primary"):
        if start_d > end_d:
            st.error("시작 날짜가 종료 날짜보다 늦습니다.")
        else:
            with st.spinner(f"{start_d} ~ {end_d} 수집 중..."):
                try:
                    new_df = fetch_range(str(start_d), str(end_d))
                    existing = load("weather")
                    combined = pd.concat([existing, new_df], ignore_index=True)
                    combined["date"] = combined["date"].astype(str)
                    combined["hour"] = pd.to_numeric(combined["hour"], errors="coerce").astype("Int64")
                    combined = (combined.drop_duplicates(subset=["date", "hour"], keep="last")
                                .sort_values(["date", "hour"]).reset_index(drop=True))
                    save("weather", combined)
                    st.success(f"✅ {len(new_df)}건 수집 → 총 {len(combined)}건 저장")
                    st.dataframe(new_df.head(24), use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"수집 실패: {e}")

# ── 수동 추가 ─────────────────────────────────────────────────────────────────
with tab_manual:
    st.markdown("API가 동작하지 않는 날짜를 직접 입력합니다.")
    with st.form("manual_weather"):
        mc1, mc2, mc3, mc4 = st.columns(4)
        m_date  = mc1.date_input("날짜")
        m_hour  = mc2.number_input("시각 (0-23)", 0, 23, 10)
        m_temp  = mc3.number_input("기온 (°C)",  step=0.1)
        m_hum   = mc4.number_input("습도 (%)", 0.0, 100.0, step=0.1)
        if st.form_submit_button("추가"):
            new_row = pd.DataFrame([{
                "date": str(m_date), "hour": int(m_hour),
                "temperature": m_temp, "humidity": m_hum,
                "source": "수동입력",
            }])
            existing = load("weather")
            combined = pd.concat([existing, new_row], ignore_index=True)
            combined["date"] = combined["date"].astype(str)
            combined["hour"] = pd.to_numeric(combined["hour"], errors="coerce").astype("Int64")
            combined = (combined.drop_duplicates(subset=["date", "hour"], keep="last")
                        .sort_values(["date", "hour"]).reset_index(drop=True))
            save("weather", combined)
            st.success(f"✅ {m_date} {m_hour}시 날씨 추가 완료")
            st.rerun()
