"""
날씨 수집 모듈 — 기상청 ASOS 실측값 전용
직접 입력 장소도 지오코딩 → 최근접 ASOS 관측소 자동 선택 → 실측값 수집.
Open-Meteo는 ASOS가 완전히 실패할 때만 최후 fallback.
"""
import os
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

# Streamlit Cloud secrets 또는 .env에서 API 키 읽기
try:
    import streamlit as st
    KMA_API_KEY = st.secrets["kma"]["api_key"]
except Exception:
    KMA_API_KEY = os.getenv("KMA_API_KEY", "")
ASOS_URL       = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODE_URL    = "https://geocoding-api.open-meteo.com/v1/search"

# ── 자주 쓰는 장소 → ASOS 관측소 직접 매핑 ───────────────────────────────────
LOCATION_CONFIG = {
    "명지대학교 자연캠퍼스": {"stn_id": 119, "lat": 37.2215, "lon": 127.1878},
    "원정":                  {"stn_id": 108, "lat": 37.5665, "lon": 126.9780},
    "서울":                  {"stn_id": 108, "lat": 37.5714, "lon": 126.9658},
    "수원":                  {"stn_id": 119, "lat": 37.2636, "lon": 127.0286},
    "인천":                  {"stn_id": 112, "lat": 37.4563, "lon": 126.6249},
    "춘천":                  {"stn_id": 101, "lat": 37.9026, "lon": 127.7353},
    "강릉":                  {"stn_id": 105, "lat": 37.7516, "lon": 128.8906},
    "충주":                  {"stn_id": 127, "lat": 36.9714, "lon": 127.9464},
    "청주":                  {"stn_id": 131, "lat": 36.6416, "lon": 127.4408},
    "천안":                  {"stn_id": 232, "lat": 36.7764, "lon": 127.1225},
    "대전":                  {"stn_id": 133, "lat": 36.3719, "lon": 127.3742},
    "전주":                  {"stn_id": 146, "lat": 35.8208, "lon": 127.1542},
    "군산":                  {"stn_id": 140, "lat": 35.9942, "lon": 126.7161},
    "광주":                  {"stn_id": 156, "lat": 35.1714, "lon": 126.8917},
    "목포":                  {"stn_id": 165, "lat": 34.8175, "lon": 126.3814},
    "순천":                  {"stn_id": 174, "lat": 34.9950, "lon": 127.4886},
    "여수":                  {"stn_id": 168, "lat": 34.7394, "lon": 127.7400},
    "대구":                  {"stn_id": 143, "lat": 35.8853, "lon": 128.6181},
    "안동":                  {"stn_id": 136, "lat": 36.5731, "lon": 128.7072},
    "포항":                  {"stn_id": 138, "lat": 36.0321, "lon": 129.3800},
    "구미":                  {"stn_id": 281, "lat": 36.1303, "lon": 128.3194},
    "경주":                  {"stn_id": 285, "lat": 35.8400, "lon": 129.2119},
    "울산":                  {"stn_id": 152, "lat": 35.5603, "lon": 129.3189},
    "부산":                  {"stn_id": 159, "lat": 35.1042, "lon": 129.0319},
    "창원":                  {"stn_id": 155, "lat": 35.1683, "lon": 128.5644},
    "거창":                  {"stn_id": 288, "lat": 35.6831, "lon": 127.9089},
    "통영":                  {"stn_id": 162, "lat": 34.8461, "lon": 128.4347},
    "사천":                  {"stn_id": 192, "lat": 35.0956, "lon": 128.0700},
    "거제":                  {"stn_id": 294, "lat": 34.8833, "lon": 128.6031},
    "제주":                  {"stn_id": 184, "lat": 33.5144, "lon": 126.5294},
    "서귀포":                {"stn_id": 189, "lat": 33.2461, "lon": 126.5658},
}

DEFAULT_CONFIG = LOCATION_CONFIG["명지대학교 자연캠퍼스"]

