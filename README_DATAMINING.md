데이터 마이닝 프로젝트 — 서울 강수 예측 모델링

본 문서는 CRISP-DM(Cross-Industry Standard Process for Data Mining) 방법론에 따라
서울의 다음 날 강수 발생 여부 예측 모델을 개발한 과정을 정리합니다.


1. 비즈니스 이해 (Business Understanding)

목표: 서울 지역의 다음날 강수 발생 여부(precip_occur, 0.1mm 이상 기준)를 예측하는 이진 분류 모델 개발

2. 데이터 이해 (Data Understanding)


출처: 기상청(KMA) ASOS 서울 지점(108) 일별 관측 데이터
기간: 2016-07-01 ~ 2026-07-07
탐색한 외부 데이터

NOAA 기후 지수: Niño3.4, AO index, SST 계열(북태평양/북대서양/인도양)
NSIDC 해빙 데이터
→ 탐색 결과, 최종 모델에서는 ASOS 관측 데이터만으로 충분한 예측력이 확인되어 제외



EDA

precip_occur 그룹별 boxplot으로 피처 분포 비교
상관관계 히트맵으로 다중공선성 확인
월별 강수율 바 차트로 계절성 확인 → month_sin/cos 인코딩 근거 확보
lag-1 자기상관 분석





3. 데이터 준비 (Data Preparation)


Point-in-time 원칙: 예측 시점에 실제로 확보 가능한 정보만 사용
(merge_asof, direction='backward')
결측치 처리: 변수별로 ffill vs 동월 평균(climatology) 방식을 실증 비교 후 개별 적용
피처 엔지니어링

lag1 피처: 전날 값 (precip, avg_wind, avg_humid, avg_pres_sea, avg_cloud,
dewpoint_depression, temp_range 등)
변화율 피처: temp_change, pres_change, wind_change
파생 피처: dewpoint_depression(이슬점차), temp_range(일교차)
rolling 피처: 3일/7일 이동 평균·합계 (습도, 기압, 강수량)
계절 순환 인코딩: month_sin, month_cos
상호작용 피처: humid_pres_interaction(습도-기압 상호작용), pres_acceleration(기압 2차 차분)



데이터 분할: 시계열 특성을 고려해 랜덤 셔플 대신 시간 순 train/test 분할,
walk-forward validation 적용


4. 데이터 모델링 (Modeling)


탐색한 모델: Logistic Regression, Random Forest, XGBoost, MLP
하이퍼파라미터 튜닝: Optuna 기반 자동 탐색 (TPESampler)
모델별 특이사항

XGBoost: 경미한 과적합 확인, learning curve 분석으로 검증
MLP: 14일 관련 피처를 제거한 버전이 최종 채택됨



최종 모델: Logistic Regression + MLP 가중 앙상블 (0.7 : 0.3)


5. 평가 (Evaluation)


평가지표: log_loss, F1-score, AUC, accuracy
검증 방식: walk-forward validation으로 시계열 특성을 반영한 평가 수행
개별 모델 대비 앙상블 조합이 더 안정적인 성능을 보여 최종 채택


참고: 학습/실험 노트북

T+n강수여부예측.ipynb에 데이터 수집부터 EDA, 피처 엔지니어링, 모델 튜닝,
최종 모델 저장까지의 전체 과정이 담겨 있습니다.