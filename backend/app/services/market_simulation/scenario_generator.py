"""
시나리오 생성기
토론 결과를 기반으로 시나리오 및 리포트 생성

출력:
1. 정성적 시나리오 (베이스/리스크/블라인드스팟)
2. 정량적 시뮬레이션 (자산군/섹터/팩터별 전망)
3. 에이전트별 상세 전망 및 전략
4. 리포트용 포맷
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from openai import OpenAI

from ...config import Config
from ...utils.logger import get_logger
from .discussion_engine import DiscussionResult, DiscussionPhase

logger = get_logger('mirofish.market_simulation.scenario')


class OutlookLevel(str, Enum):
    """전망 수준"""
    VERY_POSITIVE = "▲▲"
    POSITIVE = "▲"
    NEUTRAL = "─"
    NEGATIVE = "▼"
    VERY_NEGATIVE = "▼▼"


@dataclass
class AssetOutlook:
    """자산군별 전망"""
    asset_class: str
    outlook: OutlookLevel
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    confidence: float = 0.5
    rationale: str = ""


@dataclass
class SectorOutlook:
    """섹터별 전망"""
    sector: str
    outlook: OutlookLevel
    positive_votes: int = 0
    neutral_votes: int = 0
    negative_votes: int = 0
    key_drivers: List[str] = field(default_factory=list)


@dataclass
class FactorOutlook:
    """팩터별 전망"""
    factor: str
    rank: int
    outlook: OutlookLevel
    rationale: str = ""


@dataclass
class AgentScenario:
    """에이전트별 시나리오"""
    agent_id: str
    agent_name: str

    # 현황 인식
    situation_analysis: str

    # 전망
    outlook_short_term: str  # 1M
    outlook_medium_term: str  # 3M
    risks: List[str]

    # 대응 전략
    strategy: str
    specific_actions: List[str]

    # 모니터링
    monitoring_points: List[str]

    # 자산/섹터/팩터 전망
    asset_outlook: Dict[str, str]  # {"주식": "▲", "채권": "─", ...}
    sector_preference: List[str]  # ["반도체", "금융", ...]
    factor_preference: List[str]  # ["모멘텀", "퀄리티", ...]

    # 확신도
    confidence: float = 0.5


@dataclass
class Scenario:
    """시나리오"""
    name: str
    probability: float
    description: str
    implications: Dict[str, str]  # 자산군별 영향
    triggers: List[str]  # 트리거 이벤트


@dataclass
class SimulationResult:
    """시뮬레이션 최종 결과"""

    # 메타 정보
    generated_at: str
    context_summary: str
    total_agents: int
    discussion_duration: float

    # 정성적 시나리오
    base_scenario: Scenario
    risk_scenarios: List[Scenario]
    blind_spots: List[str]

    # 정량적 전망
    asset_outlooks: List[AssetOutlook]
    sector_outlooks: List[SectorOutlook]
    factor_outlooks: List[FactorOutlook]

    # 에이전트별 상세
    agent_scenarios: List[AgentScenario]

    # 분석
    conflict_points: List[str]
    consensus_areas: List[str]

    # 원본 토론 데이터
    discussion_result: Optional[DiscussionResult] = None

    def to_report_dict(self) -> Dict[str, Any]:
        """리포트용 딕셔너리 변환"""
        return {
            "meta": {
                "generated_at": self.generated_at,
                "context_summary": self.context_summary,
                "total_agents": self.total_agents,
                "discussion_duration": self.discussion_duration,
            },
            "scenarios": {
                "base": {
                    "name": self.base_scenario.name,
                    "probability": self.base_scenario.probability,
                    "description": self.base_scenario.description,
                },
                "risks": [
                    {
                        "name": s.name,
                        "probability": s.probability,
                        "description": s.description,
                    }
                    for s in self.risk_scenarios
                ],
                "blind_spots": self.blind_spots,
            },
            "outlook": {
                "assets": [
                    {
                        "asset": o.asset_class,
                        "outlook": o.outlook.value,
                        "range": f"{o.range_low}~{o.range_high}%" if o.range_low else None,
                        "confidence": o.confidence,
                    }
                    for o in self.asset_outlooks
                ],
                "sectors": [
                    {
                        "sector": o.sector,
                        "outlook": o.outlook.value,
                        "votes": f"+{o.positive_votes}/-{o.negative_votes}",
                    }
                    for o in self.sector_outlooks
                ],
                "factors": [
                    {"rank": o.rank, "factor": o.factor, "outlook": o.outlook.value}
                    for o in self.factor_outlooks
                ],
            },
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "agent_name": a.agent_name,
                    "outlook_short": a.outlook_short_term,
                    "outlook_medium": a.outlook_medium_term,
                    "strategy": a.strategy,
                    "confidence": a.confidence,
                }
                for a in self.agent_scenarios
            ],
            "analysis": {
                "conflicts": self.conflict_points,
                "consensus": self.consensus_areas,
            },
        }

    def to_report_markdown(self) -> str:
        """마크다운 리포트 생성"""
        lines = [
            f"# 시장 전망 시뮬레이션 리포트",
            f"",
            f"**생성일시**: {self.generated_at}",
            f"**참여 에이전트**: {self.total_agents}명",
            f"**토론 시간**: {self.discussion_duration:.1f}초",
            f"",
            f"## Executive Summary",
            f"",
            f"{self.context_summary}",
            f"",
            f"---",
            f"",
            f"## 시나리오 분석",
            f"",
            f"### 베이스 케이스 ({self.base_scenario.probability*100:.0f}%)",
            f"",
            f"{self.base_scenario.description}",
            f"",
            f"### 리스크 시나리오",
            f"",
        ]

        for scenario in self.risk_scenarios:
            lines.append(f"**{scenario.name}** ({scenario.probability*100:.0f}%)")
            lines.append(f"{scenario.description}")
            lines.append("")

        lines.extend([
            f"### 블라인드 스팟",
            f"",
        ])
        for blind_spot in self.blind_spots:
            lines.append(f"- {blind_spot}")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 정량적 전망",
            f"",
            f"### 자산군별",
            f"",
            f"| 자산군 | 전망 | 예상 범위 | 확신도 |",
            f"|--------|------|-----------|--------|",
        ])

        for outlook in self.asset_outlooks:
            range_str = f"{outlook.range_low:+.1f}~{outlook.range_high:+.1f}%" if outlook.range_low else "-"
            lines.append(f"| {outlook.asset_class} | {outlook.outlook.value} | {range_str} | {outlook.confidence:.0%} |")

        lines.extend([
            f"",
            f"### 섹터별",
            f"",
            f"| 섹터 | 전망 | 긍정/부정 |",
            f"|------|------|-----------|",
        ])

        for outlook in self.sector_outlooks:
            lines.append(f"| {outlook.sector} | {outlook.outlook.value} | {outlook.positive_votes}/{outlook.negative_votes} |")

        lines.extend([
            f"",
            f"### 팩터 선호도",
            f"",
        ])

        for outlook in self.factor_outlooks:
            lines.append(f"{outlook.rank}. {outlook.factor} {outlook.outlook.value}")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 에이전트별 상세 전망",
            f"",
        ])

        for agent in self.agent_scenarios:
            lines.extend([
                f"### {agent.agent_name}",
                f"",
                f"**현황 인식**: {agent.situation_analysis[:200]}...",
                f"",
                f"**전망**",
                f"- 단기(1M): {agent.outlook_short_term}",
                f"- 중기(3M): {agent.outlook_medium_term}",
                f"",
                f"**대응 전략**: {agent.strategy}",
                f"",
                f"**확신도**: {agent.confidence:.0%}",
                f"",
            ])

        lines.extend([
            f"---",
            f"",
            f"## 분석",
            f"",
            f"### 의견 충돌 지점",
            f"",
        ])
        for conflict in self.conflict_points:
            lines.append(f"- {conflict}")

        lines.extend([
            f"",
            f"### 합의 영역",
            f"",
        ])
        for consensus in self.consensus_areas:
            lines.append(f"- {consensus}")

        lines.extend([
            f"",
            f"---",
            f"",
            f"*이 리포트는 AI 에이전트 시뮬레이션을 기반으로 생성되었습니다.*",
            f"*투자 결정의 참고자료로만 활용하시기 바랍니다.*",
        ])

        return "\n".join(lines)


class ScenarioGenerator:
    """
    시나리오 생성기
    토론 결과를 기반으로 시나리오 및 리포트 생성
    """

    def __init__(self, llm_client: Optional[OpenAI] = None):
        self.llm_client = llm_client or OpenAI(api_key=Config.OPENAI_API_KEY)

    def generate(self, discussion_result: DiscussionResult) -> SimulationResult:
        """
        토론 결과로부터 시뮬레이션 결과 생성

        Args:
            discussion_result: 토론 결과

        Returns:
            시뮬레이션 결과
        """
        logger.info("시나리오 생성 시작")

        # 1. 에이전트별 시나리오 추출
        agent_scenarios = self._extract_agent_scenarios(discussion_result)

        # 2. 시나리오 생성
        base_scenario, risk_scenarios = self._generate_scenarios(discussion_result)

        # 3. 정량적 전망 집계
        asset_outlooks = self._aggregate_asset_outlooks(agent_scenarios)
        sector_outlooks = self._aggregate_sector_outlooks(agent_scenarios)
        factor_outlooks = self._aggregate_factor_outlooks(agent_scenarios)

        # 4. 컨텍스트 요약
        context_summary = self._summarize_context(discussion_result)

        return SimulationResult(
            generated_at=datetime.now().isoformat(),
            context_summary=context_summary,
            total_agents=len(agent_scenarios),
            discussion_duration=discussion_result.total_duration,
            base_scenario=base_scenario,
            risk_scenarios=risk_scenarios,
            blind_spots=discussion_result.blind_spots,
            asset_outlooks=asset_outlooks,
            sector_outlooks=sector_outlooks,
            factor_outlooks=factor_outlooks,
            agent_scenarios=agent_scenarios,
            conflict_points=discussion_result.conflict_points,
            consensus_areas=discussion_result.consensus_areas,
            discussion_result=discussion_result,
        )

    def _extract_agent_scenarios(self, discussion_result: DiscussionResult) -> List[AgentScenario]:
        """에이전트별 시나리오 추출"""
        scenarios = []

        for agent_data in discussion_result.agent_scenarios:
            # TODO: LLM으로 상세 파싱
            scenario = AgentScenario(
                agent_id=agent_data["agent_id"],
                agent_name=agent_data["agent_name"],
                situation_analysis=self._extract_section(agent_data["scenario"], "현황 인식", "전망"),
                outlook_short_term=self._extract_section(agent_data["scenario"], "단기", "중기"),
                outlook_medium_term=self._extract_section(agent_data["scenario"], "중기", "리스크"),
                risks=self._extract_list(agent_data["scenario"], "리스크"),
                strategy=self._extract_section(agent_data["scenario"], "대응 전략", "모니터링"),
                specific_actions=[],
                monitoring_points=self._extract_list(agent_data["scenario"], "모니터링"),
                asset_outlook=self._parse_asset_outlook(agent_data["scenario"]),
                sector_preference=[],
                factor_preference=[],
                confidence=agent_data.get("confidence", 0.5),
            )
            scenarios.append(scenario)

        return scenarios

    def _generate_scenarios(self, discussion_result: DiscussionResult) -> tuple:
        """베이스 및 리스크 시나리오 생성"""

        # 토론 요약
        discussion_summary = "\n".join([
            f"{s['agent_name']}: {s['scenario'][:300]}..."
            for s in discussion_result.agent_scenarios[:5]
        ])

        prompt = f"""다음 투자 토론 결과를 바탕으로 시나리오를 생성해주세요.

