import service from './index'

/**
 * 마켓 에이전트 목록 조회
 */
export const getMarketAgents = () => {
  return service.get('/api/market/agents')
}

/**
 * 마켓 시뮬레이션 실행
 * @param {Object} params
 * @param {string} params.context - 시장 상황 컨텍스트
 * @param {Array<string>} params.agent_ids - 참여 에이전트 ID (선택)
 */
export const runMarketSimulation = (params) => {
  return service.post('/api/market/simulate', params)
}

/**
 * 마켓 시뮬레이션 리포트 생성
 * @param {Object} params
 * @param {string} params.context - 시장 상황 컨텍스트
 * @param {Array<string>} params.agent_ids - 참여 에이전트 ID (선택)
 */
export const getMarketReport = (params) => {
  return service.post('/api/market/simulate/report', params)
}

/**
 * 토론만 실행
 * @param {Object} params
 * @param {string} params.context - 시장 상황 컨텍스트
 * @param {Array<string>} params.agent_ids - 참여 에이전트 ID (선택)
 */
export const runMarketDiscussion = (params) => {
  return service.post('/api/market/discussion', params)
}
