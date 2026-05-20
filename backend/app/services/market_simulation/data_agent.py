"""
데이터 에이전트
토론에서 데이터 요청을 추출하고 통합 조회하여 제공

지원 데이터 소스:
- FRED: 매크로 데이터 (금리, CPI, 실업률 등)
- LSEG: 시장 데이터 (가격, 수급, 재무)
- FactorDB: 팩터 스코어 (밸류, 모멘텀, 퀄리티 등)
- OECD: 경제지표
- NewsDB: 뉴스 및 센티먼트
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from openai import OpenAI

from ...config import Config
from ...utils.logger import get_logger

logger = get_logger('mirofish.market_simulation.data_agent')


def get_llm_client() -> OpenAI:
    """Config 기반 LLM 클라이언트 생성"""
    return OpenAI(
        api_key=Config.LLM_API_KEY,
        base_url=Config.LLM_BASE_URL,
    )


class DataSource(str, Enum):
    """데이터 소스 유형"""
    FRED = "fred"
    LSEG = "lseg"
    FACTOR_DB = "factor_db"
    OECD = "oecd"
    NEWS_DB = "news_db"


@dataclass
class DataRequest:
    """데이터 요청"""
    source: DataSource
    query_type: str  # "time_series", "snapshot", "comparison", "search"
    parameters: Dict[str, Any]
    requested_by: Optional[str] = None  # 요청한 에이전트 ID
    priority: int = 1  # 1: 높음, 2: 중간, 3: 낮음


@dataclass
class DataResponse:
    """데이터 응답"""
    request: DataRequest
    success: bool
    data: Any = None
    summary: str = ""  # LLM이 읽기 쉬운 요약
    error: Optional[str] = None


@dataclass
class DataPackage:
    """토론에 제공할 통합 데이터 패키지"""
    requests: List[DataRequest]
    responses: List[DataResponse]
    summary: str  # 전체 데이터 요약
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_context_string(self) -> str:
        """토론 컨텍스트에 삽입할 문자열 생성"""
        parts = ["[데이터 에이전트 제공 정보]", ""]

        for resp in self.responses:
            if resp.success:
                parts.append(f"## {resp.request.source.value.upper()} 데이터")
                parts.append(resp.summary)
                parts.append("")

        if not any(r.success for r in self.responses):
            parts.append("요청된 데이터를 가져오지 못했습니다.")

        return "\n".join(parts)


class DataAgent:
    """
    데이터 에이전트
    토론에서 데이터 요청을 추출하고 통합 조회
    """

    def __init__(self, llm_client: Optional[OpenAI] = None):
        """
        Args:
            llm_client: OpenAI 클라이언트 (요청 추출용)
        """
        self.llm_client = llm_client or get_llm_client()
        self.model_name = Config.LLM_MODEL_NAME

        # 데이터 소스 클라이언트들 (실제 구현 시 연결)
        self.data_clients: Dict[DataSource, Any] = {}

    def extract_data_requests(self, discussion_text: str) -> List[DataRequest]:
        """
        토론 텍스트에서 데이터 요청 추출

        Args:
            discussion_text: 에이전트들의 토론 내용

        Returns:
            추출된 데이터 요청 목록
        """
        extraction_prompt = """다음 투자 토론 내용에서 데이터 요청을 추출해주세요.

토론 내용:
{discussion}

다음 형식의 JSON 배열로 응답해주세요:
```json
[
  {{
    "source": "fred|lseg|factor_db|oecd|news_db",
    "query_type": "time_series|snapshot|comparison|search",
    "parameters": {{
      "series": "시리즈명 또는 종목코드",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "keywords": ["키워드1", "키워드2"],
      ...
    }},
    "description": "요청 설명"
  }}
]
```

데이터 소스 가이드:
- fred: 금리, CPI, 실업률, GDP 등 매크로 데이터
- lseg: 주가, 수급, 재무제표, 밸류에이션
- factor_db: 팩터 스코어 (밸류, 모멘텀, 퀄리티, 배당 등)
- oecd: 국가별 경제지표
- news_db: 뉴스 검색 및 센티먼트

