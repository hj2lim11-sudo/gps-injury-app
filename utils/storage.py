"""중앙 데이터 저장소 — 모든 Excel 읽기/쓰기."""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(r"C:\Users\user\Desktop\연구재단시작\데이터")
DATA_DIR.mkdir(parents=True, exist_ok=True)

PATHS = {
    "players":  DATA_DIR / "players.xlsx",
    "sessions": DATA_DIR / "session_master.xlsx",
    "gps":      DATA_DIR / "gps_data.xlsx",
    "weather":  DATA_DIR / "weather_data.xlsx",
    "injuries": DATA_DIR / "injury_data.xlsx",
    "merged":   DATA_DIR / "merged_dataset.xlsx",
}

# ── 스키마 기본값 ─────────────────────────────────────────────────────────────

SCHEMA = {
    "players": ["player_id", "jersey_no", "player_name", "position", "birth_year", "active"],
    "sessions": ["session_id", "date", "session_type", "session_order",
                 "start_time", "duration_min", "location", "opponent"],
    "gps": ["session_id", "date", "player_id", "jersey_no", "player_name", "position",
            "session_type", "session_order", "start_time", "duration_min", "location", "opponent",
            "total_distance_km", "distance_per_min", "max_speed",
            "hsr_distance", "sprint_distance", "hsr_count", "sprint_count",
            "med_acc_count", "med_dec_count", "acd_load",
            "zone1_distance", "zone2_distance", "zone3_distance", "zone4_distance", "zone5_distance"],
    "weather": ["date", "hour", "temperature", "humidity", "source"],
    "injuries": ["injury_id", "date", "player_id", "jersey_no", "player_name",
                 "participated", "injury_status", "body_part", "pain_level",
                 "absence_days", "session_id", "notes"],
}

GPS_METRIC_COLS = [
    "total_distance_km", "distance_per_min", "max_speed",
    "hsr_distance", "sprint_distance", "hsr_count", "sprint_count",
    "med_acc_count", "med_dec_count", "acd_load",
    "zone1_distance", "zone2_distance", "zone3_distance", "zone4_distance", "zone5_distance",
]


# ── 공통 로드/저장 ────────────────────────────────────────────────────────────

def load(key: str) -> pd.DataFrame:
    path = PATHS[key]
    if path.exists():
        df = pd.read_excel(path, dtype=str)
        # 누락 컬럼 추가
        for col in SCHEMA.get(key, []):
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=SCHEMA.get(key, []))


def save(key: str, df: pd.DataFrame) -> None:
    df.to_excel(PATHS[key], index=False)


def append_rows(key: str, new_rows: pd.DataFrame) -> pd.DataFrame:
    """기존 데이터에 행 추가 후 저장, 업데이트된 DataFrame 반환."""
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
    nums = df[id_col].dropna().str.extract(r"(\d+)")[0].astype(int, errors="ignore")
    nums = pd.to_numeric(nums, errors="coerce").dropna()
    return f"{prefix}{int(nums.max()) + 1:03d}" if not nums.empty else f"{prefix}001"


def player_id_from_jersey(jersey_no) -> str:
    try:
        return f"P{int(jersey_no):02d}"
    except (ValueError, TypeError):
        return "P00"


def get_weather_for_date(target_date: str, target_hour: int = 10) -> dict | None:
    """weather_data.xlsx에서 날짜·시각에 맞는 기온·습도 반환."""
    df = load("weather")
    if df.empty:
        return None
    df["date"] = df["date"].astype(str).str.strip()
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(-1).astype(int)
    match = df[(df["date"] == target_date) & (df["hour"] == target_hour)]
    if match.empty:
        # 같은 날짜 중 가장 가까운 시각
        same_day = df[df["date"] == target_date]
        if same_day.empty:
            return None
        idx = (same_day["hour"] - target_hour).abs().idxmin()
        match = same_day.loc[[idx]]
    row = match.iloc[0]
    return {
        "temperature": row.get("temperature"),
        "humidity": row.get("humidity"),
        "source": row.get("source", "weather_data.xlsx"),
    }


def is_duplicate_session(target_date: str, order: int) -> bool:
    df = load("sessions")
    if df.empty:
        return False
    return not df[(df["date"] == target_date) & (df["session_order"].astype(str) == str(order))].empty
