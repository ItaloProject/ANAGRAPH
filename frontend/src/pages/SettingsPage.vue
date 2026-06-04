<template>
  <q-page class="settings-page">

    <!-- ── Toolbar ── -->
    <div class="st-toolbar">
      <div>
        <div class="text-weight-bold text-neon-cyan" style="font-size:18px;letter-spacing:3px;">CONFIGURAÇÕES</div>
        <div class="text-caption text-muted">Modo conservador — qualidade sobre quantidade</div>
      </div>
      <div class="row items-center gap-2">
        <div :class="['status-dot', botStore.backendOnline ? 'dot-green' : 'dot-red']" />
        <span class="text-caption" :class="botStore.backendOnline ? 'text-neon-green' : 'text-neon-red'">
          {{ botStore.backendOnline ? 'Backend Online' : 'Backend Offline' }}
        </span>
        <q-btn flat round dense icon="refresh" size="sm" color="grey-6" @click="botStore.checkBackend()" />
      </div>
    </div>

    <!-- ── Barra Start/Stop em destaque ── -->
    <div class="bot-control-bar" :class="botStore.running ? 'bcb-live' : 'bcb-off'">
      <div class="row items-center gap-3">
        <div :class="['bot-dot', botStore.running ? 'bd-live' : 'bd-off']" />
        <div>
          <div class="text-caption text-muted" style="font-size:10px;letter-spacing:1px;">ESTADO DO ROBÔ</div>
          <div class="text-weight-bold" :class="botStore.running ? 'text-neon-green' : 'text-muted'" style="font-size:15px;">
            {{ botStore.running ? 'ATIVO — roda no servidor 24/7' : 'INATIVO' }}
          </div>
          <div v-if="botStore.running" class="text-caption text-muted" style="font-size:10px;">
            Pode fechar o app — o robô continua operando
          </div>
        </div>
      </div>

      <div class="row items-center gap-3 flex-wrap">
        <div v-if="errorMsg" class="error-msg">
          <q-icon name="error_outline" size="14px" />
          {{ errorMsg }}
        </div>
        <q-btn
          v-if="!botStore.running"
          unelevated size="md" color="positive" icon="play_arrow"
          label="INICIAR ROBÔ"
          :loading="starting"
          :disable="!canStart"
          @click="startBot"
          style="font-weight:700;letter-spacing:1px;min-width:160px;"
        />
        <q-btn
          v-else
          unelevated size="md" color="negative" icon="stop"
          label="PARAR ROBÔ"
          :loading="stopping"
          @click="stopBot"
          style="font-weight:700;letter-spacing:1px;min-width:160px;"
        />
      </div>
    </div>

    <!-- ── Corpo ── -->
    <div class="st-body">

      <!-- Coluna esquerda -->
      <div class="st-col-left">

        <!-- Checklist de pré-voo -->
        <div class="preflight-card q-mb-md">
          <div class="section-title">PRÉ-VOO</div>
          <div class="preflight-list">
            <div class="pf-item" :class="botStore.backendOnline ? 'pf-ok' : 'pf-fail'">
              <q-icon :name="botStore.backendOnline ? 'check_circle' : 'cancel'" size="16px" />
              <span>Backend acessível</span>
            </div>
            <div class="pf-item" :class="accountReady ? 'pf-ok' : 'pf-warn'">
              <q-icon :name="accountReady ? 'check_circle' : 'warning'" size="16px" />
              <span>{{ accountReady ? 'Conta conectada' : 'Conta não configurada' }}</span>
            </div>
            <div class="pf-item" :class="botStore.running ? 'pf-ok' : 'pf-warn'">
              <q-icon :name="botStore.running ? 'cloud_done' : 'cloud_off'" size="16px" />
              <span>{{ botStore.running ? 'Robô ativo no servidor (2º plano)' : 'Robô parado no servidor' }}</span>
            </div>
            <div class="pf-item" :class="riskOk ? 'pf-ok' : 'pf-warn'">
              <q-icon :name="riskOk ? 'check_circle' : 'warning'" size="16px" />
              <span>{{ riskOk ? 'Risco dentro do limite' : 'Stake alto em relação ao limite' }}</span>
            </div>
          </div>
        </div>

        <!-- Conta Deriv -->
        <div class="glass-card q-pa-lg">
          <div class="section-title">DERIV API</div>

          <div v-if="authStore.isLoggedIn" class="connected-box q-mb-md">
            <q-icon name="check_circle" color="positive" size="18px" />
            <div>
              <div class="text-caption text-muted">Conta OAuth</div>
              <div class="text-weight-bold" :class="authStore.isDemo ? 'text-neon-green' : 'text-neon-amber'">
                {{ authStore.accountLabel }}
              </div>
            </div>
            <q-space />
            <q-badge :color="authStore.isDemo ? 'positive' : 'warning'"
              :label="authStore.isDemo ? 'DEMO' : 'REAL'" rounded />
          </div>

          <div v-else-if="serverCredentials" class="connected-box q-mb-md">
            <q-icon name="vpn_key" color="positive" size="18px" />
            <div>
              <div class="text-caption text-muted">Servidor (.env)</div>
              <div class="text-weight-bold text-neon-green">Token + conta configurados</div>
            </div>
            <q-space />
            <q-badge color="positive" label="AUTO" rounded />
          </div>

          <div v-else class="q-mb-sm">
            <q-input v-model="config.api_token" label="API Token DERIV *" dark filled
              type="password" color="cyan" label-color="grey-6" class="q-mb-sm"
              hint="Token gerado em developers.deriv.com → API Tokens">
              <template #prepend><q-icon name="vpn_key" color="grey-6" /></template>
            </q-input>
            <q-input v-model="config.account_id" label="Account ID (Demo)" dark filled
              color="cyan" label-color="grey-6"
              hint="Ex: DOT91884478">
              <template #prepend><q-icon name="person" color="grey-6" /></template>
            </q-input>
          </div>

          <div class="setting-row q-mb-sm">
            <span class="row-label">Ativo</span>
            <span class="text-neon-cyan text-weight-bold font-mono">
              {{ config.auto_asset ? 'Auto (EUR/USD · USD/JPY)' : 'EUR/USD' }}
            </span>
          </div>
          <div class="setting-row q-mb-sm">
            <span class="row-label">Timeframe</span>
            <span class="text-neon-cyan text-weight-bold">M15</span>
          </div>

          <div class="q-mb-sm">
            <div class="row-label q-mb-xs">Horizonte de análise</div>
            <q-btn-toggle v-model="config.contract_duration"
              :options="durations"
              toggle-color="purple" color="transparent" text-color="grey-5"
              unelevated dense />
            <div class="text-caption text-muted q-mt-xs">
              <span v-if="config.contract_duration <= 15">
                M15 — análise e contrato em 15 min
              </span>
              <span v-else>
                H1 — análise horária, contrato 15 min (limite Deriv Rise/Fall)
              </span>
            </div>
          </div>

          <!-- Multi-ativo automático -->
          <div class="auto-asset-box q-mb-sm">
            <div class="row items-center justify-between">
              <div>
                <div class="row-label text-weight-bold">Multi-ativo automático (24h)</div>
                <div class="text-caption text-muted">Opera o par certo para cada sessão</div>
              </div>
              <q-toggle v-model="config.auto_asset" color="cyan" />
            </div>
            <div v-if="config.auto_asset" class="auto-asset-detail q-mt-xs">
              <q-icon name="schedule" size="12px" color="cyan" />
              <span class="text-caption text-muted">
                <b class="text-neon-cyan">EUR/USD</b> em London/NY (07–20:30 UTC) ·
                <b class="text-neon-cyan">USD/JPY</b> na sessão asiática (volume real de Tóquio)
              </span>
            </div>
          </div>

          <div class="q-mb-sm" v-if="!config.auto_asset">
            <div class="row-label q-mb-xs">Horário de operação</div>
            <q-btn-toggle v-model="config.session_mode"
              :options="sessionModes"
              toggle-color="cyan" color="transparent" text-color="grey-5"
              unelevated dense />
            <div class="text-caption q-mt-xs" :class="config.session_mode === 'all' ? 'text-neon-amber' : 'text-muted'">
              <template v-if="config.session_mode === 'all'">⚠ 24h — opera em qualquer horário, inclusive sessão asiática</template>
              <template v-else-if="config.session_mode === 'london_ny'">London 07–16 + New York 13–20:30 UTC (recomendado)</template>
              <template v-else-if="config.session_mode === 'london'">Apenas London 07:00–16:00 UTC</template>
              <template v-else-if="config.session_mode === 'new_york'">Apenas New York 13:00–20:30 UTC</template>
              <template v-else-if="config.session_mode === 'asian'">Apenas Asian 21:00–07:00 UTC (baixa liquidez)</template>
            </div>
          </div>
        </div>
      </div>

      <!-- Coluna direita -->
      <div class="st-col-right">

        <!-- Perfil -->
        <div class="glass-card q-pa-lg q-mb-md">
          <div class="section-title">PERFIL CONSERVADOR</div>

          <div class="profile-badge q-mb-md">
            <q-icon name="verified" color="positive" size="20px" />
            <div>
              <div class="text-weight-bold text-neon-green">Modo Precisão ativo</div>
              <div class="text-caption text-muted">EUR/USD · M15 · conf ≥78% · ADX ≥22 · confluência 5+</div>
            </div>
          </div>

          <div class="strategy-note q-mb-md">
            <q-icon name="info" size="14px" color="cyan" />
            <span class="text-caption text-muted">
              O bot só opera quando RSI, MACD, BB, EMA e ADX concordam.
              Menos operações, análise mais rigorosa — proteção do capital em primeiro lugar.
            </span>
          </div>

          <!-- Cotação USD/BRL -->
          <div class="currency-note q-mb-lg">
            <q-icon name="currency_exchange" size="13px" color="amber" />
            <span class="text-caption text-muted">
              Limites em R$ — execução em USD (cotação ~R$ {{ usdRate.toFixed(2) }}/US$)
            </span>
          </div>

          <!-- Sliders de risco -->
          <div class="section-title">GERENCIAMENTO DE RISCO</div>

          <div class="slider-block">
            <div class="slider-header">
              <span class="row-label">Stake por Operação</span>
              <span class="text-neon-cyan font-mono">R$ {{ config.stake_amount?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.stake_amount" :min="3" :max="300" :step="1" color="cyan" dark />
            <div class="slider-hint">
              {{ ((config.stake_amount ?? 1) / (config.daily_loss_limit ?? 1) * 100).toFixed(1) }}% do limite diário por trade
            </div>
          </div>

          <div class="slider-block">
            <div class="slider-header">
              <span class="row-label">Stake Máximo</span>
              <span class="text-neon-cyan font-mono">R$ {{ config.max_stake?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.max_stake" :min="10" :max="600" :step="5" color="cyan" dark />
          </div>

          <div class="slider-block">
            <div class="slider-header">
              <span class="row-label">Limite de Perda Diária</span>
              <span class="text-neon-red font-mono">-R$ {{ config.daily_loss_limit?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.daily_loss_limit" :min="20" :max="2000" :step="10" color="negative" dark />
            <div class="risk-progress-wrap">
              <div
                class="risk-progress-fill"
                :style="{
                  width: Math.min(100, (botStore.displayStatsBrl.pnl < 0 ? Math.abs(botStore.displayStatsBrl.pnl) / (config.daily_loss_limit ?? 1) * 100 : 0)) + '%',
                  background: 'var(--accent-red)'
                }"
              />
            </div>
            <div class="slider-hint text-neon-red" v-if="botStore.displayStatsBrl.pnl < 0">
              {{ Math.abs(botStore.displayStatsBrl.pnl).toFixed(2) }} /
              {{ config.daily_loss_limit?.toFixed(2) }} usados hoje
            </div>
          </div>

          <div class="slider-block">
            <div class="slider-header">
              <span class="row-label">Meta de Lucro Diária</span>
              <span class="text-neon-green font-mono">+R$ {{ config.daily_profit_target?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.daily_profit_target" :min="30" :max="2000" :step="10" color="positive" dark />
          </div>

          <div class="slider-block">
            <div class="slider-header">
              <span class="row-label">Confiança Mínima</span>
              <span class="text-neon-cyan font-mono">{{ config.min_confidence?.toFixed(0) }}%</span>
            </div>
            <q-slider v-model="config.min_confidence" :min="60" :max="95" :step="1" color="cyan" dark />
            <div class="slider-hint">Recomendado: ≥78% — só opera sinais fortes</div>
          </div>

          <!-- Resumo de risco -->
          <div class="risk-summary">
            <div class="risk-row">
              <span class="text-muted">Risco por trade</span>
              <span class="font-mono" :class="parseFloat(String(riskPct)) > 10 ? 'text-neon-red' : 'text-neon-cyan'">
                {{ riskPct }}% do limite
              </span>
            </div>
            <div class="risk-row">
              <span class="text-muted">Ratio Lucro/Risco</span>
              <span class="font-mono" :class="parseFloat(String(ratio)) >= 2 ? 'text-neon-green' : 'text-neon-red'">
                {{ ratio }}:1
              </span>
            </div>
            <div class="risk-row">
              <span class="text-muted">Trades até stop diário</span>
              <span class="text-neon-cyan font-mono">{{ maxTrades }}</span>
            </div>
          </div>
        </div>

        <!-- Indicadores -->
        <div class="glass-card q-pa-lg">
          <div class="section-title">INDICADORES ATIVOS</div>
          <div class="row q-gutter-sm q-mb-sm">
            <q-chip v-for="ind in indicators" :key="ind.name"
              :selected="ind.active"
              :color="ind.active ? ind.color : 'transparent'"
              :text-color="ind.active ? 'white' : 'grey-6'"
              :outline="!ind.active"
              clickable
              @click="ind.active = !ind.active"
            >{{ ind.name }}</q-chip>
          </div>
          <div class="text-caption text-muted">
            Confluência de RSI, MACD, BB, EMA, Stochastic e ADX — quanto mais concordam, maior a confiança
          </div>
        </div>
      </div>
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useBotStore } from '../stores/bot'
import { useAuthStore } from '../stores/auth'
import { CONSERVATIVE_PROFILE, enforceConservative } from '../config/conservative'
import type { BotConfig } from '../services/botApi'
import { botApi } from '../services/botApi'
import { migrateConfigToBrl, getUsdBrlRate } from '../utils/currency'

const $q        = useQuasar()
const botStore  = useBotStore()
const authStore = useAuthStore()

const starting          = ref(false)
const stopping          = ref(false)
const errorMsg          = ref('')
const serverCredentials = ref(false)

const STORAGE_KEY = 'anagraph_config'

function defaultConfig(): BotConfig {
  return { api_token: '', app_id: '33qwHdRH3vY9cCAeAzIa7', account_id: '', ...CONSERVATIVE_PROFILE }
}

function loadConfig(): BotConfig {
  const def = defaultConfig()
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      Object.keys(parsed).forEach(k => {
        if (parsed[k] === '' || parsed[k] === null || parsed[k] === undefined) delete parsed[k]
      })
      if (parsed.multiplier && !parsed.contract_duration) parsed.contract_duration = 15
      if (parsed.contract_duration && parsed.contract_duration < 15) parsed.contract_duration = 15
      delete parsed.multiplier; delete parsed.stop_loss; delete parsed.take_profit
      return enforceConservative(migrateConfigToBrl({ ...def, ...parsed }))
    }
  } catch { /* ignore */ }
  return def
}

const config  = ref<BotConfig>(loadConfig())
const usdRate = computed(() => getUsdBrlRate())

const durations = [
  { label: 'M15', value: 15 },
  { label: 'H1 (30m)', value: 30 },
  { label: 'H1 (60m)', value: 60 },
]

const sessionModes = [
  { label: '24h',       value: 'all'      },
  { label: 'London+NY', value: 'london_ny' },
  { label: 'London',    value: 'london'   },
  { label: 'New York',  value: 'new_york' },
  { label: 'Asian',     value: 'asian'    },
]

const indicators = ref([
  { name: 'RSI',   active: true, color: 'amber'    },
  { name: 'MACD',  active: true, color: 'cyan'     },
  { name: 'BB',    active: true, color: 'purple'   },
  { name: 'EMA',   active: true, color: 'positive' },
  { name: 'ADX',   active: true, color: 'orange'   },
  { name: 'Stoch', active: true, color: 'pink'     },
])

// Computed de risco
const riskPct   = computed(() => ((config.value.stake_amount ?? 1) / (config.value.daily_loss_limit ?? 20) * 100).toFixed(1))
const ratio     = computed(() => ((config.value.daily_profit_target ?? 50) / (config.value.daily_loss_limit ?? 20)).toFixed(1))
const maxTrades = computed(() => Math.floor((config.value.daily_loss_limit ?? 20) / (config.value.stake_amount ?? 1)))

// Pré-voo
const accountReady = computed(() =>
  authStore.isLoggedIn || serverCredentials.value || !!config.value.api_token
)
const riskOk   = computed(() => parseFloat(String(riskPct.value)) <= 15)
const canStart  = computed(() => botStore.backendOnline && accountReady.value)

async function startBot() {
  const payload: BotConfig = enforceConservative({ ...config.value, api_token: '', account_id: '' })
  const oauthToken = authStore.account?.token
  if (oauthToken && oauthToken !== 'server') {
    payload.api_token  = oauthToken
    payload.account_id = authStore.account!.account
  }
  errorMsg.value = ''
  starting.value = true
  try {
    await botStore.startBot(payload)
    $q.notify({ type: 'positive', message: 'Robô iniciado — modo precisão conservador', position: 'top-right' })
  } catch (e: any) {
    errorMsg.value = e.message
    $q.notify({ type: 'negative', message: e.message, position: 'top-right' })
  } finally {
    starting.value = false
  }
}

async function stopBot() {
  stopping.value = true
  try {
    await botStore.stopBot()
    $q.notify({ type: 'warning', message: 'Robô parado.', position: 'top-right' })
  } finally {
    stopping.value = false
  }
}

watch(config, (val) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(enforceConservative({ ...val, api_token: '' })))
}, { deep: true })

onMounted(async () => {
  await botStore.fetchCurrencyConfig()
  config.value = enforceConservative(migrateConfigToBrl(config.value))
  botStore.checkBackend()
  try {
    const res = await botApi.credentials()
    serverCredentials.value = res.data.token_configured && res.data.account_configured
  } catch { /* offline */ }
})
</script>

<style lang="scss" scoped>
.settings-page { background: var(--bg-deep); min-height: 100vh; }

.font-mono  { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }

// ── Toolbar ───────────────────────────────────────────────────────────────────
.st-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px;
  padding: 14px 20px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  @media (max-width: 599px) { padding: 12px; }
}

// ── Bot control bar ───────────────────────────────────────────────────────────
.bot-control-bar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px;
  padding: 16px 20px;
  border-bottom: 2px solid transparent;
  transition: background 0.3s, border-color 0.3s;

  &.bcb-live {
    background: rgba(0,255,136,0.05);
    border-bottom-color: rgba(0,255,136,0.3);
  }
  &.bcb-off {
    background: rgba(0,0,0,0.2);
    border-bottom-color: var(--border-subtle);
  }
  @media (max-width: 599px) { padding: 12px; }
}
.bot-dot {
  width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0;
  &.bd-live { background: var(--accent-green); box-shadow: 0 0 12px var(--accent-green); animation: pulse-green 1.5s ease-in-out infinite; }
  &.bd-off  { background: rgba(255,255,255,0.12); }
}
.error-msg {
  display: flex; align-items: center; gap: 5px;
  color: var(--accent-red); font-size: 12px; max-width: 260px;
}

