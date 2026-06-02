<template>
  <div class="signal-row q-pa-sm" :class="rowClass">
    <div class="row items-center no-wrap gap-2">
      <!-- Type icon -->
      <div class="signal-icon-wrap" :class="iconClass">
        <q-icon :name="icon" size="16px" />
      </div>

      <div class="col">
        <div class="row items-center justify-between">
          <span :class="['signal-badge', `signal-${signal.type.toLowerCase()}`]" style="font-size:10px;padding:2px 8px;">
            {{ signal.type === 'BUY' ? 'SOBE ↑' : signal.type === 'SELL' ? 'DESCE ↓' : 'AGUARDAR' }}
          </span>
          <span class="text-caption font-mono" style="color:var(--text-muted);">{{ signal.time }}</span>
        </div>
        <div class="row items-center justify-between q-mt-xs">
          <div class="confidence-wrap">
            <q-linear-progress
              :value="signal.confidence / 100"
              :color="confidenceColor"
              track-color="transparent"
              rounded
              style="height:3px;width:80px;"
            />
            <span class="text-caption" style="color:var(--text-secondary);font-size:10px;">
              {{ signal.confidence }}%
            </span>
          </div>
          <span
            v-if="signal.result"
            class="text-caption font-mono"
            :class="resultClass"
            style="font-size:10px;font-weight:700;"
          >
            {{ signal.result === 'WIN' ? '✓ WIN' : signal.result === 'LOSS' ? '✗ LOSS' : '⋯' }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Signal } from 'stores/market'

const props = defineProps<{ signal: Signal }>()

const icon = computed(() =>
  props.signal.type === 'BUY' ? 'trending_up' :
  props.signal.type === 'SELL' ? 'trending_down' : 'pause'
)
const iconClass = computed(() => ({
  'icon-buy':  props.signal.type === 'BUY',
  'icon-sell': props.signal.type === 'SELL',
  'icon-wait': props.signal.type === 'WAIT',
}))
const rowClass = computed(() => ({
  'row-win':  props.signal.result === 'WIN',
  'row-loss': props.signal.result === 'LOSS',
}))
const resultClass = computed(() => ({
  'text-neon-green': props.signal.result === 'WIN',
  'text-neon-red':   props.signal.result === 'LOSS',
  'text-muted':      props.signal.result === 'PENDING',
}))
const confidenceColor = computed(() =>
  props.signal.confidence >= 80 ? 'positive' :
  props.signal.confidence >= 60 ? 'cyan' : 'warning'
)
</script>

<style lang="scss" scoped>
.signal-row {
  border-radius: 8px;
  transition: background 0.2s;
  &:hover { background: rgba(255,255,255,0.03); }
  &.row-win  { border-left: 2px solid rgba(0,255,136,0.3); }
  &.row-loss { border-left: 2px solid rgba(255,68,102,0.3); }
}
.signal-icon-wrap {
  width: 30px; height: 30px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  &.icon-buy  { background: rgba(0,255,136,0.15); color: #00FF88; }
  &.icon-sell { background: rgba(255,68,102,0.15); color: #FF4466; }
  &.icon-wait { background: rgba(255,184,0,0.15);  color: #FFB800; }
}
.confidence-wrap {
  display: flex; align-items: center; gap: 6px;
}
.font-mono { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.gap-2 { gap: 8px; }
</style>
