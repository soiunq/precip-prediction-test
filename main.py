from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import joblib
import pandas as pd
import numpy as np
import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 캐시: 마지막으로 받아온 기상청 데이터와 받은 시각
_asos_cache = {"data": None, "fetched_at": None}
CACHE_TTL_SECONDS = 3600  # 1시간 동안은 캐시된 데이터 재사용

load_dotenv()
SERVICE_KEY = os.getenv("SERVICE_KEY")  # 기상청 API 인증키 (.env에서 로드)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# 학습 완료된 모델/스케일러 로드
model_logreg = joblib.load("models/logreg_20260715.joblib")
model_mlp = joblib.load("models/mlp_20260715.joblib")
scaler = joblib.load("models/scaler_20260715.joblib")

THRESHOLD = 0.5  # 강수 판정 확률 임계값

# 모델 입력 피처 순서
FEATURE_COLS = [
    'avg_temp', 'min_temp', 'max_temp', 'avg_wind', 'max_wind_dir',
    'avg_dewpoint', 'avg_humid', 'avg_pres_sea', 'avg_cloud',
    'dewpoint_depression', 'temp_range', 'temp_change', 'pres_change', 'wind_change',
    'precip_lag1', 'avg_wind_lag1', 'avg_humid_lag1', 'avg_pres_sea_lag1',
    'avg_cloud_lag1', 'dewpoint_depression_lag1', 'temp_range_lag1',
    'humid_rolling_3d_mean', 'pres_rolling_3d_mean', 'precip_rolling_3d_sum',
    'precip_rolling_7d_sum', 'precip_today', 'month_sin', 'month_cos',
    'humid_rolling_5d_mean', 'pres_rolling_5d_mean',
    'humid_pres_interaction', 'pres_acceleration'
]


def _fetch_asos_range_raw(days_back=12):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back - 1)

    url = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": "20",
        "dataType": "JSON",
        "dataCd": "ASOS",
        "dateCd": "DAY",
        "startDt": start_date.strftime("%Y%m%d"),
        "endDt": end_date.strftime("%Y%m%d"),
        "stnIds": "108"
    }
    response = requests.get(url, params=params)
    result = response.json()

    if 'body' not in result.get('response', {}):
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=days_back - 1)
        params["startDt"] = start_date.strftime("%Y%m%d")
        params["endDt"] = end_date.strftime("%Y%m%d")
        response = requests.get(url, params=params)
        result = response.json()

    return result


def fetch_asos_range(days_back=12):
    now = datetime.now()
    if (_asos_cache["data"] is not None and
            _asos_cache["fetched_at"] is not None and
            (now - _asos_cache["fetched_at"]).total_seconds() < CACHE_TTL_SECONDS):
        return _asos_cache["data"]

    result = _fetch_asos_range_raw(days_back=days_back)
    _asos_cache["data"] = result
    _asos_cache["fetched_at"] = now
    return result


