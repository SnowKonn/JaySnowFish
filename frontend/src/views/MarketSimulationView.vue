<template>
  <div class="market-simulation">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">
          <span class="brand-icon">◈</span>
          <span class="brand-text">MIROFISH</span>
        </div>
        <div class="module-badge">Market Outlook</div>
      </div>
      <div class="header-center">
        <div class="nav-tabs">
          <button
            class="nav-tab"
            :class="{ active: currentView === 'simulation' }"
            @click="currentView = 'simulation'"
          >
            Simulation
          </button>
          <button
            class="nav-tab"
            :class="{ active: currentView === 'history' }"
            @click="currentView = 'history'"
          >
            History
            <span v-if="history.length" class="history-count">{{ history.length }}</span>
          </button>
        </div>
      </div>
      <div class="header-right">
        <LanguageSwitcher />
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content" v-if="currentView === 'simulation'">
      <!-- Left Panel: Input -->
      <aside class="input-panel">
        <div class="panel-section">
          <div class="section-header">
            <span class="section-icon">▣</span>
            <span class="section-title">Market Context</span>
          </div>

          <!-- Sample Contexts -->
          <div class="sample-contexts">
            <button
              v-for="sample in sampleContexts"
              :key="sample.id"
              class="sample-btn"
              @click="applySample(sample)"
            >
              {{ sample.label }}
            </button>
          </div>

          <!-- Context Input -->
          <textarea
            v-model="context"
            class="context-input"
            placeholder="현재 시장 상황을 입력하세요..."
            rows="10"
          ></textarea>
          <div class="char-count">{{ context.length }} / 2000</div>
        </div>

        <div class="panel-section">
          <div class="section-header">
            <span class="section-icon">◇</span>
            <span class="section-title">Agents</span>
            <span class="agent-count">{{ selectedAgents.length }}/{{ agents.length }}</span>
          </div>

          <div class="agent-list">
            <div
              v-for="agent in agents"
              :key="agent.agent_id"
              class="agent-item"
              :class="{ selected: selectedAgents.includes(agent.agent_id) }"
              @click="toggleAgent(agent.agent_id)"
            >
              <div class="agent-checkbox">
                <span v-if="selectedAgents.includes(agent.agent_id)">✓</span>
              </div>
              <div class="agent-info">
                <span class="agent-name-ko">{{ agent.name_ko }}</span>
                <span class="agent-name-en">{{ agent.name_en }}</span>
              </div>
            </div>
          </div>

          <div class="agent-controls">
            <button class="ctrl-btn" @click="selectAllAgents">All</button>
            <button class="ctrl-btn" @click="clearAgents">Clear</button>
          </div>
        </div>

        <!-- Run Button -->
        <button
          class="run-button"
          :disabled="!canRun"
          @click="runSimulation"
        >
          <span v-if="loading" class="btn-spinner"></span>
          <span v-else class="btn-icon">▶</span>
          <span class="btn-text">{{ loading ? '분석 중...' : '시뮬레이션 실행' }}</span>
        </button>

        <!-- Error Message -->
        <div v-if="error" class="error-box">
          <span class="error-icon">⚠</span>
          <span class="error-text">{{ error }}</span>
          <button class="error-dismiss" @click="error = null">×</button>
        </div>
      </aside>

      <!-- Right Panel: Results -->
      <section class="result-panel">
        <!-- Loading State -->
        <div v-if="loading" class="loading-state">
          <div class="loading-header">
            <div class="loading-title">시장 분석 진행 중</div>
            <div class="loading-subtitle">{{ phaseMessage }}</div>
          </div>

          <div class="loading-progress">
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: progress + '%' }"></div>
            </div>
            <span class="progress-text">{{ Math.round(progress) }}%</span>
          </div>

          <div class="loading-agents">
            <div
              v-for="(status, idx) in agentStatuses"
              :key="idx"
              class="agent-status"
              :class="status.state"
            >
              <span class="status-indicator"></span>
              <span class="status-name">{{ status.name }}</span>
              <span class="status-label">{{ status.label }}</span>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="!result" class="empty-state">
          <div class="empty-visual">
            <div class="empty-chart">
              <div class="chart-bar" style="height: 40%"></div>
              <div class="chart-bar" style="height: 70%"></div>
              <div class="chart-bar" style="height: 55%"></div>
              <div class="chart-bar" style="height: 85%"></div>
              <div class="chart-bar" style="height: 60%"></div>
            </div>
          </div>
          <h3>시장 상황을 입력하고 분석을 시작하세요</h3>
          <p>10명의 전문가 에이전트가 토론을 통해 시장 전망을 도출합니다</p>
        </div>

        <!-- Results -->
        <div v-else class="results-container">
          <!-- Result Header -->
          <div class="result-header">
            <div class="result-meta">
              <span class="result-time">{{ formatTime(result.timestamp) }}</span>
              <span class="result-duration">{{ result.duration?.toFixed(1) }}s</span>
            </div>
            <div class="result-actions">
              <button class="action-btn" @click="exportResult">
                <span>↓</span> Export
              </button>
              <button class="action-btn" @click="saveToHistory">
                <span>★</span> Save
              </button>
            </div>
          </div>

          <!-- Result Tabs -->
          <div class="result-tabs">
            <button
              v-for="tab in resultTabs"
              :key="tab.key"
              class="result-tab"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              <span class="tab-icon">{{ tab.icon }}</span>
              <span class="tab-label">{{ tab.label }}</span>
            </button>
          </div>

          <!-- Tab Content -->
          <div class="tab-content">
            <!-- Overview Tab -->
            <div v-if="activeTab === 'overview'" class="tab-pane overview-pane">
              <!-- Scenarios -->
              <div class="scenarios-grid">
                <div class="scenario-card base">
                  <div class="scenario-header">
                    <span class="scenario-badge">BASE</span>
                    <span class="scenario-prob">{{ formatPercent(result.scenarios?.base_scenario?.probability) }}</span>
                  </div>
                  <p class="scenario-desc">{{ result.scenarios?.base_scenario?.description }}</p>
                  <div class="scenario-triggers" v-if="result.scenarios?.base_scenario?.triggers?.length">
                    <span class="triggers-label">Triggers:</span>
                    <span v-for="(t, i) in result.scenarios?.base_scenario?.triggers" :key="i" class="trigger-tag">{{ t }}</span>
                  </div>
                </div>

                <div class="scenario-card risk">
                  <div class="scenario-header">
                    <span class="scenario-badge">RISK</span>
                    <span class="scenario-prob">{{ formatPercent(result.scenarios?.risk_scenario?.probability) }}</span>
                  </div>
                  <p class="scenario-desc">{{ result.scenarios?.risk_scenario?.description }}</p>
                  <div class="scenario-triggers" v-if="result.scenarios?.risk_scenario?.triggers?.length">
                    <span class="triggers-label">Triggers:</span>
                    <span v-for="(t, i) in result.scenarios?.risk_scenario?.triggers" :key="i" class="trigger-tag">{{ t }}</span>
                  </div>
                </div>
              </div>

              <!-- Outlook Charts -->
              <div class="outlook-section">
                <h4 class="section-subtitle">Asset Outlook</h4>
                <div class="outlook-chart" ref="assetChartRef"></div>
              </div>

              <div class="outlook-section">
                <h4 class="section-subtitle">Sector Outlook</h4>
                <div class="outlook-chart" ref="sectorChartRef"></div>
              </div>

              <div class="outlook-section">
                <h4 class="section-subtitle">Factor Outlook</h4>
                <div class="outlook-chart" ref="factorChartRef"></div>
              </div>
            </div>

            <!-- Agents Tab -->
            <div v-if="activeTab === 'agents'" class="tab-pane agents-pane">
              <div class="agent-cards">
                <div
                  v-for="agent in result.agent_scenarios"
                  :key="agent.agent_id"
                  class="agent-card"
                  :class="{ expanded: expandedAgent === agent.agent_id }"
                  @click="toggleAgentExpand(agent.agent_id)"
                >
                  <div class="agent-card-header">
                    <div class="agent-identity">
                      <span class="agent-avatar">{{ agent.agent_name?.charAt(0) }}</span>
                      <span class="agent-card-name">{{ agent.agent_name }}</span>
                    </div>
                    <div class="agent-confidence">
                      <div class="confidence-bar">
                        <div class="confidence-fill" :style="{ width: (agent.confidence * 100) + '%' }"></div>
                      </div>
                      <span class="confidence-value">{{ formatPercent(agent.confidence) }}</span>
                    </div>
                  </div>
                  <div class="agent-card-body">
                    <pre>{{ agent.scenario }}</pre>
                  </div>
                </div>
              </div>
            </div>

            <!-- Analysis Tab -->
            <div v-if="activeTab === 'analysis'" class="tab-pane analysis-pane">
              <div class="analysis-grid">
                <div class="analysis-card consensus">
                  <div class="analysis-header">
                    <span class="analysis-icon">🤝</span>
                    <span class="analysis-title">Consensus Areas</span>
                  </div>
                  <ul class="analysis-list">
                    <li v-for="(item, idx) in result.consensus_areas" :key="idx">{{ item }}</li>
                  </ul>
                </div>

                <div class="analysis-card conflict">
                  <div class="analysis-header">
                    <span class="analysis-icon">⚔️</span>
                    <span class="analysis-title">Conflict Points</span>
                  </div>
                  <ul class="analysis-list">
                    <li v-for="(item, idx) in result.conflict_points" :key="idx">{{ item }}</li>
                  </ul>
                </div>

                <div class="analysis-card blindspot">
                  <div class="analysis-header">
                    <span class="analysis-icon">👁️</span>
                    <span class="analysis-title">Blind Spots</span>
                  </div>
                  <ul class="analysis-list">
                    <li v-for="(item, idx) in result.blind_spots" :key="idx">{{ item }}</li>
                  </ul>
                </div>
              </div>

              <!-- Agent Confidence Chart -->
              <div class="confidence-section">
                <h4 class="section-subtitle">Agent Confidence Distribution</h4>
                <div class="confidence-chart" ref="confidenceChartRef"></div>
              </div>
            </div>

            <!-- Report Tab -->
            <div v-if="activeTab === 'report'" class="tab-pane report-pane">
              <div class="report-toolbar">
                <button class="toolbar-btn" @click="copyReport">
                  <span>📋</span> Copy
                </button>
                <button class="toolbar-btn" @click="downloadReport">
                  <span>↓</span> Download
                </button>
              </div>
              <div class="report-content" v-html="renderedReport"></div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- History View -->
    <main class="main-content history-view" v-else>
      <div class="history-panel">
        <div class="history-header">
          <h2>Simulation History</h2>
          <button class="clear-history-btn" @click="clearHistory" v-if="history.length">
            Clear All
          </button>
        </div>

        <div v-if="!history.length" class="history-empty">
          <p>저장된 시뮬레이션이 없습니다</p>
        </div>

        <div v-else class="history-list">
          <div
            v-for="(item, idx) in history"
            :key="idx"
            class="history-item"
            @click="loadFromHistory(item)"
          >
            <div class="history-item-header">
              <span class="history-time">{{ formatTime(item.timestamp) }}</span>
              <button class="history-delete" @click.stop="deleteHistoryItem(idx)">×</button>
            </div>
            <p class="history-context">{{ truncate(item.context, 100) }}</p>
            <div class="history-item-footer">
              <span class="history-agents">{{ item.agentCount }} agents</span>
              <span class="history-duration">{{ item.duration?.toFixed(1) }}s</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import * as d3 from 'd3'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { getMarketAgents, runMarketSimulation } from '../api/market'

