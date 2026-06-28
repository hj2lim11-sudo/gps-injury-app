"""선수단 관리 — 등록·수정·삭제 + Excel 일괄 업로드."""
import streamlit as st
import pandas as pd
from io import BytesIO
from utils.auth import require_login
require_login()

from utils.storage import load, save, next_id, player_id_from_jersey

st.set_page_config(page_title="선수단 관리", page_icon="👥", layout="wide")
st.title("👥 선수단 관리")

POSITIONS = ["FW", "MF", "DF", "GK"]
COLS = ["player_id", "player_name", "jersey_no", "position", "birth_date", "grade", "height", "prev_school", "active"]

def reload():
    st.rerun()

players = load("players")

tab_view, tab_add, tab_bulk, tab_edit = st.tabs(["📋 선수 목록", "➕ 선수 등록", "📤 일괄 업로드", "✏️ 수정·삭제"])

# ── 선수 목록 ─────────────────────────────────────────────────────────────────
with tab_view:
    if players.empty:
        st.info("등록된 선수가 없습니다. '선수 등록' 또는 '일괄 업로드' 탭을 이용하세요.")
    else:
        disp_cols = [c for c in ["player_id", "player_name", "jersey_no", "position", "birth_date", "grade", "height", "prev_school"] if c in players.columns]
        show_df = players[disp_cols].copy()
        if "jersey_no" in show_df.columns:
            show_df["jersey_no"] = pd.to_numeric(show_df["jersey_no"], errors="coerce").astype("Int64")
            show_df = show_df.sort_values("jersey_no")
        st.dataframe(show_df, use_container_width=True, hide_index=True)
        st.caption(f"총 {len(players)}명 등록")

        buf = BytesIO()
        show_df.to_excel(buf, index=False)
        st.download_button("⬇️ 선수 목록 다운로드", buf.getvalue(),
                           file_name="players.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── 선수 등록 ─────────────────────────────────────────────────────────────────
with tab_add:
    with st.form("add_player"):
        c1, c2, c3, c4 = st.columns(4)
        name   = c1.text_input("선수명")
        jersey = c2.number_input("등번호", min_value=1, max_value=99, step=1)
        pos    = c3.selectbox("포지션", POSITIONS)
        birth  = c4.text_input("생년월일 (예: 2003-05-12)")

        c5, c6, c7 = st.columns(3)
        grade  = c5.selectbox("학년", ["1학년", "2학년", "3학년", "4학년", "기타"])
        height = c6.number_input("키 (cm)", min_value=140, max_value=220, value=175, step=1)
        prev_school = c7.text_input("전 출신학교")

        if st.form_submit_button("등록", type="primary"):
            if not name.strip():
                st.error("선수명을 입력하세요.")
            elif not players.empty and int(jersey) in pd.to_numeric(players.get("jersey_no", pd.Series()), errors="coerce").tolist():
                st.error(f"등번호 {jersey}는 이미 등록되어 있습니다.")
            else:
                pid = player_id_from_jersey(jersey)
                new_row = pd.DataFrame([{
                    "player_id": pid,
                    "player_name": name.strip(),
                    "jersey_no": int(jersey),
                    "position": pos,
                    "birth_date": birth.strip(),
                    "grade": grade,
                    "height": int(height),
                    "prev_school": prev_school.strip(),
                    "active": "True",
                }])
                updated = pd.concat([players, new_row], ignore_index=True)
                updated["jersey_no"] = pd.to_numeric(updated["jersey_no"], errors="coerce")
                updated = updated.sort_values("jersey_no").reset_index(drop=True)
                save("players", updated)
                st.success(f"✅ {name} (#{jersey}) 등록 완료")
                reload()

# ── 일괄 업로드 ───────────────────────────────────────────────────────────────
with tab_bulk:
    st.markdown("""
**Excel 컬럼:** `선수명` | `등번호` | `포지션` | `생년월일` | `학년` | `키` | `전 출신학교`

포지션 값: FW / MF / DF / GK
""")
    template = pd.DataFrame([
        {"선수명": "홍길동", "등번호": 7, "포지션": "MF", "생년월일": "2003-05-12", "학년": "2학년", "키": 175, "전 출신학교": "○○고"},
        {"선수명": "김철수", "등번호": 9, "포지션": "FW", "생년월일": "2002-11-03", "학년": "3학년", "키": 180, "전 출신학교": "△△고"},
    ])
    buf = BytesIO()
    template.to_excel(buf, index=False)
    st.download_button("⬇️ 양식 다운로드", buf.getvalue(), file_name="players_template.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    uploaded = st.file_uploader("선수단 Excel 업로드", type=["xlsx", "xls"])
    if uploaded:
        try:
            df = pd.read_excel(uploaded, dtype=str).fillna("")
            col_map = {
                "선수명": "player_name", "이름": "player_name",
                "등번호": "jersey_no", "no": "jersey_no",
                "포지션": "position",
                "생년월일": "birth_date", "출생연도": "birth_date",
                "학년": "grade",
                "키": "height",
                "전 출신학교": "prev_school", "출신학교": "prev_school",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            if "player_name" not in df.columns:
                st.error("선수명 컬럼이 없습니다.")
            else:
                df["jersey_no"] = pd.to_numeric(df.get("jersey_no", pd.Series(dtype=str)), errors="coerce")
                df["player_id"] = df["jersey_no"].apply(player_id_from_jersey)
                df["active"] = "True"
                for col in ["birth_date", "grade", "height", "prev_school", "position"]:
                    if col not in df.columns:
                        df[col] = ""

                disp = [c for c in ["player_id", "player_name", "jersey_no", "position", "birth_date", "grade", "height", "prev_school"] if c in df.columns]
                st.dataframe(df[disp], use_container_width=True, hide_index=True)
                st.caption(f"{len(df)}명 인식됨")

                overwrite = st.radio("저장 방식", ["기존 데이터에 추가", "전체 덮어쓰기"])
                if st.button("업로드 확정", type="primary"):
                    if overwrite == "전체 덮어쓰기":
                        save("players", df)
                    else:
                        combined = pd.concat([players, df], ignore_index=True)
                        combined = combined.drop_duplicates(subset="player_name", keep="last")
                        save("players", combined)
                    st.success(f"✅ {len(df)}명 저장 완료")
                    reload()
        except Exception as e:
            st.error(f"파일 읽기 오류: {e}")

# ── 수정·삭제 ─────────────────────────────────────────────────────────────────
with tab_edit:
    if players.empty:
        st.info("등록된 선수가 없습니다.")
    else:
        player_opts = {
            f"{row['player_id']} | #{int(pd.to_numeric(row.get('jersey_no', 0), errors='coerce') or 0):02d} {row['player_name']}": idx
            for idx, row in players.iterrows()
        }
        sel_label = st.selectbox("선수 선택", list(player_opts.keys()))
        sel_idx = player_opts[sel_label]
        sel = players.loc[sel_idx]

        with st.form("edit_player"):
            c1, c2, c3, c4 = st.columns(4)
            new_name   = c1.text_input("선수명", value=str(sel.get("player_name", "")))
            new_jersey = c2.number_input("등번호", value=int(pd.to_numeric(sel.get("jersey_no", 1), errors="coerce") or 1), min_value=1, max_value=99)
            pos_idx    = POSITIONS.index(sel.get("position")) if sel.get("position") in POSITIONS else 0
            new_pos    = c3.selectbox("포지션", POSITIONS, index=pos_idx)
            new_birth  = c4.text_input("생년월일", value=str(sel.get("birth_date", "")))

            c5, c6, c7 = st.columns(3)
            grade_opts = ["1학년", "2학년", "3학년", "4학년", "기타"]
            g_idx = grade_opts.index(sel.get("grade")) if sel.get("grade") in grade_opts else 4
            new_grade  = c5.selectbox("학년", grade_opts, index=g_idx)
            new_height = c6.number_input("키 (cm)", value=int(pd.to_numeric(sel.get("height", 175), errors="coerce") or 175), min_value=140, max_value=220)
            new_prev   = c7.text_input("전 출신학교", value=str(sel.get("prev_school", "")))
            new_active = st.checkbox("활성 선수", value=str(sel.get("active", "True")) == "True")

            c_save, c_del = st.columns(2)
            if c_save.form_submit_button("저장", type="primary"):
                players.at[sel_idx, "player_name"]  = new_name.strip()
                players.at[sel_idx, "jersey_no"]    = new_jersey
                players.at[sel_idx, "position"]     = new_pos
                players.at[sel_idx, "birth_date"]   = new_birth.strip()
                players.at[sel_idx, "grade"]        = new_grade
                players.at[sel_idx, "height"]       = new_height
                players.at[sel_idx, "prev_school"]  = new_prev.strip()
                players.at[sel_idx, "active"]       = str(new_active)
                players.at[sel_idx, "player_id"]    = player_id_from_jersey(new_jersey)
                save("players", players)
                st.success("✅ 수정 완료")
                reload()
            if c_del.form_submit_button("삭제", type="secondary"):
                players = players.drop(index=sel_idx).reset_index(drop=True)
                save("players", players)
                st.success("삭제 완료")
                reload()
