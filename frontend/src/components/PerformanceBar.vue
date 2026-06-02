<template>
  <div class="perf-wrap">
    <div class="bars-row">
      <div v-for="d in data" :key="d.day" class="bar-col">
        <div class="bar-stack">
          <div
            class="bar-segment bar-win"
            :style="{ height: (d.wins / total(d)) * 80 + 'px' }"
          />
          <div
            class="bar-segment bar-loss"
            :style="{ height: (d.losses / total(d)) * 80 + 'px' }"
          />
        </div>
        <div class="bar-label">{{ d.day }}</div>
      </div>
    </div>

    <div class="legend row items-center gap-2 q-mt-sm">
      <div class="legend-dot" style="background:var(--accent-green);" />
      <span class="text-caption" style="color:var(--text-muted);">Wins</span>
      <div class="legend-dot q-ml-sm" style="background:var(--accent-red);" />
      <span class="text-caption" style="color:var(--text-muted);">Losses</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  data: { day: string; wins: number; losses: number }[]
}>()

function total(d: { wins: number; losses: number }) {
  return d.wins + d.losses || 1
}
</script>

<style lang="scss" scoped>
.perf-wrap { width: 100%; }
.bars-row {
  display: flex; align-items: flex-end; gap: 8px;
  height: 100px; padding-bottom: 4px;
  border-bottom: 1px solid rgba(0,212,255,0.08);
}
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; }
.bar-stack {
  display: flex; flex-direction: column-reverse;
  align-items: center; gap: 1px;
  width: 100%;
}
.bar-segment {
  width: 100%;
  border-radius: 3px;
  transition: height 0.6s ease;
  min-height: 2px;
  &.bar-win  { background: rgba(0,255,136,0.7); }
  &.bar-loss { background: rgba(255,68,102,0.7); }
}
.bar-label {
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.5px;
}
.legend { display: flex; align-items: center; }
.legend-dot { width: 8px; height: 8px; border-radius: 2px; }
.gap-2 { gap: 8px; }
</style>
