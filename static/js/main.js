window.addEventListener('load', () => {
    setTimeout(() => document.getElementById('bubble1').classList.add('show'), 500);
    setTimeout(() => document.getElementById('bubble2').classList.add('show'), 1400);
    setTimeout(() => {
        document.getElementById('chatIntro').classList.add('hide');
        document.getElementById('mainContent').classList.add('show');
    }, 2400);
});

const placesByArea = {
    "강남": {
        certain_no: ["반포한강공원", "양재천", "도산공원"],
        maybe_no: ["코엑스몰 야외광장", "신사동 가로수길", "강남역 먹자골목", "압구정 로데오거리"],
        maybe_yes: ["일상비일상의틈byU+", "강남역 지하상가", "고속터미널 파미에스테이션", "코엑스몰"],
        certain_yes: ["메가박스 강남", "코엑스몰", "별마당 도서관"]
    },
    "홍대": {
        certain_no: ["경의선숲길", "홍대걷고싶은거리", "망원한강공원", "하늘공원"],
        maybe_no: ["홍대걷고싶은거리", "연남동 카페거리", "상수동 카페거리", "책거리"],
        maybe_yes: ["연남동 카페거리", "AK플라자 홍대점", "KT&G 상상마당 홍대", "카카오프렌즈 홍대 플래그십 스토어", "T팩토리"],
        certain_yes: ["AK플라자 홍대", "CGV 홍대", "홍대 메가박스"]
    },
    "종로": {
        certain_no: ["청계천", "북촌한옥마을", "창덕궁"],
        maybe_no: ["익선동한옥거리", "인사동 쌈지길", "서촌 마을", "삼청동길"],
        maybe_yes: ["익선동한옥거리", "인사동 쌈지길", "서촌 마을"],
        certain_yes: ["교보문고 광화문점", "영풍문고 종로점", "안녕인사동", "종로타워"]
    },
    "이태원": {
        certain_no: ["경리단길", "남산공원", "N서울타워", "이태원 앤틱가구거리"],
        maybe_no: ["이태원 앤틱가구거리", "우사단로", "경리단길", "해방촌 신흥시장", "이태원 세계음식거리"],
        maybe_yes: ["이태원 앤틱가구거리", "한남동 리움미술관", "현대카드 스토리지", "용산공예관", "사운즈한남"],
        certain_yes: ["한남동 리움미술관", "디뮤지엄", "이태원 몬드리안 호텔"]
    },
    "잠실": {
        certain_no: ["석촌호수", "잠실한강공원", "올림픽공원 나홀로나무", "석촌고분군"],
        maybe_no: ["석촌호수", "송리단길", "방이동 먹자골목"],
        maybe_yes: ["서울리즘", "잠실 롯데백화점", "롯데월드 어드벤처"],
        certain_yes: ["롯데월드몰", "롯데월드타워 서울스카이", "롯데시네마 월드타워", "롯데월드 아쿠아리움"]
    }
};

function getPlaceCategory(prediction) {
    if (prediction === "온다!") return "certain_yes";
    if (prediction === "올 듯!") return "maybe_yes";
    if (prediction === "안 올 듯!") return "maybe_no";
    return "certain_no";
}

function getPlaceTypeLabel(prediction) {
    if (prediction === "온다!") return "무조건 안";
    if (prediction === "올 듯!") return "혹시 모르니까 안";
    if (prediction === "안 올 듯!") return "그래도 밖";
    return "무조건 밖";
}

function clearRain() {
    document.querySelectorAll('.raindrop').forEach(el => el.remove());
}

function startRain() {
    clearRain();
    for (let i = 0; i < 60; i++) {
        const drop = document.createElement('div');
        drop.className = 'raindrop';
        drop.style.left = Math.random() * 100 + 'vw';
        drop.style.top = (Math.random() * -150) + 'px';
        drop.style.animationDuration = (0.5 + Math.random() * 0.5) + 's';
        document.body.appendChild(drop);
    }
}

function setWeatherBackground(isRainy) {
    document.body.classList.remove('rainy', 'sunny');
    clearRain();
    if (isRainy) {
        document.body.classList.add('rainy');
        startRain();
    } else {
        document.body.classList.add('sunny');
    }
}

async function getPrediction() {
    const resultDiv = document.getElementById('result');
    const area = document.getElementById('areaSelect').value;
    resultDiv.innerHTML = '<p class="placeholder">비가 올까나~ 안 올까나~</p>';

    try {
        const response = await fetch('/predict/today');
        const data = await response.json();

        const isRainy = data.예측 === "온다!" || data.예측 === "올 듯!";
        setWeatherBackground(isRainy);

        const category = getPlaceCategory(data.예측);
        const places = placesByArea[area][category];
        const placeType = getPlaceTypeLabel(data.예측);

        const placeLinks = places.map(p => {
            const encoded = encodeURIComponent(p);
            return `<li><a href="https://map.kakao.com/?q=${encoded}" target="_blank">${p}</a></li>`;
        }).join('');

        resultDiv.innerHTML = `
            <div class="date-info">${data.예측_대상일} 예측 (${area})</div>
            <div class="probability">${data["강수확률(%)"]}%</div>
            <div class="prediction">${data.예측}</div>
            <div class="places">
                <h3>${placeType}에서 놀자!</h3>
                <ul>${placeLinks}</ul>
            </div>
        `;

        document.getElementById('predictBtn').textContent = "아 여기 말고~";
    } catch (error) {
        resultDiv.innerHTML = '<p class="placeholder">앗! 오류가 발생했습니다</p>';
    }
}
