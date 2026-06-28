"""홈 — GPS 업로드 → 세션 정보 입력 → 저장 (날씨 자동 수집 포함)."""
import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.auth import require_login
require_login()

from utils.storage import (
    load, save, append_rows, next_id,
    is_duplicate_session, GPS_METRIC_COLS,
)
from utils.parser import parse_daily_csv
from utils.weather import fetch_session_weather, LOCATION_CONFIG

st.set_page_config(page_title="홈", page_icon="🏠", layout="wide")
st.title("⚽ 세션 데이터 입력")
st.caption("GPS 파일 업로드 → 세션 정보 입력 → 저장 버튼 하나로 GPS·날씨가 자동 저장됩니다.")

LOCATION_LIST = list(LOCATION_CONFIG.keys())

# ────────────────────────────────────────────────────────────────────────────
# STEP 1 — GPS CSV 업로드
# ────────────────────────────────────────────────────────────────────────────
st.subheader("① GPS 파일 업로드")

gps_file = st.file_uploader(
    "Fitogether Daily Stats by Player CSV 또는 Trend CSV",
    type=["csv"],
    help="날짜·시간 정보는 아래 세션 정보에서 직접 입력합니다.",
)

gps_df = None

if gps_file:
    file_bytes = gps_file.read()
    try:
        gps_df = parse_daily_csv(file_bytes)
        st.success(f"✅ GPS 파싱 완료 — {len(gps_df)}명 데이터")
        with st.expander("GPS 데이터 미리보기", expanded=False):
            st.dataframe(gps_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"파일 파싱 오류: {e}")

st.divider()

# ────────────────────────────────────────────────────────────────────────────
# STEP 2 — 세션 정보 입력
# ────────────────────────────────────────────────────────────────────────────
st.subheader("② 세션 정보 입력")
st.caption("날짜·장소를 입력하면 저장 시 날씨가 자동 수집됩니다.")

col1, col2, col3 = st.columns(3)
sess_date  = col1.date_input("날짜", value=date.today())
sess_order = col2.number_input("세션 순서 (하루 중 몇 번째)", min_value=1, max_value=3, value=1)

type_opts = ["훈련", "경기", "체력측정", "회복", "기타"]
sess_type  = col3.selectbox("세션 유형", type_opts)

col4, col5, col6 = st.columns(3)
sess_start = col4.text_input("운동 시작 시간 (HH:MM)", value="10:00")
sess_dur   = col5.number_input("운동 시간 (분)", min_value=1, max_value=300, value=90)

LOCATION_OPTS   = LOCATION_LIST + ["기타 (직접 입력)"]
default_loc_idx = LOCATION_OPTS.index("명지대학교 자연캠퍼스") if "명지대학교 자연캠퍼스" in LOCATION_OPTS else 0
loc_select      = col6.selectbox("장소", LOCATION_OPTS, index=default_loc_idx)

if loc_select == "기타 (직접 입력)":
    sess_location = st.text_input(
        "장소 직접 입력 (예: 사천, 창원, 청주)",
        placeholder="도시명 또는 장소명 입력 → 지도에서 좌표 자동 검색",
    )
else:
    sess_location = loc_select

sess_opponent = ""
if sess_type == "경기":
    sess_opponent = st.text_input("상대팀")

st.divider()

# ────────────────────────────────────────────────────────────────────────────
# STEP 3 — 저장
# ────────────────────────────────────────────────────────────────────────────
st.subheader("③ 저장")

if gps_df is None:
    st.info("GPS 파일을 먼저 업로드하세요.")
