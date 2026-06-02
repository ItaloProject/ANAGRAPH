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
            <q-slider v-model="params.count" :min="100" :max="1000" :step="50" color="cyan" dark />
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

          <!-- Dica -->
          <div class="param-hint q-mt-md">
            <q-icon name="info_outline" size="13px" />
            O backtest simula cada candle com o engine completo — mesmo critério do bot ao vivo.
          </div>
        </div>
      </div>

      <!-- ── Área de resultados ── -->
      <div class="bt-results-col">

        <!-- Estado vazio -->
        <div v-if="!result && !running" class="bt-empty">
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