명시적으로 데이터를 요청하는 부분만 추출하세요.
"~가 어땠지?", "~를 확인해보자", "~데이터가 필요해" 등의 표현을 찾으세요.
요청이 없으면 빈 배열 []을 반환하세요."""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 투자 토론에서 데이터 요청을 추출하는 분석가입니다. JSON 형식으로만 응답하세요."
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt.format(discussion=discussion_text)
                    }
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content

            # JSON 추출
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                requests_data = json.loads(json_match.group())
            else:
                requests_data = []

            # DataRequest 객체로 변환
            requests = []
            for req_data in requests_data:
                try:
                    source = DataSource(req_data.get("source", "lseg"))
                    requests.append(DataRequest(
                        source=source,
                        query_type=req_data.get("query_type", "snapshot"),
                        parameters=req_data.get("parameters", {}),
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"데이터 요청 파싱 실패: {e}")
                    continue

            return requests

        except Exception as e:
            logger.error(f"데이터 요청 추출 실패: {e}")
            return []

    def deduplicate_requests(self, requests: List[DataRequest]) -> List[DataRequest]:
        """중복 요청 제거"""
        seen = set()
        unique = []

        for req in requests:
            key = (req.source, req.query_type, json.dumps(req.parameters, sort_keys=True))
            if key not in seen:
                seen.add(key)
                unique.append(req)

        return unique

    def fetch_data(self, request: DataRequest) -> DataResponse:
        """
        단일 데이터 요청 처리

        실제 구현 시 각 데이터 소스 API 연동 필요
        """
        try:
            # TODO: 실제 데이터 소스 연동
            # 현재는 mock 데이터 반환

            if request.source == DataSource.FRED:
                return self._fetch_fred_mock(request)
            elif request.source == DataSource.LSEG:
                return self._fetch_lseg_mock(request)
            elif request.source == DataSource.FACTOR_DB:
                return self._fetch_factor_mock(request)
            elif request.source == DataSource.OECD:
                return self._fetch_oecd_mock(request)
            elif request.source == DataSource.NEWS_DB:
                return self._fetch_news_mock(request)
            else:
                return DataResponse(
                    request=request,
                    success=False,
                    error=f"지원하지 않는 데이터 소스: {request.source}"
                )

        except Exception as e:
            logger.error(f"데이터 조회 실패: {e}")
            return DataResponse(
                request=request,
                success=False,
                error=str(e)
            )

    def process_discussion(self, discussion_text: str) -> DataPackage:
        """
        토론 내용을 분석하여 필요한 데이터를 수집하고 패키지로 제공

        Args:
            discussion_text: 에이전트들의 토론 내용

        Returns:
            통합 데이터 패키지
        """
        # 1. 데이터 요청 추출
        requests = self.extract_data_requests(discussion_text)
        logger.info(f"추출된 데이터 요청: {len(requests)}건")

        # 2. 중복 제거
        requests = self.deduplicate_requests(requests)
        logger.info(f"중복 제거 후: {len(requests)}건")

        # 3. 데이터 조회
        responses = [self.fetch_data(req) for req in requests]

        # 4. 전체 요약 생성
        summary = self._generate_summary(responses)

        return DataPackage(
            requests=requests,
            responses=responses,
            summary=summary,
        )

    def _generate_summary(self, responses: List[DataResponse]) -> str:
        """전체 데이터 요약 생성"""
        successful = [r for r in responses if r.success]

        if not successful:
            return "요청된 데이터가 없거나 조회에 실패했습니다."

        summaries = [r.summary for r in successful if r.summary]
        return "\n\n".join(summaries)

    # ============== Mock 데이터 함수들 (실제 구현 시 교체) ==============

    def _fetch_fred_mock(self, request: DataRequest) -> DataResponse:
        """FRED 데이터 Mock"""
        series = request.parameters.get("series", "FEDFUNDS")

        mock_data = {
            "FEDFUNDS": {
                "name": "연방기금금리",
                "latest": 5.25,
                "change_1m": 0.0,
                "change_3m": -0.25,
            },
            "CPIAUCSL": {
                "name": "소비자물가지수",
                "latest": 314.5,
                "yoy_change": 3.2,
            },
            "UNRATE": {
                "name": "실업률",
                "latest": 3.9,
                "change_1m": 0.1,
            },
        }

        data = mock_data.get(series, {"name": series, "latest": "N/A"})

        return DataResponse(
            request=request,
            success=True,
            data=data,
            summary=f"**{data['name']}**: 최근값 {data['latest']}"
        )

    def _fetch_lseg_mock(self, request: DataRequest) -> DataResponse:
        """LSEG 데이터 Mock"""
        symbol = request.parameters.get("symbol", "")

        mock_data = {
            "summary": f"시장 데이터 조회: {symbol or '전체 시장'}",
            "kospi": {"close": 2847.5, "change": 1.2},
            "sector_performance": {
                "반도체": 8.2,
                "금융": 3.1,
                "유틸리티": -1.2,
            }
        }

        summary_parts = [
            f"**KOSPI**: {mock_data['kospi']['close']:,.1f} ({mock_data['kospi']['change']:+.1f}%)",
            "**섹터 수익률 (1M)**:",
        ]
        for sector, ret in mock_data['sector_performance'].items():
            summary_parts.append(f"  - {sector}: {ret:+.1f}%")

        return DataResponse(
            request=request,
            success=True,
            data=mock_data,
            summary="\n".join(summary_parts)
        )

    def _fetch_factor_mock(self, request: DataRequest) -> DataResponse:
        """팩터 데이터 Mock"""
        mock_data = {
            "factor_returns_1m": {
                "momentum": 4.3,
                "value": 1.2,
                "quality": 2.8,
                "low_vol": 0.5,
            }
        }

        summary_parts = ["**팩터 수익률 (1M)**:"]
        for factor, ret in mock_data['factor_returns_1m'].items():
            summary_parts.append(f"  - {factor}: {ret:+.1f}%")

        return DataResponse(
            request=request,
            success=True,
            data=mock_data,
            summary="\n".join(summary_parts)
        )

    def _fetch_oecd_mock(self, request: DataRequest) -> DataResponse:
        """OECD 데이터 Mock"""
        indicator = request.parameters.get("indicator", "GDP")

        mock_data = {
            "indicator": indicator,
            "korea": 2.1,
            "us": 2.4,
            "eurozone": 0.8,
        }

        return DataResponse(
            request=request,
            success=True,
            data=mock_data,
            summary=f"**{indicator} 성장률**: 한국 {mock_data['korea']}%, 미국 {mock_data['us']}%, 유로존 {mock_data['eurozone']}%"
        )

    def _fetch_news_mock(self, request: DataRequest) -> DataResponse:
        """뉴스 데이터 Mock"""
        keywords = request.parameters.get("keywords", [])

        mock_data = {
            "keywords": keywords,
            "article_count": 42,
            "sentiment": "neutral",
            "sentiment_score": 0.12,
            "top_headlines": [
                "반도체 업황 개선 기대감 확산",
                "연준, 금리 동결 시사",
            ]
        }

        summary_parts = [
            f"**뉴스 검색**: {', '.join(keywords) if keywords else '전체'}",
            f"  - 기사 수: {mock_data['article_count']}건",
            f"  - 센티먼트: {mock_data['sentiment']} ({mock_data['sentiment_score']:+.2f})",
            "  - 주요 헤드라인:",
        ]
        for headline in mock_data['top_headlines']:
            summary_parts.append(f"    · {headline}")

        return DataResponse(
            request=request,
            success=True,
            data=mock_data,
            summary="\n".join(summary_parts)
        )
