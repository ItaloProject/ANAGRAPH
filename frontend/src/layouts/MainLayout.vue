<template>
  <q-layout view="lHh Lpr lFf">
    <!-- Header -->
    <q-header elevated>
      <q-toolbar style="min-height:56px;">
        <q-btn flat round dense icon="menu" @click="drawer = !drawer" color="grey-5" />

        <div class="row items-center q-ml-md gap-2">
          <div class="logo-mark" />
          <span class="text-weight-bold text-h6 tracking-widest text-neon-cyan">ANA</span>
          <span class="text-weight-light text-h6 text-grey-5">GRAPH</span>
        </div>

        <q-space />

        <!-- Bot / Demo + saldo DERIV -->
        <div class="row items-center gap-2 q-mr-md">
          <div :class="['live-dot', botStore.running ? '' : 'dot-sim']" />
          <span class="text-caption" :class="botStore.running ? 'text-neon-green' : 'text-neon-cyan'"
            style="letter-spacing:1px;">
            {{ botStore.running ? 'BOT ON' : (botStore.accountIsDemo ? 'DEMO' : 'REAL') }}
          </span>
        </div>

        <!-- Saldo conta DERIV -->
        <div
          v-if="botStore.accountBalance !== null"
          class="balance-chip q-mr-md"
          :class="botStore.accountIsDemo ? 'chip-demo' : 'chip-real'"
        >
          <q-icon name="account_balance_wallet" size="14px" />
          <div class="balance-text">
            <span v-if="botStore.accountBalanceBrl !== null" class="font-mono text-weight-bold">
              {{ botStore.formatBrl(botStore.accountBalanceBrl) }}
            </span>
            <span class="text-caption text-muted q-ml-xs">conta USD</span>
          </div>
          <span v-if="botStore.accountLoginId" class="text-caption login-hint">
            {{ botStore.accountLoginId }}
          </span>
        </div>
        <div v-else-if="botStore.accountLoadFailed" class="text-caption text-neon-amber q-mr-md">
          Saldo indisponível
          <q-btn flat dense size="xs" icon="refresh" color="amber" @click="botStore.fetchAccountStatus()" />
        </div>
        <div v-else-if="botStore.backendOnline" class="text-caption text-muted q-mr-md">
          Carregando saldo...
        </div>

        <!-- Current asset price -->
        <div class="row items-center gap-3 q-mr-lg" v-if="store.connected">
          <div class="text-right">
            <div class="text-caption text-muted">{{ store.activeAsset }}</div>
            <div class="text-subtitle2 text-neon-cyan font-mono">
              {{ store.currentPrice.toFixed(5) }}
            </div>
          </div>
          <q-badge
            :color="store.priceChange >= 0 ? 'positive' : 'negative'"
            :label="(store.priceChange >= 0 ? '+' : '') + store.priceChange.toFixed(4)"
            rounded
          />
        </div>

        <!-- Account info -->
        <div class="row items-center gap-2 q-mr-sm" v-if="authStore.isLoggedIn">
          <div class="account-chip" :class="authStore.isDemo ? 'chip-demo' : 'chip-real'">
            <q-icon :name="authStore.isDemo ? 'school' : 'account_balance'" size="12px" />
            <span>{{ authStore.accountLabel }}</span>
          </div>
        </div>

        <q-btn flat round icon="logout" color="grey-5" size="sm" @click="logout" title="Sair" />
      </q-toolbar>
    </q-header>

    <!-- Drawer -->
    <q-drawer v-model="drawer" show-if-above :width="220" :breakpoint="700">
      <q-scroll-area class="fit">
        <div class="q-pt-lg q-pb-md q-px-md">
          <div class="text-caption text-muted q-mb-md" style="letter-spacing:2px;">NAVIGATION</div>

          <q-list padding>
            <q-item
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              exact
              clickable
              v-ripple
              class="nav-item q-mb-xs"
              style="border-radius:10px;"
            >
              <q-item-section avatar>
                <q-icon :name="item.icon" size="20px" />
              </q-item-section>
              <q-item-section>
                <q-item-label class="text-weight-medium" style="font-size:13px;">
                  {{ item.label }}
                </q-item-label>
              </q-item-section>
              <q-item-section side v-if="item.badge">
                <q-badge :color="item.badgeColor || 'accent'" :label="item.badge" rounded />
              </q-item-section>
            </q-item>
          </q-list>

          <q-separator class="q-my-lg" />
          <div class="text-caption text-muted q-mb-md" style="letter-spacing:2px;">INDICATORS</div>

          <div class="indicator-list q-px-sm">
            <div
              v-for="ind in indicators"
              :key="ind.name"
              class="indicator-row row items-center justify-between q-py-xs"
            >
              <span class="text-caption text-secondary">{{ ind.name }}</span>
              <span class="text-caption font-mono" :class="ind.color">{{ ind.value }}</span>
            </div>
          </div>
        </div>

        <!-- Version -->
        <div class="absolute-bottom q-pa-md">
          <div class="text-caption text-muted text-center">ANAGRAPH v1.0.0</div>
          <div class="text-caption text-muted text-center" style="font-size:10px;">
            Powered by DERIV API
          </div>
        </div>
      </q-scroll-area>
    </q-drawer>

    <!-- Page content -->
    <q-page-container>
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMarketStore } from 'stores/market'
import { useBotStore } from '../stores/bot'
import { useAuthStore } from '../stores/auth'

