<template>
  <q-page class="signals-page q-pa-lg">

    <!-- Header -->
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <h5 class="q-ma-none text-neon-cyan" style="letter-spacing:2px;">SINAIS</h5>
        <div class="text-caption text-muted">Histórico de análises do robô</div>
      </div>
      <div class="row gap-2">
        <q-chip
          v-for="f in filters"
          :key="f.value"
          :selected="activeFilter === f.value"
          :color="activeFilter === f.value ? f.color : 'transparent'"
          :text-color="activeFilter === f.value ? 'white' : 'grey-6'"
          :outline="activeFilter !== f.value"
          clickable
          @click="activeFilter = f.value"
        >{{ f.label }}</q-chip>
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="row q-gutter-md q-mb-lg">
      <div class="col">
        <div class="stat-card text-center">
          <div class="stat-value text-neon-green">{{ wins }}</div>
          <div class="stat-label">WINS</div>
        </div>
      </div>
      <div class="col">
        <div class="stat-card text-center">
          <div class="stat-value text-neon-red">{{ losses }}</div>
          <div class="stat-label">LOSSES</div>
        </div>
      </div>
      <div class="col">
        <div class="stat-card text-center">
          <div class="stat-value text-neon-cyan">{{ store.accuracy }}%</div>
          <div class="stat-label">ACURÁCIA</div>
        </div>
      </div>
      <div class="col">
        <div class="stat-card text-center">
          <div class="stat-value text-neon-purple">{{ pending }}</div>
          <div class="stat-label">PENDENTES</div>
        </div>
      </div>
    </div>

    <!-- Signals Table -->
    <div class="chart-container">
      <div class="chart-header">
        <span class="text-weight-medium text-secondary">Histórico Completo</span>
        <q-btn flat dense icon="refresh" color="cyan" size="sm" @click="store.connect()" />
      </div>

      <q-table
        flat
        :rows="filteredSignals"
        :columns="columns"
        row-key="id"
        dark
        :pagination="{ rowsPerPage: 15 }"
        hide-bottom
        class="signals-table"
      >
        <template #body-cell-type="props">
          <q-td :props="props">
            <span :class="['signal-badge', `signal-${props.value.toLowerCase()}`]">
              <q-icon
                :name="props.value === 'BUY' ? 'trending_up' : props.value === 'SELL' ? 'trending_down' : 'pause'"
                size="12px"
              />
              {{ props.value === 'BUY' ? 'SOBE ↑' : props.value === 'SELL' ? 'DESCE ↓' : 'AGUARDAR' }}
            </span>
          </q-td>
        </template>

        <template #body-cell-confidence="props">
          <q-td :props="props">
            <div class="row items-center gap-2">
              <q-linear-progress
                :value="props.value / 100"
                :color="props.value >= 80 ? 'positive' : props.value >= 60 ? 'cyan' : 'warning'"
                track-color="transparent"
                rounded
                style="width:60px;height:4px;"
              />
              <span class="text-caption font-mono">{{ props.value }}%</span>
            </div>
          </q-td>
        </template>

        <template #body-cell-result="props">
          <q-td :props="props">
            <span
              v-if="props.value"
              class="text-caption font-mono text-weight-bold"
              :class="{
                'text-neon-green': props.value === 'WIN',
                'text-neon-red': props.value === 'LOSS',
                'text-muted': props.value === 'PENDING',
              }"
            >
              {{ props.value === 'WIN' ? '✓ WIN' : props.value === 'LOSS' ? '✗ LOSS' : '⋯ PENDING' }}
            </span>
          </q-td>
        </template>
      </q-table>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMarketStore } from 'stores/market'

const store = useMarketStore()
const activeFilter = ref('ALL')

const filters = [
  { label: 'Todos',    value: 'ALL',     color: 'cyan' },
  { label: 'Sobe ↑',   value: 'BUY',     color: 'positive' },
  { label: 'Desce ↓',  value: 'SELL',    color: 'negative' },
  { label: 'Wins',     value: 'WIN',     color: 'positive' },
  { label: 'Losses',   value: 'LOSS',    color: 'negative' },
]

const filteredSignals = computed(() => {
  if (activeFilter.value === 'ALL') return store.signals
  if (activeFilter.value === 'WIN' || activeFilter.value === 'LOSS')
    return store.signals.filter(s => s.result === activeFilter.value)
  return store.signals.filter(s => s.type === activeFilter.value)
})

const wins    = computed(() => store.signals.filter(s => s.result === 'WIN').length)
const losses  = computed(() => store.signals.filter(s => s.result === 'LOSS').length)
const pending = computed(() => store.signals.filter(s => s.result === 'PENDING').length)

const columns = [
  { name: 'time',       label: 'Hora',      field: 'time',       align: 'left' as const },
  { name: 'asset',      label: 'Ativo',     field: 'asset',      align: 'left' as const },
  { name: 'type',       label: 'Sinal',     field: 'type',       align: 'left' as const },
  { name: 'confidence', label: 'Confiança', field: 'confidence', align: 'left' as const },
  { name: 'duration',   label: 'Duração',   field: 'duration',   align: 'left' as const },
  { name: 'result',     label: 'Resultado', field: 'result',     align: 'left' as const },
]
</script>

<style lang="scss" scoped>
.signals-page { background: var(--bg-deep); min-height: 100vh; }
.gap-2 { gap: 8px; }
.font-mono { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }

:deep(.signals-table) {
  background: transparent !important;
  .q-table__top { background: transparent; }
  thead tr th {
    color: var(--text-muted);
    font-size: 10px;
    letter-spacing: 1.5px;
    font-weight: 600;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border-subtle);
    background: transparent;
  }
  tbody tr {
    td { border-bottom: 1px solid rgba(255,255,255,0.03); }
    &:hover td { background: rgba(0,212,255,0.03) !important; }
  }
}
</style>
