"""부상 데이터 — Excel 일괄 업로드 + 단건 입력 + 조회."""
import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from utils.auth import require_login
require_login()

from utils.storage import load, save, append_rows, PATHS

st.set_page_config(page_title="부상 데이터", page_icon="🩹", layout="wide")
st.title("🩹 부상 데이터")

BODY_PARTS = [
    "", "허벅지 앞(대퇴사두)", "허벅지 뒤(햄스트링)", "종아리", "발목", "무릎",
    "고관절/사타구니", "허리/척추", "발", "어깨", "기타",
]
INJURY_STATUS = ["정상", "부상", "재활 중", "결장", "컨디션 난조"]
PARTICIPATED  = ["O", "X"]

players_db = load("players")
injuries   = load("injuries")

tab_upload, tab_add, tab_view, tab_stats = st.tabs(
    ["📤 Excel 업로드", "✏️ 단건 입력", "📋 이력 조회", "📊 통계"]
)

# ════════════════════════════════════════════════════════
# TAB 1 — Excel 업로드
# ════════════════════════════════════════════════════════
with tab_upload:
    st.subheader("Excel 일괄 업로드")
    st.caption("날짜별 전체 선수 현황을 한 번에 업로드합니다. 2025-12-26부터 현재까지 전체도 가능합니다.")

    # ── 템플릿 다운로드 ──────────────────────────────────────────────────────
    with st.expander("📥 템플릿 다운로드", expanded=True):
        # 등록된 선수로 템플릿 생성
        if not players_db.empty:
            template_rows = []
            for _, p in players_db.iterrows():
                template_rows.append({
                    "날짜":         "2025-12-26",
                    "선수명":       p["player_name"],
                    "운동참여여부":  "O",
                    "부상상황":     "정상",
                    "부상부위":     "",
                    "통증강도(1-5)": "",
                    "결장일수":     "",
                })
            template_df = pd.DataFrame(template_rows)
        else:
            template_df = pd.DataFrame([
                {"날짜": "2025-12-26", "선수명": "홍길동", "운동참여여부": "O",
                 "부상상황": "정상", "부상부위": "", "통증강도(1-5)": "", "결장일수": ""},
                {"날짜": "2025-12-26", "선수명": "김철수", "운동참여여부": "X",
                 "부상상황": "부상", "부상부위": "햄스트링", "통증강도(1-5)": 6, "결장일수": 7},
            ])

        st.dataframe(template_df, use_container_width=True, hide_index=True)
        st.caption("부상상황: 정상 / 부상 / 재활 중 / 결장 / 컨디션 난조")
        st.caption("통증강도: 0(없음) ~ 10(극심)")

        buf = BytesIO()
        template_df.to_excel(buf, index=False)
        st.download_button(
            "⬇️ 템플릿 Excel 다운로드", buf.getvalue(),
            file_name="injury_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.divider()

    # ── 파일 업로드 ──────────────────────────────────────────────────────────
    uploaded = st.file_uploader("부상 데이터 Excel 업로드", type=["xlsx", "xls", "csv"])

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_raw = pd.read_csv(uploaded)
            else:
                df_raw = pd.read_excel(uploaded)

            # 컬럼 정규화
            col_map = {
                "날짜": "date", "선수명": "player_name",
                "운동참여여부": "participated",
                "부상상황": "injury_status",
                "부상부위": "body_part",
                "통증강도(1-5)": "pain_level", "통증강도": "pain_level",
                "결장일수": "absence_days",
                "비고": "notes",
            }
            df_raw = df_raw.rename(columns={k: v for k, v in col_map.items() if k in df_raw.columns})

            # 필수 컬럼 확인
            missing = {"date", "player_name"} - set(df_raw.columns)
            if missing:
                st.error(f"필수 컬럼 없음: {missing}  |  현재 컬럼: {list(df_raw.columns)}")
                st.stop()

            # 날짜 정규화
            df_raw["date"] = pd.to_datetime(df_raw["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df_raw = df_raw[df_raw["date"].notna() & df_raw["player_name"].notna()]

            # player_id / jersey_no 매핑
            def get_player_info(name):
                if players_db.empty:
                    return None, None
                m = players_db[players_db["player_name"].astype(str).str.strip() == str(name).strip()]
                if not m.empty:
                    return m.iloc[0]["player_id"], m.iloc[0]["jersey_no"]
                return None, None

            df_raw["player_id"]  = df_raw["player_name"].apply(lambda n: get_player_info(n)[0])
            df_raw["jersey_no"]  = df_raw["player_name"].apply(lambda n: get_player_info(n)[1])
            df_raw["session_id"] = None
            df_raw["notes"]      = df_raw.get("notes", "")

            # injury_id 부여
            ex_count = len(load("injuries"))
            df_raw = df_raw.reset_index(drop=True)
            df_raw["injury_id"] = [f"I{ex_count + i + 1:03d}" for i in range(len(df_raw))]

            # 수치 컬럼
            for col in ["pain_level", "absence_days"]:
                if col in df_raw.columns:
                    df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")

            # 미리보기
            show_cols = ["date", "player_name", "participated", "injury_status",
                         "body_part", "pain_level", "absence_days"]
            show = df_raw[[c for c in show_cols if c in df_raw.columns]]

            st.subheader(f"미리보기 ({len(show)}행)")
            st.dataframe(show, use_container_width=True, hide_index=True)

            unmatched = df_raw["player_id"].isna().sum()
            if unmatched:
                st.warning(f"⚠️ 선수단 미등록 {unmatched}명 — player_id 없이 저장됩니다.")

            # 저장 방식
            col_opt1, col_opt2 = st.columns(2)
            overwrite = col_opt1.radio("저장 방식", ["기존에 추가", "전체 덮어쓰기"])

            if col_opt2.button("✅ 업로드 확정", type="primary"):
                final_cols = ["injury_id", "date", "player_id", "jersey_no", "player_name",
                              "participated", "injury_status", "body_part",
                              "pain_level", "absence_days", "session_id", "notes"]
                for c in final_cols:
                    if c not in df_raw.columns:
                        df_raw[c] = None
                df_save = df_raw[final_cols]

                if overwrite == "전체 덮어쓰기":
                    save("injuries", df_save)
                else:
                    existing = load("injuries")
                    combined = pd.concat([existing, df_save], ignore_index=True)
                    # 날짜+선수명 중복 제거 (나중 것 우선)
                    combined = combined.drop_duplicates(
                        subset=["date", "player_name"], keep="last"
                    ).sort_values("date").reset_index(drop=True)
                    save("injuries", combined)

                st.success(f"✅ {len(df_save)}건 저장 완료")
                st.rerun()

        except Exception as e:
            st.error(f"파일 처리 오류: {e}")

# ════════════════════════════════════════════════════════
# TAB 2 — 단건 입력
# ════════════════════════════════════════════════════════
with tab_add:
    st.subheader("날짜·선수별 단건 입력")

    player_opts = {}
    if not players_db.empty:
        for _, r in players_db.iterrows():
            j = pd.to_numeric(r["jersey_no"], errors="coerce")
            label = f"#{int(j):02d} {r['player_name']}" if pd.notna(j) else r["player_name"]
            player_opts[label] = r

    with st.form("injury_single"):
        c1, c2 = st.columns(2)
        inj_date   = c1.date_input("날짜", value=date.today())
        sel_player = c2.selectbox("선수", list(player_opts.keys()) if player_opts else ["(선수 없음)"])

        c3, c4, c5 = st.columns(3)
        participated  = c3.selectbox("운동참여여부", PARTICIPATED)
        injury_status = c4.selectbox("부상상황", INJURY_STATUS)
        body_part     = c5.selectbox("부상부위", BODY_PARTS)

        c6, c7 = st.columns(2)
        pain_level   = c6.slider("통증강도 (1=약함, 5=극심, 0=없음)", 0, 5, 0)
        absence_days = c7.number_input("결장일수", 0, 365, 0)
        notes        = st.text_input("비고")

        if st.form_submit_button("저장", type="primary"):
            if not player_opts:
                st.error("선수단 관리에서 선수를 먼저 등록하세요.")
            else:
                p  = player_opts[sel_player]
                ex = load("injuries")
                new_row = pd.DataFrame([{
                    "injury_id":    f"I{len(ex)+1:03d}",
                    "date":         str(inj_date),
                    "player_id":    p["player_id"],
                    "jersey_no":    p["jersey_no"],
                    "player_name":  p["player_name"],
                    "participated": participated,
                    "injury_status": injury_status,
                    "body_part":    body_part,
                    "pain_level":   pain_level,
                    "absence_days": absence_days if absence_days > 0 else None,
                    "session_id":   None,
                    "notes":        notes,
                }])
                append_rows("injuries", new_row)
                st.success(f"✅ {p['player_name']} ({str(inj_date)}) 저장 완료")
                st.rerun()

# ════════════════════════════════════════════════════════
# TAB 3 — 이력 조회
# ════════════════════════════════════════════════════════
with tab_view:
    injuries = load("injuries")
    if injuries.empty:
        st.info("데이터 없음")
    else:
        inj = injuries.copy()
        inj["date"] = pd.to_datetime(inj["date"], errors="coerce")
        inj = inj.sort_values("date", ascending=False)

        # 필터
        fc1, fc2, fc3, fc4 = st.columns(4)
        sel_p   = fc1.multiselect("선수", inj["player_name"].dropna().unique())
        sel_par = fc2.multiselect("참여여부", ["O", "X"])
        sel_st  = fc3.multiselect("부상상황", INJURY_STATUS)
        date_range = fc4.date_input("기간", value=[], key="view_date")

        filtered = inj.copy()
        if sel_p:   filtered = filtered[filtered["player_name"].isin(sel_p)]
        if sel_par: filtered = filtered[filtered["participated"].isin(sel_par)]
        if sel_st:  filtered = filtered[filtered["injury_status"].isin(sel_st)]
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            filtered = filtered[
                (filtered["date"] >= pd.Timestamp(date_range[0])) &
                (filtered["date"] <= pd.Timestamp(date_range[1]))
            ]

        filtered["date"] = filtered["date"].dt.strftime("%Y-%m-%d")

        show_cols = ["date", "player_name", "participated", "injury_status",
                     "body_part", "pain_level", "absence_days", "notes"]
        st.dataframe(
            filtered[[c for c in show_cols if c in filtered.columns]],
            use_container_width=True, hide_index=True,
        )
        st.caption(f"총 {len(filtered)}건")

        buf = BytesIO()
        filtered.to_excel(buf, index=False)
        st.download_button("⬇️ Excel 다운로드", buf.getvalue(),
                           file_name="injury_filtered.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ════════════════════════════════════════════════════════
# TAB 4 — 통계
# ════════════════════════════════════════════════════════
with tab_stats:
    injuries = load("injuries")
    if injuries.empty:
        st.info("데이터 없음")
    else:
        inj = injuries.copy()
        inj["pain_level"]   = pd.to_numeric(inj.get("pain_level"),   errors="coerce")
        inj["absence_days"] = pd.to_numeric(inj.get("absence_days"), errors="coerce")
        inj["date"]         = pd.to_datetime(inj["date"], errors="coerce")

        # X(불참) 행만
        inj_only = inj[inj.get("participated", pd.Series()) == "X"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("전체 기록 수", len(inj))
        c2.metric("불참 건수",    len(inj_only))
        c3.metric("평균 통증강도", round(inj_only["pain_level"].mean(), 1) if not inj_only.empty else "-")
        c4.metric("평균 결장일수", round(inj_only["absence_days"].mean(), 1) if not inj_only.empty else "-")

        st.subheader("선수별 불참 횟수")
        if not inj_only.empty:
            pc = inj_only["player_name"].value_counts().reset_index()
            pc.columns = ["선수", "불참 횟수"]
            st.bar_chart(pc.set_index("선수"))

        st.subheader("부상 부위별 빈도")
        bp = inj_only[inj_only["body_part"].notna() & (inj_only["body_part"] != "")]
        if not bp.empty:
            bc = bp["body_part"].value_counts().reset_index()
            bc.columns = ["부상 부위", "건수"]
            st.bar_chart(bc.set_index("부상 부위"))

        st.subheader("날짜별 불참 인원 추이")
        if not inj_only.empty:
            daily = (inj_only.groupby("date")["player_name"]
                     .count().reset_index()
                     .rename(columns={"player_name": "불참 인원"}))
            daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
            st.line_chart(daily.set_index("date"))
