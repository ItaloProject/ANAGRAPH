<template>
  <q-page class="backtest-page">

    <!-- ── Toolbar ── -->
    <div class="bt-toolbar">
      <div>
        <div class="text-weight-bold text-neon-cyan" style="font-size:18px;letter-spacing:3px;">BACKTEST</div>
        <div class="text-caption text-muted">Simulação walk-forward em histórico real da Deriv</div>
      </div>
      <q-btn
        unelevated :color="running ? 'grey-8' : 'cyan'" text-color="black"
        :icon="running ? 'hourglass_empty' : 'play_arrow'"
        :label="running ? `Analisando ${params.count} candles...` : 'Rodar Backtest'"
        :loading="running"
        @click="runBacktest"
        style="font-weight:700;letter-spacing:1px;"
      />
    </div>

    <div class="bt-body">

      <!-- ── Parâmetros (lateral no desktop, accordion no mobile) ── -->
      <div class="bt-params-col">
        <div class="params-card">
          <div class="params-title">PARÂMETROS</div>

          <div class="param-block">
            <div class="param-row-label">
              <span>Candles históricos</span>
              <span class="param-val text-neon-cyan">{{ params.count }}</span>
            </div>
            <q-slider v-model="params.count" :min="100" :max="2000" :step="100" color="cyan" dark />
            <div class="text-caption text-muted" style="font-size:9px;margin-top:2px;">
              ≈ {{ Math.round(params.count * params.granularity / 86400) }} dias de histórico
            </div>
          </div>

          <div class="param-block">
            <div class="param-row-label">
              <span>Confiança mín.</span>
              <span class="param-val text-neon-cyan">{{ params.min_confidence }}%</span>
            </div>
            <q-slider v-model="params.min_confidence" :min="60" :max="95" :step="1" color="cyan" dark />
          </div>

          <div class="param-block">
            <div class="param-row-label">
              <span>Score mín.</span>
              <span class="param-val text-neon-cyan">{{ params.min_score }}</span>
            </div>
            <q-slider v-model="params.min_score" :min="3" :max="9" :step="1" color="cyan" dark />
          </div>

          <div class="param-block">
            <div class="param-row-label">
              <span>ADX mín.</span>
              <span class="param-val text-neon-cyan">{{ params.min_adx }}</span>
            </div>
            <q-slider v-model="params.min_adx" :min="15" :max="35" :step="1" color="cyan" dark />
          </div>

          <div class="param-block">
            <div class="param-row-label">
              <span>Stake (USD)</span>
              <span class="param-val text-neon-cyan">${{ params.stake }}</span>
            </div>
            <q-slider v-model="params.stake" :min="1" :max="50" :step="1" color="cyan" dark />
          </div>

          <q-separator dark class="q-my-md" />

          <div class="param-row-label q-mb-xs">
            <span class="text-muted" style="font-size:10px;letter-spacing:1px;">GRANULARIDADE</span>
          </div>
          <q-btn-toggle
            v-model="params.granularity"
            toggle-color="cyan" color="transparent" text-color="grey-6"
            dense unelevated
            :options="[{label:'M15',value:900},{label:'H1',value:3600}]"
          />

          <q-separator dark class="q-my-md" />

          <!-- MTF toggle -->
          <div class="row items-center justify-between q-mb-sm">
            <div>
              <div class="param-row-label" style="margin-bottom:0;">
                <span>Fidelidade MTF</span>
              </div>
              <div class="text-caption text-muted" style="font-size:9px;">H1/H4 + DXY (igual ao bot)</div>
            </div>
            <q-toggle v-model="params.use_mtf" color="cyan" dense />
          </div>

          <!-- Grid search -->
          <q-btn
            outline color="purple" text-color="purple"
            icon="tune" label="Otimizar (Grid)"
            :loading="gridRunning"
            class="full-width q-mt-sm"
            size="sm"
            @click="runGrid"
            style="font-weight:600;letter-spacing:0.5px;"
          />

          <!-- Dica -->
          <div class="param-hint q-mt-md">
            <q-icon name="info_outline" size="13px" />
            {{ params.use_mtf
              ? 'MTF on: usa analyze_mtf com H1/H4 e DXY — fiel ao bot ao vivo.'
              : 'MTF off: só o timeframe primário (mais sinais, menos preciso).' }}
            Fluxo de ticks, notícias e IA são camadas ao vivo (não entram no backtest).
          </div>
        </div>
      </div>

      <!-- ── Área de resultados ── -->
      <div class="bt-results-col">

        <!-- Estado vazio -->
        <div v-if="!result && !running && !gridResult && !gridRunning" class="bt-empty">
          <q-icon name="query_stats" size="56px" style="opacity:.2;" />
          <div class="text-muted q-mt-md" style="font-size:15px;">Configure os parâmetros e clique em Rodar</div>
          <div class="text-caption text-muted q-mt-xs">Histórico real da Deriv via walk-forward</div>
        </div>

        <!-- Loading -->
        <div v-else-if="running" class="bt-empty">
          <q-spinner-grid color="cyan" size="52px" />
          <div class="text-neon-cyan q-mt-md" style="font-size:15px;font-weight:700;">
            Analisando {{ params.count }} candles...
          </div>
          <div class="text-caption text-muted q-mt-xs">Simulando confluência de indicadores em cada vela</div>
        </div>

        <!-- Grid search: loading -->
        <div v-if="gridRunning" class="bt-empty">
          <q-spinner-gears color="purple" size="52px" />
          <div class="text-neon-purple q-mt-md" style="font-size:15px;font-weight:700;">
            Otimizando parâmetros...
          </div>
          <div class="text-caption text-muted q-mt-xs">Testando combinações de score × ADX × confiança</div>
        </div>

        <!-- Grid search: resultado -->
        <div v-if="gridResult && !gridRunning" class="grid-card q-mb-md">
          <div class="grid-header">
            <span class="text-caption text-secondary" style="letter-spacing:1.5px;">
              OTIMIZAÇÃO — {{ gridResult.total_combos }} COMBINAÇÕES
            </span>
            <q-btn flat dense size="sm" icon="close" color="grey-6" @click="gridResult = null" />
          </div>

          <div v-if="gridResult.best" class="grid-best">
            <div class="row items-center justify-between">
              <div>
                <div class="text-caption text-muted" style="font-size:9px;letter-spacing:1px;">MELHOR COMBINAÇÃO</div>
                <div class="text-weight-bold text-neon-green" style="font-size:13px;">
                  Score {{ gridResult.best.min_score }} · ADX {{ gridResult.best.min_adx }} · Conf {{ gridResult.best.min_confidence }}%
                </div>
                <div class="text-caption text-muted">
                  {{ gridResult.best.trades }} trades · WR {{ gridResult.best.win_rate }}% ·
                  PF {{ gridResult.best.profit_factor }}
                </div>
              </div>
              <q-btn
                unelevated color="positive" text-color="black" size="sm"
                icon="check" label="Aplicar"
                @click="applyBest"
                style="font-weight:700;"
              />
            </div>
          </div>

          <div class="grid-table-wrap">
            <table class="grid-table">
              <thead>
                <tr>
                  <th>Score</th><th>ADX</th><th>Conf</th>
                  <th>Trades</th><th>WR</th><th>P&L</th><th>PF</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(c, i) in gridResult.combos" :key="i"
                  :class="{ 'grid-row-best': i === 0 && c.trades >= 10, 'grid-row-thin': c.trades < 10 }">
                  <td>{{ c.min_score }}</td>
                  <td>{{ c.min_adx }}</td>
                  <td>{{ c.min_confidence }}%</td>
                  <td>{{ c.trades }}</td>
                  <td :class="c.win_rate >= 55 ? 'text-neon-green' : c.win_rate >= 45 ? 'text-neon-amber' : 'text-neon-red'">
                    {{ c.win_rate }}%
                  </td>
                  <td :class="c.pnl >= 0 ? 'text-neon-green' : 'text-neon-red'" class="font-mono">
                    {{ c.pnl >= 0 ? '+' : '' }}{{ c.pnl.toFixed(1) }}
                  </td>
                  <td>{{ c.profit_factor }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="text-caption text-muted q-pa-sm" style="font-size:9px;">
            Combinações com menos de 10 trades aparecem esmaecidas (amostra pequena).
          </div>
        </div>

        <!-- Métricas: 2-por-linha mobile / 5 em linha desktop -->
        <div v-if="result" class="row q-col-gutter-md q-mb-md">

          <div class="col-6 col-sm-4 col-md">
            <div class="metric-card" :class="result.win_rate >= 55 ? 'mc-green' : result.win_rate >= 45 ? 'mc-amber' : 'mc-red'">
              <div class="mc-label">WIN RATE</div>
              <div class="mc-val">{{ result.win_rate }}%</div>
              <div class="mc-sub">{{ result.wins }}W / {{ result.losses }}L</div>
              <div class="mc-bar-wrap">
                <div class="mc-bar" :style="{
                  width: result.win_rate + '%',
                  background: result.win_rate >= 55 ? 'var(--accent-green)' : result.win_rate >= 45 ? 'var(--accent-amber)' : 'var(--accent-red)'
                }" />
              </div>
            </div>
          </div>

          <div class="col-6 col-sm-4 col-md">
            <div class="metric-card" :class="result.pnl >= 0 ? 'mc-green' : 'mc-red'">
              <div class="mc-label">P&L SIMULADO</div>
              <div class="mc-val font-mono">${{ result.pnl.toFixed(2) }}</div>
              <div class="mc-sub">{{ result.total_trades }} trades</div>
            </div>
          </div>

          <div class="col-6 col-sm-4 col-md">
            <div class="metric-card mc-red-soft">
              <div class="mc-label">MAX DRAWDOWN</div>
              <div class="mc-val font-mono text-neon-red">${{ result.max_drawdown.toFixed(2) }}</div>
              <div class="mc-sub">Profit factor: {{ result.profit_factor }}</div>
            </div>
          </div>

          <div class="col-6 col-sm-4 col-md">
            <div class="metric-card">
              <div class="mc-label">CONF. MÉDIA</div>
              <div class="mc-val text-neon-cyan">{{ result.avg_confidence }}%</div>
              <div class="mc-sub">Sharpe: {{ result.sharpe }}</div>
            </div>
          </div>

          <div class="col-6 col-sm-4 col-md">
            <div class="metric-card">
              <div class="mc-label">SINAIS</div>
              <div class="mc-val text-neon-purple">{{ result.total_signals }}</div>
              <div class="mc-sub">filtrados: {{ result.total_signals - result.total_trades }}</div>
            </div>
          </div>
        </div>

        <!-- Curva de equity -->
        <div v-if="result && result.equity_curve.length" class="equity-card q-mb-md">
          <div class="equity-header">
            <span class="text-caption text-secondary" style="letter-spacing:1.5px;">CURVA DE EQUITY</span>
            <q-badge
              :color="result.pnl >= 0 ? 'positive' : 'negative'"
              :label="(result.pnl >= 0 ? '+' : '') + '$' + result.pnl.toFixed(2)"
              rounded
            />
          </div>
          <div ref="equityChartEl" style="height:200px;" />
        </div>

        <!-- Breakdown: sessão + direção + padrão -->
        <div v-if="result" class="row q-col-gutter-md">

          <div class="col-12 col-md-6">
            <div class="breakdown-card">
              <div class="bd-title">POR SESSÃO</div>
              <div v-if="!Object.keys(result.by_session).length" class="text-caption text-muted q-pa-sm">Sem dados</div>
              <div v-for="(data, sess) in result.by_session" :key="sess" class="bd-row">
                <span class="bd-name">{{ sess }}</span>
                <div class="bd-bar-wrap">
                  <div class="bd-bar-fill" :style="{
                    width: data.win_rate + '%',
                    background: data.win_rate >= 55 ? 'var(--accent-green)' : data.win_rate >= 45 ? 'var(--accent-amber)' : 'var(--accent-red)'
                  }" />
                </div>
                <span class="bd-stat" :class="data.win_rate >= 55 ? 'text-neon-green' : data.win_rate >= 45 ? 'text-neon-amber' : 'text-neon-red'">
                  {{ data.win_rate }}%
                </span>
                <span class="bd-trades text-muted">{{ data.trades }}t</span>
              </div>
            </div>
          </div>

          <div class="col-12 col-md-6">
            <div class="breakdown-card">
              <div class="bd-title">POR DIREÇÃO</div>
              <div v-for="(data, sig) in result.by_signal" :key="sig" class="bd-row">
                <span class="bd-name row items-center gap-1">
                  <q-icon :name="sig === 'BUY' ? 'trending_up' : 'trending_down'"
                    :color="sig === 'BUY' ? 'positive' : 'negative'" size="13px" />
                  {{ sig === 'BUY' ? 'SOBE' : 'DESCE' }}
                </span>
                <div class="bd-bar-wrap">
                  <div class="bd-bar-fill" :style="{
                    width: data.win_rate + '%',
                    background: data.win_rate >= 55 ? 'var(--accent-green)' : 'var(--accent-red)'
                  }" />
                </div>
                <span class="bd-stat" :class="data.win_rate >= 55 ? 'text-neon-green' : 'text-neon-red'">
                  {{ data.win_rate }}%
                </span>
                <span class="bd-trades text-muted">${{ data.pnl.toFixed(1) }}</span>
              </div>

              <template v-if="Object.keys(result.by_pattern).length">
                <div class="bd-title q-mt-md">POR PADRÃO</div>
                <div v-for="(data, pat) in result.by_pattern" :key="pat" class="bd-row">
                  <span class="bd-name" style="font-size:11px;">{{ pat }}</span>
                  <div class="bd-bar-wrap">
                    <div class="bd-bar-fill" :style="{
                      width: data.win_rate + '%',
                      background: data.win_rate >= 55 ? 'var(--accent-green)' : 'var(--accent-red)'
                    }" />
                  </div>
                  <span class="bd-stat" :class="data.win_rate >= 55 ? 'text-neon-green' : 'text-neon-red'">
                    {{ data.win_rate }}%
                  </span>
                  <span class="bd-trades text-muted">{{ data.trades }}t</span>
                </div>
              </template>
            </div>
          </div>
        </div>

      </div>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { api } from '../services/http'
