# Market Simulation 개발 기록

## 프로젝트 개요

**목표**: MiroFish 플랫폼에 금융 시장 시뮬레이션 기능 추가  
**기간**: 2024-05-20  
**브랜치**: `claude/slack-session-ZJmAR`

### 핵심 아이디어
- 10명의 시장 참여자 에이전트가 토론을 통해 시장 전망 도출
- 오더북 없이 매크로 + 알파 관점에 집중
- 토론 후 데이터 에이전트가 필요한 데이터를 일괄 수집 (툴콜링 최소화)
- 각 에이전트의 시나리오와 정량적 전망을 리포트 형태로 출력

---

## 참고 자료

### 1. FCLAgent 논문
- **핵심**: LLM for intent (의도 파악) + rule-based execution (규칙 기반 실행)
- **적용**: 에이전트가 자연어로 데이터 요청 → 데이터 에이전트가 파싱하여 실행

### 2. Harvard 논문 (Loss Aversion & ATH Anomaly)
- **핵심**: 손실 회피 성향, 전고점(ATH) 기준 투자 행동
- **적용**: "손실회피형 투자자" 에이전트 아키타입 추가

### 3. 대신증권 수급 리포트
- **핵심**: 시장 참여자별 행동 패턴 (외국인, 기관, 개인 등)
- **적용**: 에이전트 아키타입 설계 시 참고

---

## 구현 내용

### 1. 에이전트 아키타입 (10종)

**파일**: `backend/app/services/market_simulation/market_agents.py`

| ID | 한글명 | 영문명 | 특성 |
|----|--------|--------|------|
| insider | 내부자/스마트머니 | Insider/Smart Money | 선행 정보 기반, 시장 전환점 포착 |
| momentum | 모멘텀 추종자 | Momentum Trader | 추세 추종, 상대강도 중시 |
| contrarian_retail | 역추세 개인 | Contrarian Retail | 저점 매수, 고점 매도 시도 |
| pension | 연기금/장기투자자 | Pension Fund | 장기 관점, 밸류에이션 중시 |
| etf_lp | ETF LP/패시브 | ETF LP/Passive | 지수 추종, 리밸런싱 기반 |
| long_short_hedge | 롱숏 헤지펀드 | Long-Short Hedge | 상대가치, 페어트레이딩 |
| fundamentalist | 펀더멘털 애널리스트 | Fundamentalist | 재무제표, 밸류에이션 분석 |
| noise_trader | 노이즈 트레이더 | Noise Trader | 뉴스/센티먼트 반응, 단기 |
| loss_averse | 손실회피형 투자자 | Loss Averse Investor | 손절 민감, ATH 기준 판단 |
| macro_strategist | 매크로 전략가 | Macro Strategist | 금리/환율/정책 분석 |

각 에이전트는 다음 속성 보유:
- `system_prompt_template`: LLM 시스템 프롬프트
- `behavior_traits`: 행동 특성 리스트
- `decision_factors`: 의사결정 요소
- `preferred_data_sources`: 선호 데이터 소스

### 2. 데이터 에이전트

**파일**: `backend/app/services/market_simulation/data_agent.py`

**역할**: 토론 텍스트에서 데이터 요청 추출 → 통합 조회 → 결과 패키징

**지원 데이터 소스** (현재 Mock):
- FRED: 매크로 데이터 (금리, CPI, 실업률)
- LSEG: 시장 데이터 (가격, 수급, 재무)
- FactorDB: 팩터 스코어
- OECD: 경제지표
- NewsDB: 뉴스/센티먼트

**주요 클래스**:
```python
@dataclass
class DataRequest:
    source: DataSource
    query_type: str  # time_series, snapshot, comparison, search
    parameters: Dict[str, Any]

@dataclass
class DataPackage:
    requests: List[DataRequest]
    responses: List[DataResponse]
    summary: str
```

### 3. 토론 엔진

**파일**: `backend/app/services/market_simulation/discussion_engine.py`

**토론 플로우**:
```
1. BRIEFING     → 현재 상황 브리핑 (컨텍스트 제공)
2. FIRST_ROUND  → 1차 토론 (각 에이전트 의견 + 데이터 요청)
3. DATA_COLLECTION → 데이터 에이전트가 필요 데이터 수집
4. SECOND_ROUND → 2차 토론 (데이터 기반 심화 논의)
5. CONCLUSION   → 최종 전망 및 전략 도출
```

**출력**:
- 라운드별 에이전트 발언 (`AgentStatement`)
- 의견 충돌 지점 (`conflict_points`)
- 합의 영역 (`consensus_areas`)
- 블라인드 스팟 (`blind_spots`)

### 4. 시나리오 생성기

**파일**: `backend/app/services/market_simulation/scenario_generator.py`

**생성 결과**:
```python
@dataclass
class SimulationResult:
    scenarios: ScenarioSet           # base/risk 시나리오
    quantitative_outlook: QuantitativeOutlook  # 자산/섹터/팩터 전망
    agent_scenarios: List[Dict]      # 에이전트별 시나리오
    consensus_areas: List[str]       # 합의점
    conflict_points: List[str]       # 충돌점
    blind_spots: List[str]           # 놓친 포인트
    report: str                      # 마크다운 리포트
```

**시나리오 구조**:
- Base Scenario: 확률 60%, 가장 가능성 높은 전개
- Risk Scenario: 확률 25%, 주의해야 할 리스크 시나리오

### 5. REST API

