<template>
  <q-page class="backtest-page q-pa-lg">

    <!-- Cabeçalho -->
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <h5 class="q-ma-none text-neon-cyan" style="letter-spacing:2px;">BACKTEST</h5>
        <div class="text-caption text-muted">Simulação walk-forward em histórico real da Deriv</div>
      </div>
      <q-btn
        unelevated color="cyan" text-color="black" icon="play_arrow" label="Rodar Backtest"
        :loading="running" @click="runBacktest"
        style="font-weight:700;letter-spacing:1px;"
      />
    </div>

    <div class="row q-gutter-lg">

      <!-- ── Painel de parâmetros ── -->
      <div class="col-12 col-md-3">
        <div class="glass-card q-pa-lg">
          <div class="param-title q-mb-md">PARÂMETROS</div>

          <div class="param-row">
            <span class="param-label">Candles históricos</span>
            <q-slider v-model="params.count" :min="100" :max="1000" :step="50"
              color="cyan" label :label-value="params.count" dark />
          </div>
          <div class="param-row">
            <span class="param-label">Confiança mín. (%)</span>
            <q-slider v-model="params.min_confidence" :min="60" :max="95" :step="1"
              color="cyan" label :label-value="params.min_confidence + '%'" dark />
          </div>
          <div class="param-row">
            <span class="param-label">Score mín.</span>
            <q-slider v-model="params.min_score" :min="3" :max="9" :step="1"
              color="cyan" label :label-value="params.min_score" dark />
          </div>
          <div class="param-row">
            <span class="param-label">ADX mín.</span>
            <q-slider v-model="params.min_adx" :min="15" :max="35" :step="1"
              color="cyan" label :label-value="params.min_adx" dark />
          </div>
          <div class="param-row">
            <span class="param-label">Stake (USD)</span>
            <q-slider v-model="params.stake" :min="1" :max="50" :step="1"
              color="cyan" label :label-value="'$' + params.stake" dark />
          </div>

          <q-separator class="q-my-md" />
          <div class="text-caption text-muted q-mb-xs">Granularidade</div>
          <q-btn-toggle
            v-model="params.granularity"
            toggle-color="cyan" color="transparent" text-color="grey-6"
            dense unelevated
            :options="[
              {label:'M15',value:900},
              {label:'H1', value:3600},
            ]"
          />
        </div>
      </div>

      <!-- ── Resultados ── -->
      <div class="col">

        <!-- Cards de métricas -->
        <div class="row q-gutter-md q-mb-md" v-if="result">
          <div class="col">
            <div class="metric-card" :class="result.win_rate >= 55 ? 'card-green' : result.win_rate >= 45 ? 'card-amber' : 'card-red'">
              <div class="metric-label">WIN RATE</div>
              <div class="metric-value">{{ result.win_rate }}%</div>
              <div class="metric-sub">{{ result.wins }}W / {{ result.losses }}L</div>
            </div>
          </div>
          <div class="col">
            <div class="metric-card" :class="result.pnl >= 0 ? 'card-green' : 'card-red'">
              <div class="metric-label">P&L SIMULADO</div>
              <div class="metric-value">${{ result.pnl.toFixed(2) }}</div>
              <div class="metric-sub">{{ result.total_trades }} trades executados</div>
            </div>
          </div>
          <div class="col">
            <div class="metric-card">
              <div class="metric-label">MAX DRAWDOWN</div>
              <div class="metric-value text-neon-red">${{ result.max_drawdown.toFixed(2) }}</div>
              <div class="metric-sub">Profit Factor: {{ result.profit_factor }}</div>
            </div>
          </div>
          <div class="col">
            <div class="metric-card">
              <div class="metric-label">CONF. MÉDIA</div>
              <div class="metric-value text-neon-cyan">{{ result.avg_confidence }}%</div>
              <div class="metric-sub">Sharpe: {{ result.sharpe }}</div>
            </div>
          </div>
          <div class="col">
            <div class="metric-card">
              <div class="metric-label">SINAIS GERADOS</div>
              <div class="metric-value text-neon-purple">{{ result.total_signals }}</div>
              <div class="metric-sub">filtrados: {{ result.total_signals - result.total_trades }}</div>
            </div>
          </div>
        </div>

        <!-- Estado vazio -->
        <div v-if="!result && !running" class="empty-state">
          <q-icon name="query_stats" size="64px" style="color:var(--text-muted);opacity:0.3;" />
          <div class="text-subtitle1 text-muted q-mt-md">Ajuste os parâmetros e clique em Rodar Backtest</div>
          <div class="text-caption text-muted q-mt-xs">O backtest usa histórico real da Deriv (walk-forward)</div>
        </div>

        <!-- Loading -->
        <div v-if="running" class="empty-state">
          <q-spinner-grid color="cyan" size="48px" />
          <div class="text-subtitle1 text-neon-cyan q-mt-md">Analisando {{ params.count }} candles...</div>
          <div class="text-caption text-muted q-mt-xs">Simulando cada candle com o engine completo</div>
        </div>

        <!-- Curva de Equity -->
        <div v-if="result && result.equity_curve.length" class="glass-card q-mb-md">
          <div class="chart-header">
            <span class="text-caption text-secondary" style="letter-spacing:1.5px;">CURVA DE EQUITY</span>
            <q-badge
              :color="result.pnl >= 0 ? 'positive' : 'negative'"
              :label="(result.pnl >= 0 ? '+' : '') + '$' + result.pnl.toFixed(2)"
              rounded
            />
          </div>
          <div ref="equityChartEl" style="height:200px;" />
        </div>

        <!-- Breakdown por Sessão + Sinal -->
        <div v-if="result" class="row q-gutter-md q-mb-md">

          <!-- Por Sessão -->
          <div class="col-12 col-md-6">
            <div class="glass-card q-pa-md">
              <div class="param-title q-mb-sm">POR SESSÃO</div>
              <div v-if="Object.keys(result.by_session).length === 0" class="text-caption text-muted">
                Nenhum dado por sessão
              </div>
              <div v-for="(data, sess) in result.by_session" :key="sess" class="session-row">
                <div class="session-name">{{ sess }}</div>
                <div class="session-bar-wrap">
                  <div class="session-bar-fill" :style="{width: data.win_rate + '%', background: data.win_rate >= 55 ? 'var(--accent-green)' : data.win_rate >= 45 ? 'var(--accent-amber)' : 'var(--accent-red)'}"/>
                </div>
                <div class="session-stats">
                  <span :class="data.win_rate >= 55 ? 'text-neon-green' : data.win_rate >= 45 ? 'text-neon-amber' : 'text-neon-red'">
                    {{ data.win_rate }}%
                  </span>
                  <span class="text-muted"> · {{ data.trades }}t</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Por Sinal -->
          <div class="col-12 col-md-6">
            <div class="glass-card q-pa-md">
              <div class="param-title q-mb-sm">POR DIREÇÃO</div>
              <div v-for="(data, sig) in result.by_signal" :key="sig" class="session-row">
                <div class="session-name">
                  <q-icon :name="sig === 'BUY' ? 'trending_up' : 'trending_down'"
                    :color="sig === 'BUY' ? 'positive' : 'negative'" size="14px" />
                  {{ sig === 'BUY' ? 'SOBE' : 'DESCE' }}
                </div>
                <div class="session-bar-wrap">
                  <div class="session-bar-fill" :style="{width: data.win_rate + '%', background: data.win_rate >= 55 ? 'var(--accent-green)' : data.win_rate >= 45 ? 'var(--accent-amber)' : 'var(--accent-red)'}"/>
                </div>
                <div class="session-stats">
                  <span :class="data.win_rate >= 55 ? 'text-neon-green' : data.win_rate >= 45 ? 'text-neon-amber' : 'text-neon-red'">
                    {{ data.win_rate }}%
                  </span>
                  <span class="text-muted"> · {{ data.trades }}t · ${{ data.pnl.toFixed(2) }}</span>
                </div>
              </div>

              <template v-if="Object.keys(result.by_pattern).length">
                <div class="param-title q-mt-md q-mb-sm">POR PADRÃO</div>
                <div v-for="(data, pat) in result.by_pattern" :key="pat" class="session-row">
                  <div class="session-name" style="font-size:11px;">{{ pat }}</div>
                  <div class="session-bar-wrap">
                    <div class="session-bar-fill" :style="{width: data.win_rate + '%', background: data.win_rate >= 55 ? 'var(--accent-green)' : 'var(--accent-red)'}"/>
                  </div>
                  <div class="session-stats">
                    <span :class="data.win_rate >= 55 ? 'text-neon-green' : 'text-neon-red'">{{ data.win_rate }}%</span>
                    <span class="text-muted"> · {{ data.trades }}t</span>
                  </div>
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
import { ref, watch, nextTick } from 'vue'
import { api } from '../services/http'
import { createChart, ColorType, LineStyle } from 'lightweight-charts'

