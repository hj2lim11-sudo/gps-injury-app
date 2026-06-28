"""앱 진입점 — 페이지 설정만 담당."""
import streamlit as st

st.set_page_config(
    page_title="GPS 부상위험 데이터 수집",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.switch_page("pages/1_🏠_홈.py")