**파일**: `backend/app/api/market_simulation.py`

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/market/agents` | 에이전트 목록 조회 |
| POST | `/api/market/simulate` | 시뮬레이션 실행 |
| POST | `/api/market/simulate/report` | 리포트만 생성 |
| POST | `/api/market/discussion` | 토론만 실행 |

**요청 예시**:
```json
POST /api/market/simulate
{
  "context": "연준이 금리 동결을 시사했고, 반도체 업황 개선 기대감이 확산되고 있다.",
  "agent_ids": ["momentum", "macro_strategist", "fundamentalist"]
}
```

### 6. 프론트엔드 UI

**파일**: `frontend/src/views/MarketSimulationView.vue`

**기능**:
- 시장 상황 입력 (텍스트)
- 샘플 컨텍스트 버튼 (연준/반도체/중국/지정학)
- 에이전트 선택 (체크박스)
- 실시간 로딩 UX (에이전트별 상태 표시)
- 결과 탭: 시나리오 / 에이전트 뷰 / 분석 / 리포트
- D3.js 차트: 자산/섹터/팩터 전망, 신뢰도 분포
- 히스토리: 로컬스토리지 저장/불러오기
- Export: JSON 내보내기, 리포트 다운로드

**라우트**: `http://localhost:3000/market`

---

## 설정 변경

### LLM 클라이언트 통합

기존 하드코딩된 LLM 설정을 Config 기반으로 변경:

```python
# backend/app/config.py
class Config:
    LLM_API_KEY = os.getenv('LLM_API_KEY')
    LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', 'gpt-4o')
```

**지원 LLM**:
- OpenAI (GPT-4, GPT-4o)
- Google Gemini (via OpenAI 호환 API)
- Alibaba Qwen (via DashScope)
- 기타 OpenAI API 호환 서비스

### 환경변수 예시 (.env)

```env
# Gemini 사용 시
LLM_API_KEY=your_gemini_api_key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL_NAME=gemini-2.0-flash

# Qwen 사용 시
LLM_API_KEY=your_dashscope_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
```

---

## 파일 구조

```
JaySnowFish/
├── backend/
│   └── app/
│       ├── api/
│       │   ├── __init__.py          # market_bp 등록
│       │   └── market_simulation.py # REST API 엔드포인트
│       ├── services/
│       │   └── market_simulation/
│       │       ├── __init__.py
│       │       ├── market_agents.py      # 에이전트 아키타입
│       │       ├── data_agent.py         # 데이터 수집 (Mock)
│       │       ├── discussion_engine.py  # 토론 엔진
│       │       └── scenario_generator.py # 시나리오 생성
│       └── config.py                # LLM 설정 추가
├── frontend/
│   └── src/
│       ├── api/
│       │   └── market.js            # API 클라이언트
│       ├── views/
│       │   ├── Home.vue             # 네비게이션 링크 추가
│       │   └── MarketSimulationView.vue  # 메인 UI
│       ├── router/
│       │   └── index.js             # /market 라우트
│       └── package.json             # marked 의존성 추가
├── docs/
│   ├── MARKET_SIMULATION_TODO.md    # TODO 체크리스트
│   └── MARKET_SIMULATION_DEV_LOG.md # 이 파일
└── .env.example                     # LLM 설정 예시
```

---

## 커밋 히스토리

```
fdd3b9e docs: add Market Simulation TODO checklist
06e3dae feat: polish Market Simulation frontend with full features
cc3a26b feat: add Market Simulation frontend UI
6424759 refactor: use Config-based LLM client for model flexibility
cf836c0 chore: translate zep_graph_memory_updater.py to Korean
...
```

---

## 남은 작업

### 필수 (테스트 전 완료 필요)
1. **LLM 연결 검증** - `.env` 설정 후 실제 호출 테스트
2. **에러 핸들링** - API 키 오류, 타임아웃 등 처리

### 중요 (기능 완성도)
3. **실제 데이터 연동** - Mock → 실제 API (FRED, yfinance 등)
4. **에이전트 Tool Use** - LLM function calling 적용

### 개선 (품질 향상)
5. **프롬프트 튜닝** - 더 구체적인 전망 유도
6. **토론 메커니즘** - 반박/동조, 수렴 조건
7. **ZEP 연동** - 과거 시뮬레이션 학습

상세 내용은 `docs/MARKET_SIMULATION_TODO.md` 참조

---

## 실행 방법

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 LLM_API_KEY 등 설정

# 2. 의존성 설치
npm run setup:all

# 3. 실행
npm run dev

# 4. 접속
# http://localhost:3000/market
```

---

## 설계 결정 사항

### 왜 오더북을 제외했나?
- 타겟이 매크로 + 알파 관점
- 오더북 시뮬레이션은 복잡도 대비 인사이트 제한적
- 자산배분/섹터 로테이션에 더 집중

### 왜 토론 후 데이터 수집인가?
- 에이전트별 개별 API 호출 시 툴콜링 폭발
- 토론에서 필요 데이터 자연스럽게 도출
- 데이터 에이전트가 중복 제거 후 일괄 조회

### 왜 10개 아키타입인가?
- 실제 시장의 주요 참여자 유형 커버
- 다양한 관점 확보 (모멘텀 vs 역추세, 단기 vs 장기)
- 너무 많으면 토론 품질 저하, 적으면 다양성 부족

---

## 참고 링크

- MiroFish 원본: https://github.com/666ghj/MiroFish
- OASIS (시뮬레이션 엔진): https://github.com/camel-ai/oasis
- ZEP Cloud: https://app.getzep.com/