const router = useRouter()

// View State
const currentView = ref('simulation')
const activeTab = ref('overview')
const expandedAgent = ref(null)

// Input State
const context = ref('')
const agents = ref([])
const selectedAgents = ref([])

// Loading State
const loading = ref(false)
const progress = ref(0)
const phaseMessage = ref('')
const agentStatuses = ref([])

// Result State
const result = ref(null)
const error = ref(null)

// History State
const history = ref([])

// Chart Refs
const assetChartRef = ref(null)
const sectorChartRef = ref(null)
const factorChartRef = ref(null)
const confidenceChartRef = ref(null)

// Sample Contexts
const sampleContexts = [
  {
    id: 'fed',
    label: '🏛️ 연준 금리 동결',
    context: '연준이 이번 FOMC에서 금리를 동결했다. 파월 의장은 인플레이션이 여전히 목표치를 상회하지만, 경기 둔화 우려로 추가 인상은 신중하게 접근하겠다고 밝혔다. 시장은 연내 금리 인하 기대를 낮추는 분위기다.'
  },
  {
    id: 'semiconductor',
    label: '💾 반도체 업황 개선',
    context: 'AI 수요 급증으로 HBM, GPU 등 고부가 반도체 가격이 상승세를 보이고 있다. 삼성전자와 SK하이닉스의 HBM3 생산량이 빠르게 증가 중이며, NVIDIA 실적 호조로 관련 공급망 전반에 기대감이 확산되고 있다.'
  },
  {
    id: 'china',
    label: '🇨🇳 중국 경기 부양',
    context: '중국 정부가 대규모 경기 부양책을 발표했다. 부동산 시장 안정화를 위한 금리 인하와 지방정부 부채 해소 방안이 포함되었다. 외국인 투자자들의 중국 증시 복귀 조짐이 보이며, 원자재 가격도 반등하고 있다.'
  },
  {
    id: 'geopolitics',
    label: '🌍 지정학 리스크',
    context: '중동 지역 긴장이 고조되면서 유가가 급등했다. WTI 기준 배럴당 90달러를 돌파했으며, 안전자산 선호로 금 가격도 사상 최고치를 경신했다. 글로벌 공급망 차질 우려가 다시 부각되고 있다.'
  }
]