const running = ref(false)
const result  = ref<any>(null)
const equityChartEl = ref<HTMLElement | null>(null)
let equityChart: any = null

const params = ref({
  count:          300,
  min_confidence: 78,
  min_score:      5,
  min_adx:        22,
  stake:          6,
  granularity:    900,
})

async function runBacktest() {
  running.value = true
  result.value  = null
  equityChart?.remove()
  equityChart = null

  try {
    const res = await api.get('/backtest/run', { params: params.value, timeout: 120000 })
    result.value = res.data
    await nextTick()
    renderEquityChart()
  } catch (e: any) {
    console.error('Backtest error:', e)
  } finally {
    running.value = false
  }
}

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
      vertLines: { color: 'rgba(0,212,255,0.05)' },
      horzLines: { color: 'rgba(0,212,255,0.05)' },
    },
    rightPriceScale: { borderColor: 'rgba(0,212,255,0.1)' },
    timeScale:       { borderColor: 'rgba(0,212,255,0.1)', timeVisible: false },
    crosshair: {
      vertLine: { color: 'rgba(0,212,255,0.4)', style: LineStyle.Dashed },
      horzLine: { color: 'rgba(0,212,255,0.4)', style: LineStyle.Dashed },
    },
  })

  const areaSeries = equityChart.addAreaSeries({
    lineColor:        result.value.pnl >= 0 ? '#00FF88' : '#FF4466',
    topColor:         result.value.pnl >= 0 ? 'rgba(0,255,136,0.25)' : 'rgba(255,68,102,0.25)',
    bottomColor:      'rgba(0,0,0,0)',
    lineWidth:        2,
    priceLineVisible: false,
  })

  // Map equity curve: use trade index as "time" (integer sequence)
  const data = result.value.equity_curve.map((p: any, i: number) => ({
    time: i + 1,
    value: p.equity,
  }))

  areaSeries.setData(data)
  equityChart.timeScale().fitContent()

  const ro = new ResizeObserver(() => {
    if (equityChart && equityChartEl.value)
      equityChart.resize(equityChartEl.value.clientWidth, 200)
  })
  ro.observe(equityChartEl.value)
}

