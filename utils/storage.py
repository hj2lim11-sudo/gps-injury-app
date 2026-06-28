"""중앙 데이터 저장소 — Google Sheets 읽기/쓰기."""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ── Google Sheets 연결 ────────────────────────────────────────────────────────

SHEET_NAMES = {
    "players":  "MJU_Players",
    "sessions": "GPS_sessions",
    "gps":      "GPS_gps_data",
    "weather":  "Weather_data",
    "injuries": "Injury_data",
    "merged":   "Merged_dataset",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SCHEMA = {
    "players": ["player_id", "player_name", "jersey_no", "position", "birth_date", "grade", "height", "prev_school", "active"],
    "sessions": ["session_id", "date", "session_type", "session_order",
                 "start_time", "duration_min", "location", "opponent"],
    "gps": ["session_id", "date", "player_id", "jersey_no", "player_name", "position",
            "session_type", "session_order", "start_time", "duration_min", "location", "opponent",
            "total_distance_km", "distance_per_min", "max_speed",
            "hsr_distance", "sprint_distance", "hsr_count", "sprint_count",
            "med_acc_count", "med_dec_count", "acd_load",
            "zone1_distance", "zone2_distance", "zone3_distance", "zone4_distance", "zone5_distance",
            "temperature", "humidity"],
    "weather": ["date", "hour", "location", "temperature", "humidity", "source"],
    "injuries": ["injury_id", "date", "player_id", "jersey_no", "player_name",
                 "participated", "injury_status", "body_part", "pain_level",
                 "absence_days", "session_id", "notes"],
    "merged": [],
}

GPS_METRIC_COLS = [
    "total_distance_km", "distance_per_min", "max_speed",
    "hsr_distance", "sprint_distance", "hsr_count", "sprint_count",
    "med_acc_count", "med_dec_count", "acd_load",
    "zone1_distance", "zone2_distance", "zone3_distance", "zone4_distance", "zone5_distance",
]


@st.cache_resource
def _get_client():
    info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(dict(info), scopes=SCOPES)
    return gspread.authorize(creds)


def _worksheet(key: str):
    client = _get_client()
    return client.open(SHEET_NAMES[key]).sheet1


# ── 공통 로드/저장 ────────────────────────────────────────────────────────────

def load(key: str) -> pd.DataFrame:
    ws = _worksheet(key)
    data = ws.get_all_values()
    if not data or len(data) < 1:
        return pd.DataFrame(columns=SCHEMA.get(key, []))
    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)
    # 빈 행 제거
    df = df[df.apply(lambda r: r.str.strip().any(), axis=1)].reset_index(drop=True)
    # 누락 컬럼 추가
    for col in SCHEMA.get(key, []):
        if col not in df.columns:
            df[col] = ""
    return df


def save(key: str, df: pd.DataFrame) -> None:
    ws = _worksheet(key)
    df = df.fillna("").astype(str)
    ws.clear()
    ws.update([df.columns.tolist()] + df.values.tolist())


def append_rows(key: str, new_rows: pd.DataFrame) -> pd.DataFrame:
    existing = load(key)
    combined = pd.concat([existing, new_rows], ignore_index=True)
    save(key, combined)
    return combined


# ── 편의 함수 ─────────────────────────────────────────────────────────────────

def next_id(key: str, prefix: str) -> str:
    df = load(key)
    id_col = {"players": "player_id", "sessions": "session_id", "injuries": "injury_id"}[key]
    if df.empty or id_col not in df.columns:
        return f"{prefix}001"
    nums = df[id_col].dropna().str.extract(r"(\d+)")[0]
    nums = pd.to_numeric(nums, errors="coerce").dropna()
    return f"{prefix}{int(nums.max()) + 1:03d}" if not nums.empty else f"{prefix}001"


def player_id_from_jersey(jersey_no) -> str:
    try:
        return f"P{int(jersey_no):02d}"
    except (ValueError, TypeError):
        return "P00"


def get_weather_for_date(target_date: str, target_hour: int = 10) -> dict | None:
    df = load("weather")
    if df.empty:
        return None
    df["date"] = df["date"].astype(str).str.strip()
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(-1).astype(int)
    match = df[(df["date"] == target_date) & (df["hour"] == target_hour)]
    if match.empty:
        same_day = df[df["date"] == target_date]
        if same_day.empty:
            return None
        idx = (same_day["hour"] - target_hour).abs().idxmin()
        match = same_day.loc[[idx]]
    row = match.iloc[0]
    return {
        "temperature": row.get("temperature"),
        "humidity": row.get("humidity"),
        "source": row.get("source", "Google Sheets"),
    }


def is_duplicate_session(target_date: str, order: int) -> bool:
    df = load("sessions")
    if df.empty:
        return False
    return not df[(df["date"] == target_date) & (df["session_order"].astype(str) == str(order))].empty