import { createChart, ColorType, LineStyle } from 'lightweight-charts'

const running = ref(false)
const result  = ref<any>(null)
const gridRunning = ref(false)
const gridResult  = ref<any>(null)
const equityChartEl = ref<HTMLElement | null>(null)
let equityChart: any = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const LS_BT_JOB   = 'anagraph_bt_job_id'
const LS_GRID_JOB = 'anagraph_grid_job_id'
const LS_BT_RES   = 'anagraph_bt_result'
const LS_GRID_RES = 'anagraph_grid_result'

const params = ref({
  count:          500,
  min_confidence: 78,
  min_score:      5,
  min_adx:        20,
  stake:          6,
  granularity:    900,
  use_mtf:        true,
})

// ── Polling ───────────────────────────────────────────────────────────────────

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function pollJob(jobId: string, type: 'backtest' | 'grid') {
  try {
    const res = await api.get(`/backtest/status/${jobId}`)
    const job = res.data

    if (job.status === 'done') {
      stopPolling()
      if (type === 'backtest') {
        running.value = false
        result.value  = job.result
        localStorage.removeItem(LS_BT_JOB)
        localStorage.setItem(LS_BT_RES, JSON.stringify(job.result))
        await nextTick()
        renderEquityChart()
      } else {
        gridRunning.value = false
        gridResult.value  = job.result
        localStorage.removeItem(LS_GRID_JOB)
        localStorage.setItem(LS_GRID_RES, JSON.stringify(job.result))
      }
    } else if (job.status === 'error') {
      stopPolling()
      if (type === 'backtest') { running.value = false; localStorage.removeItem(LS_BT_JOB) }
      else { gridRunning.value = false; localStorage.removeItem(LS_GRID_JOB) }
      console.error(`Job ${jobId} error:`, job.error)
    }
  } catch (e: any) {
    if (e?.response?.status === 404) {
      // Job expirou no servidor (reinicio) — limpa estado
      stopPolling()
      if (type === 'backtest') { running.value = false; localStorage.removeItem(LS_BT_JOB) }
      else { gridRunning.value = false; localStorage.removeItem(LS_GRID_JOB) }
    }
  }
}

