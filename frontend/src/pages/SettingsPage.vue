<template>
  <q-page class="settings-page q-pa-lg">
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <h5 class="q-ma-none text-neon-cyan" style="letter-spacing:2px;">CONFIGURAÇÕES</h5>
        <div class="text-caption text-muted">Gerencie o robô — modo conservador recomendado</div>
      </div>
      <!-- Backend status -->
      <div class="row items-center gap-2">
        <div :class="['status-dot', botStore.backendOnline ? 'dot-green' : 'dot-red']" />
        <span class="text-caption" :class="botStore.backendOnline ? 'text-neon-green' : 'text-neon-red'">
          {{ botStore.backendOnline ? 'Backend Online' : 'Backend Offline' }}
        </span>
        <q-btn flat dense icon="refresh" size="sm" color="grey-6" @click="botStore.checkBackend()" />
      </div>
    </div>

    <div class="row q-gutter-lg">

      <!-- ── DERIV API ── -->
      <div class="col-12 col-md-5">
        <div class="glass-card q-pa-lg">
          <div class="section-title">DERIV API</div>

          <!-- Conta conectada via OAuth -->
          <div v-if="authStore.isLoggedIn" class="connected-account q-mb-md">
            <div class="row items-center gap-2">
              <q-icon name="check_circle" color="positive" size="20px" />
              <div>
                <div class="text-caption text-muted">Conta conectada</div>
                <div class="text-weight-bold" :class="authStore.isDemo ? 'text-neon-green' : 'text-neon-amber'">
                  {{ authStore.accountLabel }}
                </div>
              </div>
              <q-space />
              <q-badge :color="authStore.isDemo ? 'positive' : 'warning'"
                :label="authStore.isDemo ? 'DEMO' : 'REAL'" rounded />
            </div>
          </div>

          <!-- Credenciais fixas no servidor -->
          <div v-else-if="serverCredentials" class="connected-account q-mb-md">
            <div class="row items-center gap-2">
              <q-icon name="vpn_key" color="positive" size="20px" />
              <div>
                <div class="text-caption text-muted">Credenciais no servidor</div>
                <div class="text-weight-bold text-neon-green">
                  Token + conta configurados (.env)
                </div>
              </div>
              <q-space />
              <q-badge color="positive" label="AUTO" rounded />
            </div>
          </div>

          <!-- Não logado - permite inserir token manualmente -->
          <div v-else>
            <q-input v-model="config.api_token" label="API Token DERIV *" dark filled
              type="password" color="cyan" label-color="grey-6" class="q-mb-md"
              hint="Token gerado em developers.deriv.com → API Tokens">
              <template #prepend><q-icon name="vpn_key" color="grey-6" /></template>
            </q-input>
            <q-input v-model="config.app_id" label="App ID" dark filled
              color="cyan" label-color="grey-6" class="q-mb-md"
              hint="ID do seu app em developers.deriv.com">
              <template #prepend><q-icon name="apps" color="grey-6" /></template>
            </q-input>
            <q-input v-model="config.account_id" label="Account ID (Demo)" dark filled
              color="cyan" label-color="grey-6" class="q-mb-md"
              hint="Ex: DOT91884478 — ID da sua conta demo">
              <template #prepend><q-icon name="person" color="grey-6" /></template>
            </q-input>
          </div>

          <div class="q-mb-md">
            <div class="row-label">Ativo (fixo no perfil precisão)</div>
            <q-select v-model="config.asset" :options="assets"
              dark filled color="cyan" label-color="grey-6" disable />
          </div>

          <div class="q-mb-md">
            <div class="row-label">Timeframe (fixo M15)</div>
            <q-btn-toggle v-model="config.granularity"
              :options="timeframes"
              toggle-color="cyan" color="transparent" text-color="grey-5"
              unelevated dense disable />
          </div>

          <div class="q-mb-lg">
            <div class="row-label">Duração Sobe/Desce</div>
            <q-btn-toggle v-model="config.contract_duration"
              :options="durations"
              toggle-color="purple" color="transparent" text-color="grey-5"
              unelevated dense />
            <div class="text-caption text-muted q-mt-xs">
              EUR/USD — aposta se sobe ou desce (mín. 15 min na DERIV). Use M15 com contrato 15 min.
            </div>
          </div>

          <!-- Start / Stop bot -->
          <div v-if="!botStore.running">
            <q-btn
              unelevated color="positive" icon="play_arrow"
              label="Iniciar Robô" class="full-width q-py-sm text-weight-bold"
              :loading="starting"
              @click="startBot"
            />
          </div>
          <div v-else>
            <q-btn
              unelevated color="negative" icon="stop"
              label="Parar Robô" class="full-width q-py-sm text-weight-bold animate-pulse-green"
              :loading="stopping"
              @click="stopBot"
            />
          </div>
          <div v-if="errorMsg" class="text-caption text-neon-red q-mt-sm text-center">
            {{ errorMsg }}
          </div>
        </div>
      </div>

      <!-- ── Risk Management ── -->
      <div class="col-12 col-md-6">
        <div class="glass-card q-pa-lg q-mb-lg">
          <div class="section-title">PERFIL OFICIAL — CONSERVADOR</div>

          <div class="profile-badge q-mb-md">
            <q-icon name="verified" color="positive" size="20px" />
            <div>
              <div class="text-weight-bold text-neon-green">Modo Precisão ativo</div>
              <div class="text-caption text-muted">
                EUR/USD · M15 · 15 min · confiança ≥78% · ADX ≥22 · confluência 5+
              </div>
            </div>
          </div>

          <div class="strategy-note q-mb-lg">
            <q-icon name="info" size="16px" color="cyan" class="q-mr-xs" />
            <span class="text-caption text-muted">
              O bot só aposta quando vários indicadores concordam. Priorizamos qualidade e
              proteção de capital — menos operações, análises mais rigorosas.
            </span>
          </div>

          <div class="section-title">GERENCIAMENTO DE RISCO (valores em R$)</div>

          <div class="currency-note q-mb-md">
            <q-icon name="currency_exchange" size="14px" color="amber" class="q-mr-xs" />
            <span class="text-caption text-muted">
              Limites e metas em reais. A DERIV executa em USD — conversão automática (cotação ~R$ {{ usdRate.toFixed(2) }}/US$).
            </span>
          </div>

          <div class="q-mb-md">
            <div class="row items-center justify-between q-mb-xs">
              <span class="row-label">Stake por Operação</span>
              <span class="text-neon-cyan font-mono">R$ {{ config.stake_amount?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.stake_amount" :min="3" :max="300" :step="1"
              color="cyan" dark />
          </div>

          <div class="q-mb-md">
            <div class="row items-center justify-between q-mb-xs">
              <span class="row-label">Stake Máximo</span>
              <span class="text-neon-cyan font-mono">R$ {{ config.max_stake?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.max_stake" :min="10" :max="600" :step="5"
              color="cyan" dark />
          </div>

          <div class="q-mb-md">
            <div class="row items-center justify-between q-mb-xs">
              <span class="row-label">Limite de Perda Diária</span>
              <span class="text-neon-red font-mono">-R$ {{ config.daily_loss_limit?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.daily_loss_limit" :min="20" :max="2000" :step="10"
              color="negative" dark />
          </div>

          <div class="q-mb-md">
            <div class="row items-center justify-between q-mb-xs">
              <span class="row-label">Meta de Lucro Diária</span>
              <span class="text-neon-green font-mono">+R$ {{ config.daily_profit_target?.toFixed(2) }}</span>
            </div>
            <q-slider v-model="config.daily_profit_target" :min="30" :max="2000" :step="10"
              color="positive" dark />
          </div>

          <div class="q-mb-lg">
            <div class="row items-center justify-between q-mb-xs">
              <span class="row-label">Confiança Mínima</span>
              <span class="text-neon-cyan font-mono">{{ config.min_confidence?.toFixed(0) }}%</span>
            </div>
            <q-slider v-model="config.min_confidence" :min="60" :max="95" :step="1"
              color="cyan" dark />
            <div class="text-caption text-muted q-mt-xs">
              Padrão conservador: 78% — só opera sinais fortes
            </div>
          </div>

          <!-- Risk summary card -->
          <div class="risk-summary">
            <div class="risk-row">
              <span class="text-muted">Risco por trade</span>
              <span class="text-neon-cyan font-mono">
                {{ ((config.stake_amount ?? 1) / (config.daily_loss_limit ?? 20) * 100).toFixed(1) }}% do limite
              </span>
            </div>
            <div class="risk-row">
              <span class="text-muted">Ratio Lucro/Risco</span>
              <span :class="ratio >= 2 ? 'text-neon-green' : 'text-neon-red'" class="font-mono">
                {{ ratio }}:1
              </span>
            </div>
            <div class="risk-row">
              <span class="text-muted">Max operações até stop</span>
              <span class="text-neon-cyan font-mono">{{ maxTrades }}</span>
            </div>
          </div>
        </div>

        <!-- Indicators -->
        <div class="glass-card q-pa-lg">
          <div class="section-title">INDICADORES ATIVOS</div>
          <div class="row q-gutter-sm">
            <q-chip v-for="ind in indicators" :key="ind.name"
              :selected="ind.active" :color="ind.active ? ind.color : 'transparent'"
              :text-color="ind.active ? 'white' : 'grey-6'" :outline="!ind.active"
              clickable @click="ind.active = !ind.active">{{ ind.name }}
            </q-chip>
          </div>
          <div class="text-caption text-muted q-mt-sm">
            Motor usa confluência de RSI, MACD, BB, EMA, Stochastic e ADX (filtro de tendência)
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

const starting = ref(false)
const stopping  = ref(false)
const errorMsg  = ref('')
const serverCredentials = ref(false)

const STORAGE_KEY = 'anagraph_config'

function loadConfig(): BotConfig {
  const def = defaultConfig()
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      // Não sobrescreve defaults com valores vazios do localStorage
      Object.keys(parsed).forEach(k => {
        if (parsed[k] === '' || parsed[k] === null || parsed[k] === undefined) {
          delete parsed[k]
        }
      })
      // migra config antiga (multiplicador → rise/fall)
      if (parsed.multiplier && !parsed.contract_duration) {
        parsed.contract_duration = 15
      }
      if (parsed.contract_duration && parsed.contract_duration < 15) {
        parsed.contract_duration = 15
      }
      delete parsed.multiplier
      delete parsed.stop_loss
      delete parsed.take_profit
      return enforceConservative(migrateConfigToBrl({ ...def, ...parsed }))
    }
  } catch { /* ignore corrupt localStorage */ }
  return def
}

function defaultConfig(): BotConfig {
  return {
    api_token:  '',
    app_id:     '33qwHdRH3vY9cCAeAzIa7',
    account_id: '',
    ...CONSERVATIVE_PROFILE,
  }
}

const config = ref<BotConfig>(loadConfig())
const usdRate = computed(() => getUsdBrlRate())

const assets = ['EUR/USD']
const timeframes = [
  { label:'M15', value: 900, disable: false },
]
const durations = [
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '60 min', value: 60 },
]

const indicators = ref([
  { name:'RSI',    active:true,  color:'amber'    },
  { name:'MACD',   active:true,  color:'cyan'     },
  { name:'BB',     active:true,  color:'purple'   },
  { name:'EMA',    active:true,  color:'positive' },
  { name:'ADX',    active:true,  color:'orange'   },
  { name:'Stoch',  active:true,  color:'pink'     },
])

const ratio = computed(() => {
  const r = (config.value.daily_profit_target ?? 50) / (config.value.daily_loss_limit ?? 20)
  return r.toFixed(1)
})
const maxTrades = computed(() => {
  return Math.floor((config.value.daily_loss_limit ?? 20) / (config.value.stake_amount ?? 1))
})

async function startBot() {
  const payload: BotConfig = enforceConservative({
    ...config.value,
    api_token: '',
    account_id: '',
  })

  // OAuth tem prioridade sobre .env do servidor
  if (authStore.account?.token) {
    payload.api_token = authStore.account.token
    payload.account_id = authStore.account.account
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

// Salva config automaticamente (exceto token por segurança)
watch(config, (val) => {
  const toSave = enforceConservative({ ...val, api_token: '' })
  localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
}, { deep: true })

onMounted(async () => {
  await botStore.fetchCurrencyConfig()
  config.value = enforceConservative(migrateConfigToBrl(config.value))
  botStore.checkBackend()
  try {
    const res = await botApi.credentials()
    serverCredentials.value = res.data.token_configured && res.data.account_configured
  } catch { /* backend offline */ }
})
</script>

<style lang="scss" scoped>
.settings-page { background: var(--bg-deep); min-height: 100vh; }
.connected-account {
  background: rgba(0,255,136,0.06);
  border: 1px solid rgba(0,255,136,0.2);
  border-radius: 10px;
  padding: 12px 16px;
}
.not-connected {
  display: flex; align-items: center;
  background: rgba(255,184,0,0.06);
  border: 1px solid rgba(255,184,0,0.2);
  border-radius: 10px;
  padding: 10px 14px;
}
.section-title {
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--text-muted); text-transform: uppercase;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-subtle);
}
.row-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.font-mono  { font-family: 'Roboto Mono', monospace; }
.text-muted { color: var(--text-muted); }
.gap-2 { gap: 8px; }
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  &.dot-green { background: var(--accent-green); box-shadow: var(--glow-green); animation: pulse-green 2s ease-in-out infinite; }
  &.dot-red   { background: var(--accent-red); }
}
.risk-summary {
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 12px 16px;
}
.risk-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  &:last-child { border-bottom: none; }
  font-size: 12px;
}
.strategy-note {
  display: flex; align-items: flex-start;
  padding: 10px 12px;
  background: rgba(0,212,255,0.06);
  border: 1px solid rgba(0,212,255,0.15);
  border-radius: 10px;
}
.profile-badge {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px;
  background: rgba(0,255,136,0.06);
  border: 1px solid rgba(0,255,136,0.25);
  border-radius: 10px;
}
.currency-note {
  display: flex; align-items: flex-start;
  padding: 8px 10px;
  background: rgba(255,184,0,0.06);
  border: 1px solid rgba(255,184,0,0.15);
  border-radius: 8px;
}
</style>
