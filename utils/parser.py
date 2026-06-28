"""GPS CSV 파싱 — Fitogether details / Trend CSV 지원."""
import pandas as pd
from io import BytesIO

# ── Fitogether details CSV 컬럼 매핑 ─────────────────────────────────────────
DETAILS_COL_MAP = {
    "날짜":                  "date",
    "액티비티 타입":          "activity_type",
    "액티비티 이름":          "activity_name",
    "세션 타입":              "session_half",
    "세션 이름":              "session_name",
    "시작 시간":              "start_datetime",
    "종료 시간":              "end_datetime",
    "등번호":                 "jersey_no",
    "선수 이름":              "player_name",
    "포지션":                 "position",
    "뛴 시간 (min)":          "duration_min",
    "뛴 거리 (km)":           "total_distance_km",
    "분당 뛴 거리 (m/min)":   "distance_per_min",
    "최고 속도 (km/h)":       "max_speed",
    "HSR 거리 (m)":           "hsr_distance",
    "스프린트 거리 (m)":      "sprint_distance",
    "HSR 횟수 (times)":       "hsr_count",
    "스프린트 횟수 (times)":  "sprint_count",
    "폭발적 가속 횟수 (times)": "med_acc_count",
    "폭발적 감속 횟수 (times)": "med_dec_count",
    "속도 1구간 거리 (km)":   "zone1_distance",
    "속도 2구간 거리 (km)":   "zone2_distance",
    "속도 3구간 거리 (km)":   "zone3_distance",
    "속도 4구간 거리 (km)":   "zone4_distance",
    "속도 5구간 거리 (km)":   "zone5_distance",
    "ACD Load":               "acd_load",
    "평균 심박수 (bpm)":      "avg_hr",
    "최대 HR (bpm)":          "max_hr",
    "최대 가속 (m/s²)":       "max_acc",
    "최대 감속 (m/s²)":       "max_dec",
}

# Stats_by_Player 형식 (기존 호환)
DAILY_COL_MAP = {
    # 선수 정보
    "선수명": "player_name", "선수 이름": "player_name", "이름": "player_name", "Player": "player_name",
    "등번호": "jersey_no",   "No": "jersey_no", "No.": "jersey_no",
    "포지션": "position",    "Position": "position",
    # 기본 지표
    "뛴 시간 (min)": "duration_min",
    "뛴 거리 (km)": "total_distance_km",
    "총 이동거리": "total_distance_km", "Total Distance": "total_distance_km",
    "Total Distance (km)": "total_distance_km",
    "분당 뛴 거리 (m/min)": "distance_per_min",
    "분당이동거리": "distance_per_min", "Distance / min": "distance_per_min",
    "최고 속도 (km/h)": "max_speed",
    "최고속도": "max_speed",  "Max Speed": "max_speed",
    # HSR / Sprint
    "HSR 거리 (m)": "hsr_distance",
    "고속달리기 거리": "hsr_distance", "HSR Distance": "hsr_distance",
    "Sprint 거리 (m)": "sprint_distance",
    "스프린트 거리": "sprint_distance", "Sprint Distance": "sprint_distance",
    "HSR 횟수 (times)": "hsr_count",
    "고속달리기 횟수": "hsr_count",    "HSR Count": "hsr_count",
    "Sprint 횟수 (times)": "sprint_count",
    "스프린트 횟수": "sprint_count",   "Sprint Count": "sprint_count",
    # 가속/감속
    "Medium Acceleration 횟수 (times)": "med_acc_count",
    "중간가속 횟수": "med_acc_count",  "Med Acc Count": "med_acc_count",
    "폭발적 가속 횟수 (times)": "med_acc_count",
    "Medium Deceleration 횟수 (times)": "med_dec_count",
    "중간감속 횟수": "med_dec_count",  "Med Dec Count": "med_dec_count",
    "폭발적 감속 횟수 (times)": "med_dec_count",
    # ACD Load
    "ACD Load": "acd_load",
    # 속도 구간
    "속도 1구간 거리 (km)": "zone1_distance",
    "존1 거리": "zone1_distance", "Zone1 Distance": "zone1_distance",
    "속도 2구간 거리 (km)": "zone2_distance",
    "존2 거리": "zone2_distance", "Zone2 Distance": "zone2_distance",
    "속도 3구간 거리 (km)": "zone3_distance",
    "존3 거리": "zone3_distance", "Zone3 Distance": "zone3_distance",
    "속도 4구간 거리 (km)": "zone4_distance",
    "존4 거리": "zone4_distance", "Zone4 Distance": "zone4_distance",
    "속도 5구간 거리 (km)": "zone5_distance",
    "존5 거리": "zone5_distance", "Zone5 Distance": "zone5_distance",
}