[토론 요약]
{discussion_summary}

[충돌 지점]
{', '.join(discussion_result.conflict_points)}

[합의 영역]
{', '.join(discussion_result.consensus_areas)}

다음 형식의 JSON으로 응답해주세요:
```json
{{
  "base_scenario": {{
    "name": "시나리오 이름",
    "probability": 0.6,
    "description": "상세 설명"
  }},
  "risk_scenarios": [
    {{
      "name": "리스크 시나리오 이름",
      "probability": 0.25,
      "description": "상세 설명"
    }}
  ]
}}
```"""

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 투자 전략가입니다. JSON 형식으로만 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )

            content = response.choices[0].message.content
            json_match = re.search(r'\{[\s\S]*\}', content)

            if json_match:
                data = json.loads(json_match.group())

                base = Scenario(
                    name=data["base_scenario"]["name"],
                    probability=data["base_scenario"]["probability"],
                    description=data["base_scenario"]["description"],
                    implications={},
                    triggers=[],
                )

                risks = [
                    Scenario(
                        name=r["name"],
                        probability=r["probability"],
                        description=r["description"],
                        implications={},
                        triggers=[],
                    )
                    for r in data.get("risk_scenarios", [])
                ]

                return base, risks

        except Exception as e:
            logger.error(f"시나리오 생성 실패: {e}")

        # 기본값
        return (
            Scenario("베이스 케이스", 0.6, "현재 추세 유지", {}, []),
            [Scenario("리스크 시나리오", 0.4, "시장 조정", {}, [])]
        )

    def _aggregate_asset_outlooks(self, agent_scenarios: List[AgentScenario]) -> List[AssetOutlook]:
        """자산군별 전망 집계"""
        assets = ["국내주식", "해외주식", "채권", "원자재", "현금"]
        outlooks = []

        for asset in assets:
            votes = {"positive": 0, "neutral": 0, "negative": 0}

            for agent in agent_scenarios:
                outlook_str = agent.asset_outlook.get(asset, "─")
                if "▲" in outlook_str:
                    votes["positive"] += 1
                elif "▼" in outlook_str:
                    votes["negative"] += 1
                else:
                    votes["neutral"] += 1

            # 다수결로 전망 결정
            total = sum(votes.values()) or 1
            if votes["positive"] > votes["negative"]:
                outlook = OutlookLevel.POSITIVE if votes["positive"] > total * 0.6 else OutlookLevel.NEUTRAL
            elif votes["negative"] > votes["positive"]:
                outlook = OutlookLevel.NEGATIVE if votes["negative"] > total * 0.6 else OutlookLevel.NEUTRAL
            else:
                outlook = OutlookLevel.NEUTRAL

            outlooks.append(AssetOutlook(
                asset_class=asset,
                outlook=outlook,
                range_low=-2.0 if outlook == OutlookLevel.NEGATIVE else 1.0,
                range_high=2.0 if outlook == OutlookLevel.NEGATIVE else 5.0,
                confidence=max(votes.values()) / total,
            ))

        return outlooks

    def _aggregate_sector_outlooks(self, agent_scenarios: List[AgentScenario]) -> List[SectorOutlook]:
        """섹터별 전망 집계"""
        sectors = ["반도체", "금융", "헬스케어", "에너지", "유틸리티", "소비재", "산업재"]
        outlooks = []

        for sector in sectors:
            # TODO: 실제 에이전트 의견에서 집계
            outlooks.append(SectorOutlook(
                sector=sector,
                outlook=OutlookLevel.NEUTRAL,
                positive_votes=4,
                neutral_votes=3,
                negative_votes=3,
            ))

        return outlooks

    def _aggregate_factor_outlooks(self, agent_scenarios: List[AgentScenario]) -> List[FactorOutlook]:
        """팩터별 전망 집계"""
        factors = [
            ("모멘텀", OutlookLevel.POSITIVE),
            ("퀄리티", OutlookLevel.POSITIVE),
            ("밸류", OutlookLevel.NEUTRAL),
            ("저변동성", OutlookLevel.NEUTRAL),
        ]

        return [
            FactorOutlook(factor=f, rank=i+1, outlook=o)
            for i, (f, o) in enumerate(factors)
        ]

    def _summarize_context(self, discussion_result: DiscussionResult) -> str:
        """컨텍스트 요약"""
        return discussion_result.context[:500] + "..." if len(discussion_result.context) > 500 else discussion_result.context

    def _extract_section(self, text: str, start_marker: str, end_marker: str) -> str:
        """텍스트에서 섹션 추출"""
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""

            end_idx = text.find(end_marker, start_idx + len(start_marker))
            if end_idx == -1:
                end_idx = min(start_idx + 500, len(text))

            return text[start_idx:end_idx].strip()
        except:
            return ""

    def _extract_list(self, text: str, marker: str) -> List[str]:
        """텍스트에서 리스트 추출"""
        items = []
        lines = text.split("\n")

        in_section = False
        for line in lines:
            if marker in line:
                in_section = True
                continue
            if in_section:
                if line.strip().startswith("-") or line.strip().startswith("•"):
                    items.append(line.strip().lstrip("-•").strip())
                elif line.strip() and not line.strip().startswith("*"):
                    break

        return items[:5]

    def _parse_asset_outlook(self, text: str) -> Dict[str, str]:
        """텍스트에서 자산 전망 파싱"""
        outlook = {}
        assets = ["주식", "채권", "원자재", "현금"]

        for asset in assets:
            if asset in text:
                if "▲▲" in text[text.find(asset):text.find(asset)+20]:
                    outlook[asset] = "▲▲"
                elif "▲" in text[text.find(asset):text.find(asset)+20]:
                    outlook[asset] = "▲"
                elif "▼▼" in text[text.find(asset):text.find(asset)+20]:
                    outlook[asset] = "▼▼"
                elif "▼" in text[text.find(asset):text.find(asset)+20]:
                    outlook[asset] = "▼"
                else:
                    outlook[asset] = "─"
            else:
                outlook[asset] = "─"

        return outlook
