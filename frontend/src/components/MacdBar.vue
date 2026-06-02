<template>
  <div class="macd-wrap">
    <div class="row items-end justify-between q-mb-sm">
      <div>
        <div class="text-caption" style="color:var(--text-muted);">MACD</div>
        <div class="text-subtitle1 font-mono" :class="value >= 0 ? 'text-neon-green' : 'text-neon-red'">
          {{ value >= 0 ? '+' : '' }}{{ value.toFixed(5) }}
        </div>
      </div>
      <div class="text-right">
        <div class="text-caption" style="color:var(--text-muted);">Signal</div>
        <div class="text-subtitle1 font-mono text-neon-cyan">{{ signal.toFixed(5) }}</div>
      </div>
    </div>

    <!-- Histogram bars -->
    <div class="histogram" ref="histEl">
      <div
        v-for="(bar, i) in histBars"
        :key="i"
        class="hist-bar"
        :class="bar >= 0 ? 'bar-pos' : 'bar-neg'"
        :style="{ height: Math.abs(bar / maxBar) * 60 + '%' }"
      />
    </div>

    <!-- Crossover label -->
    <div class="q-mt-sm text-center">
      <span
        class="signal-badge"
        :class="value > signal ? 'signal-buy' : 'signal-sell'"
        style="font-size:10px;"
      >
        <q-icon :name="value > signal ? 'trending_up' : 'trending_down'" size="12px" />
        {{ value > signal ? 'BULLISH' : 'BEARISH' }} CROSSOVER
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: number; signal: number }>()

const histBars = computed(() => {
  const bars: number[] = []
  let v = props.value * 0.5
  for (let i = 0; i < 20; i++) {
    v += (Math.random() - 0.48) * 0.0003
    bars.push(v)
  }
  bars[bars.length - 1] = props.value - props.signal
  return bars
})

const maxBar = computed(() => Math.max(...histBars.value.map(Math.abs), 0.0001))
</script>

<style lang="scss" scoped>
.macd-wrap { width: 100%; }
.histogram {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 80px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0,212,255,0.1);
}
.hist-bar {
  flex: 1;
  min-height: 2px;
  border-radius: 2px;
  transition: height 0.3s ease;
  &.bar-pos { background: rgba(0,255,136,0.6); }
  &.bar-neg { background: rgba(255,68,102,0.6); }
}
.font-mono { font-family: 'Roboto Mono', monospace; }
</style>
