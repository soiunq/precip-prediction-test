# 어디서 놀까나 — 서울 강수 예측 서비스

서울 지역의 다음날 강수 발생 확률을 예측하고,
예측 결과에 맞는 지역별 실내/실외 장소를 추천하는 웹 서비스입니다.

## 프로젝트 개요

- **문제**: "내일 어디서 놀지 정하기 애매한" 상황을 해결하기 위해, 다음날 강수 확률을 예측하고
  그 결과에 맞춰 지역별(강남/홍대/종로/이태원/잠실) 실내·실외 장소를 자동 추천
- **핵심 기능**
  - 오늘 기준 다음날 강수 확률 예측
  - 강수 확률 구간(안 온다 / 안 올 듯 / 올 듯 / 온다)에 따라 실내외 비중을 다르게 추천
  - 지역 선택 시 카카오맵 링크로 바로 연결되는 장소 리스트 제공

## 디렉토리 구조

```
├── static/               # 프론트엔드 (HTML/CSS/JS)
│   ├── index.html
│   ├── css/style.css
│   └── js/main.js
├── models/                # 학습 완료 모델 (joblib)
│   ├── logreg_20260715.joblib
│   ├── mlp_20260715.joblib
│   └── scaler_20260715.joblib
├── data/                  # 원본 학습 데이터
├── main.py                # FastAPI 백엔드 서버
├── T+n강수여부예측.ipynb   # 모델 학습/실험 노트북
├── requirements.txt       # 파이썬 의존성 명세
├── Dockerfile
├── .dockerignore
├── .gitignore
└── .env                   # 기상청 API 서비스키 (미포함, 직접 생성 필요)
```

## 기술 스택

- **Backend**: FastAPI, Uvicorn
- **ML**: scikit-learn, Optuna(하이퍼파라미터 튜닝)
- **Data**: pandas, numpy
- **Frontend**: HTML/CSS/JS (Vanilla)
- **Infra**: Docker
- **형상관리**: Git, GitLab

## 실행 방법

### 1. 환경 변수 설정

프로젝트 루트에 `.env` 파일 생성:

```
SERVICE_KEY=발급받은_기상청_API_인증키
```

### 2. 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
fastapi dev main.py
```

### 3. Docker 실행

```bash
docker build -t precip-prediction .
docker run -p 8000:8000 --env-file .env --name precip-app precip-prediction
```

실행 후 `http://localhost:8000/static/index.html` 접속.

## API 엔드포인트

| 엔드포인트 | 설명 |
|---|---|
| `GET /` | 헬스체크 |
| `GET /predict/today` | 오늘 기준 다음날 강수 예측 |
| `GET /test-asos` | 피처 생성 파이프라인 디버깅용 |

## 서비스 동작 흐름

```
사용자가 지역 선택 + 확인하기 클릭
    ↓
프론트엔드가 /predict/today 호출
    ↓
백엔드가 기상청 API에서 최근 관측치 수집 → 피처 생성 → 모델 예측
    ↓
강수확률 + 예측 라벨 반환
    ↓
프론트엔드가 확률 구간에 맞는 지역별 장소 리스트 표시
   (배경도 맑음/비 애니메이션으로 전환)
```

## 모델링 요약

Logistic Regression과 MLP를 0.7 : 0.3 비율로 가중 앙상블한 모델을 사용합니다.
데이터 분석 및 모델 개발 과정에 대한 상세 내용은 별도 데이터 마이닝 README를 참고하세요.
## 실험용 브랜치 테스트