function startPolling(jobId: string, type: 'backtest' | 'grid') {
  stopPolling()
  pollJob(jobId, type)                                      // primeira chamada imediata
  pollTimer = setInterval(() => pollJob(jobId, type), 2000) // depois a cada 2s
}

// ── Ações ─────────────────────────────────────────────────────────────────────

async function runBacktest() {
  running.value = true
  result.value  = null
  equityChart?.remove()
  equityChart = null
  localStorage.removeItem(LS_BT_RES)

  try {
    const res = await api.get('/backtest/start', { params: params.value })
    const jobId = res.data.job_id
    localStorage.setItem(LS_BT_JOB, jobId)
    startPolling(jobId, 'backtest')
  } catch (e: any) {
    console.error('Backtest start error:', e)
    running.value = false
  }
}

async function runGrid() {
  gridRunning.value = true
  gridResult.value  = null
  localStorage.removeItem(LS_GRID_RES)

  try {
    const res = await api.get('/backtest/grid/start', {
      params: {
        granularity: params.value.granularity,
        count:       params.value.count,
        stake:       params.value.stake,
        use_mtf:     params.value.use_mtf,
      },
    })
    const jobId = res.data.job_id
    localStorage.setItem(LS_GRID_JOB, jobId)
    startPolling(jobId, 'grid')
  } catch (e: any) {
    console.error('Grid start error:', e)
    gridRunning.value = false
  }
}

