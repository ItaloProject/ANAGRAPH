<template>
  <q-page class="dashboard-page">

    <!-- Status Bar -->
    <div class="status-bar q-mb-md row items-center justify-between">
      <div class="row items-center q-gutter-sm">
        <div class="bot-badge" :class="botStore.running ? 'badge-live' : 'badge-off'">
          <div :class="['status-dot', botStore.running ? 'dot-live' : 'dot-off']" />
          <span>{{ botStore.running ? 'BOT ATIVO' : 'BOT INATIVO' }}</span>
        </div>
        <span v-if="botStore.running" class="text-caption">
          Regime: <span class="text-weight-bold" :class="regimeColor">{{ adaptiveRegime }}</span>
        </span>
        <span v-if="botStore.running && botStore.adaptive.min_confidence" class="text-caption text-muted gt-xs">
          Confiança mín: <span class="font-mono">{{ botStore.adaptive.min_confidence }}%</span>
        </span>
      </div>
      <div class="row items-center gap-1 text-caption text-muted gt-xs">
        <q-icon name="sync" size="12px" />
        {{ botStore.lastSyncAt || 'Aguardando sync...' }}
      </div>
    </div>

    <!-- Top Stats Row: 1 col mobile / 2 col tablet / 4 col desktop -->
    <div class="row q-col-gutter-md q-mb-md">

      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">Taxa de Acerto</div>
          <div class="stat-value" :class="accuracyColor">
            {{ displayStats.accuracy.toFixed(1) }}%
          </div>
          <div class="stat-sub q-mt-xs">
            <span class="text-neon-green text-caption">{{ displayStats.wins }}W</span>
            <span class="text-muted text-caption"> / </span>
            <span class="text-neon-red text-caption">{{ displayStats.losses }}L</span>
            <span v-if="displayStats.open_positions > 0" class="text-neon-amber text-caption">
              &nbsp;/ {{ displayStats.open_positions }} aberto{{ displayStats.open_positions > 1 ? 's' : '' }}
            </span>
          </div>
          <q-icon name="track_changes" class="stat-icon" />
          <div class="stat-bar q-mt-sm">
            <div class="stat-bar-fill" :style="{ width: displayStats.accuracy + '%', background: accuracyGradient }" />
          </div>
        </div>
      </div>

      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">PnL Hoje</div>
          <div class="stat-value font-mono" :class="pnlColor">
            {{ pnlFormatted }}
          </div>
          <div class="stat-sub q-mt-xs">
            <span class="text-caption text-muted">{{ displayStats.trades }} operaç{{ displayStats.trades === 1 ? 'ão' : 'ões' }}</span>
            <span v-if="displayStats.current_streak !== 0" class="text-caption q-ml-xs" :class="streakColor">
              {{ displayStats.current_streak > 0 ? '🔥 +' : '❄ ' }}{{ displayStats.current_streak }}
            </span>
          </div>
          <q-icon :name="displayStatsBrl.pnl >= 0 ? 'trending_up' : 'trending_down'" class="stat-icon" />
        </div>
      </div>

      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">Saldo Conta</div>
          <div v-if="botStore.accountBalance !== null" class="stat-value font-mono text-neon-cyan">
            {{ botStore.formatBrl(botStore.accountBalanceBrl ?? 0) }}
          </div>
          <div v-else class="stat-value text-muted">—</div>
          <div class="stat-sub q-mt-xs row items-center gap-1">
            <q-badge
              :color="botStore.accountIsDemo ? 'positive' : 'amber'"
              :label="botStore.accountIsDemo ? 'DEMO' : 'REAL'"
              dense rounded
            />
            <span v-if="botStore.accountLoginId" class="text-caption text-muted gt-xs">
              {{ botStore.accountLoginId }}
            </span>
          </div>
          <q-icon name="account_balance_wallet" class="stat-icon" />
        </div>
      </div>

      <div class="col-12 col-sm-6 col-md-3">
        <div class="stat-card">
          <div class="stat-label">{{ store.activeAsset }}</div>
          <div class="stat-value font-mono text-neon-cyan">
            {{ store.currentPrice.toFixed(5) }}
          </div>
          <div class="stat-sub q-mt-xs row items-center gap-1">
            <div
              v-if="lastMarketSignal"
              :class="['signal-pill', `pill-${lastMarketSignal.type.toLowerCase()}`]"
            >
              <q-icon
                :name="lastMarketSignal.type === 'BUY' ? 'trending_up' : lastMarketSignal.type === 'SELL' ? 'trending_down' : 'pause'"
                size="11px"
              />
              {{ lastMarketSignal.type === 'BUY' ? 'SOBE' : lastMarketSignal.type === 'SELL' ? 'DESCE' : 'AGUARDAR' }}
            </div>
            <span v-if="lastMarketSignal" class="text-caption text-muted">{{ lastMarketSignal.confidence }}%</span>
            <span
              v-else
              class="text-caption"
              :class="store.priceChange >= 0 ? 'text-neon-green' : 'text-neon-red'"
            >
              <q-icon :name="store.priceChange >= 0 ? 'arrow_upward' : 'arrow_downward'" size="11px" />
              {{ Math.abs(store.priceChange * 10000).toFixed(1) }} pips
            </span>
          </div>
          <q-icon name="show_chart" class="stat-icon" />
        </div>
      </div>
    </div>

    <!-- Chart + Trades: lado a lado em md+, empilhado em mobile/tablet -->
    <div class="row q-col-gutter-md q-mb-md">

      <div class="col-12 col-md-8">
        <div class="chart-container">
          <div class="chart-header">
            <div class="row items-center gap-2">
              <div class="live-dot" />
              <span class="text-weight-bold text-neon-cyan">{{ store.activeAsset }}</span>
              <span class="text-caption text-muted">M1 · Ao Vivo</span>
            </div>
            <div class="row items-center gap-2">
              <span class="text-caption text-muted font-mono gt-xs">{{ store.currentPrice.toFixed(5) }}</span>
              <q-badge
                :color="store.priceChange >= 0 ? 'positive' : 'negative'"
                :label="(store.priceChange >= 0 ? '+' : '') + store.priceChange.toFixed(5)"
                dense rounded
              />
            </div>
          </div>
          <div class="chart-body">
            <MiniChart :candles="store.candles" :height="chartHeight" />
          </div>
        </div>
      </div>

      <div class="col-12 col-md-4">
        <div class="chart-container" style="height:100%;">
          <div class="chart-header">
            <span class="text-weight-bold" style="color:var(--text-secondary);">Trades Recentes</span>
            <q-badge color="cyan" :label="botStore.trades.length" rounded />
          </div>
          <q-scroll-area :style="`height:${tradesHeight}px;`">
            <div class="q-pa-sm">
              <div v-if="botStore.trades.length === 0" class="text-center text-muted q-pa-xl text-caption">
                <q-icon name="inbox" size="28px" class="q-mb-xs block" style="opacity:.3;" />
                Nenhum trade hoje
              </div>
              <div
                v-for="trade in botStore.trades.slice(0, 12)"
                :key="trade.id"
                class="trade-row q-py-xs q-px-sm row items-center justify-between q-mb-xs"
                :class="`trade-${trade.status.toLowerCase()}`"
              >
                <div class="row items-center gap-2">
                  <q-icon
                    :name="trade.signal === 'BUY' ? 'trending_up' : 'trending_down'"
                    size="14px"
                    :color="trade.signal === 'BUY' ? 'positive' : 'negative'"
                  />
                  <div>
                    <div class="text-caption text-weight-bold" style="font-size:11px;">
                      {{ trade.signal }} · {{ trade.confidence }}%
                    </div>
                    <div class="text-caption text-muted" style="font-size:10px;">
                      {{ trade.opened_at.slice(11, 16) }}
                    </div>
                  </div>
                </div>
                <div class="text-right">
                  <div
                    class="font-mono text-caption text-weight-bold"
                    :class="trade.status === 'WIN' ? 'text-neon-green' : trade.status === 'LOSS' ? 'text-neon-red' : 'text-muted'"
                  >
                    <template v-if="trade.status === 'OPEN'">···</template>
                    <template v-else>
                      {{ trade.pnl >= 0 ? '+' : '' }}{{ botStore.formatBrl(botStore.usdToBrl(trade.pnl)) }}
                    </template>
                  </div>
                  <q-badge
                    :color="trade.status === 'WIN' ? 'positive' : trade.status === 'LOSS' ? 'negative' : trade.status === 'OPEN' ? 'cyan' : 'grey'"
                    :label="trade.status"
                    dense
                    style="font-size:9px;"
                  />
                </div>
              </div>
            </div>
          </q-scroll-area>
        </div>
      </div>
    </div>

    <!-- Indicators: 1 col mobile / 2 col tablet / 3 col desktop -->
    <div class="row q-col-gutter-md">

      <div class="col-12 col-sm-6 col-md-4">
        <div class="glass-card q-pa-md">
          <div class="text-caption text-muted q-mb-sm" style="letter-spacing:2px;">RSI (14)</div>
          <RsiGauge :value="rsiValue" />
        </div>
      </div>

      <div class="col-12 col-sm-6 col-md-4">
        <div class="glass-card q-pa-md">
          <div class="row items-center justify-between q-mb-sm">
            <span class="text-caption text-muted" style="letter-spacing:2px;">MACD</span>
            <span class="font-mono text-caption text-weight-bold" :class="macdColor">
              {{ macdValue > 0 ? '+' : '' }}{{ macdValue.toFixed(5) }}
            </span>
          </div>
          <MacdBar :value="macdValue" :signal="macdSignalVal" />
          <div class="row justify-between q-mt-md q-px-xs">
            <div class="indicator-mini">
              <span class="text-caption text-muted" style="font-size:10px;">ADX</span>
              <span class="font-mono text-caption text-weight-bold" :class="adxColor">{{ adxValue.toFixed(1) }}</span>
            </div>
            <div class="indicator-mini">
              <span class="text-caption text-muted" style="font-size:10px;">ATR</span>
              <span class="font-mono text-caption text-neon-cyan">{{ atrRatio.toFixed(2) }}x</span>
            </div>
            <div class="indicator-mini">
              <span class="text-caption text-muted" style="font-size:10px;">H1</span>
              <span class="font-mono text-caption" :class="biasColor(store.liveIndicators.h1_bias)">
                {{ store.liveIndicators.h1_bias }}
              </span>
            </div>
            <div class="indicator-mini">
              <span class="text-caption text-muted" style="font-size:10px;">H4</span>
              <span class="font-mono text-caption" :class="biasColor(store.liveIndicators.h4_bias)">
                {{ store.liveIndicators.h4_bias }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="col-12 col-sm-12 col-md-4">
        <div class="glass-card q-pa-md">
          <div class="row items-center justify-between q-mb-sm">
            <span class="text-caption text-muted" style="letter-spacing:2px;">PERFORMANCE HOJE</span>
            <div class="row gap-2">
              <span class="text-caption text-neon-green font-mono">+{{ botStore.formatBrl(botStore.totalWinPnlBrl) }}</span>
              <span class="text-caption text-neon-red font-mono">-{{ botStore.formatBrl(botStore.totalLossPnlBrl) }}</span>
            </div>
          </div>
          <PerformanceBar :data="perfData" />
          <div v-if="perfData.length === 0" class="text-center text-muted text-caption q-mt-md">
            Sem dados de performance
          </div>
        </div>
      </div>
    </div>

    <!-- Padrões detectados (condicional) -->
    <div
      v-if="store.liveIndicators.patterns.length > 0 || store.liveIndicators.divergences.length > 0"
      class="row q-mt-md"
    >
      <div class="col-12">
        <div class="glass-card q-pa-sm row items-center q-gutter-xs flex-wrap">
          <span class="text-caption text-muted q-mr-xs" style="letter-spacing:2px;">PADRÕES</span>
          <q-chip
            v-for="p in store.liveIndicators.patterns"
            :key="p"
            dense color="cyan" text-color="dark" size="sm"
          >{{ p }}</q-chip>
          <q-chip
            v-for="d in store.liveIndicators.divergences"
            :key="d"
            dense color="purple" text-color="white" size="sm"
          >{{ d }}</q-chip>
        </div>
      </div>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useQuasar } from 'quasar'
