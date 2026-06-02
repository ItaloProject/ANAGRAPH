<template>
  <q-page class="chart-page">

    <!-- ── Toolbar ── -->
    <div class="chart-toolbar">

      <!-- Ativo + status -->
      <div class="row items-center gap-2">
        <div class="live-dot" />
        <span class="text-weight-bold text-neon-cyan" style="font-size:15px;letter-spacing:1px;">
          {{ market.activeAsset }}
        </span>
        <span class="text-caption text-muted">FOREX</span>
      </div>

      <!-- OHLC info (crosshair ou último candle) -->
      <div class="ohlc-bar row items-center gap-2 gt-xs">
        <span class="ohlc-item">
          <span class="ohlc-label">O</span>
          <span class="ohlc-val">{{ ohlc.open }}</span>
        </span>
        <span class="ohlc-item">
          <span class="ohlc-label">H</span>
          <span class="ohlc-val text-neon-green">{{ ohlc.high }}</span>
        </span>
        <span class="ohlc-item">
          <span class="ohlc-label">L</span>
          <span class="ohlc-val text-neon-red">{{ ohlc.low }}</span>
        </span>
        <span class="ohlc-item">
          <span class="ohlc-label">C</span>
          <span class="ohlc-val" :class="ohlcCloseColor">{{ ohlc.close }}</span>
        </span>
      </div>

      <!-- Timeframe + indicadores -->
      <div class="row items-center gap-2">
        <div class="tf-group">
          <button
            v-for="tf in timeframes" :key="tf.value"
            class="tf-btn"
            :class="{ 'tf-active': timeframe === tf.value }"
            @click="timeframe = tf.value"
          >{{ tf.label }}</button>
        </div>

        <div class="ind-group gt-sm">
          <button class="ind-btn" :class="{ 'ind-active-ema': showEMA }" @click="showEMA = !showEMA">EMA</button>
          <button class="ind-btn" :class="{ 'ind-active-bb': showBB }"   @click="showBB  = !showBB">BB</button>
          <button class="ind-btn" :class="{ 'ind-active-vol': showVol }" @click="showVol = !showVol">VOL</button>
        </div>
      </div>
    </div>

    <!-- ── Preço atual grande ── -->
    <div class="price-strip">
      <span class="current-price font-mono" :class="market.priceChange >= 0 ? 'text-neon-green' : 'text-neon-red'">
        {{ market.currentPrice.toFixed(5) }}
      </span>
      <span class="price-change" :class="market.priceChange >= 0 ? 'text-neon-green' : 'text-neon-red'">
        {{ market.priceChange >= 0 ? '▲' : '▼' }}
        {{ Math.abs(market.priceChange * 10000).toFixed(1) }} pips
      </span>
      <div class="row items-center gap-2 q-ml-auto">
        <!-- EMA legend -->
        <span v-if="showEMA" class="legend-dot" style="background:#00D4FF;" />
        <span v-if="showEMA" class="legend-label text-neon-cyan">EMA 9</span>
        <span v-if="showEMA" class="legend-dot" style="background:#8B5CF6;" />
        <span v-if="showEMA" class="legend-label text-neon-purple">EMA 21</span>
        <!-- BB legend -->
        <span v-if="showBB" class="legend-dot" style="background:rgba(255,184,0,0.7);" />
        <span v-if="showBB" class="legend-label text-neon-amber">BB (20)</span>
      </div>
    </div>

    <!-- ── Gráfico principal ── -->
    <div class="chart-main-wrap">
      <FullChart
        :candles="aggregatedCandles"
        :height="chartHeight"
        :show-e-m-a="showEMA"
        :show-b-b="showBB"
        :show-volume="showVol"
        :trades="bot.trades"
      />
    </div>

    <!-- ── Painel de indicadores (abaixo do gráfico, mobile-friendly) ── -->
    <div class="ind-panel row q-col-gutter-sm q-mt-sm">

      <div class="col-6 col-sm-3">
        <div class="ind-card">
          <span class="ind-name">RSI (14)</span>
          <span class="ind-val" :class="rsiColor">{{ market.liveIndicators.rsi.toFixed(1) }}</span>
          <span class="ind-sub">
            {{ market.liveIndicators.rsi < 30 ? 'Sobrevendido' : market.liveIndicators.rsi > 70 ? 'Sobrecomprado' : 'Neutro' }}
          </span>
        </div>
      </div>

      <div class="col-6 col-sm-3">
        <div class="ind-card">
          <span class="ind-name">MACD</span>
          <span class="ind-val font-mono" :class="market.liveIndicators.macd > market.liveIndicators.macd_signal ? 'text-neon-green' : 'text-neon-red'">
            {{ market.liveIndicators.macd > 0 ? '+' : '' }}{{ market.liveIndicators.macd.toFixed(5) }}
          </span>
          <span class="ind-sub text-muted">Signal: {{ market.liveIndicators.macd_signal.toFixed(5) }}</span>
        </div>
      </div>

      <div class="col-6 col-sm-3">
        <div class="ind-card">
          <span class="ind-name">ADX</span>
          <span class="ind-val" :class="market.liveIndicators.adx >= 25 ? 'text-neon-green' : 'text-neon-amber'">
            {{ market.liveIndicators.adx.toFixed(1) }}
          </span>
          <span class="ind-sub">{{ market.liveIndicators.adx >= 25 ? 'Tendência forte' : 'Mercado lateral' }}</span>
        </div>
      </div>

      <div class="col-6 col-sm-3">
        <div class="ind-card">
          <span class="ind-name">ATR × ratio</span>
          <span class="ind-val text-neon-cyan">{{ market.liveIndicators.atr_ratio.toFixed(2) }}×</span>
          <span class="ind-sub">
            EMA 9: <span class="font-mono" style="font-size:10px;">{{ market.liveIndicators.ema9.toFixed(5) }}</span>
          </span>
        </div>
      </div>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuasar } from 'quasar'
