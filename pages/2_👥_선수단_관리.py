"""선수단 관리 — 등록·수정·삭제 + Excel 일괄 업로드."""
import streamlit as st
import pandas as pd
from io import BytesIO

from utils.storage import load, save, next_id, player_id_from_jersey

st.set_page_config(page_title="선수단 관리", page_icon="👥", layout="wide")
st.title("👥 선수단 관리")

POSITIONS = ["FW", "MF", "DF", "GK"]


def reload():
    st.rerun()


players = load("players")

tab_view, tab_add, tab_bulk, tab_edit = st.tabs(["📋 선수 목록", "➕ 선수 등록", "📤 일괄 업로드", "✏️ 수정·삭제"])

# ── 선수 목록 ─────────────────────────────────────────────────────────────────
with tab_view:
    if players.empty:
        st.info("등록된 선수가 없습니다. '선수 등록' 또는 '일괄 업로드' 탭을 이용하세요.")
    else:
        show_df = players[["player_id", "jersey_no", "player_name", "position", "birth_year", "active"]].copy()
        show_df["jersey_no"] = pd.to_numeric(show_df["jersey_no"], errors="coerce").astype("Int64")
        show_df = show_df.sort_values("jersey_no")
        st.dataframe(show_df, use_container_width=True, hide_index=True)
        st.caption(f"총 {len(players)}명 등록")

        # 다운로드
        buf = BytesIO()
        show_df.to_excel(buf, index=False)
        st.download_button("⬇️ 선수 목록 다운로드", buf.getvalue(),
                           file_name="players.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── 선수 등록 ─────────────────────────────────────────────────────────────────
with tab_add:
    with st.form("add_player"):
        c1, c2, c3, c4 = st.columns(4)
        jersey = c1.number_input("등번호", min_value=1, max_value=99, step=1)
        name = c2.text_input("이름")
        pos = c3.selectbox("포지션", POSITIONS)
        birth = c4.number_input("출생연도 (선택)", min_value=1990, max_value=2010, value=2003, step=1)

        if st.form_submit_button("등록", type="primary"):
            if not name.strip():
                st.error("이름을 입력하세요.")
            elif not players.empty and int(jersey) in pd.to_numeric(players["jersey_no"], errors="coerce").tolist():
                st.error(f"등번호 {jersey}는 이미 등록되어 있습니다.")
            else:
                pid = player_id_from_jersey(jersey)
                new_row = pd.DataFrame([{
                    "player_id": pid, "jersey_no": int(jersey),
                    "player_name": name.strip(), "position": pos,
                    "birth_year": int(birth), "active": "True",
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
**Excel 양식:** `jersey_no` | `player_name` | `position` | `birth_year` (선택)

포지션 값: FW / MF / DF / GK
""")
    # 양식 다운로드
    template = pd.DataFrame([
        {"jersey_no": 7, "player_name": "홍길동", "position": "MF", "birth_year": 2003},
        {"jersey_no": 9, "player_name": "김철수", "position": "FW", "birth_year": 2002},
    ])
    buf = BytesIO()
    template.to_excel(buf, index=False)
    st.download_button("⬇️ 양식 다운로드", buf.getvalue(), file_name="players_template.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    uploaded = st.file_uploader("선수단 Excel 업로드", type=["xlsx", "xls"])
    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            df.columns = [c.strip().lower() for c in df.columns]
            col_map = {"이름": "player_name", "선수명": "player_name",
                       "등번호": "jersey_no", "no": "jersey_no",
                       "포지션": "position", "출생연도": "birth_year"}
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            if "player_name" not in df.columns:
                st.error("선수명(player_name) 컬럼이 없습니다.")
            else:
                df["jersey_no"] = pd.to_numeric(df.get("jersey_no", pd.Series()), errors="coerce")
                df["player_id"] = df["jersey_no"].apply(player_id_from_jersey)
                df["active"] = "True"
                if "birth_year" not in df.columns:
                    df["birth_year"] = None
                if "position" not in df.columns:
                    df["position"] = None

                st.dataframe(df[["player_id", "jersey_no", "player_name", "position", "birth_year"]],
                             use_container_width=True, hide_index=True)
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
            f"{row['player_id']} | #{int(pd.to_numeric(row['jersey_no'], errors='coerce') or 0):02d} {row['player_name']}": idx
            for idx, row in players.iterrows()
        }
        sel_label = st.selectbox("선수 선택", list(player_opts.keys()))
        sel_idx = player_opts[sel_label]
        sel = players.loc[sel_idx]

        with st.form("edit_player"):
            c1, c2, c3 = st.columns(3)
            new_jersey = c1.number_input("등번호", value=int(pd.to_numeric(sel["jersey_no"], errors="coerce") or 1), min_value=1, max_value=99)
            new_name = c2.text_input("이름", value=str(sel["player_name"]))
            pos_idx = POSITIONS.index(sel["position"]) if sel["position"] in POSITIONS else 0
            new_pos = c3.selectbox("포지션", POSITIONS, index=pos_idx)
            new_birth = st.number_input("출생연도", value=int(pd.to_numeric(sel["birth_year"], errors="coerce") or 2003), min_value=1990, max_value=2010)
            new_active = st.checkbox("활성 선수", value=str(sel.get("active", "True")) == "True")

            c_save, c_del = st.columns(2)
            if c_save.form_submit_button("저장", type="primary"):
                players.at[sel_idx, "jersey_no"] = new_jersey
                players.at[sel_idx, "player_name"] = new_name.strip()
                players.at[sel_idx, "position"] = new_pos
                players.at[sel_idx, "birth_year"] = new_birth
                players.at[sel_idx, "active"] = str(new_active)
                players.at[sel_idx, "player_id"] = player_id_from_jersey(new_jersey)
                save("players", players)
                st.success("✅ 수정 완료")
                reload()
            if c_del.form_submit_button("삭제", type="secondary"):
                players = players.drop(index=sel_idx).reset_index(drop=True)
                save("players", players)
                st.success("삭제 완료")
                reload()
