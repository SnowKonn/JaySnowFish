"""
토론 엔진
에이전트들의 시장 전망 토론 진행

플로우:
1. 현재 상황 브리핑 (컨텍스트)
2. 1차 토론 (각 에이전트 의견 + 데이터 니즈)
3. 데이터 에이전트가 필요한 데이터 수집
4. 2차 토론 (데이터 기반 심화 논의)
5. 최종 전망 및 전략 도출
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from openai import OpenAI

from ...config import Config
from ...utils.logger import get_logger
from .market_agents import MarketAgentArchetype, MARKET_AGENT_ARCHETYPES, AGENT_BY_ID
from .data_agent import DataAgent, DataPackage

logger = get_logger('mirofish.market_simulation.discussion')


class DiscussionPhase(str, Enum):
    """토론 단계"""
    BRIEFING = "briefing"
    FIRST_ROUND = "first_round"
    DATA_COLLECTION = "data_collection"
    SECOND_ROUND = "second_round"
    CONCLUSION = "conclusion"


@dataclass
class AgentStatement:
    """에이전트 발언"""
    agent_id: str
    agent_name: str
    phase: DiscussionPhase
    content: str
    outlook: Optional[Dict[str, str]] = None  # 자산/섹터별 전망
    strategy: Optional[str] = None
    data_requests: Optional[List[str]] = None
    confidence: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DiscussionRound:
    """토론 라운드"""
    phase: DiscussionPhase
    statements: List[AgentStatement]
    data_package: Optional[DataPackage] = None
    summary: str = ""


@dataclass
class DiscussionResult:
    """토론 결과"""
    context: str
    rounds: List[DiscussionRound]
    agent_scenarios: List[Dict[str, Any]]  # 에이전트별 시나리오
    conflict_points: List[str]  # 의견 충돌 지점
    consensus_areas: List[str]  # 합의된 영역
    blind_spots: List[str]  # 놓치고 있는 포인트
    total_duration: float = 0.0


class DiscussionEngine:
    """
    토론 엔진
    에이전트들의 시장 전망 토론 진행
    """

    def __init__(
        self,
        llm_client: Optional[OpenAI] = None,
        agents: Optional[List[MarketAgentArchetype]] = None,
    ):
        """
        Args:
            llm_client: OpenAI 클라이언트
            agents: 참여 에이전트 목록 (기본: 전체 10개)
        """
        self.llm_client = llm_client or OpenAI(api_key=Config.OPENAI_API_KEY)
        self.agents = agents or MARKET_AGENT_ARCHETYPES
        self.data_agent = DataAgent(llm_client=self.llm_client)

    def run_discussion(
        self,
        context: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> DiscussionResult:
        """
        전체 토론 실행

        Args:
            context: 현재 시장 상황 및 컨텍스트 (길게 제공 가능)
            additional_data: 추가 데이터 (시세, 뉴스 등)

        Returns:
            토론 결과
        """
        start_time = datetime.now()
        rounds: List[DiscussionRound] = []

        logger.info(f"토론 시작: {len(self.agents)}명 에이전트 참여")

        # 1. 브리핑 단계
        briefing = self._create_briefing(context, additional_data)
        rounds.append(briefing)

        # 2. 1차 토론 (의견 + 데이터 요청)
        first_round = self._run_first_round(context, briefing)
        rounds.append(first_round)

        # 3. 데이터 수집
        discussion_text = self._compile_discussion_text(first_round)
        data_package = self.data_agent.process_discussion(discussion_text)

        data_round = DiscussionRound(
            phase=DiscussionPhase.DATA_COLLECTION,
            statements=[],
            data_package=data_package,
            summary=data_package.summary,
        )
        rounds.append(data_round)

        # 4. 2차 토론 (데이터 기반 심화)
        second_round = self._run_second_round(context, first_round, data_package)
        rounds.append(second_round)

        # 5. 결론 도출
        conclusion = self._run_conclusion(context, rounds)
        rounds.append(conclusion)

        # 6. 분석 (충돌점, 합의점, 블라인드스팟)
        agent_scenarios = self._extract_agent_scenarios(rounds)
        conflict_points = self._identify_conflicts(rounds)
        consensus_areas = self._identify_consensus(rounds)
        blind_spots = self._identify_blind_spots(rounds, context)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"토론 완료: {duration:.1f}초")

        return DiscussionResult(
            context=context,
            rounds=rounds,
            agent_scenarios=agent_scenarios,
            conflict_points=conflict_points,
            consensus_areas=consensus_areas,
            blind_spots=blind_spots,
            total_duration=duration,
        )

    def _create_briefing(
        self,
        context: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> DiscussionRound:
        """브리핑 생성"""
        briefing_content = f"""[시장 상황 브리핑]