import { useMarketStore } from 'stores/market'
import { useBotStore } from 'stores/bot'
import MiniChart from 'components/MiniChart.vue'
import RsiGauge from 'components/RsiGauge.vue'
import MacdBar from 'components/MacdBar.vue'
import PerformanceBar from 'components/PerformanceBar.vue'

const $q       = useQuasar()
const store    = useMarketStore()
const botStore = useBotStore()

// Alturas responsivas
const chartHeight = computed(() => $q.screen.lt.md ? ($q.screen.lt.sm ? 180 : 220) : 280)
const tradesHeight = computed(() => $q.screen.lt.md ? 220 : 280)

const lastMarketSignal = computed(() => store.signals[0] ?? null)
const displayStats     = computed(() => botStore.displayStats)
const displayStatsBrl  = computed(() => botStore.displayStatsBrl)

// Indicadores reais do backend
const rsiValue     = computed(() => store.liveIndicators.rsi)
const macdValue    = computed(() => store.liveIndicators.macd)
const macdSignalVal= computed(() => store.liveIndicators.macd_signal)
const adxValue     = computed(() => store.liveIndicators.adx)
const atrRatio     = computed(() => store.liveIndicators.atr_ratio)

// Cores
const accuracyColor = computed(() => {
  const a = displayStats.value.accuracy
  return a >= 65 ? 'text-neon-green' : a >= 50 ? 'text-neon-amber' : 'text-neon-red'
})
const accuracyGradient = computed(() => {
  const a = displayStats.value.accuracy
  return a >= 65 ? 'var(--accent-green)' : a >= 50 ? 'var(--accent-amber)' : 'var(--accent-red)'
})
const pnlColor = computed(() => displayStatsBrl.value.pnl >= 0 ? 'text-neon-green' : 'text-neon-red')
const pnlFormatted = computed(() => {
  const p = displayStatsBrl.value.pnl
  return (p >= 0 ? '+' : '') + botStore.formatBrl(p)
})
const rsiColor = computed(() => {
  const r = rsiValue.value
  return r < 30 ? 'text-neon-green' : r > 70 ? 'text-neon-red' : 'text-neon-cyan'
})
const macdColor   = computed(() => macdValue.value > macdSignalVal.value ? 'text-neon-green' : 'text-neon-red')
const adxColor    = computed(() => adxValue.value >= 25 ? 'text-neon-green' : 'text-neon-amber')
const streakColor = computed(() => {
  const s = displayStats.value.current_streak
  return s > 0 ? 'text-neon-green' : s < 0 ? 'text-neon-red' : 'text-muted'
})

