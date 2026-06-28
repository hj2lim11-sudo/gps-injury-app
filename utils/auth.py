"""로그인 상태 확인 — 각 페이지 상단에서 호출."""
import streamlit as st


def require_login():
    if not st.session_state.get("authentication_status"):
        st.warning("로그인이 필요합니다.")
        st.stop()
