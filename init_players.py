"""선수단 명단 초기화 스크립트 — 로컬에서 한 번만 실행."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
# secrets.toml 경로 설정
os.environ.setdefault("STREAMLIT_SECRETS_FILE",
                      os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml"))

import tomllib, pandas as pd, gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

with open(os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml"), "rb") as f:
    secrets = tomllib.load(f)
info = secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(info, scopes=SCOPES)
client = gspread.authorize(creds)

players = [
    ("MJU_P001",  1, "한경수"),
    ("MJU_P002",  2, "박준성"),
    ("MJU_P003",  3, "김채영"),
    ("MJU_P004",  4, "전성언"),
    ("MJU_P005",  5, "민승기"),
    ("MJU_P006",  6, "김경수"),
    ("MJU_P007",  7, "김민영"),
    ("MJU_P008",  8, "강민형"),
    ("MJU_P009",  9, "강기찬"),
    ("MJU_P010", 10, "강명준"),
    ("MJU_P011", 11, "김도현"),
    ("MJU_P012", 12, "주우찬"),
    ("MJU_P013", 13, "김형진"),
    ("MJU_P014", 14, "박채웅"),
    ("MJU_P015", 15, "정희찬"),
    ("MJU_P016", 16, "이주형"),
    ("MJU_P017", 17, "이권욱"),
    ("MJU_P018", 18, "박준희"),
    ("MJU_P019", 19, "신승관"),
    ("MJU_P020", 20, "윤호진"),
    ("MJU_P021", 21, "박주현"),
    ("MJU_P022", 22, "신상용"),
    ("MJU_P023", 25, "엄지욱"),
    ("MJU_P024", 27, "문종호"),
    ("MJU_P025", 28, "양주원"),
    ("MJU_P026", 29, "박주한"),
    ("MJU_P027", 30, "강현수"),
    ("MJU_P028", 33, "홍민석"),
    ("MJU_P029", 37, "유제원"),
    ("MJU_P030", 66, "김민국"),
    ("MJU_P031", 77, "오동욱"),
]

HEADER = ["player_id", "player_name", "jersey_no", "position",
          "birth_date", "grade", "height", "prev_school", "active"]

rows = []
for pid, jersey, name in players:
    rows.append([pid, name, jersey, "", "", "", "", "", "TRUE"])

df = pd.DataFrame(rows, columns=HEADER)

ws = client.open("MJU_Players").sheet1
ws.clear()
ws.update([HEADER] + df.values.tolist())

print(f"✅ 선수 {len(rows)}명 업로드 완료")