// Re-render chart if result changes
watch(result, async (val) => {
  if (val) { await nextTick(); renderEquityChart() }
})
</script>

<style lang="scss" scoped>
.backtest-page { background: var(--bg-deep); min-height: 100vh; }

.param-title {
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted); text-transform: uppercase;
}
.param-row {
  margin-bottom: 16px;
}
.param-label {
  display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;
}

// ── Metric cards ──
.metric-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 16px 18px;
  text-align: center;
  transition: border-color 0.3s;
  &.card-green { border-color: rgba(0,255,136,0.3); }
  &.card-red   { border-color: rgba(255,68,102,0.3); }
  &.card-amber { border-color: rgba(255,184,0,0.3); }
}
.metric-label {
  font-size: 9px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted); margin-bottom: 6px;
}
.metric-value {
  font-size: 26px; font-weight: 700;
  font-family: 'Roboto Mono', monospace;
  line-height: 1; color: var(--text-primary);
}
.metric-sub {
  font-size: 11px; color: var(--text-muted); margin-top: 4px;
}

// ── Chart header ──
.chart-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
}

// ── Empty state ──
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 60px 24px;
  margin-bottom: 16px;
  text-align: center;
}

// ── Session breakdown ──
.session-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  &:last-child { border-bottom: none; }
}
.session-name {
  font-size: 11px; color: var(--text-secondary);
  width: 140px; flex-shrink: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.session-bar-wrap {
  flex: 1; height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden;
}
.session-bar-fill {
  height: 100%; border-radius: 2px; transition: width 0.8s ease;
}
.session-stats {
  font-size: 11px; font-weight: 600; white-space: nowrap;
}

.text-muted    { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }
</style>
