"""
시장 시뮬레이션 API 라우트
에이전트 기반 시장 전망 토론 및 시나리오 생성
"""

import traceback
from flask import Blueprint, request, jsonify

from ..services.market_simulation import (
    MARKET_AGENT_ARCHETYPES,
    DiscussionEngine,
    ScenarioGenerator,
)
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.market_simulation')

market_bp = Blueprint('market', __name__, url_prefix='/api/market')


@market_bp.route('/agents', methods=['GET'])
def get_agents():
    """
    사용 가능한 에이전트 목록 조회

    Returns:
        에이전트 아키타입 목록
    """
    try:
        agents = [agent.to_dict() for agent in MARKET_AGENT_ARCHETYPES]
        return jsonify({
            "success": True,
            "data": {
                "agents": agents,
                "total": len(agents),
            }
        })
    except Exception as e:
        logger.error(f"에이전트 목록 조회 실패: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@market_bp.route('/simulate', methods=['POST'])
def run_simulation():
    """
    시장 시뮬레이션 실행

    Request Body:
        {
            "context": "현재 시장 상황 설명 (필수)",
            "additional_data": {...},  // 추가 데이터 (선택)
            "agent_ids": ["insider", "momentum", ...],  // 참여 에이전트 (선택, 기본=전체)
        }

    Returns:
        시뮬레이션 결과
    """
    try:
        data = request.get_json() or {}

        context = data.get("context")
        if not context:
            return jsonify({
                "success": False,
                "error": "context는 필수입니다.",
            }), 400

        additional_data = data.get("additional_data")
        agent_ids = data.get("agent_ids")

        # 에이전트 필터링
        agents = MARKET_AGENT_ARCHETYPES
        if agent_ids:
            agents = [a for a in MARKET_AGENT_ARCHETYPES if a.agent_id in agent_ids]
            if not agents:
                return jsonify({
                    "success": False,
                    "error": f"유효한 에이전트가 없습니다: {agent_ids}",
                }), 400

        logger.info(f"시뮬레이션 시작: {len(agents)}명 에이전트, 컨텍스트 {len(context)}자")

        # 토론 실행
        discussion_engine = DiscussionEngine(agents=agents)
        discussion_result = discussion_engine.run_discussion(
            context=context,
            additional_data=additional_data,
        )

        # 시나리오 생성
        scenario_generator = ScenarioGenerator()
        simulation_result = scenario_generator.generate(discussion_result)

        return jsonify({
            "success": True,
            "data": simulation_result.to_report_dict(),
        })

    except Exception as e:
        logger.error(f"시뮬레이션 실패: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@market_bp.route('/simulate/report', methods=['POST'])
def run_simulation_with_report():
    """
    시장 시뮬레이션 실행 및 마크다운 리포트 생성

    Request Body:
        {
            "context": "현재 시장 상황 설명 (필수)",
            "additional_data": {...},  // 추가 데이터 (선택)
            "agent_ids": ["insider", "momentum", ...],  // 참여 에이전트 (선택)
        }

    Returns:
        시뮬레이션 결과 + 마크다운 리포트
    """
    try:
        data = request.get_json() or {}

        context = data.get("context")
        if not context:
            return jsonify({
                "success": False,
                "error": "context는 필수입니다.",
            }), 400

        additional_data = data.get("additional_data")
        agent_ids = data.get("agent_ids")

        # 에이전트 필터링
        agents = MARKET_AGENT_ARCHETYPES
        if agent_ids:
            agents = [a for a in MARKET_AGENT_ARCHETYPES if a.agent_id in agent_ids]

        logger.info(f"시뮬레이션+리포트 시작: {len(agents)}명 에이전트")

        # 토론 실행
        discussion_engine = DiscussionEngine(agents=agents)
        discussion_result = discussion_engine.run_discussion(
            context=context,
            additional_data=additional_data,
        )

        # 시나리오 생성
        scenario_generator = ScenarioGenerator()
        simulation_result = scenario_generator.generate(discussion_result)

        return jsonify({
            "success": True,
            "data": simulation_result.to_report_dict(),
            "report_markdown": simulation_result.to_report_markdown(),
        })

    except Exception as e:
        logger.error(f"시뮬레이션+리포트 실패: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@market_bp.route('/discussion', methods=['POST'])
def run_discussion_only():
    """
    토론만 실행 (시나리오 생성 없이)

    Request Body:
        {
            "context": "현재 시장 상황 설명",
            "additional_data": {...},
        }

    Returns:
        토론 결과
    """
    try:
        data = request.get_json() or {}

        context = data.get("context")
        if not context:
            return jsonify({
                "success": False,
                "error": "context는 필수입니다.",
            }), 400

        discussion_engine = DiscussionEngine()
        result = discussion_engine.run_discussion(
            context=context,
            additional_data=data.get("additional_data"),
        )

        # 토론 결과만 반환
        rounds_data = []
        for round in result.rounds:
            rounds_data.append({
                "phase": round.phase.value,
                "statements": [
                    {
                        "agent_id": s.agent_id,
                        "agent_name": s.agent_name,
                        "content": s.content,
                    }
                    for s in round.statements
                ],
                "summary": round.summary,
            })

        return jsonify({
            "success": True,
            "data": {
                "rounds": rounds_data,
                "agent_scenarios": result.agent_scenarios,
                "conflict_points": result.conflict_points,
                "consensus_areas": result.consensus_areas,
                "blind_spots": result.blind_spots,
                "duration": result.total_duration,
            }
        })

    except Exception as e:
        logger.error(f"토론 실패: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