function applyBest() {
  const b = gridResult.value?.best
  if (!b) return
  params.value.min_score      = b.min_score
  params.value.min_adx        = b.min_adx
  params.value.min_confidence = b.min_confidence
  gridResult.value = null
  runBacktest()
}

// ── Lifecycle — retoma job pendente ao voltar para a página ──────────────────

onMounted(async () => {
  // Restaura último resultado salvo (se houver)
  const savedBt   = localStorage.getItem(LS_BT_RES)
  const savedGrid = localStorage.getItem(LS_GRID_RES)
  if (savedBt)   { result.value     = JSON.parse(savedBt);   await nextTick(); renderEquityChart() }
  if (savedGrid) { gridResult.value = JSON.parse(savedGrid) }

  // Retoma polling se havia job em andamento
  const btJob   = localStorage.getItem(LS_BT_JOB)
  const gridJob = localStorage.getItem(LS_GRID_JOB)
  if (btJob)   { running.value     = true;  startPolling(btJob,   'backtest') }
  if (gridJob) { gridRunning.value = true;  startPolling(gridJob, 'grid') }
})

onUnmounted(() => {
  stopPolling()   // limpa timer ao sair, mas o job continua no servidor
})

function renderEquityChart() {
  if (!equityChartEl.value || !result.value?.equity_curve?.length) return

  equityChart = createChart(equityChartEl.value, {
    width:  equityChartEl.value.clientWidth,
    height: 200,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#8A9BBE',
    },
    grid: {
      vertLines: { color: 'rgba(0,212,255,0.04)' },
      horzLines: { color: 'rgba(0,212,255,0.04)' },
    },
    rightPriceScale: { borderColor: 'rgba(0,212,255,0.08)' },
    timeScale:       { borderColor: 'rgba(0,212,255,0.08)', timeVisible: false },
    crosshair: {
      vertLine: { color: 'rgba(0,212,255,0.4)', style: LineStyle.Dashed },
      horzLine: { color: 'rgba(0,212,255,0.4)', style: LineStyle.Dashed },
    },
  })

  const areaSeries = equityChart.addAreaSeries({
    lineColor:        result.value.pnl >= 0 ? '#00FF88' : '#FF4466',
    topColor:         result.value.pnl >= 0 ? 'rgba(0,255,136,0.2)' : 'rgba(255,68,102,0.2)',
    bottomColor:      'rgba(0,0,0,0)',
    lineWidth:        2,
    priceLineVisible: false,
  })

  areaSeries.setData(
    result.value.equity_curve.map((p: any, i: number) => ({ time: i + 1, value: p.equity }))
  )
  equityChart.timeScale().fitContent()

  const ro = new ResizeObserver(() => {
    if (equityChart && equityChartEl.value)
      equityChart.resize(equityChartEl.value.clientWidth, 200)
  })
  ro.observe(equityChartEl.value)
}

