<template>
  <div class="market-simulation">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH</div>
        <span class="module-tag">Market Simulation</span>
      </div>
      <div class="header-right">
        <LanguageSwitcher />
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Left Panel: Input -->
      <div class="input-panel">
        <div class="panel-header">
          <span class="icon">◈</span> Market Context
        </div>

        <!-- Context Input -->
        <div class="input-section">
          <label>시장 상황 입력</label>
          <textarea
            v-model="context"
            placeholder="현재 시장 상황을 입력하세요. 예: 연준이 금리 동결을 시사했고, 반도체 업황 개선 기대감이 확산되고 있다..."
            rows="8"
          ></textarea>
        </div>

        <!-- Agent Selection -->
        <div class="input-section">
          <label>참여 에이전트 선택</label>
          <div class="agent-grid">
            <div
              v-for="agent in agents"
              :key="agent.agent_id"
              class="agent-chip"
              :class="{ selected: selectedAgents.includes(agent.agent_id) }"
              @click="toggleAgent(agent.agent_id)"
            >
              <span class="agent-name">{{ agent.name_ko }}</span>
              <span class="agent-name-en">{{ agent.name_en }}</span>
            </div>
          </div>
          <div class="agent-actions">
            <button class="btn-text" @click="selectAllAgents">전체 선택</button>
            <button class="btn-text" @click="clearAgents">선택 해제</button>
          </div>
        </div>

        <!-- Run Button -->
        <button
          class="run-btn"
          :disabled="!context.trim() || loading"
          @click="runSimulation"
        >
          <span v-if="loading" class="spinner"></span>
          <span v-else>시뮬레이션 실행</span>
        </button>

        <!-- Status -->
        <div v-if="loading" class="status-box">
          <div class="status-text">{{ statusMessage }}</div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- Right Panel: Results -->
      <div class="result-panel">
        <div class="panel-header">
          <span class="icon">◇</span> Simulation Results
        </div>

        <!-- Empty State -->
        <div v-if="!result && !loading" class="empty-state">
          <div class="empty-icon">📊</div>
          <p>시장 상황을 입력하고 시뮬레이션을 실행하세요</p>
        </div>

        <!-- Results -->
        <div v-if="result" class="results-content">
          <!-- Tabs -->
          <div class="result-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="tab-btn"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>

          <!-- Tab Content -->
          <div class="tab-content">
            <!-- Overview -->
            <div v-if="activeTab === 'overview'" class="tab-pane">
              <div class="scenario-section">
                <h3>Base Scenario</h3>
                <p>{{ result.scenarios?.base_scenario?.description }}</p>
                <div class="probability-badge">
                  확률: {{ (result.scenarios?.base_scenario?.probability * 100).toFixed(0) }}%
                </div>
              </div>

              <div class="scenario-section risk">
                <h3>Risk Scenario</h3>
                <p>{{ result.scenarios?.risk_scenario?.description }}</p>
                <div class="probability-badge">
                  확률: {{ (result.scenarios?.risk_scenario?.probability * 100).toFixed(0) }}%
                </div>
              </div>

              <!-- Outlook Summary -->
              <div class="outlook-grid">
                <div class="outlook-card">
                  <h4>자산군 전망</h4>
                  <div v-for="(view, asset) in result.quantitative_outlook?.asset_views" :key="asset" class="outlook-item">
                    <span class="asset-name">{{ asset }}</span>
                    <span class="outlook-value" :class="getOutlookClass(view)">{{ view }}</span>
                  </div>
                </div>
                <div class="outlook-card">
                  <h4>섹터 전망</h4>
                  <div v-for="(view, sector) in result.quantitative_outlook?.sector_views" :key="sector" class="outlook-item">
                    <span class="asset-name">{{ sector }}</span>
                    <span class="outlook-value" :class="getOutlookClass(view)">{{ view }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Agent Views -->
            <div v-if="activeTab === 'agents'" class="tab-pane">
              <div
                v-for="agent in result.agent_scenarios"
                :key="agent.agent_id"
                class="agent-card"
              >
                <div class="agent-header">
                  <span class="agent-name">{{ agent.agent_name }}</span>
                  <span class="confidence-badge">확신도: {{ (agent.confidence * 100).toFixed(0) }}%</span>
                </div>
                <div class="agent-scenario">
                  <pre>{{ agent.scenario }}</pre>
                </div>
              </div>
            </div>

            <!-- Analysis -->
            <div v-if="activeTab === 'analysis'" class="tab-pane">
              <div class="analysis-section">
                <h3>🤝 합의 영역</h3>
                <ul>
                  <li v-for="(item, idx) in result.consensus_areas" :key="idx">{{ item }}</li>
                </ul>
              </div>

              <div class="analysis-section">
                <h3>⚔️ 의견 충돌</h3>
                <ul>
                  <li v-for="(item, idx) in result.conflict_points" :key="idx">{{ item }}</li>
                </ul>
              </div>

              <div class="analysis-section">
                <h3>👁️ 블라인드 스팟</h3>
                <ul>
                  <li v-for="(item, idx) in result.blind_spots" :key="idx">{{ item }}</li>
                </ul>
              </div>
            </div>

            <!-- Report -->
            <div v-if="activeTab === 'report'" class="tab-pane">
              <div class="report-content" v-html="renderedReport"></div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { getMarketAgents, runMarketSimulation } from '../api/market'

const router = useRouter()

// State
const context = ref('')
const agents = ref([])
const selectedAgents = ref([])
const loading = ref(false)
const statusMessage = ref('')
const progress = ref(0)
const result = ref(null)
const activeTab = ref('overview')

const tabs = [
  { key: 'overview', label: '시나리오' },
  { key: 'agents', label: '에이전트 뷰' },
  { key: 'analysis', label: '분석' },
  { key: 'report', label: '리포트' },
]

// Computed
const renderedReport = computed(() => {
  if (!result.value?.report) return ''
  return marked(result.value.report)
})

// Methods
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

const getOutlookClass = (view) => {
  if (view?.includes('▲') || view?.includes('비중확대') || view?.includes('긍정')) return 'positive'
  if (view?.includes('▼') || view?.includes('비중축소') || view?.includes('부정')) return 'negative'
  return 'neutral'
}

const runSimulation = async () => {
  if (!context.value.trim()) return

  loading.value = true
  progress.value = 0
  statusMessage.value = '에이전트 토론 시작...'
  result.value = null

  // Simulate progress
  const progressInterval = setInterval(() => {
    if (progress.value < 90) {
      progress.value += Math.random() * 10

      if (progress.value > 20 && progress.value < 40) {
        statusMessage.value = '1차 토론 진행 중...'
      } else if (progress.value >= 40 && progress.value < 60) {
        statusMessage.value = '데이터 수집 중...'
      } else if (progress.value >= 60 && progress.value < 80) {
        statusMessage.value = '2차 토론 진행 중...'
      } else if (progress.value >= 80) {
        statusMessage.value = '시나리오 생성 중...'
      }
    }
  }, 500)

  try {
    const params = {
      context: context.value,
    }
    if (selectedAgents.value.length > 0) {
      params.agent_ids = selectedAgents.value
    }

    const response = await runMarketSimulation(params)
    result.value = response.data
    progress.value = 100
    statusMessage.value = '완료!'
  } catch (error) {
    console.error('Simulation failed:', error)
    statusMessage.value = '오류 발생: ' + (error.message || 'Unknown error')
  } finally {
    clearInterval(progressInterval)
    setTimeout(() => {
      loading.value = false
    }, 500)
  }
}

// Lifecycle
onMounted(async () => {
  try {
    const response = await getMarketAgents()
    agents.value = response.data || []
    selectedAgents.value = agents.value.map(a => a.agent_id)
  } catch (error) {
    console.error('Failed to load agents:', error)
  }
})
</script>

<style scoped>
.market-simulation {
  min-height: 100vh;
  background: #0a0a0a;
  color: #e0e0e0;
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
}

/* Header */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  border-bottom: 1px solid #222;
  background: #0f0f0f;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.2rem;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  letter-spacing: 2px;
}