{context}
"""
        if additional_data:
            briefing_content += f"\n[추가 데이터]\n{json.dumps(additional_data, ensure_ascii=False, indent=2)}"

        statement = AgentStatement(
            agent_id="moderator",
            agent_name="진행자",
            phase=DiscussionPhase.BRIEFING,
            content=briefing_content,
        )

        return DiscussionRound(
            phase=DiscussionPhase.BRIEFING,
            statements=[statement],
            summary="시장 상황 브리핑 완료",
        )

    def _run_first_round(
        self,
        context: str,
        briefing: DiscussionRound,
    ) -> DiscussionRound:
        """1차 토론 실행"""
        statements: List[AgentStatement] = []

        for agent in self.agents:
            statement = self._get_agent_statement(
                agent=agent,
                context=context,
                phase=DiscussionPhase.FIRST_ROUND,
                previous_statements=statements,
                instruction="현재 시장 상황에 대한 의견을 제시하고, 필요한 데이터가 있다면 요청해주세요.",
            )
            statements.append(statement)
            logger.debug(f"1차 발언: {agent.name_ko}")

        return DiscussionRound(
            phase=DiscussionPhase.FIRST_ROUND,
            statements=statements,
            summary=f"1차 토론 완료: {len(statements)}명 발언",
        )

    def _run_second_round(
        self,
        context: str,
        first_round: DiscussionRound,
        data_package: DataPackage,
    ) -> DiscussionRound:
        """2차 토론 실행 (데이터 기반)"""
        statements: List[AgentStatement] = []
        data_context = data_package.to_context_string()

        for agent in self.agents:
            statement = self._get_agent_statement(
                agent=agent,
                context=context,
                phase=DiscussionPhase.SECOND_ROUND,
                previous_statements=first_round.statements + statements,
                additional_context=data_context,
                instruction="제공된 데이터를 참고하여 전망을 구체화하고, 대응 전략을 제시해주세요.",
            )
            statements.append(statement)
            logger.debug(f"2차 발언: {agent.name_ko}")

        return DiscussionRound(
            phase=DiscussionPhase.SECOND_ROUND,
            statements=statements,
            summary=f"2차 토론 완료: {len(statements)}명 발언",
        )

    def _run_conclusion(
        self,
        context: str,
        rounds: List[DiscussionRound],
    ) -> DiscussionRound:
        """결론 라운드"""
        statements: List[AgentStatement] = []

        for agent in self.agents:
            statement = self._get_agent_conclusion(agent, context, rounds)
            statements.append(statement)
            logger.debug(f"결론: {agent.name_ko}")

        return DiscussionRound(
            phase=DiscussionPhase.CONCLUSION,
            statements=statements,
            summary="최종 결론 도출 완료",
        )

    def _get_agent_statement(
        self,
        agent: MarketAgentArchetype,
        context: str,
        phase: DiscussionPhase,
        previous_statements: List[AgentStatement],
        additional_context: str = "",
        instruction: str = "",
    ) -> AgentStatement:
        """에이전트 발언 생성"""

        # 이전 발언 컴파일
        prev_discussion = ""
        if previous_statements:
            prev_parts = []
            for stmt in previous_statements[-5:]:  # 최근 5개만
                prev_parts.append(f"[{stmt.agent_name}]: {stmt.content[:500]}")
            prev_discussion = "\n\n".join(prev_parts)

        prompt = f"""당신은 {agent.name_ko}({agent.name_en}) 관점의 투자 전문가입니다.

{agent.system_prompt_template}

---
[현재 시장 상황]
{context}

{f'[추가 데이터]{chr(10)}{additional_context}' if additional_context else ''}

{f'[이전 토론 내용]{chr(10)}{prev_discussion}' if prev_discussion else ''}

---
{instruction}

다음 형식으로 응답해주세요:

**현황 인식**
(현재 상황에 대한 당신의 해석)

**전망**
- 단기(1M):
- 중기(3M):
- 리스크:

**대응 전략**
(구체적인 액션 플랜)

**모니터링 포인트**
(주시해야 할 지표/이벤트)