// Result Tabs
const resultTabs = [
  { key: 'overview', label: '시나리오', icon: '◈' },
  { key: 'agents', label: '에이전트', icon: '◇' },
  { key: 'analysis', label: '분석', icon: '▣' },
  { key: 'report', label: '리포트', icon: '▤' }
]

// Computed
const canRun = computed(() => {
  return context.value.trim().length > 10 && selectedAgents.value.length > 0 && !loading.value
})

const renderedReport = computed(() => {
  if (!result.value?.report) return ''
  return marked(result.value.report)
})

// Methods
const applySample = (sample) => {
  context.value = sample.context
}

const toggleAgent = (agentId) => {
  const idx = selectedAgents.value.indexOf(agentId)
  if (idx === -1) {
    selectedAgents.value.push(agentId)
  } else {
    selectedAgents.value.splice(idx, 1)
  }
}

const selectAllAgents = () => {
  selectedAgents.value = agents.value.map(a => a.agent_id)
}

const clearAgents = () => {
  selectedAgents.value = []
}

const toggleAgentExpand = (agentId) => {
  expandedAgent.value = expandedAgent.value === agentId ? null : agentId
}

const formatPercent = (val) => {
  if (val === undefined || val === null) return '-'
  return (val * 100).toFixed(0) + '%'
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleString('ko-KR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const truncate = (str, len) => {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

// Simulation
const runSimulation = async () => {
  if (!canRun.value) return

  loading.value = true
  progress.value = 0
  error.value = null
  result.value = null
  phaseMessage.value = '에이전트 초기화 중...'

  // Initialize agent statuses
  agentStatuses.value = selectedAgents.value.map(id => {
    const agent = agents.value.find(a => a.agent_id === id)
    return { name: agent?.name_ko || id, state: 'waiting', label: '대기' }
  })

  // Simulate progress
  const phases = [
    { msg: '1차 토론 진행 중...', target: 30 },
    { msg: '데이터 수집 중...', target: 50 },
    { msg: '2차 토론 진행 중...', target: 75 },
    { msg: '시나리오 생성 중...', target: 90 }
  ]

  let phaseIdx = 0
  const progressInterval = setInterval(() => {
    if (phaseIdx < phases.length && progress.value >= phases[phaseIdx].target - 10) {
      phaseMessage.value = phases[phaseIdx].msg

      // Update random agent status
      const waitingAgents = agentStatuses.value.filter(a => a.state === 'waiting')
      if (waitingAgents.length > 0) {
        const randomAgent = waitingAgents[Math.floor(Math.random() * waitingAgents.length)]
        randomAgent.state = 'active'
        randomAgent.label = '발언 중'

        setTimeout(() => {
          randomAgent.state = 'done'
          randomAgent.label = '완료'
        }, 1500)
      }

      phaseIdx++
    }

    if (progress.value < 90) {
      progress.value += Math.random() * 5 + 1
    }
  }, 400)

  try {
    const params = {
      context: context.value,
      agent_ids: selectedAgents.value.length < agents.value.length ? selectedAgents.value : undefined
    }

    const response = await runMarketSimulation(params)

    clearInterval(progressInterval)
    progress.value = 100
    phaseMessage.value = '완료!'

    // Mark all agents as done
    agentStatuses.value.forEach(a => {
      a.state = 'done'
      a.label = '완료'
    })

    result.value = {
      ...response.data,
      timestamp: new Date().toISOString(),
      duration: response.data.total_duration || 0
    }

    // Render charts after result is set
    await nextTick()
    renderCharts()

  } catch (err) {
    clearInterval(progressInterval)
    console.error('Simulation failed:', err)
    error.value = err.response?.data?.error || err.message || '시뮬레이션 실패'

    // Retry logic
    if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
      error.value = '요청 시간 초과. 다시 시도해주세요.'
    }
  } finally {
    setTimeout(() => {
      loading.value = false
    }, 500)
  }
}

// Charts
const renderCharts = () => {
  if (!result.value) return

  // Asset Chart
  if (assetChartRef.value && result.value.quantitative_outlook?.asset_views) {
    renderBarChart(assetChartRef.value, result.value.quantitative_outlook.asset_views, 'asset')
  }

  // Sector Chart
  if (sectorChartRef.value && result.value.quantitative_outlook?.sector_views) {
    renderBarChart(sectorChartRef.value, result.value.quantitative_outlook.sector_views, 'sector')
  }

  // Factor Chart
  if (factorChartRef.value && result.value.quantitative_outlook?.factor_views) {
    renderBarChart(factorChartRef.value, result.value.quantitative_outlook.factor_views, 'factor')
  }

  // Confidence Chart
  if (confidenceChartRef.value && result.value.agent_scenarios) {
    renderConfidenceChart(confidenceChartRef.value, result.value.agent_scenarios)
  }
}

const renderBarChart = (container, data, type) => {
  d3.select(container).selectAll('*').remove()

  const entries = Object.entries(data)
  if (entries.length === 0) return

  const margin = { top: 20, right: 30, bottom: 40, left: 100 }
  const width = container.clientWidth - margin.left - margin.right
  const height = Math.max(entries.length * 35, 100)

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  // Parse outlook values
  const parseOutlook = (val) => {
    if (typeof val === 'string') {
      if (val.includes('▲') || val.includes('비중확대')) return 1
      if (val.includes('▼') || val.includes('비중축소')) return -1
      return 0
    }
    return val || 0
  }

  const chartData = entries.map(([key, val]) => ({
    name: key,
    value: parseOutlook(val),
    label: val
  }))

  const x = d3.scaleLinear()
    .domain([-1.5, 1.5])
    .range([0, width])

  const y = d3.scaleBand()
    .domain(chartData.map(d => d.name))
    .range([0, height])
    .padding(0.3)

  // Zero line
  svg.append('line')
    .attr('x1', x(0))
    .attr('x2', x(0))
    .attr('y1', 0)
    .attr('y2', height)
    .attr('stroke', '#333')
    .attr('stroke-dasharray', '3,3')

  // Bars
  svg.selectAll('.bar')
    .data(chartData)
    .join('rect')
    .attr('class', 'bar')
    .attr('x', d => d.value >= 0 ? x(0) : x(d.value))
    .attr('y', d => y(d.name))
    .attr('width', d => Math.abs(x(d.value) - x(0)))
    .attr('height', y.bandwidth())
    .attr('fill', d => d.value > 0 ? '#4ade80' : d.value < 0 ? '#f87171' : '#666')
    .attr('rx', 3)

  // Labels (left)
  svg.selectAll('.label')
    .data(chartData)
    .join('text')
    .attr('class', 'label')
    .attr('x', -10)
    .attr('y', d => y(d.name) + y.bandwidth() / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'end')
    .attr('fill', '#aaa')
    .attr('font-size', '12px')
    .text(d => d.name)

  // Value labels
  svg.selectAll('.value-label')
    .data(chartData)
    .join('text')
    .attr('class', 'value-label')
    .attr('x', d => d.value >= 0 ? x(d.value) + 5 : x(d.value) - 5)
    .attr('y', d => y(d.name) + y.bandwidth() / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', d => d.value >= 0 ? 'start' : 'end')
    .attr('fill', '#888')
    .attr('font-size', '11px')
    .text(d => d.label)
}

const renderConfidenceChart = (container, agentData) => {
  d3.select(container).selectAll('*').remove()

  const margin = { top: 20, right: 30, bottom: 40, left: 120 }
  const width = container.clientWidth - margin.left - margin.right
  const height = Math.max(agentData.length * 35, 100)

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  const x = d3.scaleLinear()
    .domain([0, 1])
    .range([0, width])

  const y = d3.scaleBand()
    .domain(agentData.map(d => d.agent_name))
    .range([0, height])
    .padding(0.3)

  // Background bars
  svg.selectAll('.bg-bar')
    .data(agentData)
    .join('rect')
    .attr('class', 'bg-bar')
    .attr('x', 0)
    .attr('y', d => y(d.agent_name))
    .attr('width', width)
    .attr('height', y.bandwidth())
    .attr('fill', '#1a1a1a')
    .attr('rx', 3)

  // Confidence bars
  svg.selectAll('.conf-bar')
    .data(agentData)
    .join('rect')
    .attr('class', 'conf-bar')
    .attr('x', 0)
    .attr('y', d => y(d.agent_name))
    .attr('width', d => x(d.confidence || 0.5))
    .attr('height', y.bandwidth())
    .attr('fill', d => {
      const c = d.confidence || 0.5
      if (c >= 0.7) return '#4ade80'
      if (c >= 0.5) return '#facc15'
      return '#f87171'
    })
    .attr('rx', 3)

  // Labels
  svg.selectAll('.label')
    .data(agentData)
    .join('text')
    .attr('x', -10)
    .attr('y', d => y(d.agent_name) + y.bandwidth() / 2)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'end')
    .attr('fill', '#aaa')
    .attr('font-size', '12px')
    .text(d => d.agent_name)

  // Value labels
  svg.selectAll('.value')
    .data(agentData)
    .join('text')
    .attr('x', d => x(d.confidence || 0.5) + 8)
    .attr('y', d => y(d.agent_name) + y.bandwidth() / 2)
    .attr('dy', '0.35em')
    .attr('fill', '#888')
    .attr('font-size', '11px')
    .text(d => formatPercent(d.confidence))
}

// History
const saveToHistory = () => {
  if (!result.value) return

  const item = {
    timestamp: result.value.timestamp,
    context: context.value,
    agentCount: selectedAgents.value.length,
    duration: result.value.duration,
    result: result.value
  }

  history.value.unshift(item)
  if (history.value.length > 20) {
    history.value = history.value.slice(0, 20)
  }

  localStorage.setItem('marketSimHistory', JSON.stringify(history.value))
}

const loadFromHistory = (item) => {
  context.value = item.context
  result.value = item.result
  currentView.value = 'simulation'
  activeTab.value = 'overview'

  nextTick(() => renderCharts())
}

const deleteHistoryItem = (idx) => {
  history.value.splice(idx, 1)
  localStorage.setItem('marketSimHistory', JSON.stringify(history.value))
}

const clearHistory = () => {
  history.value = []
  localStorage.removeItem('marketSimHistory')
}

// Export
const exportResult = () => {
  if (!result.value) return

  const data = JSON.stringify(result.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `market-simulation-${new Date().toISOString().slice(0,10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const copyReport = () => {
  if (!result.value?.report) return
  navigator.clipboard.writeText(result.value.report)
}

const downloadReport = () => {
  if (!result.value?.report) return

  const blob = new Blob([result.value.report], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `market-report-${new Date().toISOString().slice(0,10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

// Lifecycle
onMounted(async () => {
  // Load agents
  try {
    const response = await getMarketAgents()
    agents.value = response.data || []
    selectedAgents.value = agents.value.map(a => a.agent_id)
  } catch (err) {
    console.error('Failed to load agents:', err)
    error.value = '에이전트 목록을 불러오지 못했습니다'
  }

  // Load history
  try {
    const saved = localStorage.getItem('marketSimHistory')
    if (saved) {
      history.value = JSON.parse(saved)
    }
  } catch (err) {
    console.error('Failed to load history:', err)
  }
})

// Watch for tab changes to re-render charts
watch(activeTab, (newTab) => {
  if (result.value && (newTab === 'overview' || newTab === 'analysis')) {
    nextTick(() => renderCharts())
  }
})
</script>

<style scoped>
/* Base */
.market-simulation {
  min-height: 100vh;
  background: #080808;
  color: #d0d0d0;
  font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif;
}

/* Header */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
  height: 56px;
  background: #0c0c0c;
  border-bottom: 1px solid #1a1a1a;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.brand:hover {
  opacity: 0.8;
}

.brand-icon {
  color: #f97316;
  font-size: 1.2rem;
}

.brand-text {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 1.1rem;
  letter-spacing: 1px;
  color: #fff;
}

.module-badge {
  background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
  color: #000;
  padding: 4px 10px;
  font-size: 0.7rem;
  font-weight: 600;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.nav-tabs {
  display: flex;
  gap: 4px;
  background: #111;
  padding: 4px;
  border-radius: 6px;
}

.nav-tab {
  background: transparent;
  border: none;
  color: #666;
  padding: 6px 16px;
  font-size: 0.85rem;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-tab:hover {
  color: #999;
}

.nav-tab.active {
  background: #222;
  color: #fff;
}

.history-count {
  background: #f97316;
  color: #000;
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
}

/* Main Content */
.main-content {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 0;
  height: calc(100vh - 56px);
}

/* Input Panel */
.input-panel {
  background: #0c0c0c;
  border-right: 1px solid #1a1a1a;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-section {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 0.85rem;
}

.section-icon {
  color: #f97316;
}

.section-title {
  color: #888;
  font-weight: 500;
}

.agent-count {
  margin-left: auto;
  color: #555;
  font-size: 0.75rem;
}

/* Sample Contexts */
.sample-contexts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.sample-btn {
  background: #1a1a1a;
  border: 1px solid #252525;
  border-radius: 4px;
  padding: 6px 10px;
  font-size: 0.75rem;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}

.sample-btn:hover {
  border-color: #f97316;
  color: #f97316;
}

/* Context Input */
.context-input {
  width: 100%;
  background: #0a0a0a;
  border: 1px solid #222;
  border-radius: 6px;
  padding: 12px;
  color: #d0d0d0;
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1.6;
  resize: none;
  transition: border-color 0.2s;
}

.context-input:focus {
  outline: none;
  border-color: #f97316;
}

.context-input::placeholder {
  color: #444;
}

.char-count {
  text-align: right;
  font-size: 0.7rem;
  color: #444;
  margin-top: 6px;
}

/* Agent List */
.agent-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: #0a0a0a;
  border: 1px solid #1a1a1a;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.agent-item:hover {
  border-color: #333;
}

.agent-item.selected {
  border-color: #f97316;
  background: rgba(249, 115, 22, 0.1);
}

.agent-checkbox {
  width: 18px;
  height: 18px;
  border: 1px solid #333;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  color: #f97316;
  flex-shrink: 0;
}

.agent-item.selected .agent-checkbox {
  background: #f97316;
  border-color: #f97316;
  color: #000;
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-name-ko {
  font-size: 0.85rem;
  color: #ccc;
}

.agent-name-en {
  font-size: 0.7rem;
  color: #555;
}

.agent-controls {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.ctrl-btn {
  background: transparent;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 4px 12px;
  font-size: 0.75rem;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.ctrl-btn:hover {
  border-color: #555;
  color: #999;
}

/* Run Button */
.run-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
  border: none;
  border-radius: 8px;
  color: #000;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s;
}

.run-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3);
}

.run-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-icon {
  font-size: 0.8rem;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Error Box */
.error-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  margin-top: 12px;
}

.error-icon {
  color: #ef4444;
}

.error-text {
  flex: 1;
  font-size: 0.85rem;
  color: #ef4444;
}

.error-dismiss {
  background: none;
  border: none;
  color: #666;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

/* Result Panel */
.result-panel {
  background: #0a0a0a;
  overflow-y: auto;
  padding: 24px;
}

/* Loading State */
.loading-state {
  max-width: 600px;
  margin: 60px auto;
}

.loading-header {
  text-align: center;
  margin-bottom: 32px;
}

.loading-title {
  font-size: 1.4rem;
  font-weight: 600;
  color: #fff;
  margin-bottom: 8px;
}

.loading-subtitle {
  color: #f97316;
  font-size: 0.95rem;
}

.loading-progress {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.progress-track {
  flex: 1;
  height: 6px;
  background: #1a1a1a;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #f97316, #fb923c);
  transition: width 0.3s;
}

.progress-text {
  font-size: 0.85rem;
  color: #888;
  min-width: 40px;
}

.loading-agents {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.agent-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 6px;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #333;
}

.agent-status.waiting .status-indicator {
  background: #333;
}

.agent-status.active .status-indicator {
  background: #f97316;
  animation: pulse 1s infinite;
}

.agent-status.done .status-indicator {
  background: #4ade80;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-name {
  flex: 1;
  font-size: 0.85rem;
  color: #ccc;
}

.status-label {
  font-size: 0.75rem;
  color: #666;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
  text-align: center;
}

.empty-visual {
  margin-bottom: 24px;
}

.empty-chart {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 80px;
}

.chart-bar {
  width: 24px;
  background: linear-gradient(180deg, #333 0%, #1a1a1a 100%);
  border-radius: 4px 4px 0 0;
  animation: barPulse 2s ease-in-out infinite;
}

.chart-bar:nth-child(2) { animation-delay: 0.2s; }
.chart-bar:nth-child(3) { animation-delay: 0.4s; }
.chart-bar:nth-child(4) { animation-delay: 0.6s; }
.chart-bar:nth-child(5) { animation-delay: 0.8s; }

@keyframes barPulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.6; }
}

.empty-state h3 {
  font-size: 1.1rem;
  font-weight: 500;
  color: #888;
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 0.9rem;
  color: #555;
}

/* Results Container */
.results-container {
  max-width: 1000px;
  margin: 0 auto;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #1a1a1a;
}

.result-meta {
  display: flex;
  gap: 16px;
  font-size: 0.85rem;
  color: #666;
}

.result-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #1a1a1a;
  border: 1px solid #252525;
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 0.8rem;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  border-color: #f97316;
  color: #f97316;
}

/* Result Tabs */
.result-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 24px;
}

.result-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 0.85rem;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.result-tab:hover {
  border-color: #333;
  color: #999;
}

.result-tab.active {
  background: #f97316;
  border-color: #f97316;
  color: #000;
}

.tab-icon {
  font-size: 0.9rem;
}

/* Tab Panes */
.tab-content {
  animation: fadeIn 0.3s;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Overview Pane */
.scenarios-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 32px;
}

.scenario-card {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 20px;
}

.scenario-card.base {
  border-left: 3px solid #4ade80;
}

.scenario-card.risk {
  border-left: 3px solid #f87171;
}

.scenario-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.scenario-badge {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 3px 8px;
  border-radius: 3px;
}

.scenario-card.base .scenario-badge {
  background: rgba(74, 222, 128, 0.2);
  color: #4ade80;
}

.scenario-card.risk .scenario-badge {
  background: rgba(248, 113, 113, 0.2);
  color: #f87171;
}

.scenario-prob {
  font-size: 0.85rem;
  color: #888;
}

.scenario-desc {
  font-size: 0.9rem;
  line-height: 1.7;
  color: #bbb;
  margin-bottom: 12px;
}

.scenario-triggers {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.triggers-label {
  font-size: 0.75rem;
  color: #555;
}

.trigger-tag {
  font-size: 0.7rem;
  padding: 2px 8px;
  background: #1a1a1a;
  border-radius: 3px;
  color: #888;
}

/* Outlook Section */
.outlook-section {
  margin-bottom: 24px;
}

.section-subtitle {
  font-size: 0.9rem;
  font-weight: 500;
  color: #888;
  margin-bottom: 12px;
}

.outlook-chart {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 16px;
  min-height: 120px;
}

/* Agents Pane */
.agent-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.agent-card {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
}

.agent-card:hover {
  border-color: #333;
}

.agent-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
}

.agent-identity {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-avatar {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: #000;
  font-size: 0.9rem;
}

.agent-card-name {
  font-weight: 500;
  color: #ddd;
}

.agent-confidence {
  display: flex;
  align-items: center;
  gap: 10px;
}

.confidence-bar {
  width: 60px;
  height: 4px;
  background: #1a1a1a;
  border-radius: 2px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  background: #f97316;
  transition: width 0.3s;
}

.confidence-value {
  font-size: 0.8rem;
  color: #888;
  min-width: 36px;
}

.agent-card-body {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s;
  border-top: 1px solid transparent;
}

.agent-card.expanded .agent-card-body {
  max-height: 500px;
  border-top-color: #1a1a1a;
}

.agent-card-body pre {
  padding: 16px;
  margin: 0;
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 0.85rem;
  line-height: 1.7;
  color: #aaa;
  white-space: pre-wrap;
}

/* Analysis Pane */
.analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.analysis-card {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 16px;
}

.analysis-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.analysis-icon {
  font-size: 1.1rem;
}

.analysis-title {
  font-size: 0.85rem;
  font-weight: 500;
  color: #888;
}

.analysis-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.analysis-list li {
  padding: 8px 0;
  font-size: 0.85rem;
  color: #aaa;
  border-bottom: 1px solid #1a1a1a;
}

.analysis-list li:last-child {
  border-bottom: none;
}

.confidence-section {
  margin-top: 24px;
}

.confidence-chart {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 16px;
  min-height: 200px;
}

/* Report Pane */
.report-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #1a1a1a;
  border: 1px solid #252525;
  border-radius: 4px;
  padding: 8px 14px;
  font-size: 0.85rem;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover {
  border-color: #f97316;
  color: #f97316;
}

.report-content {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 24px;
  font-size: 0.9rem;
  line-height: 1.8;
  color: #bbb;
}

.report-content :deep(h1),
.report-content :deep(h2),
.report-content :deep(h3) {
  color: #fff;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  font-weight: 600;
}

.report-content :deep(h1) { font-size: 1.4rem; }
.report-content :deep(h2) { font-size: 1.2rem; color: #f97316; }
.report-content :deep(h3) { font-size: 1rem; }

.report-content :deep(p) {
  margin-bottom: 1em;
}

.report-content :deep(ul),
.report-content :deep(ol) {
  padding-left: 1.5em;
  margin-bottom: 1em;
}

.report-content :deep(li) {
  margin-bottom: 0.5em;
}

.report-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}

.report-content :deep(th),
.report-content :deep(td) {
  border: 1px solid #252525;
  padding: 10px 14px;
  text-align: left;
}

.report-content :deep(th) {
  background: #1a1a1a;
  font-weight: 500;
}

/* History View */
.history-view {
  display: block;
  padding: 32px;
}

.history-panel {
  max-width: 800px;
  margin: 0 auto;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.history-header h2 {
  font-size: 1.2rem;
  font-weight: 500;
  color: #fff;
}

.clear-history-btn {
  background: transparent;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 6px 12px;
  font-size: 0.8rem;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-history-btn:hover {
  border-color: #f87171;
  color: #f87171;
}

.history-empty {
  text-align: center;
  padding: 60px;
  color: #555;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  background: #111;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  border-color: #f97316;
}

.history-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.history-time {
  font-size: 0.8rem;
  color: #666;
}

.history-delete {
  background: none;
  border: none;
  color: #444;
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: color 0.2s;
}

.history-delete:hover {
  color: #f87171;
}

.history-context {
  font-size: 0.9rem;
  color: #aaa;
  margin-bottom: 12px;
  line-height: 1.5;
}

.history-item-footer {
  display: flex;
  gap: 16px;
  font-size: 0.8rem;
  color: #555;
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: #0a0a0a;
}

::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #444;
}

/* Responsive */
@media (max-width: 1200px) {
  .analysis-grid {
    grid-template-columns: 1fr;
  }

  .scenarios-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .input-panel {
    border-right: none;
    border-bottom: 1px solid #1a1a1a;
    max-height: 50vh;
  }
}
</style>