watch(result, async (val) => {
  if (val) { await nextTick(); renderEquityChart() }
})
</script>

<style lang="scss" scoped>
.backtest-page {
  background: var(--bg-deep);
  min-height: 100vh;
}

.font-mono { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.gap-1 { gap: 4px; }

// ── Toolbar ───────────────────────────────────────────────────────────────────
.bt-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-surface);

  @media (max-width: 599px) { padding: 12px; }
}

// ── Layout ────────────────────────────────────────────────────────────────────
.bt-body {
  display: flex;
  gap: 20px;
  padding: 20px;
  align-items: flex-start;

  @media (max-width: 1023px) {
    flex-direction: column;
    padding: 14px;
    gap: 14px;
  }
  @media (max-width: 599px) { padding: 10px; gap: 10px; }
}

.bt-params-col {
  width: 260px;
  flex-shrink: 0;
  @media (max-width: 1023px) { width: 100%; }
}

.bt-results-col {
  flex: 1;
  min-width: 0;
}

// ── Params card ───────────────────────────────────────────────────────────────
.params-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 18px 20px;

  @media (max-width: 1023px) {
    // Horizontal sliders on tablet
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 20px;
    .params-title { grid-column: 1 / -1; }
    .q-separator  { grid-column: 1 / -1; }
    > :last-child  { grid-column: 1 / -1; }
  }
  @media (max-width: 599px) {
    grid-template-columns: 1fr;
  }
}

