<template>
  <div class="rsi-gauge">
    <svg :width="size" :height="size / 2 + 20" :viewBox="`0 0 ${size} ${size / 2 + 20}`">
      <!-- Background arc -->
      <path :d="bgArc" fill="none" stroke="rgba(255,255,255,0.06)" :stroke-width="strokeW" stroke-linecap="round" />
      <!-- Oversold zone -->
      <path :d="oversoldArc" fill="none" stroke="rgba(255,68,102,0.3)" :stroke-width="strokeW" stroke-linecap="round" />
      <!-- Overbought zone -->
      <path :d="overboughtArc" fill="none" stroke="rgba(0,255,136,0.3)" :stroke-width="strokeW" stroke-linecap="round" />
      <!-- Value arc -->
      <path :d="valueArc" fill="none" :stroke="gaugeColor" :stroke-width="strokeW" stroke-linecap="round"
        style="filter: drop-shadow(0 0 6px currentColor);" />
      <!-- Needle -->
      <line :x1="cx" :y1="cy" :x2="needleX" :y2="needleY"
        stroke="white" stroke-width="2" stroke-linecap="round" />
      <circle :cx="cx" :cy="cy" r="5" fill="rgba(255,255,255,0.9)" />
    </svg>

    <!-- Labels -->
    <div class="rsi-labels">
      <span style="color:var(--accent-red);font-size:10px;">0</span>
      <div class="rsi-center">
        <div class="text-h5 font-mono" :style="{ color: gaugeColor }">{{ value.toFixed(1) }}</div>
        <div class="text-caption" style="color:var(--text-muted);letter-spacing:1px;">RSI</div>
        <div class="text-caption" :style="{ color: gaugeColor }">{{ rsiLabel }}</div>
      </div>
      <span style="color:var(--accent-green);font-size:10px;">100</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: number }>()

const size = 200
const cx = size / 2
const cy = size / 2
const r = 80
const strokeW = 12

function polarToXY(angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function arcPath(startDeg: number, endDeg: number) {
  const s = polarToXY(startDeg)
  const e = polarToXY(endDeg)
  const large = endDeg - startDeg > 180 ? 1 : 0
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`
}

// Gauge goes from 180° (left) to 0° (right) = 180° sweep
const startAngle = 180
const endAngle = 0
const sweepAngle = 180

const bgArc         = arcPath(startAngle, endAngle + 0.01)
const oversoldArc   = arcPath(startAngle, startAngle - (30 / 100) * sweepAngle)
const overboughtArc = arcPath(endAngle + (30 / 100) * sweepAngle, endAngle + 0.01)

const valueArc = computed(() => {
  const deg = startAngle - (props.value / 100) * sweepAngle
  return arcPath(startAngle, deg)
})

const needleAngle = computed(() => startAngle - (props.value / 100) * sweepAngle)
const needleX = computed(() => cx + (r - 10) * Math.cos((needleAngle.value * Math.PI) / 180))
const needleY = computed(() => cy + (r - 10) * Math.sin((needleAngle.value * Math.PI) / 180))

const gaugeColor = computed(() =>
  props.value <= 30 ? '#FF4466' :
  props.value >= 70 ? '#00FF88' :
  '#00D4FF'
)

const rsiLabel = computed(() =>
  props.value <= 30 ? 'Sobrevenda' :
  props.value >= 70 ? 'Sobrecompra' :
  'Neutro'
)
</script>

<style lang="scss" scoped>
.rsi-gauge { display: flex; flex-direction: column; align-items: center; }
.rsi-labels {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%; margin-top: -16px;
}
.rsi-center { text-align: center; }
.font-mono { font-family: 'Roboto Mono', monospace; }
</style>