import { useMarketStore } from 'stores/market'
import { useBotStore } from 'stores/bot'
import FullChart from 'components/FullChart.vue'
import type { Candle } from 'stores/market'

const $q     = useQuasar()
const market = useMarketStore()
const bot    = useBotStore()

const timeframe = ref('1')
const showEMA   = ref(true)
const showBB    = ref(true)
const showVol   = ref(true)

const timeframes = [
  { label: 'M1',  value: '1'  },
  { label: 'M5',  value: '5'  },
  { label: 'M15', value: '15' },
  { label: 'H1',  value: '60' },
]

// Altura responsiva do gráfico
const chartHeight = computed(() =>
  $q.screen.lt.sm ? 260 : $q.screen.lt.md ? 340 : 460
)

// Agrega velas M1 em M5/M15/H1
function aggregateCandles(candles: Candle[], minutes: number): Candle[] {
  if (minutes === 1) return candles
  const bucket = minutes * 60
  const result: Candle[] = []
  for (const c of candles) {
    const t = Math.floor(c.time / bucket) * bucket
    const last = result[result.length - 1]
    if (last && last.time === t) {
      last.high  = Math.max(last.high,  c.high)
      last.low   = Math.min(last.low,   c.low)
      last.close = c.close
      if (c.volume) last.volume = (last.volume ?? 0) + c.volume
    } else {
      result.push({ ...c, time: t })
    }
  }
  return result
}

const aggregatedCandles = computed(() =>
  aggregateCandles(market.candles, parseInt(timeframe.value))
)

// OHLC do último candle
const lastCandle = computed(() => {
  const c = aggregatedCandles.value
  return c[c.length - 1]
})
const ohlc = computed(() => ({
  open:  lastCandle.value?.open.toFixed(5)  ?? '—',
  high:  lastCandle.value?.high.toFixed(5)  ?? '—',
  low:   lastCandle.value?.low.toFixed(5)   ?? '—',
  close: lastCandle.value?.close.toFixed(5) ?? '—',
}))
const ohlcCloseColor = computed(() => {
  const c = lastCandle.value
  if (!c) return ''
  return c.close >= c.open ? 'text-neon-green' : 'text-neon-red'
})

// Cores indicadores
const rsiColor = computed(() => {
  const r = market.liveIndicators.rsi
  return r < 30 ? 'text-neon-green' : r > 70 ? 'text-neon-red' : 'text-neon-cyan'
})
</script>

<style lang="scss" scoped>
.chart-page {
  background: var(--bg-deep);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.font-mono { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.gap-2 { gap: 8px; }

// ── Toolbar ──────────────────────────────────────────────────────────────────
.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);

  @media (max-width: 599px) { padding: 8px 12px; }
}

// OHLC
.ohlc-bar { gap: 10px; }
.ohlc-item { display: flex; align-items: center; gap: 4px; }
.ohlc-label { font-size: 10px; color: var(--text-muted); font-weight: 700; }
.ohlc-val   { font-size: 11px; font-family: 'Roboto Mono', monospace; font-weight: 600; }

// Timeframe
.tf-group {
  display: flex;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow: hidden;
}
.tf-btn {
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 700;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: 0.5px;

  &:hover { color: var(--text-primary); }
  &.tf-active {
    background: var(--accent-cyan);
    color: var(--bg-deep);
  }
}

// Indicator toggles
.ind-group {
  display: flex;
  gap: 4px;
}
.ind-btn {
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  background: rgba(0,0,0,0.2);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;

  &:hover { color: var(--text-primary); }
  &.ind-active-ema { border-color: #00D4FF; color: #00D4FF; background: rgba(0,212,255,0.08); }
  &.ind-active-bb  { border-color: #FFB800; color: #FFB800; background: rgba(255,184,0,0.08); }
  &.ind-active-vol { border-color: rgba(255,255,255,0.3); color: var(--text-secondary); background: rgba(255,255,255,0.04); }
}

// ── Price strip ───────────────────────────────────────────────────────────────
.price-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 16px;
  background: rgba(0,0,0,0.15);
  border-bottom: 1px solid var(--border-subtle);

  @media (max-width: 599px) { padding: 6px 12px; }
}
.current-price {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
  @media (max-width: 599px) { font-size: 18px; }
}
.price-change {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.legend-dot {
  width: 10px; height: 2px;
  border-radius: 1px;
}
.legend-label { font-size: 10px; font-weight: 600; }

// ── Chart ─────────────────────────────────────────────────────────────────────
.chart-main-wrap {
  flex: 1;
  background: var(--bg-surface);
}

// ── Indicator panel ───────────────────────────────────────────────────────────
.ind-panel {
  padding: 8px 12px 12px;
}
.ind-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  transition: border-color 0.2s;

  &:hover { border-color: var(--border-glow); }
}
.ind-name { font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: var(--text-muted); }
.ind-val  { font-size: 18px; font-weight: 700; line-height: 1; margin-top: 2px; }
.ind-sub  { font-size: 10px; color: var(--text-muted); margin-top: 2px; }
</style>