else:
    if is_duplicate_session(str(sess_date), sess_order):
        st.warning(f"⚠️ {sess_date} {sess_order}번째 세션이 이미 저장되어 있습니다. 덮어쓰기됩니다.")

    if st.button("💾 GPS + 날씨 저장", type="primary", use_container_width=True):

        # ── 날씨 자동 수집 (세션 시간대 전체 수집 → 평균) ──────────────────────
        temp = humi = None
        w_source = "오류"
        with st.spinner("날씨 데이터 수집 중 (세션 시간대 전체)..."):
            try:
                wr = fetch_session_weather(sess_location, str(sess_date), sess_start, sess_dur)
                if "error" in wr:
                    st.warning(f"날씨 수집 실패 (GPS는 저장됨): {wr['error']}")
                else:
                    temp     = wr["temperature"]   # 기온 평균
                    humi     = wr["humidity"]       # 습도 평균
                    w_source = wr["source"]
                    hourly   = wr.get("hourly", [])

                    # weather_data.xlsx — 시각별 행 추가 (날짜+시각 중복 방지)
                    existing_w = load("weather")
                    new_rows = []
                    for h_row in hourly:
                        h = h_row["hour"]
                        mask = (
                            (existing_w["date"].astype(str) == str(sess_date)) &
                            (pd.to_numeric(existing_w["hour"], errors="coerce") == h)
                        )
                        existing_w = existing_w[~mask]
                        new_rows.append({
                            "date":        str(sess_date),
                            "hour":        h,
                            "temperature": h_row["temperature"],
                            "humidity":    h_row["humidity"],
                            "source":      w_source,
                        })
                    save("weather", pd.concat(
                        [existing_w, pd.DataFrame(new_rows)], ignore_index=True
                    ))

                    hours_str = ", ".join(str(h["hour"]) + "시" for h in hourly)
                    st.success(
                        f"날씨 수집 완료 [{w_source}]  |  "
                        f"수집 시각: {hours_str}  |  "
                        f"기온 평균 **{temp}°C** | 습도 평균 **{humi}%**"
                    )
            except Exception as we:
                st.warning(f"날씨 수집 실패 (GPS는 저장됨): {we}")

        # ── 세션 마스터 저장 ─────────────────────────────────────────────────
        session_id = next_id("sessions", "S")
        existing_s = load("sessions")
        dup_mask = (
            (existing_s["date"].astype(str) == str(sess_date)) &
            (existing_s["session_order"].astype(str) == str(sess_order))
        )
        sess_row = pd.DataFrame([{
            "session_id":    session_id,
            "date":          str(sess_date),
            "session_type":  sess_type,
            "session_order": sess_order,
            "start_time":    sess_start,
            "duration_min":  sess_dur,
            "location":      sess_location,
            "opponent":      sess_opponent,
        }])
        save("sessions", pd.concat([existing_s[~dup_mask], sess_row], ignore_index=True))

        # ── GPS 데이터 + 날씨 합쳐서 저장 ───────────────────────────────────
        players_db = load("players")

        def lookup_player(jersey, name):
            if not players_db.empty:
                m = players_db[
                    players_db["player_name"].astype(str).str.strip() == str(name).strip()
                ]
                if not m.empty:
                    return m.iloc[0]["player_id"], m.iloc[0]["position"]
            pid = f"P{int(jersey):02d}" if pd.notna(jersey) else "P00"
            return pid, None

        gps_rows = []
        for _, row in gps_df.iterrows():
            pid, pos = lookup_player(row.get("jersey_no"), row.get("player_name"))
            r = {
                "session_id":    session_id,
                "date":          str(sess_date),
                "player_id":     pid,
                "jersey_no":     row.get("jersey_no"),
                "player_name":   row.get("player_name"),
                "position":      pos or row.get("position"),
                "session_type":  sess_type,
                "session_order": sess_order,
                "start_time":    sess_start,
                "duration_min":  sess_dur,
                "location":      sess_location,
                "opponent":      sess_opponent,
                "temperature":   temp,
                "humidity":      humi,
            }
            for col in GPS_METRIC_COLS:
                r[col] = row.get(col)
            gps_rows.append(r)

        gps_new = pd.DataFrame(gps_rows)
        existing_g = load("gps")
        if "session_id" in existing_g.columns:
            existing_g = existing_g[existing_g["session_id"] != session_id]
        save("gps", pd.concat([existing_g, gps_new], ignore_index=True))

        st.success(
            f"✅ 저장 완료!  세션 ID: **{session_id}**  |  "
            f"선수 {len(gps_rows)}명  |  기온 {temp}°C  |  습도 {humi}%"
        )
        st.balloons()