// ── Body ──────────────────────────────────────────────────────────────────────
.st-body {
  display: flex; gap: 20px; align-items: flex-start;
  padding: 20px;
  @media (max-width: 1023px) { flex-direction: column; padding: 14px; gap: 14px; }
  @media (max-width: 599px)  { padding: 10px; gap: 10px; }
}

.st-col-left  { width: 300px; flex-shrink: 0; @media (max-width: 1023px) { width: 100%; } }
.st-col-right { flex: 1; min-width: 0; }

// ── Preflight card ────────────────────────────────────────────────────────────
.preflight-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 16px 18px;
}
.preflight-list { display: flex; flex-direction: column; gap: 8px; }
.pf-item {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; font-weight: 600;
  padding: 6px 10px; border-radius: 8px;
  &.pf-ok   { background: rgba(0,255,136,0.07); color: var(--accent-green); }
  &.pf-warn { background: rgba(255,184,0,0.07); color: var(--accent-amber); }
  &.pf-fail { background: rgba(255,68,102,0.07); color: var(--accent-red); }
}

// ── Section title ─────────────────────────────────────────────────────────────
.section-title {
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted); text-transform: uppercase;
  margin-bottom: 14px; padding-bottom: 8px;
  border-bottom: 1px solid var(--border-subtle);
}