const adaptiveRegime = computed(() => ({
  neutral: 'NEUTRO', reward: 'AGRESSIVO', caution: 'CAUTELOSO', danger: 'PERIGO',
}[botStore.adaptive.regime] ?? botStore.adaptive.regime.toUpperCase()))

const regimeColor = computed(() => ({
  neutral: 'text-neon-cyan', reward: 'text-neon-green',
  caution: 'text-neon-amber', danger: 'text-neon-red',
}[botStore.adaptive.regime] ?? 'text-muted'))

function biasColor(bias: string) {
  if (bias === 'BUY' || bias === 'BULLISH') return 'text-neon-green'
  if (bias === 'SELL' || bias === 'BEARISH') return 'text-neon-red'
  return 'text-muted'
}

// Performance real: agrupa trades fechados por hora
const perfData = computed(() => {
  const closed = botStore.trades.filter(t => t.status === 'WIN' || t.status === 'LOSS')
  if (closed.length === 0) return []

  const byHour: Record<string, { wins: number; losses: number }> = {}
  closed.forEach(t => {
    const hour = (t.opened_at?.slice(11, 13) ?? '00') + 'h'
    if (!byHour[hour]) byHour[hour] = { wins: 0, losses: 0 }
    if (t.status === 'WIN') byHour[hour].wins++
    else byHour[hour].losses++
  })

  return Object.entries(byHour)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, data]) => ({ day, ...data }))
})
</script>

