<template>
  <q-page class="dashboard-page q-pa-lg">

    <!-- Top Stats Row -->
    <div class="row q-gutter-md q-mb-lg animate-float">
      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">Acurácia Total</div>
          <div class="stat-value text-neon-green">{{ store.accuracy }}%</div>
          <div class="stat-trend text-caption text-neon-green q-mt-xs">
            <q-icon name="trending_up" size="12px" /> +2.3% hoje
          </div>
          <q-icon name="track_changes" class="stat-icon" />
          <div class="stat-bar q-mt-sm">
            <div class="stat-bar-fill" :style="{ width: store.accuracy + '%', background: 'var(--accent-green)' }" />
          </div>
        </div>
      </div>
      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">Sinais Hoje</div>
          <div class="stat-value text-neon-cyan">{{ store.totalSignals }}</div>
          <div class="stat-trend text-caption text-neon-cyan q-mt-xs">
            <q-icon name="bolt" size="12px" /> {{ store.wins }} wins / {{ store.totalSignals - store.wins }} loss
          </div>
          <q-icon name="bolt" class="stat-icon" />
        </div>
      </div>
      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">Preço Atual</div>
          <div class="stat-value text-neon-cyan font-mono">{{ store.currentPrice.toFixed(5) }}</div>
          <div
            class="stat-trend text-caption q-mt-xs"
            :class="store.priceChange >= 0 ? 'text-neon-green' : 'text-neon-red'"
          >
            <q-icon :name="store.priceChange >= 0 ? 'arrow_upward' : 'arrow_downward'" size="12px" />
            {{ Math.abs(store.priceChange * 10000).toFixed(1) }} pips
          </div>
          <q-icon name="show_chart" class="stat-icon" />
        </div>
      </div>
      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">Último Sinal</div>
          <div v-if="lastSignal" class="q-mt-xs">
            <div :class="['signal-badge', `signal-${lastSignal.type.toLowerCase()}`]">
              <q-icon :name="lastSignal.type === 'BUY' ? 'trending_up' : lastSignal.type === 'SELL' ? 'trending_down' : 'pause'" size="12px" />
              {{ lastSignal.type === 'BUY' ? 'SOBE ↑' : lastSignal.type === 'SELL' ? 'DESCE ↓' : 'AGUARDAR' }}
            </div>
            <div class="text-caption text-muted q-mt-xs">{{ lastSignal.confidence }}% confiança</div>
          </div>
          <q-icon name="radar" class="stat-icon" />
        </div>
      </div>
    </div>

    <!-- Main Chart + Signal Panel -->
    <div class="row q-gutter-md q-mb-lg">
      <!-- Mini Chart -->
      <div class="col-12 col-md-8">
        <div class="chart-container">
          <div class="chart-header">
            <div class="row items-center gap-2">
              <div class="live-dot" />
              <span class="text-weight-bold text-neon-cyan">EUR/USD</span>
              <span class="text-caption text-muted">M1</span>
            </div>
            <div class="row gap-3">
              <q-btn flat dense size="sm" label="M1" color="cyan" />
              <q-btn flat dense size="sm" label="M5" color="grey-6" />
              <q-btn flat dense size="sm" label="M15" color="grey-6" />
            </div>
          </div>
          <div class="chart-body">
            <MiniChart :candles="store.candles" :height="280" />
          </div>
        </div>
      </div>

      <!-- Signal Panel -->
      <div class="col-12 col-md-4">
        <div class="chart-container" style="height:100%;">
          <div class="chart-header">
            <span class="text-weight-bold text-secondary">Últimos Sinais</span>
            <q-badge color="cyan" :label="store.signals.length" rounded />
          </div>
          <q-scroll-area style="height:280px;">
            <div class="q-pa-sm">
              <SignalCard
                v-for="sig in store.signals.slice(0,8)"
                :key="sig.id"
                :signal="sig"
                class="q-mb-xs"
              />
            </div>
          </q-scroll-area>
        </div>
      </div>
    </div>

    <!-- Indicators Row -->
    <div class="row q-gutter-md">
      <div class="col-12 col-md-4">
        <div class="glass-card q-pa-lg">
          <div class="text-caption text-muted q-mb-md" style="letter-spacing:2px;">RSI (14)</div>
          <RsiGauge :value="rsiValue" />
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="glass-card q-pa-lg">
          <div class="text-caption text-muted q-mb-md" style="letter-spacing:2px;">MACD</div>
          <MacdBar :value="macdValue" :signal="macdSignal" />
        </div>
      </div>
      <div class="col-12 col-md-4">
        <div class="glass-card q-pa-lg">
          <div class="text-caption text-muted q-mb-md" style="letter-spacing:2px;">PERFORMANCE 7 DIAS</div>
          <PerformanceBar :data="perfData" />
        </div>
      </div>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMarketStore } from 'stores/market'
import MiniChart from 'components/MiniChart.vue'
import SignalCard from 'components/SignalCard.vue'
import RsiGauge from 'components/RsiGauge.vue'
import MacdBar from 'components/MacdBar.vue'
import PerformanceBar from 'components/PerformanceBar.vue'

const store = useMarketStore()

const lastSignal = computed(() => store.signals[0])
const rsiValue = ref(58.4)
const macdValue = ref(0.00124)
const macdSignal = ref(0.00098)

const perfData = ref([
  { day: 'Seg', wins: 8, losses: 2 },
  { day: 'Ter', wins: 6, losses: 4 },
  { day: 'Qua', wins: 9, losses: 1 },
  { day: 'Qui', wins: 7, losses: 3 },
  { day: 'Sex', wins: 10, losses: 2 },
  { day: 'Sáb', wins: 5, losses: 5 },
  { day: 'Dom', wins: 8, losses: 2 },
])
</script>

<style lang="scss" scoped>
.dashboard-page { background: var(--bg-deep); min-height: 100vh; }
.gap-2 { gap: 8px; }
.gap-3 { gap: 8px; }
.font-mono { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }

.stat-bar {
  height: 3px;
  background: rgba(255,255,255,0.06);
  border-radius: 2px;
  overflow: hidden;
}
.stat-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 1s ease;
}
</style>