.params-title {
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted);
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 16px;
}

.param-block { margin-bottom: 16px; }

.param-row-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.param-val { font-family: 'Roboto Mono', monospace; font-weight: 700; }

.param-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.4;
  padding: 8px 10px;
  background: rgba(0,0,0,0.15);
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
}

// ── Empty state ───────────────────────────────────────────────────────────────
.bt-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 60px 24px;
  margin-bottom: 16px;
  text-align: center;
  min-height: 220px;
}

// ── Metric cards ──────────────────────────────────────────────────────────────
.metric-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 14px 16px;
  text-align: center;
  transition: border-color 0.2s;
  &:hover { border-color: var(--border-glow); }

  &.mc-green     { border-color: rgba(0,255,136,0.3); }
  &.mc-amber     { border-color: rgba(255,184,0,0.3); }
  &.mc-red       { border-color: rgba(255,68,102,0.3); }
  &.mc-red-soft  { border-color: rgba(255,68,102,0.15); }

  @media (max-width: 599px) { padding: 12px; border-radius: 10px; }
}
.mc-label { font-size: 9px; font-weight: 700; letter-spacing: 2px; color: var(--text-muted); margin-bottom: 6px; }
.mc-val   { font-size: 24px; font-weight: 700; line-height: 1; color: var(--text-primary); @media (max-width: 599px) { font-size: 20px; } }
.mc-sub   { font-size: 10px; color: var(--text-muted); margin-top: 4px; }
.mc-bar-wrap { height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; margin-top: 8px; }
.mc-bar  { height: 100%; border-radius: 2px; transition: width 0.8s ease; }

// ── Grid search card ──────────────────────────────────────────────────────────
.grid-card {
  background: var(--bg-surface);
  border: 1px solid rgba(149,76,233,0.25);
  border-radius: 14px;
  overflow: hidden;
}
.grid-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
}
.grid-best {
  padding: 12px 16px;
  background: rgba(0,255,136,0.05);
  border-bottom: 1px solid var(--border-subtle);
}
.grid-table-wrap { overflow-x: auto; }
.grid-table {
  width: 100%; border-collapse: collapse; font-size: 11px;
  th {
    text-align: center; padding: 8px 6px; font-size: 9px; letter-spacing: 1px;
    color: var(--text-muted); border-bottom: 1px solid var(--border-subtle);
    position: sticky; top: 0; background: var(--bg-surface);
  }
  td {
    text-align: center; padding: 7px 6px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    color: var(--text-secondary);
  }
  .font-mono { font-family: 'Roboto Mono', monospace; font-weight: 600; }
}
.grid-row-best { background: rgba(0,255,136,0.07); td { font-weight: 700; } }
.grid-row-thin { opacity: 0.4; }

// ── Equity card ───────────────────────────────────────────────────────────────
.equity-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  overflow: hidden;
}
.equity-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
}

// ── Breakdown cards ───────────────────────────────────────────────────────────
.breakdown-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 16px;
  height: 100%;
}
.bd-title {
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-subtle);
}
.bd-row {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  &:last-child { border-bottom: none; }
}
.bd-name   { font-size: 11px; color: var(--text-secondary); width: 100px; flex-shrink: 0; }
.bd-bar-wrap { flex: 1; height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
.bd-bar-fill { height: 100%; border-radius: 2px; transition: width 0.8s ease; }
.bd-stat   { font-size: 11px; font-weight: 700; width: 36px; text-align: right; flex-shrink: 0; }
.bd-trades { font-size: 10px; width: 48px; text-align: right; flex-shrink: 0; }
</style>