const router    = useRouter()
const drawer    = ref(true)
const store     = useMarketStore()
const botStore  = useBotStore()
const authStore = useAuthStore()
store.connect()

function logout() {
  botStore.stopBot()
  authStore.logout()
  router.push('/login')
}

const navItems = [
  { path: '/',         icon: 'dashboard',        label: 'Dashboard',  badge: null },
  { path: '/live',     icon: 'radio_button_checked', label: 'Ao Vivo', badge: 'LIVE', badgeColor: 'positive' },
  { path: '/chart',    icon: 'candlestick_chart', label: 'Gráfico',   badge: null },
  { path: '/signals',  icon: 'bolt',             label: 'Sinais',     badge: null },
  { path: '/backtest', icon: 'query_stats',      label: 'Backtest',   badge: null },
  { path: '/settings', icon: 'tune',             label: 'Config',     badge: null },
]

const indicators = computed(() => {
  const li = store.liveIndicators
  if (botStore.running) {
    return [
      { name: 'RSI (14)',  value: li.rsi.toFixed(1),  color: li.rsi < 30 ? 'text-neon-green' : li.rsi > 70 ? 'text-neon-red' : 'text-neon-cyan' },
      { name: 'MACD',      value: (li.macd > 0 ? '+' : '') + li.macd.toFixed(5), color: li.macd > li.macd_signal ? 'text-neon-green' : 'text-neon-red' },
      { name: 'BB Upper',  value: li.bb_upper ? li.bb_upper.toFixed(5) : '—', color: 'text-secondary' },
      { name: 'BB Lower',  value: li.bb_lower ? li.bb_lower.toFixed(5) : '—', color: 'text-secondary' },
      { name: 'EMA 9',     value: li.ema9 ? li.ema9.toFixed(5) : '—', color: 'text-neon-cyan' },
      { name: 'EMA 21',    value: li.ema21 ? li.ema21.toFixed(5) : '—', color: 'text-secondary' },
      { name: 'Previsão',  value: li.last_signal === 'BUY' ? 'SOBE ↑' : li.last_signal === 'SELL' ? 'DESCE ↓' : 'AGUARDAR', color: 'text-neon-purple' },
    ]
  }
  return [
    { name: 'RSI (14)',  value: '—', color: 'text-muted' },
    { name: 'MACD',      value: '—', color: 'text-muted' },
    { name: 'BB Upper',  value: '—', color: 'text-muted' },
    { name: 'BB Lower',  value: '—', color: 'text-muted' },
    { name: 'EMA 9',     value: '—', color: 'text-muted' },
    { name: 'EMA 21',    value: '—', color: 'text-muted' },
    { name: 'Sinal',     value: 'OFF', color: 'text-muted' },
  ]
})

let priceInterval: ReturnType<typeof setInterval>
let balanceInterval: ReturnType<typeof setInterval>

onMounted(() => {
  botStore.connectBackend()
  botStore.checkBackend()
  botStore.fetchAccountStatus()
  priceInterval = setInterval(() => {
    if (!botStore.running && !botStore.backendOnline) store.simulateTick()
  }, 1200)
  balanceInterval = setInterval(() => botStore.fetchAccountStatus(), 30000)
})
onUnmounted(() => {
  clearInterval(priceInterval)
  clearInterval(balanceInterval)
})
</script>

<style lang="scss" scoped>
.dot-sim { background: var(--accent-cyan) !important; animation: pulse-cyan 2s ease-in-out infinite; }
.account-chip {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 100px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
  &.chip-demo {
    background: rgba(0,255,136,0.1);
    color: var(--accent-green);
    border: 1px solid rgba(0,255,136,0.3);
  }
  &.chip-real {
    background: rgba(255,184,0,0.1);
    color: var(--accent-amber);
    border: 1px solid rgba(255,184,0,0.3);
  }
}
.balance-chip {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-radius: 10px;
  &.chip-demo {
    background: rgba(0,255,136,0.08);
    border: 1px solid rgba(0,255,136,0.25);
    color: var(--accent-green);
  }
  &.chip-real {
    background: rgba(255,184,0,0.08);
    border: 1px solid rgba(255,184,0,0.25);
    color: var(--accent-amber);
  }
  .balance-text { line-height: 1.1; }
  .login-hint {
    color: var(--text-muted);
    font-size: 10px;
    padding-left: 8px;
    border-left: 1px solid rgba(255,255,255,0.1);
  }
}
.logo-mark {
  width: 8px; height: 8px;
  background: var(--accent-cyan);
  border-radius: 2px;
  box-shadow: var(--glow-cyan);
  transform: rotate(45deg);
  margin-right: 2px;
}
.tracking-widest { letter-spacing: 4px; }
.font-mono { font-family: 'Roboto Mono', monospace; }
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }
.text-muted { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }

.indicator-row {
  border-bottom: 1px solid rgba(255,255,255,0.04);
  &:last-child { border-bottom: none; }
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