// ── Connected box ─────────────────────────────────────────────────────────────
.connected-box {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px; border-radius: 10px;
  background: rgba(0,255,136,0.06);
  border: 1px solid rgba(0,255,136,0.2);
}

// ── Auto-asset box ────────────────────────────────────────────────────────────
.auto-asset-box {
  padding: 10px 12px; border-radius: 10px;
  background: rgba(0,212,255,0.05);
  border: 1px solid rgba(0,212,255,0.15);
}
.auto-asset-detail {
  display: flex; align-items: flex-start; gap: 6px;
  padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.05);
}

// ── Setting row ───────────────────────────────────────────────────────────────
.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  &:last-child { border-bottom: none; }
}
.row-label { font-size: 12px; color: var(--text-secondary); }

// ── Profile & notes ───────────────────────────────────────────────────────────
.profile-badge {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; border-radius: 10px;
  background: rgba(0,255,136,0.06);
  border: 1px solid rgba(0,255,136,0.2);
}
.strategy-note {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 12px; border-radius: 10px;
  background: rgba(0,212,255,0.05);
  border: 1px solid rgba(0,212,255,0.12);
}
.currency-note {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px; border-radius: 8px;
  background: rgba(255,184,0,0.05);
  border: 1px solid rgba(255,184,0,0.12);
}

// ── Sliders ───────────────────────────────────────────────────────────────────
.slider-block {
  margin-bottom: 20px;
  &:last-of-type { margin-bottom: 16px; }
}
.slider-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}
.slider-hint {
  font-size: 10px; color: var(--text-muted); margin-top: 4px;
}
.risk-progress-wrap {
  height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px;
  overflow: hidden; margin-top: 4px;
}
.risk-progress-fill { height: 100%; border-radius: 2px; transition: width 0.6s ease; }

// ── Risk summary ──────────────────────────────────────────────────────────────
.risk-summary {
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 12px 16px;
}
.risk-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 0; font-size: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  &:last-child { border-bottom: none; }
}

// ── Status dot ────────────────────────────────────────────────────────────────
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  &.dot-green { background: var(--accent-green); animation: pulse-green 2s ease-in-out infinite; }
  &.dot-red   { background: var(--accent-red); }
}
</style>