# 전국 ASOS 관측소 목록 (지오코딩 결과 → 최근접 관측소 자동 선택용)
_ASOS_ALL = [
    (90,  38.2507, 128.5641), (98,  37.9000, 127.0600), (100, 37.6771, 128.7183),
    (101, 37.9026, 127.7353), (105, 37.7516, 128.8906), (108, 37.5714, 126.9658),
    (112, 37.4786, 126.6249), (114, 37.3381, 127.9467), (119, 37.2636, 127.0286),
    (127, 36.9714, 127.9464), (129, 36.7764, 126.4942), (130, 36.9928, 129.4128),
    (131, 36.6416, 127.4408), (133, 36.3719, 127.3742), (136, 36.5731, 128.7072),
    (138, 36.0321, 129.3800), (140, 35.9942, 126.7161), (143, 35.8853, 128.6181),
    (146, 35.8208, 127.1542), (152, 35.5603, 129.3189), (155, 35.1683, 128.5644),
    (156, 35.1714, 126.8917), (159, 35.1042, 129.0319), (162, 34.8461, 128.4347),
    (165, 34.8175, 126.3814), (168, 34.7394, 127.7400), (174, 34.9950, 127.4886),
    (184, 33.5144, 126.5294), (188, 33.3869, 126.8800), (189, 33.2461, 126.5658),
    (192, 35.0956, 128.0700), (201, 37.7025, 126.4447), (202, 37.4886, 127.4947),
    (203, 37.2653, 127.4856), (211, 38.0592, 128.1694), (212, 37.6878, 127.8811),
    (232, 36.7764, 127.1225), (238, 36.3272, 126.5597), (243, 35.7306, 126.7178),
    (247, 35.5650, 126.8631), (248, 35.4161, 127.3281), (260, 34.6867, 126.9075),
    (261, 34.5542, 126.5697), (262, 34.6156, 127.2833), (263, 35.3228, 128.2681),
    (264, 35.5208, 127.7253), (271, 36.9417, 128.9167), (272, 36.8717, 128.5172),
    (276, 36.4361, 129.0569), (278, 36.5336, 129.4053), (279, 36.3553, 128.6897),
    (281, 36.1303, 128.3194), (284, 35.9778, 128.9514), (285, 35.8400, 129.2119),
    (288, 35.6831, 127.9089), (289, 35.5653, 128.1658), (294, 34.8833, 128.6031),
]


def _nearest_asos_stn(lat: float, lon: float) -> int:
    """좌표 → 가장 가까운 ASOS 관측소 stn_id."""
    return min(_ASOS_ALL, key=lambda s: (lat - s[1])**2 + (lon - s[2])**2)[0]


def get_config(location: str) -> dict:
    """
    장소명 → {stn_id, lat, lon}.
    1) LOCATION_CONFIG 완전 일치
    2) LOCATION_CONFIG 부분 일치
    3) 지오코딩 → 최근접 ASOS 관측소 자동 선택 (실측 유지)
    4) 명지대 기본값
    """
    if location in LOCATION_CONFIG:
        return LOCATION_CONFIG[location]
    for key in LOCATION_CONFIG:
        if key in location or location in key:
            return LOCATION_CONFIG[key]

    try:
        r = requests.get(GEOCODE_URL, params={
            "name": location, "count": 1,
            "language": "ko", "country_code": "KR",
        }, timeout=5)
        results = r.json().get("results", [])
        if results:
            lat = results[0]["latitude"]
            lon = results[0]["longitude"]
            stn_id = _nearest_asos_stn(lat, lon)
            return {"stn_id": stn_id, "lat": lat, "lon": lon}
    except Exception:
        pass

    return DEFAULT_CONFIG


# ── ASOS 단일 시각 ────────────────────────────────────────────────────────────

def _fetch_asos(stn_id: int, target_date: str, target_hour: int) -> dict:
    if not KMA_API_KEY or KMA_API_KEY.startswith("여기에"):
        return {"error": "API 키 미설정"}
    dt_str = datetime.strptime(target_date, "%Y-%m-%d").strftime("%Y%m%d")
    try:
        r = requests.get(ASOS_URL, params={
            "serviceKey": KMA_API_KEY, "pageNo": 1, "numOfRows": 10,
            "dataType": "JSON", "dataCd": "ASOS", "dateCd": "HR",
            "startDt": dt_str, "startHh": f"{target_hour:02d}",
            "endDt":   dt_str, "endHh":   f"{target_hour:02d}",
            "stnIds":  stn_id,
        }, timeout=10)
        r.raise_for_status()
        resp   = r.json()["response"]
        header = resp.get("header", {})
        if header.get("resultCode") != "00":
            return {"error": f"ASOS 오류: {header.get('resultMsg')}"}
        body = resp.get("body", {})
        if not body or body.get("totalCount", 0) == 0:
            return {"error": f"ASOS 데이터 없음 (stn={stn_id}, {target_date} {target_hour:02d}시)"}
        item = body["items"]["item"][0]
        temp = item.get("ta")
        hum  = item.get("hm")
        if temp is None or hum is None:
            return {"error": "기온/습도 값 없음"}
        return {
            "temperature": round(float(temp), 1),
            "humidity":    round(float(hum),  1),
            "source":      f"기상청 ASOS 실측 (관측소 {stn_id})",
        }
    except Exception as e:
        return {"error": f"ASOS API 실패: {e}"}


# ── Open-Meteo (최후 fallback) ────────────────────────────────────────────────

def _fetch_open_meteo(lat: float, lon: float, target_date: str, target_hour: int) -> dict:
    try:
        r = requests.get(OPEN_METEO_URL, params={
            "latitude": lat, "longitude": lon,
            "start_date": target_date, "end_date": target_date,
            "hourly": "temperature_2m,relative_humidity_2m",
            "timezone": "Asia/Seoul",
        }, timeout=10)
        r.raise_for_status()
        data       = r.json()["hourly"]
        times      = data["time"]
        target_str = f"{target_date}T{target_hour:02d}:00"
        idx = (times.index(target_str) if target_str in times
               else min(range(len(times)),
                        key=lambda i: abs(datetime.fromisoformat(times[i]) -
                                          datetime.strptime(target_str, "%Y-%m-%dT%H:%M"))))
        return {
            "temperature": round(float(data["temperature_2m"][idx]), 1),
            "humidity":    round(float(data["relative_humidity_2m"][idx]), 1),
            "source":      "Open-Meteo reanalysis (fallback)",
        }
    except Exception as e:
        return {"error": f"Open-Meteo 실패: {e}"}


