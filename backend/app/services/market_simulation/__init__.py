"""
시장 시뮬레이션 모듈
에이전트 기반 시장 전망 및 시나리오 생성

참고 논문:
- FCLAgent (Hashimoto et al.) - LLM 의도 + 규칙 기반 실행
- Harvard 논문 (Stephanie Lin) - 손실 회피, ATH anomaly
- 대신증권 수급 리포트 - 시장 참여자별 행동 패턴
"""

from .market_agents import (
    MarketAgentArchetype,
    MARKET_AGENT_ARCHETYPES,
    create_market_agent_profile,
)
from .discussion_engine import DiscussionEngine
from .data_agent import DataAgent
from .scenario_generator import ScenarioGenerator, SimulationResult

__all__ = [
    'MarketAgentArchetype',
    'MARKET_AGENT_ARCHETYPES',
    'create_market_agent_profile',
    'DiscussionEngine',
    'DataAgent',
    'ScenarioGenerator',
    'SimulationResult',
]