.module-tag {
  background: linear-gradient(135deg, #ff6b35, #f7931e);
  color: #000;
  padding: 4px 12px;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 4px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* Main Content */
.main-content {
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 24px;
  padding: 24px;
  max-width: 1600px;
  margin: 0 auto;
}

/* Panels */
.input-panel, .result-panel {
  background: #111;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 24px;
}

.panel-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  color: #888;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon {
  color: #ff6b35;
}

/* Input Section */
.input-section {
  margin-bottom: 20px;
}

.input-section label {
  display: block;
  font-size: 0.85rem;
  color: #aaa;
  margin-bottom: 8px;
}

textarea {
  width: 100%;
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 12px;
  color: #e0e0e0;
  font-family: inherit;
  font-size: 0.9rem;
  resize: vertical;
  transition: border-color 0.2s;
}

textarea:focus {
  outline: none;
  border-color: #ff6b35;
}

/* Agent Grid */
.agent-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.agent-chip {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.agent-chip:hover {
  border-color: #555;
}

.agent-chip.selected {
  background: #ff6b35;
  border-color: #ff6b35;
  color: #000;
}

.agent-chip .agent-name {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
}

.agent-chip .agent-name-en {
  display: block;
  font-size: 0.7rem;
  opacity: 0.7;
}

.agent-actions {
  margin-top: 8px;
  display: flex;
  gap: 12px;
}

.btn-text {
  background: none;
  border: none;
  color: #ff6b35;
  font-size: 0.8rem;
  cursor: pointer;
  padding: 0;
}

.btn-text:hover {
  text-decoration: underline;
}

/* Run Button */
.run-btn {
  width: 100%;
  background: linear-gradient(135deg, #ff6b35, #f7931e);
  border: none;
  border-radius: 6px;
  padding: 14px;
  color: #000;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.run-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.run-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid transparent;
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Status Box */
.status-box {
  margin-top: 16px;
  padding: 12px;
  background: #1a1a1a;
  border-radius: 6px;
}

.status-text {
  font-size: 0.85rem;
  color: #aaa;
  margin-bottom: 8px;
}

.progress-bar {
  height: 4px;
  background: #333;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ff6b35, #f7931e);
  transition: width 0.3s;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #555;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 16px;
}

/* Results */
.results-content {
  height: calc(100vh - 200px);
  display: flex;
  flex-direction: column;
}

.result-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #222;
  padding-bottom: 12px;
  margin-bottom: 16px;
}

.tab-btn {
  background: transparent;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 8px 16px;
  color: #888;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  border-color: #555;
  color: #aaa;
}

.tab-btn.active {
  background: #ff6b35;
  border-color: #ff6b35;
  color: #000;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
}

.tab-pane {
  animation: fadeIn 0.3s;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Scenario Section */
.scenario-section {
  background: #1a1a1a;
  border: 1px solid #2a4a2a;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.scenario-section.risk {
  border-color: #4a2a2a;
}

.scenario-section h3 {
  font-size: 1rem;
  margin-bottom: 8px;
  color: #4ade80;
}

.scenario-section.risk h3 {
  color: #f87171;
}

.scenario-section p {
  font-size: 0.9rem;
  line-height: 1.6;
  color: #ccc;
}

.probability-badge {
  display: inline-block;
  margin-top: 12px;
  padding: 4px 10px;
  background: #222;
  border-radius: 4px;
  font-size: 0.8rem;
  color: #888;
}

/* Outlook Grid */
.outlook-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.outlook-card {
  background: #1a1a1a;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 16px;
}

.outlook-card h4 {
  font-size: 0.9rem;
  color: #888;
  margin-bottom: 12px;
}

.outlook-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid #222;
}

.outlook-item:last-child {
  border-bottom: none;
}

.asset-name {
  font-size: 0.85rem;
}

.outlook-value {
  font-size: 0.85rem;
  font-weight: 500;
}

.outlook-value.positive { color: #4ade80; }
.outlook-value.negative { color: #f87171; }
.outlook-value.neutral { color: #888; }

/* Agent Card */
.agent-card {
  background: #1a1a1a;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.agent-header .agent-name {
  font-weight: 600;
  color: #ff6b35;
}

.confidence-badge {
  font-size: 0.75rem;
  background: #222;
  padding: 4px 8px;
  border-radius: 4px;
  color: #888;
}

.agent-scenario pre {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 0.85rem;
  line-height: 1.6;
  white-space: pre-wrap;
  color: #ccc;
  margin: 0;
}

/* Analysis Section */
.analysis-section {
  margin-bottom: 20px;
}

.analysis-section h3 {
  font-size: 1rem;
  margin-bottom: 10px;
}

.analysis-section ul {
  list-style: none;
  padding: 0;
}

.analysis-section li {
  padding: 8px 12px;
  background: #1a1a1a;
  border-radius: 4px;
  margin-bottom: 6px;
  font-size: 0.9rem;
}

/* Report Content */
.report-content {
  font-size: 0.9rem;
  line-height: 1.8;
}

.report-content :deep(h1),
.report-content :deep(h2),
.report-content :deep(h3) {
  color: #fff;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

.report-content :deep(h1) { font-size: 1.5rem; }
.report-content :deep(h2) { font-size: 1.2rem; }
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
  border: 1px solid #333;
  padding: 8px 12px;
  text-align: left;
}

.report-content :deep(th) {
  background: #1a1a1a;
}

/* Scrollbar */
.tab-content::-webkit-scrollbar {
  width: 6px;
}

.tab-content::-webkit-scrollbar-track {
  background: #111;
}

.tab-content::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 3px;
}

.tab-content::-webkit-scrollbar-thumb:hover {
  background: #444;
}
</style>