def parse_asos_with_lag(response_json):
    """
    API 응답에서 '오늘(예측 기준일)' 피처와 lag1(전날) 피처를 함께 만든다.

    - dewpoint_depression(이슬점차), temp_range(일교차)는 오늘/전날 각각 파생 계산
    - *_lag1 피처들은 모두 '전날' 값을 오늘 행에 붙이는 것 (point-in-time 원칙: 예측 시점에 실제로 알 수 있는 값만 사용)
    - temp_change/pres_change/wind_change는 오늘-전날 변화량
    - precip_today는 오늘 강수 발생 여부(0/1) — 주의: 이건 today_data에 들어있지만
      실제로는 '기준_관측일'의 강수 여부이며, 모델은 이걸로 '다음날' 강수를 예측함

    반환값: (오늘 기준 피처 dict, 유효 관측치 리스트)
    """
    items = response_json['response']['body']['items']['item']
    items = sorted(items, key=lambda x: x['tm'])

    def is_valid(item):
        return item.get('avgTa', '') not in ('', None)

    valid_items = [item for item in items if is_valid(item)]

    if len(valid_items) < 2:
        raise ValueError("최소 2일치 확정 데이터가 필요합니다 (아직 발표되지 않았을 수 있습니다)")

    day_before = valid_items[-2]
    latest = valid_items[-1]

    def extract(item):
        # 결측 필드는 안전하게 default(0.0)로 대체하면서 float 변환
        def safe_float(key, default=0.0):
            val = item.get(key, '')
            return float(val) if val not in ('', None) else default

        return {
            'avg_temp': safe_float('avgTa'),
            'min_temp': safe_float('minTa'),
            'max_temp': safe_float('maxTa'),
            'avg_wind': safe_float('avgWs'),
            'max_wind_dir': safe_float('maxWsWd'),
            'avg_dewpoint': safe_float('avgTd'),
            'avg_humid': safe_float('avgRhm'),
            'avg_pres_sea': safe_float('avgPa'),
            'avg_cloud': safe_float('avgTca'),
            'precip': safe_float('sumRn'),
        }

    today_data = extract(latest)
    prev_data = extract(day_before)

    # 파생 피처: 오늘/전날 각각 계산
    today_data['dewpoint_depression'] = today_data['avg_temp'] - today_data['avg_dewpoint']
    today_data['temp_range'] = today_data['max_temp'] - today_data['min_temp']

    prev_data['dewpoint_depression'] = prev_data['avg_temp'] - prev_data['avg_dewpoint']
    prev_data['temp_range'] = prev_data['max_temp'] - prev_data['min_temp']

    # lag1 피처: 전날 값을 오늘 행에 붙임
    today_data['precip_lag1'] = prev_data['precip']
    today_data['avg_wind_lag1'] = prev_data['avg_wind']
    today_data['avg_humid_lag1'] = prev_data['avg_humid']
    today_data['avg_pres_sea_lag1'] = prev_data['avg_pres_sea']
    today_data['avg_cloud_lag1'] = prev_data['avg_cloud']
    today_data['dewpoint_depression_lag1'] = prev_data['dewpoint_depression']
    today_data['temp_range_lag1'] = prev_data['temp_range']

    # 변화량 피처: 오늘 - 전날
    today_data['temp_change'] = round(today_data['avg_temp'] - prev_data['avg_temp'], 2)
    today_data['pres_change'] = round(today_data['avg_pres_sea'] - prev_data['avg_pres_sea'], 2)
    today_data['wind_change'] = round(today_data['avg_wind'] - prev_data['avg_wind'], 2)
    today_data['date'] = latest['tm']

    # 오늘 자체의 강수 발생 여부 (이진값)
    today_data['precip_today'] = 1 if today_data['precip'] > 0 else 0

    return today_data, valid_items


def compute_rolling_features(items):
    """
    최근 관측치 리스트로부터 rolling(이동 통계) 피처 계산.
    - 습도/기압은 3일/5일 평균
    - 강수량은 3일/7일 합계
    - avg_humid, avg_pres_sea가 결측인 행은 제거 후 계산 (rolling 평균 왜곡 방지)
    - tail(n)으로 '가장 최근 n일'만 사용
    """
    df = pd.DataFrame([{
        'date': item['tm'],
        'avg_humid': float(item['avgRhm']) if item.get('avgRhm', '') not in ('', None) else None,
        'avg_pres_sea': float(item['avgPa']) if item.get('avgPa', '') not in ('', None) else None,
        'precip': float(item['sumRn']) if item.get('sumRn', '') not in ('', None) else 0.0,
    } for item in items])
    df = df.dropna(subset=['avg_humid', 'avg_pres_sea'])
    df = df.sort_values('date').reset_index(drop=True)

    return {
        'humid_rolling_3d_mean': df['avg_humid'].tail(3).mean(),
        'pres_rolling_3d_mean': df['avg_pres_sea'].tail(3).mean(),
        'precip_rolling_3d_sum': df['precip'].tail(3).sum(),
        'precip_rolling_7d_sum': df['precip'].tail(7).sum(),
        'humid_rolling_5d_mean': df['avg_humid'].tail(5).mean(),
        'pres_rolling_5d_mean': df['avg_pres_sea'].tail(5).mean(),
    }


def compute_month_encoding(date_str):
    """
    날짜의 '월'을 계절 순환성이 반영되도록 sin/cos로 인코딩.
    (12월과 1월이 실제로는 가깝다는 것을 모델이 인식하도록 하는 순환 인코딩)
    """
    month = datetime.strptime(date_str, "%Y-%m-%d").month
    return {
        'month_sin': np.sin(2 * np.pi * month / 12),
        'month_cos': np.cos(2 * np.pi * month / 12),
    }