# ── 단일 시각 통합 ────────────────────────────────────────────────────────────

def fetch_weather(location: str, target_date: str, target_hour: int) -> dict:
    """ASOS 실측 우선, ASOS 실패 시에만 Open-Meteo fallback."""
    cfg    = get_config(location)
    result = _fetch_asos(cfg["stn_id"], target_date, target_hour)
    if "error" not in result:
        return result
    # ASOS 실패 → Open-Meteo (최후 수단)
    fallback = _fetch_open_meteo(cfg["lat"], cfg["lon"], target_date, target_hour)
    if "error" not in fallback:
        fallback["source"] += f" (ASOS 오류: {result['error']})"
    return fallback


# ── 세션 시간대 전체 수집 + 평균 ─────────────────────────────────────────────

def fetch_session_weather(
    location: str,
    target_date: str,
    start_time: str,    # "13:38"
    duration_min: int,  # 159
) -> dict:
    """
    세션 시작~종료 시간의 매 시각 ASOS 실측값 수집 → 기온·습도 평균 반환.

    Returns
    -------
    {
        "temperature": float,   # 기온 평균
        "humidity":    float,   # 습도 평균
        "source":      str,
        "hourly":      [{"hour": int, "temperature": float, "humidity": float}, ...]
    }
    """
    try:
        start_h = int(start_time.split(":")[0])
        end_h   = min(start_h + (duration_min // 60), 23)
    except Exception:
        start_h, end_h = 10, 11

    hourly  = []
    sources = []
    for h in range(start_h, end_h + 1):
        r = fetch_weather(location, target_date, h)
        if "error" not in r:
            hourly.append({"hour": h, "temperature": r["temperature"], "humidity": r["humidity"]})
            sources.append(r["source"])

    if not hourly:
        return {"error": f"날씨 수집 실패 ({target_date} {start_h}~{end_h}시)"}

    avg_temp = round(sum(x["temperature"] for x in hourly) / len(hourly), 1)
    avg_humi = round(sum(x["humidity"]    for x in hourly) / len(hourly), 1)

    return {
        "temperature": avg_temp,
        "humidity":    avg_humi,
        "source":      sources[0] if sources else "unknown",
        "hourly":      hourly,
    }


# ── 날짜 범위 일괄 수집 (날씨 데이터 페이지용) ───────────────────────────────

def fetch_range(start_date: str, end_date: str,
                location: str = "명지대학교 자연캠퍼스") -> "pd.DataFrame":
    import pandas as pd
    cfg = get_config(location)

    if KMA_API_KEY and not KMA_API_KEY.startswith("여기에"):
        try:
            r = requests.get(ASOS_URL, params={
                "serviceKey": KMA_API_KEY, "pageNo": 1, "numOfRows": 9999,
                "dataType": "JSON", "dataCd": "ASOS", "dateCd": "HR",
                "startDt": datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d"),
                "startHh": "00",
                "endDt":   datetime.strptime(end_date,   "%Y-%m-%d").strftime("%Y%m%d"),
                "endHh":   "23",
                "stnIds":  cfg["stn_id"],
            }, timeout=30)
            r.raise_for_status()
            body = r.json()["response"]["body"]
            if body["totalCount"] > 0:
                rows = []
                for item in body["items"]["item"]:
                    dt_val = item.get("tm", "")
                    try:
                        dt_obj = datetime.strptime(dt_val.strip(), "%Y-%m-%d %H:%M")
                        rows.append({
                            "date":        dt_obj.strftime("%Y-%m-%d"),
                            "hour":        dt_obj.hour,
                            "temperature": float(item["ta"]) if item.get("ta") else None,
                            "humidity":    float(item["hm"]) if item.get("hm") else None,
                            "source":      f"기상청 ASOS 실측 (관측소 {cfg['stn_id']})",
                        })
                    except Exception:
                        continue
                if rows:
                    return pd.DataFrame(rows)
        except Exception:
            pass

    # Open-Meteo fallback
    r = requests.get(OPEN_METEO_URL, params={
        "latitude": cfg["lat"], "longitude": cfg["lon"],
        "start_date": start_date, "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m",
        "timezone": "Asia/Seoul",
    }, timeout=30)
    r.raise_for_status()
    data = r.json()["hourly"]
    rows = []
    for t, temp, hum in zip(data["time"], data["temperature_2m"], data["relative_humidity_2m"]):
        date_part, hr_part = t.split("T")
        rows.append({"date": date_part, "hour": int(hr_part[:2]),
                     "temperature": temp, "humidity": hum, "source": "Open-Meteo reanalysis"})
    return pd.DataFrame(rows)
