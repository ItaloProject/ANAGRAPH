<template>
  <div ref="chartEl" class="mini-chart" :style="{ height: height + 'px' }" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { createChart, IChartApi, ISeriesApi, CandlestickData, ColorType } from 'lightweight-charts'
import type { Candle } from 'stores/market'

const props = defineProps<{ candles: Candle[]; height?: number }>()
const chartEl = ref<HTMLElement | null>(null)

let chart: IChartApi | null = null
let series: ISeriesApi<'Candlestick'> | null = null

onMounted(() => {
  if (!chartEl.value) return

  chart = createChart(chartEl.value, {
    width: chartEl.value.clientWidth,
    height: props.height ?? 260,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#8A9BBE',
    },
    grid: {
      vertLines: { color: 'rgba(0,212,255,0.05)' },
      horzLines: { color: 'rgba(0,212,255,0.05)' },
    },
    crosshair: {
      vertLine: { color: 'rgba(0,212,255,0.5)', width: 1, style: 2 },
      horzLine: { color: 'rgba(0,212,255,0.5)', width: 1, style: 2 },
    },
    rightPriceScale: {
      borderColor: 'rgba(0,212,255,0.1)',
      textColor: '#8A9BBE',
    },
    timeScale: {
      borderColor: 'rgba(0,212,255,0.1)',
      textColor: '#8A9BBE',
      timeVisible: true,
    },
  })

  series = chart.addCandlestickSeries({
    upColor:          '#00FF88',
    downColor:        '#FF4466',
    borderUpColor:    '#00FF88',
    borderDownColor:  '#FF4466',
    wickUpColor:      'rgba(0,255,136,0.6)',
    wickDownColor:    'rgba(255,68,102,0.6)',
  })

  _updateData()

  const ro = new ResizeObserver(() => {
    if (chart && chartEl.value) chart.resize(chartEl.value.clientWidth, props.height ?? 260)
  })
  ro.observe(chartEl.value)
})

onUnmounted(() => { chart?.remove() })

watch(() => props.candles.length, _updateData)

function _updateData() {
  if (!series || !props.candles.length) return
  const data: CandlestickData[] = props.candles.map(c => ({
    time: c.time as any,
    open: c.open, high: c.high, low: c.low, close: c.close,
  }))
  series.setData(data)
  chart?.timeScale().fitContent()
}
</script>

<style scoped>
.mini-chart { width: 100%; }
</style>
