"""앱 진입점 — 로그인 후 홈으로 이동."""
import streamlit as st
import streamlit_authenticator as stauth
import bcrypt

st.set_page_config(
    page_title="GPS 부상위험 데이터 수집",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# secrets에서 계정 정보 읽기 (없으면 기본값 admin/admin1234)
if "auth" in st.secrets:
    username  = st.secrets["auth"]["username"]
    name      = st.secrets["auth"]["name"]
    pw_hash   = st.secrets["auth"]["password"]
else:
    username  = "admin"
    name      = "관리자"
    pw_hash   = bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode()

credentials = {
    "usernames": {
        username: {"name": name, "password": pw_hash}
    }
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_name="gps_injury_cookie",
    cookie_key="gps_injury_auth_key_2026",
    cookie_expiry_days=30,
)

authenticator.login(location="main")

if st.session_state.get("authentication_status"):
    authenticator.logout("로그아웃", location="sidebar")
    st.sidebar.write(f"👤 {st.session_state['name']} 님")
    st.switch_page("pages/1_🏠_홈.py")
elif st.session_state.get("authentication_status") is False:
    st.error("아이디 또는 비밀번호가 틀렸습니다.")
else:
    st.info("아이디와 비밀번호를 입력하세요.")