def compute_pres_acceleration(valid_items):
    """
    기압의 '변화의 변화' (2차 차분) 계산.
    - 최근 3일치 기압(p1, p2, p3)을 이용해 (오늘 변화량) - (전날 변화량)을 구함
    - 기압이 얼마나 급격히 꺾이는지(가속/감속)를 나타내는 피처
    - 데이터가 3일 미만이면 계산 불가하므로 0.0 반환
    """
    if len(valid_items) < 3:
        return 0.0
    sorted_items = sorted(valid_items, key=lambda x: x['tm'])
    p1 = float(sorted_items[-3].get('avgPa', 0) or 0)
    p2 = float(sorted_items[-2].get('avgPa', 0) or 0)
    p3 = float(sorted_items[-1].get('avgPa', 0) or 0)
    change_today = p3 - p2
    change_prev = p2 - p1
    return round(change_today - change_prev, 2)


def compute_interaction_features(features, valid_items):
    """
    변수 간 상호작용 피처 추가.
    - humid_pres_interaction: 습도가 높고 기압이 표준(1013hPa)보다 낮을수록 커지는 값
      (저기압 + 고습 조합이 강수와 관련 있다는 도메인 지식을 반영)
    - pres_acceleration: 위 compute_pres_acceleration 결과 추가
    """
    features['humid_pres_interaction'] = features['avg_humid'] * (1013 - features['avg_pres_sea'])
    features['pres_acceleration'] = compute_pres_acceleration(valid_items)
    return features


CACHE_FILE = "last_prediction_cache.json"


def save_cache(data):
    """마지막 성공한 예측 결과를 파일로 저장"""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_cache():
    """저장된 마지막 예측 결과 불러오기"""
    if not os.path.exists(CACHE_FILE):
        return None
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    


@app.get("/")
def read_root():
    """헬스체크용 루트 엔드포인트"""
    return {"message": "강수 예측 API"}


@app.get("/test-asos")
def test_asos():
    """
    디버깅용 엔드포인트.
    실제 예측 없이, 피처 생성 파이프라인만 실행해서 결과를 그대로 반환.
    (API 응답 파싱이나 피처 계산이 제대로 되는지 확인할 때 사용)
    """
    data = fetch_asos_range(days_back=16)
    features, valid_items = parse_asos_with_lag(data)
    features.update(compute_rolling_features(valid_items))
    features.update(compute_month_encoding(features['date']))
    features = compute_interaction_features(features, valid_items)
    return features


def get_weather_label(proba):
    if proba < 0.25:
        return "안 온다!"
    elif proba < 0.5:
        return "안 올 듯!"
    elif proba < 0.75:
        return "올 듯!"
    else:
        return "온다!"


@app.get("/predict/today")
def predict_today():
    try:
        asos_raw = fetch_asos_range(days_back=16)
        features, valid_items = parse_asos_with_lag(asos_raw)

        features.update(compute_rolling_features(valid_items))
        features.update(compute_month_encoding(features['date']))
        features = compute_interaction_features(features, valid_items)

        input_df = pd.DataFrame([features])[FEATURE_COLS]
        input_scaled = scaler.transform(input_df)

        proba_logreg = model_logreg.predict_proba(input_scaled)[:, 1][0]
        proba_mlp = model_mlp.predict_proba(input_scaled)[:, 1][0]

        proba_ensemble = proba_logreg * 0.7 + proba_mlp * 0.3

        base_date = datetime.strptime(features['date'], "%Y-%m-%d")
        target_date = (base_date + timedelta(days=1)).strftime("%Y-%m-%d")

        result = {
            "기준_관측일": features['date'],
            "예측_대상일": target_date,
            "강수확률(%)": round(float(proba_ensemble) * 100, 1),
            "예측": get_weather_label(proba_ensemble),
            "모델별_확률": {
                "LogisticRegression(%)": round(float(proba_logreg) * 100, 1),
                "MLP(%)": round(float(proba_mlp) * 100, 1),
            },
            "오프라인_모드": False
        }

        save_cache(result)  # 성공하면 캐시 저장
        return result

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RequestException):
        # 기상청 API 연결 실패 → 캐시 사용
        cached = load_cache()
        if cached is not None:
            cached["오프라인_모드"] = True
            return cached
        else:
            return {"error": "인터넷 연결이 안 되고, 저장된 캐시도 없습니다."}
