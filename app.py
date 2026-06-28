"""앱 진입점 — 로그인 후 홈으로 이동."""
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from pathlib import Path

st.set_page_config(
    page_title="GPS 부상위험 데이터 수집",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

CONFIG_PATH = Path(__file__).parent / "auth_config.yaml"

if not CONFIG_PATH.exists():
    # 최초 실행 시 기본 설정 생성 (admin / admin1234)
    import bcrypt
    hashed = bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode()
    default_cfg = {
        "credentials": {
            "usernames": {
                "admin": {
                    "name": "관리자",
                    "password": hashed,
                }
            }
        },
        "cookie": {
            "expiry_days": 30,
            "key": "gps_injury_auth_key_2026",
            "name": "gps_injury_cookie",
        },
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(default_cfg, f, allow_unicode=True)

with open(CONFIG_PATH, encoding="utf-8") as f:
    config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
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