<style lang="scss" scoped>
.dashboard-page {
  background: var(--bg-deep);
  min-height: 100vh;

  // Padding responsivo
  padding: 24px;

  @media (max-width: 1023px) { padding: 16px; }
  @media (max-width: 599px)  { padding: 10px; }
}

.font-mono { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.gap-1 { gap: 4px; }
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }
.block { display: block; }

/* Status bar */
.status-bar {
  padding: 10px 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.bot-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;

  &.badge-live {
    background: rgba(0,255,136,0.12);
    border: 1px solid rgba(0,255,136,0.35);
    color: var(--accent-green);
  }
  &.badge-off {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    color: var(--text-muted);
  }
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;

  &.dot-live {
    background: var(--accent-green);
    animation: pulse-live 1.5s ease-in-out infinite;
  }
  &.dot-off {
    background: var(--text-muted);
  }
}

/* Stat bar */
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
.stat-sub { line-height: 1.2; }

/* Signal pill */
.signal-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  border-radius: 100px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;

  &.pill-buy  { background: rgba(0,255,136,0.15); border: 1px solid rgba(0,255,136,0.4); color: var(--accent-green); }
  &.pill-sell { background: rgba(255,68,68,0.15);  border: 1px solid rgba(255,68,68,0.4);  color: var(--accent-red); }
  &.pill-wait { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15); color: var(--text-muted); }
}

/* Trade rows */
.trade-row {
  border-radius: 8px;
  border: 1px solid transparent;
  transition: background 0.15s;

  &.trade-win  { background: rgba(0,255,136,0.05); border-color: rgba(0,255,136,0.12); }
  &.trade-loss { background: rgba(255,68,68,0.05); border-color: rgba(255,68,68,0.12); }
  &.trade-open { background: rgba(0,229,255,0.05); border-color: rgba(0,229,255,0.12); }
  &.trade-error { background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.06); }
}

/* Indicator mini */
.indicator-mini {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

@keyframes pulse-live {
  0%, 100% { opacity: 1;   box-shadow: 0 0 6px var(--accent-green); }
  50%       { opacity: 0.6; box-shadow: 0 0 12px var(--accent-green); }
}
</style>