ACD_COL_CANDIDATES = ["ACD Load", "acd_load", "ACD부하", "ACD 부하"]

GPS_METRIC_COLS = [
    "total_distance_km", "distance_per_min", "max_speed",
    "hsr_distance", "sprint_distance", "hsr_count", "sprint_count",
    "med_acc_count", "med_dec_count", "acd_load",
    "zone1_distance", "zone2_distance", "zone3_distance",
    "zone4_distance", "zone5_distance",
    "avg_hr", "max_hr", "max_acc", "max_dec",
]


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(BytesIO(file_bytes), encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV 인코딩을 인식할 수 없습니다.")


def _is_details_format(df: pd.DataFrame) -> bool:
    """Fitogether details CSV 형식 판별."""
    return "날짜" in df.columns and "액티비티 이름" in df.columns


def _normalize(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    rename = {col: col_map[col.strip()] for col in df.columns if col.strip() in col_map}
    return df.rename(columns=rename)


def _to_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            # ACD Load의 쉼표 제거 ("1,824.1" → 1824.1)
            if df[c].dtype == object:
                df[c] = df[c].astype(str).str.replace(",", "").str.strip()
                df[c] = df[c].replace(["-", "", "nan"], None)
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ── 세션 메타 자동 추출 ───────────────────────────────────────────────────────

def extract_session_meta(file_bytes: bytes) -> dict:
    """
    Fitogether details CSV에서 세션 메타정보 자동 추출.

    Returns
    -------
    dict: date, session_type, start_time, duration_min, opponent, activity_name
          (없으면 None)
    """
    try:
        df = _read_csv(file_bytes)
    except Exception:
        return {}

    if not _is_details_format(df):
        return {}

    df = _normalize(df, DETAILS_COL_MAP)

    # 합계 행(session_half 비어있음)만 사용
    total_rows = df[df.get("session_half", pd.Series(dtype=str)).isna() |
                    (df.get("session_half", pd.Series(dtype=str)).astype(str).str.strip() == "")]
    if total_rows.empty:
        total_rows = df  # fallback

    row = total_rows.iloc[0]

    # 날짜
    date_val = str(row.get("date", "")).strip()[:10]  # "2024-04-05"

    # 시작 시간
    start_dt = str(row.get("start_datetime", "")).strip()
    start_time = start_dt[11:16] if len(start_dt) >= 16 else "10:00"

    # 종료 시간 → 운동 시간 계산
    end_dt = str(row.get("end_datetime", "")).strip()
    duration = None
    try:
        from datetime import datetime
        s = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
        e = datetime.strptime(end_dt,   "%Y-%m-%d %H:%M:%S")
        duration = int((e - s).total_seconds() / 60)
    except Exception:
        pass

    # 세션 타입 매핑
    act_type = str(row.get("activity_type", "")).strip()
    type_map = {"리그": "경기", "컵": "경기", "대회": "경기",
                "훈련": "훈련", "체력": "체력측정"}
    session_type = next((v for k, v in type_map.items() if k in act_type), "훈련")

    # 활동명에서 상대팀 추출 (예: "2024-04-05 U리그 2R 관동대 원정경기" → "관동대")
    activity_name = str(row.get("activity_name", "")).strip()
    opponent = ""
    for kw in ["vs", "VS", " 대 "]:
        if kw in activity_name:
            opponent = activity_name.split(kw)[-1].strip().split()[0]
            break
    # 이름에서 날짜/리그명 제거 후 마지막 팀명 추출 시도
    if not opponent and session_type == "경기":
        parts = activity_name.replace(date_val, "").strip().split()
        # "경기", "원정", "홈" 같은 단어 앞 단어가 팀명인 경우가 많음
        for i, p in enumerate(parts):
            if p in ["원정경기", "홈경기", "경기"]:
                if i > 0:
                    opponent = parts[i - 1]
                break

    return {
        "date":          date_val,
        "session_type":  session_type,
        "start_time":    start_time,
        "duration_min":  duration,
        "opponent":      opponent,
        "activity_name": activity_name,
    }


# ── details CSV 파싱 (합계 행만) ──────────────────────────────────────────────

def parse_details_csv(file_bytes: bytes) -> pd.DataFrame:
    """
    Fitogether details CSV 파싱 → 선수별 합계 행 반환.
    전반/후반 행 제외, 팀 평균 행 제외.
    """
    df = _read_csv(file_bytes)
    df = _normalize(df, DETAILS_COL_MAP)

    # 합계 행: session_half가 비어있는 행
    if "session_half" in df.columns:
        total = df[df["session_half"].isna() |
                   (df["session_half"].astype(str).str.strip() == "")]
    else:
        total = df

    # 팀 평균 행 제거
    if "player_name" in total.columns:
        total = total[~total["player_name"].astype(str).str.contains(
            "팀 평균|평균|average|team", case=False, na=False
        )]
        total = total[total["player_name"].notna()]

    total = total.copy()
    total["jersey_no"] = pd.to_numeric(total.get("jersey_no"), errors="coerce")
    total = _to_numeric(total, GPS_METRIC_COLS)

    keep = ["jersey_no", "player_name", "position"] + \
           [c for c in GPS_METRIC_COLS if c in total.columns]
    return total[[c for c in keep if c in total.columns]].reset_index(drop=True)


# ── 기존 Stats_by_Player CSV 파싱 (호환 유지) ────────────────────────────────

def parse_daily_csv(file_bytes: bytes) -> pd.DataFrame:
    df = _read_csv(file_bytes)

    if _is_details_format(df):
        return parse_details_csv(file_bytes)

    # 선수명 컬럼 직접 통일
    for alias in ("이름", "선수 이름", "선수명", "Player", "player_name"):
        if alias in df.columns and "player_name" not in df.columns:
            df = df.rename(columns={alias: "player_name"})
            break

    df = _normalize(df, DAILY_COL_MAP)

    if "player_name" not in df.columns:
        raise ValueError(f"선수명 컬럼 없음. 현재 컬럼: {list(df.columns)}")

    df = df[df["player_name"].notna()]
    df = df[~df["player_name"].astype(str).str.contains(
        r"합계|평균|total|average", case=False, na=False)]

    if "jersey_no" not in df.columns:
        df["jersey_no"] = None
    if "position" not in df.columns:
        df["position"] = None

    df["jersey_no"] = pd.to_numeric(df["jersey_no"], errors="coerce")
    df = _to_numeric(df, GPS_METRIC_COLS)

    keep = ["jersey_no", "player_name", "position"] + \
           [c for c in GPS_METRIC_COLS if c in df.columns]
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


# ── Trend CSV (ACD Load 추출, details 없을 때 보조) ──────────────────────────

def parse_trend_csv(file_bytes: bytes) -> dict:
    """Trend CSV → {player_name: acd_load}"""
    df = _read_csv(file_bytes)

    # 이름 컬럼 찾기
    name_col = next((c for c in df.columns
                     if c.strip() in ("이름", "선수 이름", "선수명", "Player", "player_name")), None)
    if not name_col:
        raise ValueError(f"선수명 컬럼 없음. 현재 컬럼: {list(df.columns)}")

    acd_col = next((c for c in df.columns
                    if c.strip() in ACD_COL_CANDIDATES or "acd" in c.lower()), None)
    if not acd_col:
        raise ValueError(f"ACD Load 컬럼 없음. 현재 컬럼: {list(df.columns)}")

    df = df[df[name_col].notna()].copy()
    df["_acd"] = df[acd_col].astype(str).str.replace(",", "").str.strip()
    df["_acd"] = pd.to_numeric(df["_acd"], errors="coerce")
    return dict(zip(df[name_col].astype(str).str.strip(), df["_acd"]))