{f'**필요한 데이터**{chr(10)}(추가로 확인하고 싶은 데이터)' if phase == DiscussionPhase.FIRST_ROUND else ''}
"""

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": agent.system_prompt_template},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            content = response.choices[0].message.content

            return AgentStatement(
                agent_id=agent.agent_id,
                agent_name=agent.name_ko,
                phase=phase,
                content=content,
            )

        except Exception as e:
            logger.error(f"에이전트 발언 생성 실패 ({agent.name_ko}): {e}")
            return AgentStatement(
                agent_id=agent.agent_id,
                agent_name=agent.name_ko,
                phase=phase,
                content=f"[발언 생성 실패: {str(e)}]",
            )

    def _get_agent_conclusion(
        self,
        agent: MarketAgentArchetype,
        context: str,
        rounds: List[DiscussionRound],
    ) -> AgentStatement:
        """에이전트 최종 결론 생성"""

        # 토론 요약 컴파일
        discussion_summary = self._compile_full_discussion(rounds)

        prompt = f"""당신은 {agent.name_ko}({agent.name_en}) 관점의 투자 전문가입니다.

지금까지의 토론을 바탕으로 최종 결론을 내려주세요.

[토론 요약]
{discussion_summary}

다음 형식으로 최종 의견을 정리해주세요:

**최종 전망**
- 자산군: (주식/채권/원자재/현금 각각 ▲/─/▼)
- 섹터: (주요 섹터 전망)
- 팩터: (유리한 팩터 순서)

**핵심 시나리오**
(가장 가능성 높은 시나리오 서술)

**대응 전략 요약**
(1-2문장 핵심 전략)

**리스크 요인**
(가장 우려되는 1-2가지)

**확신도**: (0.0-1.0)
"""

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": agent.system_prompt_template},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800,
            )

            content = response.choices[0].message.content

            # 확신도 추출
            confidence = 0.5
            if "확신도" in content:
                import re
                match = re.search(r'확신도[:\s]*([0-9.]+)', content)
                if match:
                    confidence = float(match.group(1))

            return AgentStatement(
                agent_id=agent.agent_id,
                agent_name=agent.name_ko,
                phase=DiscussionPhase.CONCLUSION,
                content=content,
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"결론 생성 실패 ({agent.name_ko}): {e}")
            return AgentStatement(
                agent_id=agent.agent_id,
                agent_name=agent.name_ko,
                phase=DiscussionPhase.CONCLUSION,
                content=f"[결론 생성 실패: {str(e)}]",
                confidence=0.0,
            )

    def _compile_discussion_text(self, round: DiscussionRound) -> str:
        """토론 라운드를 텍스트로 컴파일"""
        parts = []
        for stmt in round.statements:
            parts.append(f"[{stmt.agent_name}]\n{stmt.content}")
        return "\n\n---\n\n".join(parts)

    def _compile_full_discussion(self, rounds: List[DiscussionRound]) -> str:
        """전체 토론을 요약 텍스트로 컴파일"""
        parts = []
        for round in rounds:
            if round.phase == DiscussionPhase.DATA_COLLECTION:
                parts.append(f"[데이터 수집]\n{round.summary}")
            else:
                for stmt in round.statements[:3]:  # 라운드당 3개만
                    parts.append(f"[{stmt.agent_name} - {round.phase.value}]\n{stmt.content[:300]}...")
        return "\n\n".join(parts)

    def _extract_agent_scenarios(self, rounds: List[DiscussionRound]) -> List[Dict[str, Any]]:
        """에이전트별 시나리오 추출"""
        scenarios = []

        conclusion_round = next(
            (r for r in rounds if r.phase == DiscussionPhase.CONCLUSION),
            None
        )

        if conclusion_round:
            for stmt in conclusion_round.statements:
                scenarios.append({
                    "agent_id": stmt.agent_id,
                    "agent_name": stmt.agent_name,
                    "scenario": stmt.content,
                    "confidence": stmt.confidence or 0.5,
                })

        return scenarios

    def _identify_conflicts(self, rounds: List[DiscussionRound]) -> List[str]:
        """의견 충돌 지점 식별"""
        # TODO: LLM으로 충돌 지점 분석
        return ["반도체 섹터 전망 (모멘텀 ↑ vs 역추세 ↓)", "채권 비중 확대 여부"]

    def _identify_consensus(self, rounds: List[DiscussionRound]) -> List[str]:
        """합의된 영역 식별"""
        # TODO: LLM으로 합의 영역 분석
        return ["금리 동결 기조 유지 전망", "방어주 상대적 선호"]

    def _identify_blind_spots(self, rounds: List[DiscussionRound], context: str) -> List[str]:
        """놓치고 있는 포인트 식별"""
        # TODO: LLM으로 블라인드스팟 분석
        return ["일본 BOJ 정책 변화 가능성", "지정학적 리스크 (중동)"]
