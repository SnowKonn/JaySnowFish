# Market Simulation TODO

## 현재 상태 (2024-05-20)

### 완료된 것
- [x] 10개 에이전트 아키타입 정의 (`market_agents.py`)
- [x] 토론 엔진 구현 (`discussion_engine.py`)
- [x] 데이터 에이전트 구현 - Mock 데이터 (`data_agent.py`)
- [x] 시나리오 생성기 구현 (`scenario_generator.py`)
- [x] REST API 엔드포인트 (`/api/market/*`)
- [x] 프론트엔드 UI (`MarketSimulationView.vue`)
- [x] Config 기반 LLM 클라이언트 (Gemini/Qwen/OpenAI 호환)

### 미완료 - 우선순위 높음

#### 1. LLM 연결 검증
- [ ] `.env` 설정 후 실제 LLM 호출 테스트
- [ ] 에러 핸들링 개선 (API 키 없음, rate limit 등)
- [ ] 응답 파싱 안정화

```bash
# 테스트 방법
curl -X POST http://localhost:5001/api/market/simulate \
  -H "Content-Type: application/json" \
  -d '{"context": "연준이 금리를 동결했다."}'
```

#### 2. 실제 데이터 소스 연동
현재 `data_agent.py`의 Mock 함수들을 실제 API로 교체 필요

| 소스 | 현재 | 목표 | 난이도 |
|------|------|------|--------|
| FRED | Mock | `fredapi` 패키지 | 쉬움 |
| 시장 데이터 | Mock | `yfinance` / LSEG API | 중간 |
| 팩터 데이터 | Mock | 자체 DB or FactSet | 어려움 |
| 뉴스 | Mock | NewsAPI / 자체 크롤링 | 중간 |
| OECD | Mock | OECD Data API | 쉬움 |

```python
# 예시: FRED 실제 연동
from fredapi import Fred

def _fetch_fred_real(self, request: DataRequest) -> DataResponse:
    fred = Fred(api_key=Config.FRED_API_KEY)
    series = request.parameters.get("series", "FEDFUNDS")
    data = fred.get_series(series)
    # ... 처리
```

#### 3. 에이전트 Tool Use 구현
현재 에이전트는 텍스트만 생성. LLM Function Calling으로 도구 사용 가능하게.

```python
# 목표 구조
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_market_data",
            "description": "시장 데이터 조회",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "data_type": {"enum": ["price", "volume", "financials"]}
                }
            }
        }
    }
]

response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=tools,
    tool_choice="auto"
)
```

---

### 미완료 - 우선순위 중간

#### 4. 토론 품질 개선
- [ ] 시스템 프롬프트 튜닝 (더 구체적인 전망 유도)
- [ ] 에이전트 간 상호작용 강화 (반박/동조 메커니즘)
- [ ] 토론 수렴 조건 추가 (합의 도달 시 조기 종료)

#### 5. 시나리오 생성 개선
- [ ] 정량 전망값 생성 (현재는 정성적)
- [ ] 확률 분포 기반 시나리오 (몬테카를로?)
- [ ] 과거 유사 상황 참조 (ZEP 그래프 연동)

#### 6. 프론트엔드 추가 기능
- [ ] 실시간 스트리밍 (SSE로 토론 진행 실시간 표시)
- [ ] 에이전트 커스터마이징 UI
- [ ] 차트 인터랙션 (클릭 시 상세 보기)

---

### 미완료 - 우선순위 낮음

#### 7. 다양성/창발성 개선
- [ ] 에이전트 파라미터 동적 샘플링
- [ ] 자유 토론 라운드 (진행자가 충돌점 기반 추가 논쟁 유도)
- [ ] 에이전트별 누적 calibration 학습

#### 8. ZEP 연동
- [ ] 과거 시뮬레이션 결과 그래프 저장
- [ ] 유사 컨텍스트 검색
- [ ] 에이전트 예측 정확도 추적

#### 9. 테스트/문서화
- [ ] 단위 테스트 작성
- [ ] API 문서 (Swagger/OpenAPI)
- [ ] 사용자 가이드

---

## 환경 설정

### 필수 환경변수 (.env)
```env
# LLM (택1)
# Gemini
LLM_API_KEY=your_gemini_api_key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL_NAME=gemini-2.0-flash

# 또는 Qwen
LLM_API_KEY=your_dashscope_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# 또는 OpenAI
LLM_API_KEY=your_openai_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o

# ZEP (기존 MiroFish 기능용)
ZEP_API_KEY=your_zep_api_key

# 데이터 소스 (추후)
FRED_API_KEY=your_fred_api_key
NEWS_API_KEY=your_news_api_key
```

### 실행 방법
```bash
cd JaySnowFish
npm run dev
# http://localhost:3000/market 접속
```

---

## 파일 구조

```
backend/app/services/market_simulation/
├── __init__.py
├── market_agents.py      # 10개 에이전트 아키타입 정의
├── data_agent.py         # 데이터 수집 에이전트 (현재 Mock)
├── discussion_engine.py  # 토론 진행 엔진
└── scenario_generator.py # 시나리오/리포트 생성

backend/app/api/
└── market_simulation.py  # REST API 엔드포인트

frontend/src/
├── api/market.js                    # API 클라이언트
├── views/MarketSimulationView.vue   # 메인 UI
└── router/index.js                  # /market 라우트
```

---

## 참고 자료

- FCLAgent 논문: LLM for intent + rule-based execution
- Harvard 논문: Loss aversion, ATH anomaly
- 대신증권 수급 리포트: 시장 참여자 패턴
