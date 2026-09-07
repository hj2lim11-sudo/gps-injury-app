"""중앙 데이터 저장소 — Google Sheets 읽기/쓰기."""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAMES = {
    "players":  "MJU_Players",
    "gps":      "GPS_gps_data",
    "injuries": "Injury_data",
    "merged":   "Merged_dataset",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

GPS_META_COLS = [
    "session_id", "season_year", "session_date", "weekday",
    "training_time_band", "event_code", "event_detail",
    "venue", "opponent", "start_time", "end_time", "session_duration_min",
    "temperature_c", "humidity_pct", "precipitation_mm",
    "player_id", "jersey_no", "player_name",
]

GPS_METRIC_COLS = [
    "total_distance_km", "distance_per_min", "max_speed",
    "hsr_distance", "sprint_distance", "hsr_count", "sprint_count",
    "high_acc_count", "high_acc_distance", "high_dec_count", "high_dec_distance",
    "max_acc", "max_dec", "acd_load",
    "zone1_distance", "zone2_distance", "zone3_distance", "zone4_distance", "zone5_distance",
    "acr_distance", "acr_hsr", "acr_sprint", "acr_acd_load",
]

SCHEMA = {
    "players": [
        "player_id", "player_name", "jersey_no", "position",
        "birth_date", "grade", "height", "prev_school", "active",
    ],
    "gps": GPS_META_COLS + GPS_METRIC_COLS,
    "injuries": [
        "injury_id", "date", "player_id", "jersey_no", "player_name",
        "participated", "injury_status", "body_part", "pain_level",
        "absence_days", "session_id", "notes",
    ],
    "merged": [],
}

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
TIME_BANDS  = ["AM", "PM", "DAWN", "NIGHT"]
EVENT_CODES = ["TRAINING", "MATCH", "FITNESS", "RECOVERY", "OTHER"]


def season_year_from_date(d: str) -> int:
    dt = pd.to_datetime(d)
    return dt.year + 1 if dt.month >= 9 else dt.year


def weekday_kr(d: str) -> str:
    return WEEKDAY_KR[pd.to_datetime(d).weekday()]


def time_band_from_hour(hour: int) -> str:
    if hour < 8:  return "DAWN"
    if hour < 12: return "AM"
    if hour < 18: return "PM"
    return "NIGHT"


def make_session_id(session_date: str, time_band: str, event_code: str, seq: int) -> str:
    d = session_date.replace("-", "")
    return f"{d}_{time_band}_{event_code}_{seq:02d}"


@st.cache_resource
def _get_client():
    info  = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(dict(info), scopes=SCOPES)
    return gspread.authorize(creds)


def _worksheet(key: str):
    return _get_client().open(SHEET_NAMES[key]).sheet1


@st.cache_data(ttl=60)
def load(key: str) -> pd.DataFrame:
    ws   = _worksheet(key)
    data = ws.get_all_values()
    if not data:
        return pd.DataFrame(columns=SCHEMA.get(key, []))
    headers = data[0]
    rows    = data[1:]
    df = pd.DataFrame(rows, columns=headers)
    df = df[df.apply(lambda r: r.str.strip().any(), axis=1)].reset_index(drop=True)
    for col in SCHEMA.get(key, []):
        if col not in df.columns:
            df[col] = ""
    return df


def save(key: str, df: pd.DataFrame) -> None:
    ws = _worksheet(key)
    df = df.fillna("").astype(str)
    ws.clear()
    ws.update([df.columns.tolist()] + df.values.tolist())
    load.clear()


def append_rows(key: str, new_rows: pd.DataFrame) -> pd.DataFrame:
    existing = load(key)
    combined = pd.concat([existing, new_rows], ignore_index=True)
    save(key, combined)
    return combined


def next_session_seq(session_date: str, time_band: str, event_code: str) -> int:
    gps = load("gps")
    if gps.empty or "session_id" not in gps.columns:
        return 1
    prefix  = f"{session_date.replace('-', '')}_{time_band}_{event_code}_"
    matches = gps["session_id"].dropna()
    matches = matches[matches.str.startswith(prefix)]
    if matches.empty:
        return 1
    nums = matches.str.extract(r"_(\d+)$")[0]
    nums = pd.to_numeric(nums, errors="coerce").dropna()
    return int(nums.max()) + 1 if not nums.empty else 1


def next_id(key: str, prefix: str) -> str:
    df     = load(key)
    id_col = {"players": "player_id", "gps": "session_id", "injuries": "injury_id"}.get(key, "id")
    if df.empty or id_col not in df.columns:
        return f"MJU_{prefix}001" if key == "players" else f"{prefix}001"
    nums = df[id_col].dropna().str.extract(r"(\d+)")[0]
    nums = pd.to_numeric(nums, errors="coerce").dropna()
    nxt  = f"{int(nums.max()) + 1:03d}" if not nums.empty else "001"
    return f"MJU_{prefix}{nxt}" if key == "players" else f"{prefix}{nxt}"


def player_id_from_jersey(jersey_no) -> str:
    try:
        return f"MJU_P{int(jersey_no):03d}"
    except (ValueError, TypeError):
        return "MJU_P000"
