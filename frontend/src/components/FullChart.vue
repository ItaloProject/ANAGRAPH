<template>
  <div ref="wrap" class="full-chart-wrap" />
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  LineData,
  HistogramData,
  ColorType,
  SeriesMarker,
  UTCTimestamp,
  SeriesMarkerPosition,
  SeriesMarkerShape,
} from 'lightweight-charts'
import type { Candle } from 'stores/market'

const props = defineProps<{
  candles:    Candle[]
  height?:    number
  showEMA?:   boolean
  showBB?:    boolean
  showVolume?: boolean
  trades?:    { signal: string; opened_at: string; status: string; pnl?: number }[]
}>()

const wrap = ref<HTMLElement | null>(null)

let chart:     IChartApi                | null = null
let candle:    ISeriesApi<'Candlestick'>| null = null
let ema9S:     ISeriesApi<'Line'>       | null = null
let ema21S:    ISeriesApi<'Line'>       | null = null
let bbUpS:     ISeriesApi<'Line'>       | null = null
let bbMidS:    ISeriesApi<'Line'>       | null = null
let bbLoS:     ISeriesApi<'Line'>       | null = null
let volS:      ISeriesApi<'Histogram'>  | null = null

// ── EMA ───────────────────────────────────────────────────────────────────
function ema(prices: number[], period: number): number[] {
  const k = 2 / (period + 1)
  const out: number[] = []
  let prev = prices[0] ?? 0
  for (const p of prices) {
    const v = prev === 0 ? p : p * k + prev * (1 - k)
    out.push(v)
    prev = v
  }
  return out
}

// ── Bollinger Bands ────────────────────────────────────────────────────────
function bollingerBands(prices: number[], period = 20, mult = 2) {
  const up: number[] = [], mid: number[] = [], lo: number[] = []
  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      up.push(prices[i]); mid.push(prices[i]); lo.push(prices[i])
      continue
    }
    const sl = prices.slice(i - period + 1, i + 1)
    const avg = sl.reduce((a, b) => a + b, 0) / period
    const std = Math.sqrt(sl.reduce((a, b) => a + (b - avg) ** 2, 0) / period)
    mid.push(avg)
    up.push(avg + mult * std)
    lo.push(avg - mult * std)
  }
  return { up, mid, lo }
}

