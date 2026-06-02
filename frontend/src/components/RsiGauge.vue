<template>
  <div class="rsi-gauge">
    <svg :width="size" :height="svgH" :viewBox="`0 0 ${size} ${svgH}`" class="rsi-svg">
      <!-- Arco fundo (cinza) -->
      <path :d="bgArc"         fill="none" stroke="rgba(255,255,255,0.07)" :stroke-width="sw" stroke-linecap="round" />
      <!-- Zona sobrevendido (30% esquerda, vermelho) -->
      <path :d="oversoldArc"   fill="none" stroke="rgba(255,68,102,0.4)"   :stroke-width="sw" stroke-linecap="round" />
      <!-- Zona sobrecomprado (30% direita, verde) -->
      <path :d="overboughtArc" fill="none" stroke="rgba(0,255,136,0.4)"    :stroke-width="sw" stroke-linecap="round" />
      <!-- Arco do valor atual -->
      <path :d="valueArc"      fill="none" :stroke="gaugeColor"             :stroke-width="sw" stroke-linecap="round"
        style="filter: drop-shadow(0 0 8px currentColor);" />
      <!-- Agulha -->
      <line :x1="cx" :y1="cy" :x2="needleX" :y2="needleY"
        stroke="rgba(255,255,255,0.9)" stroke-width="2.5" stroke-linecap="round" />
      <!-- Pivô -->
      <circle :cx="cx" :cy="cy" r="5" fill="rgba(255,255,255,0.85)" />
      <circle :cx="cx" :cy="cy" r="2" fill="var(--bg-surface)" />
    </svg>

    <!-- Labels abaixo do SVG, sem sobreposição -->
    <div class="rsi-footer">
      <span class="zone-num" style="color:var(--accent-red);">0</span>
      <div class="rsi-center">
        <span class="rsi-value font-mono" :style="{ color: gaugeColor }">{{ value.toFixed(1) }}</span>
        <span class="rsi-zone"            :style="{ color: gaugeColor }">{{ rsiLabel }}</span>
      </div>
      <span class="zone-num" style="color:var(--accent-green);">100</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: number }>()

const size = 200
const cx   = size / 2   // 100
const cy   = size / 2   // 100  (centro geométrico do semicírculo)
const r    = 75
const sw   = 12

// SVG mostra apenas a metade SUPERIOR: y vai de 0 até cy + margem para o stroke
const svgH = cy + sw + 8   // inclui stroke + folga abaixo dos endpoints

// ── Geometria ─────────────────────────────────────────────────────────────────
//
// O semicírculo SUPERIOR vai de 180° (esquerda) até 360° (direita)
// passando pelo TOPO em 270° (y = cy - r).
//
// Mapeamento de value (0..100) → ângulo:
//   0%   → 180°  (ponto esquerdo)
//   50%  → 270°  (topo)
//   100% → 360°  (ponto direito)
//
// Fórmula: angle = 180 + (value/100) * 180
//
// arcPath usa sweep=1 (direção positiva / anti-horária visual),
// que faz o traçado subir pelo topo ao ir de 180°→360°.

function polarToXY(deg: number) {
  const rad = (deg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function arcPath(startDeg: number, endDeg: number) {
  const s    = polarToXY(startDeg)
  const e    = polarToXY(endDeg)
  const diff = endDeg - startDeg
  const large = diff > 180 ? 1 : 0
  // sweep=1 → direção de ângulo crescente, que no SVG faz o arco ir para CIMA
  return `M ${s.x.toFixed(3)} ${s.y.toFixed(3)} A ${r} ${r} 0 ${large} 1 ${e.x.toFixed(3)} ${e.y.toFixed(3)}`
}

const START = 180  // 0%  = esquerda
const END   = 360  // 100% = direita (= 0°)

const bgArc         = arcPath(START, END)
const oversoldArc   = arcPath(START, START + 0.30 * 180)   // 0–30%
const overboughtArc = arcPath(START + 0.70 * 180, END)     // 70–100%

const valueArc = computed(() =>
  arcPath(START, START + (props.value / 100) * 180)
)

// Agulha: mesmo mapeamento de ângulo
const needleAngle = computed(() => START + (props.value / 100) * 180)
const needleLen   = r - 16
const needleX     = computed(() => cx + needleLen * Math.cos((needleAngle.value * Math.PI) / 180))
const needleY     = computed(() => cy + needleLen * Math.sin((needleAngle.value * Math.PI) / 180))

const gaugeColor = computed(() =>
  props.value <= 30 ? '#FF4466' :
  props.value >= 70 ? '#00FF88' :
  '#00D4FF'
)

const rsiLabel = computed(() =>
  props.value <= 30 ? 'Sobrevendido' :
  props.value >= 70 ? 'Sobrecomprado' :
  'Neutro'
)
</script>

<style lang="scss" scoped>
.rsi-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  gap: 6px;
}

.rsi-svg { display: block; overflow: hidden; }

.rsi-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0 6px;
}

.zone-num {
  font-size: 10px;
  font-weight: 600;
  opacity: 0.75;
  min-width: 20px;
}

.rsi-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  text-align: center;
}

.rsi-value {
  font-family: 'Roboto Mono', monospace;
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
}

.rsi-zone {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  line-height: 1;
}
</style>
