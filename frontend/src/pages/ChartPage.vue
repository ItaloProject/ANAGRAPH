<template>
  <q-page class="chart-page q-pa-md">
    <div class="row q-gutter-md">

      <!-- Full chart -->
      <div class="col-12">
        <div class="chart-container">
          <div class="chart-header">
            <div class="row items-center gap-3">
              <div class="live-dot" />
              <span class="text-weight-bold text-neon-cyan text-h6">EUR / USD</span>
              <q-badge color="transparent" text-color="cyan" outline label="FOREX" />
            </div>

            <div class="row items-center gap-2">
              <!-- Timeframe selector -->
              <q-btn-toggle
                v-model="timeframe"
                toggle-color="cyan"
                color="transparent"
                text-color="grey-6"
                dense
                unelevated
                :options="[
                  {label:'M1',value:'1'},
                  {label:'M5',value:'5'},
                  {label:'M15',value:'15'},
                  {label:'H1',value:'60'},
                ]"
              />
              <q-separator vertical inset />
              <!-- Indicator toggles -->
              <q-btn flat dense size="sm" label="BB" :color="showBB ? 'cyan' : 'grey-7'" @click="showBB = !showBB" />
              <q-btn flat dense size="sm" label="EMA" :color="showEMA ? 'purple' : 'grey-7'" @click="showEMA = !showEMA" />
              <q-btn flat dense size="sm" label="RSI" :color="showRSI ? 'amber' : 'grey-7'" @click="showRSI = !showRSI" />
            </div>
          </div>

          <div class="chart-body">
            <MiniChart :candles="store.candles" :height="420" />
          </div>
        </div>
      </div>

      <!-- RSI sub-chart -->
      <div class="col-12" v-if="showRSI">
        <div class="chart-container">
          <div class="chart-header">
            <span class="text-caption text-neon-cyan" style="letter-spacing:1.5px;">RSI (14)</span>
            <div class="row gap-2">
              <span class="text-caption text-muted">Oversold: 30</span>
              <span class="text-caption text-muted">Overbought: 70</span>
            </div>
          </div>
          <div style="height:120px;padding:8px 0;">
            <RsiLine :height="104" />
          </div>
        </div>
      </div>

    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMarketStore } from 'stores/market'
import MiniChart from 'components/MiniChart.vue'
import RsiLine from 'components/RsiLine.vue'

const store = useMarketStore()
const timeframe = ref('1')
const showBB = ref(true)
const showEMA = ref(true)
const showRSI = ref(true)
</script>

<style lang="scss" scoped>
.chart-page { background: var(--bg-deep); min-height: 100vh; }
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }
.text-muted { color: var(--text-muted); }
</style>