function buildChart() {
  if (!wrap.value) return
  chart = createChart(wrap.value, {
    width:  wrap.value.clientWidth,
    height: props.height ?? 420,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#8A9BBE',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(0,212,255,0.04)' },
      horzLines: { color: 'rgba(0,212,255,0.04)' },
    },
    crosshair: {
      vertLine: { color: 'rgba(0,212,255,0.4)', width: 1, style: 2 },
      horzLine: { color: 'rgba(0,212,255,0.4)', width: 1, style: 2 },
    },
    rightPriceScale: {
      borderColor: 'rgba(0,212,255,0.08)',
      textColor: '#8A9BBE',
    },
    timeScale: {
      borderColor: 'rgba(0,212,255,0.08)',
      textColor: '#8A9BBE',
      timeVisible: true,
      secondsVisible: false,
    },
    handleScroll: true,
    handleScale:  true,
  })

  // ── Candlesticks ──
  candle = chart.addCandlestickSeries({
    upColor:         '#00FF88',
    downColor:       '#FF4466',
    borderUpColor:   '#00FF88',
    borderDownColor: '#FF4466',
    wickUpColor:     'rgba(0,255,136,0.5)',
    wickDownColor:   'rgba(255,68,102,0.5)',
  })

  // ── Volume ──
  volS = chart.addHistogramSeries({
    priceFormat:   { type: 'volume' },
    priceScaleId:  'vol',
  })
  chart.priceScale('vol').applyOptions({
    scaleMargins: { top: 0.88, bottom: 0 },
  })

  // ── EMA ──
  ema9S = chart.addLineSeries({
    color: '#00D4FF', lineWidth: 1,
    lastValueVisible: false, priceLineVisible: false,
    crosshairMarkerVisible: false,
  })
  ema21S = chart.addLineSeries({
    color: '#8B5CF6', lineWidth: 1,
    lastValueVisible: false, priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  // ── Bollinger Bands ──
  bbUpS = chart.addLineSeries({
    color: 'rgba(255,184,0,0.5)', lineWidth: 1, lineStyle: 2,
    lastValueVisible: false, priceLineVisible: false,
    crosshairMarkerVisible: false,
  })
  bbMidS = chart.addLineSeries({
    color: 'rgba(255,184,0,0.25)', lineWidth: 1, lineStyle: 3,
    lastValueVisible: false, priceLineVisible: false,
    crosshairMarkerVisible: false,
  })
  bbLoS = chart.addLineSeries({
    color: 'rgba(255,184,0,0.5)', lineWidth: 1, lineStyle: 2,
    lastValueVisible: false, priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  // Responsive resize
  const ro = new ResizeObserver(() => {
    if (chart && wrap.value) {
      chart.resize(wrap.value.clientWidth, props.height ?? 420)
    }
  })
  ro.observe(wrap.value)

  updateAll()
}

function updateAll() {
  if (!candle || !props.candles.length) return

  const c = props.candles
  const times = c.map(x => x.time as UTCTimestamp)
  const closes = c.map(x => x.close)

  // Candles
  const cd: CandlestickData[] = c.map(x => ({
    time:  x.time as UTCTimestamp,
    open:  x.open, high: x.high, low: x.low, close: x.close,
  }))
  candle.setData(cd)

  // Volume
  const maxVol = Math.max(...c.map(x => x.volume ?? 1))
  const vd: HistogramData[] = c.map(x => ({
    time:  x.time as UTCTimestamp,
    value: x.volume ?? 1,
    color: x.close >= x.open
      ? 'rgba(0,255,136,0.25)'
      : 'rgba(255,68,102,0.25)',
  }))
  // only set volume if any candle has real volume
  if (maxVol > 1) volS?.setData(vd)

  // EMA
  const e9  = ema(closes, 9)
  const e21 = ema(closes, 21)
  ema9S?.setData(times.map((t, i) => ({ time: t, value: e9[i] } as LineData)))
  ema21S?.setData(times.map((t, i) => ({ time: t, value: e21[i] } as LineData)))
  ema9S?.applyOptions({ visible: props.showEMA ?? true })
  ema21S?.applyOptions({ visible: props.showEMA ?? true })

  // BB
  const bb = bollingerBands(closes)
  bbUpS?.setData(times.map((t, i) => ({ time: t, value: bb.up[i] } as LineData)))
  bbMidS?.setData(times.map((t, i) => ({ time: t, value: bb.mid[i] } as LineData)))
  bbLoS?.setData(times.map((t, i) => ({ time: t, value: bb.lo[i] } as LineData)))
  const showBB = props.showBB ?? true
  bbUpS?.applyOptions({ visible: showBB })
  bbMidS?.applyOptions({ visible: showBB })
  bbLoS?.applyOptions({ visible: showBB })

  // Trade markers
  const markers: SeriesMarker<UTCTimestamp>[] = (props.trades ?? [])
    .filter(t => t.status !== 'ERROR')
    .map(t => {
      const epoch = Math.floor(new Date(t.opened_at).getTime() / 1000) as UTCTimestamp
      const isWin  = t.status === 'WIN'
      const isLoss = t.status === 'LOSS'
      const isBuy  = t.signal === 'BUY'
      return {
        time:     epoch,
        position: (isBuy ? 'belowBar' : 'aboveBar') as SeriesMarkerPosition,
        color:    isWin ? '#00FF88' : isLoss ? '#FF4466' : '#00D4FF',
        shape:    (isBuy ? 'arrowUp' : 'arrowDown') as SeriesMarkerShape,
        text:     isWin ? '✓' : isLoss ? '✗' : '·',
        size:     1,
      }
    })
    .sort((a, b) => (a.time as number) - (b.time as number))

  candle.setMarkers(markers)
  chart?.timeScale().fitContent()
}

onMounted(buildChart)
onUnmounted(() => chart?.remove())

watch(() => props.candles.length, updateAll)
watch(() => [props.showEMA, props.showBB], updateAll)
watch(() => props.trades?.length, updateAll)
</script>

<style scoped>
.full-chart-wrap { width: 100%; }
</style>
