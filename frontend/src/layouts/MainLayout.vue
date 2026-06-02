<template>
  <q-layout view="lHh Lpr lFf">
    <!-- Header -->
    <q-header elevated>
      <q-toolbar style="min-height:52px; padding: 0 8px;">
        <q-btn flat round dense icon="menu" @click="drawer = !drawer" color="grey-5" />

        <div class="row items-center q-ml-sm gap-2">
          <div class="logo-mark" />
          <span class="text-weight-bold tracking-widest text-neon-cyan logo-text">ANA</span>
          <span class="text-weight-light text-grey-5 logo-text">GRAPH</span>
        </div>

        <q-space />

        <!-- Status bot (sempre visível) -->
        <div class="row items-center gap-2 q-mr-sm">
          <div :class="['live-dot', botStore.running ? '' : 'dot-sim']" />
          <span
            class="text-caption text-weight-bold"
            :class="botStore.running ? 'text-neon-green' : 'text-neon-cyan'"
            style="letter-spacing:1px;"
          >
            {{ botStore.running ? 'ON' : (botStore.accountIsDemo ? 'DEMO' : 'REAL') }}
          </span>
        </div>

        <!-- Saldo (oculto em mobile xs) -->
        <div
          v-if="botStore.accountBalance !== null"
          class="balance-chip q-mr-sm gt-xs"
          :class="botStore.accountIsDemo ? 'chip-demo' : 'chip-real'"
        >
          <q-icon name="account_balance_wallet" size="13px" />
          <span class="font-mono text-weight-bold">
            {{ botStore.formatBrl(botStore.accountBalanceBrl ?? 0) }}
          </span>
        </div>
        <div v-else-if="botStore.accountLoadFailed" class="text-caption text-neon-amber q-mr-sm gt-xs">
          <q-btn flat dense size="xs" icon="refresh" color="amber" @click="botStore.fetchAccountStatus()" />
        </div>

        <!-- Preço ativo (oculto em mobile) -->
        <div class="row items-center gap-2 q-mr-sm gt-sm" v-if="store.connected">
          <div class="text-right">
            <div class="text-caption text-muted" style="font-size:10px;">{{ store.activeAsset }}</div>
            <div class="text-caption text-neon-cyan font-mono text-weight-bold">
              {{ store.currentPrice.toFixed(5) }}
            </div>
          </div>
          <q-badge
            :color="store.priceChange >= 0 ? 'positive' : 'negative'"
            :label="(store.priceChange >= 0 ? '+' : '') + store.priceChange.toFixed(4)"
            dense rounded
          />
        </div>

        <q-btn flat round icon="logout" color="grey-5" size="sm" @click="logout" title="Sair" />
      </q-toolbar>
    </q-header>

    <!-- Drawer: show-if-above no sm+, mobile fecha sozinho -->
    <q-drawer v-model="drawer" show-if-above :width="210" :breakpoint="700">
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
  display: flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: 10px;
  font-size: 13px;
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

.logo-text {
  font-size: 18px;
  @media (max-width: 599px) { font-size: 15px; letter-spacing: 2px; }
}

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
